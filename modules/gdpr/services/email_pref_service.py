"""Email preference management — opt-in tracking, suppression, one-click unsubscribe."""

import hashlib
import hmac
import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Token expiry for one-click unsubscribe (30 days)
_UNSUBSCRIBE_TOKEN_TTL = 30 * 24 * 3600


def generate_unsubscribe_token(user_id: str) -> str:
    """Generate HMAC-signed token for one-click unsubscribe (RFC 8058)."""
    expiry = int(time.time()) + _UNSUBSCRIBE_TOKEN_TTL
    payload = f"{user_id}:{expiry}"
    sig = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{sig}"


def _validate_unsubscribe_token(token: str) -> str | None:
    """Validate token and return user_id if valid, None otherwise."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id, expiry_str, sig = parts
        expiry = int(expiry_str)

        # Check expiry
        if time.time() > expiry:
            return None

        # Verify HMAC
        payload = f"{user_id}:{expiry_str}"
        expected = hmac.new(
            settings.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None

        return user_id
    except (ValueError, TypeError):
        return None


async def get_preferences(
    db: AsyncSession, user_id: str
) -> dict[str, Any] | None:
    """Get current email preferences for a user."""
    row = (
        await db.execute(
            text(
                "SELECT marketing_email, transactional_email, "
                "suppressed_at, suppression_reason "
                "FROM gdpr.email_preferences WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if not row:
        return None

    return {
        "marketing_email": row["marketing_email"],
        "transactional_email": row["transactional_email"],
        "suppressed_at": str(row["suppressed_at"]) if row["suppressed_at"] else None,
        "suppression_reason": row["suppression_reason"],
    }


async def update_preferences(
    db: AsyncSession,
    user_id: str,
    marketing_email: bool = False,
    transactional_email: bool = True,
) -> dict[str, Any]:
    """Create or update email preferences."""
    existing = (
        await db.execute(
            text(
                "SELECT id FROM gdpr.email_preferences WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if existing:
        await db.execute(
            text(
                "UPDATE gdpr.email_preferences "
                "SET marketing_email = :mkt, transactional_email = :txn "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id, "mkt": marketing_email, "txn": transactional_email},
        )
    else:
        await db.execute(
            text(
                "INSERT INTO gdpr.email_preferences "
                "(user_id, marketing_email, transactional_email) "
                "VALUES (:uid, :mkt, :txn)"
            ),
            {"uid": user_id, "mkt": marketing_email, "txn": transactional_email},
        )

    await db.commit()

    # Sync suppression to email provider if marketing was disabled
    if not marketing_email:
        try:
            user_row = (
                await db.execute(
                    text("SELECT email FROM core.users WHERE id = :uid"),
                    {"uid": user_id},
                )
            ).mappings().first()
            if user_row:
                from modules.gdpr.adapters import get_email_provider

                provider = get_email_provider("marketing_email")
                await provider.sync_suppression([user_row["email"]])
        except Exception:
            logger.exception(
                "Failed to sync email preferences to provider for user %s",
                user_id,
            )

    return {
        "marketing_email": marketing_email,
        "transactional_email": transactional_email,
        "suppressed_at": None,
        "suppression_reason": None,
    }


async def unsubscribe_by_token(
    db: AsyncSession, token: str
) -> dict[str, Any]:
    """Process one-click unsubscribe via HMAC token."""
    user_id = _validate_unsubscribe_token(token)
    if not user_id:
        raise ValueError("Invalid or expired unsubscribe token")

    # Upsert: set marketing_email=false, suppress
    existing = (
        await db.execute(
            text("SELECT id FROM gdpr.email_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).mappings().first()

    if existing:
        await db.execute(
            text(
                "UPDATE gdpr.email_preferences "
                "SET marketing_email = false, suppressed_at = NOW(), "
                "suppression_reason = 'manual' "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    else:
        await db.execute(
            text(
                "INSERT INTO gdpr.email_preferences "
                "(user_id, marketing_email, transactional_email, suppressed_at, suppression_reason) "
                "VALUES (:uid, false, true, NOW(), 'manual')"
            ),
            {"uid": user_id},
        )

    await db.commit()
    logger.info("User %s unsubscribed via one-click token", user_id)

    return {"message": "Successfully unsubscribed from marketing emails"}


async def is_suppressed(db: AsyncSession, user_id: str) -> bool:
    """Check if a user's email is suppressed."""
    row = (
        await db.execute(
            text(
                "SELECT suppressed_at FROM gdpr.email_preferences "
                "WHERE user_id = :uid AND suppressed_at IS NOT NULL"
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    return row is not None
