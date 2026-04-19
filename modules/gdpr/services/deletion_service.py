"""Data deletion (Right to Erasure) with grace period and anonymization."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def request_deletion(
    db: AsyncSession, redis: Redis, user_id: str
) -> dict[str, Any]:
    """Request account deletion. Immediately revokes all sessions."""
    # Check for existing active deletion request
    existing = (
        (
            await db.execute(
                text(
                    "SELECT id, status FROM gdpr.deletion_requests "
                    "WHERE user_id = :uid AND status IN ('pending', 'grace_period') "
                    "LIMIT 1"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if existing:
        raise ValueError("Active deletion request already exists")

    grace_days = getattr(settings, "gdpr_grace_period_days", 30)
    grace_end = datetime.now(timezone.utc) + timedelta(days=grace_days)

    # Create deletion request
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO gdpr.deletion_requests "
                    "(user_id, status, grace_period_ends) "
                    "VALUES (:uid, 'grace_period', :grace_end) "
                    "RETURNING id, status, requested_at, grace_period_ends"
                ),
                {"uid": user_id, "grace_end": grace_end},
            )
        )
        .mappings()
        .first()
    )
    await db.commit()

    # Immediately revoke all sessions
    from modules.auth.services.session_service import invalidate_all_sessions

    await invalidate_all_sessions(redis, user_id)

    return {
        "id": str(row["id"]),
        "status": row["status"],
        "requested_at": str(row["requested_at"]),
        "grace_period_ends": str(row["grace_period_ends"]),
        "completed_at": None,
    }


async def get_deletion_status(
    db: AsyncSession, user_id: str, deletion_id: str
) -> dict[str, Any]:
    """Get deletion request status. Checks grace period expiry on-demand."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, status, requested_at, grace_period_ends, completed_at "
                    "FROM gdpr.deletion_requests "
                    "WHERE id = :did AND user_id = :uid"
                ),
                {"did": deletion_id, "uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Deletion request not found")

    status = row["status"]

    # On-demand grace period check
    if status == "grace_period" and row["grace_period_ends"]:
        if datetime.now(timezone.utc) > row["grace_period_ends"]:
            # Grace period expired — process deletion
            await _process_deletion(db, user_id, str(row["id"]))
            status = "completed"

    return {
        "id": str(row["id"]),
        "status": status,
        "requested_at": str(row["requested_at"]),
        "grace_period_ends": (
            str(row["grace_period_ends"]) if row["grace_period_ends"] else None
        ),
        "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
    }


async def cancel_deletion(
    db: AsyncSession, user_id: str, deletion_id: str
) -> dict[str, Any]:
    """Cancel a deletion request during grace period."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, status FROM gdpr.deletion_requests "
                    "WHERE id = :did AND user_id = :uid"
                ),
                {"did": deletion_id, "uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Deletion request not found")

    if row["status"] != "grace_period":
        raise ValueError(f"Cannot cancel deletion in status: {row['status']}")

    await db.execute(
        text(
            "UPDATE gdpr.deletion_requests "
            "SET status = 'cancelled', completed_at = NOW() "
            "WHERE id = :did"
        ),
        {"did": deletion_id},
    )
    await db.commit()

    return {
        "id": str(row["id"]),
        "status": "cancelled",
    }


async def _process_deletion(db: AsyncSession, user_id: str, deletion_id: str) -> None:
    """Anonymize personal data. Keep orders for legal/tax retention."""
    # Update status to processing
    await db.execute(
        text("UPDATE gdpr.deletion_requests SET status = 'processing' WHERE id = :did"),
        {"did": deletion_id},
    )
    await db.commit()

    try:
        anon_email = f"deleted_{uuid.uuid4().hex[:12]}@deleted.local"

        # Anonymize user profile
        await db.execute(
            text(
                "UPDATE core.users "
                "SET email = :email, first_name = '[DELETED]', last_name = '[DELETED]', "
                "password_hash = '', is_active = false "
                "WHERE id = :uid"
            ),
            {"uid": user_id, "email": anon_email},
        )

        # Delete analytics data
        await db.execute(
            text("DELETE FROM analytics.page_views WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await db.execute(
            text("DELETE FROM analytics.events WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await db.execute(
            text("DELETE FROM analytics.analytics_sessions WHERE user_id = :uid"),
            {"uid": user_id},
        )

        # Delete consent records (audit log retained for legal basis)
        await db.execute(
            text("DELETE FROM gdpr.consent_records WHERE user_id = :uid"),
            {"uid": user_id},
        )

        # Delete cookie preferences
        await db.execute(
            text("DELETE FROM gdpr.cookie_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        )

        # Delete email preferences
        await db.execute(
            text("DELETE FROM gdpr.email_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        )

        # Delete export requests and data
        await db.execute(
            text("DELETE FROM gdpr.data_export_requests WHERE user_id = :uid"),
            {"uid": user_id},
        )

        # Mark deletion as completed
        await db.execute(
            text(
                "UPDATE gdpr.deletion_requests "
                "SET status = 'completed', completed_at = NOW() "
                "WHERE id = :did"
            ),
            {"did": deletion_id},
        )
        await db.commit()

        logger.info("Deletion completed for user %s", user_id)

    except Exception:
        logger.exception("Deletion processing failed for user %s", user_id)
        await db.execute(
            text(
                "UPDATE gdpr.deletion_requests SET status = 'grace_period' "
                "WHERE id = :did"
            ),
            {"did": deletion_id},
        )
        await db.commit()
        raise
