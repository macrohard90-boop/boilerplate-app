"""Central email send service — consent check, render, send, audit log.

Every email in the application goes through this service. It:
1. Checks suppression (hard block — no emails of any type)
2. Checks consent for the email type (marketing vs transactional)
3. Renders the template via Jinja2
4. Sends via the configured email provider adapter
5. Logs the result to gdpr.email_events for GDPR audit trail
6. On failure, pushes to Redis retry queue
"""

import asyncio
import json
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def _get_consent_snapshot(
    db: AsyncSession, user_id: str
) -> dict:
    """Build a snapshot of consent state at send time for audit."""
    try:
        result = await db.execute(
            text(
                "SELECT DISTINCT ON (consent_type) consent_type, granted "
                "FROM gdpr.consent_records "
                "WHERE user_id = :uid "
                "ORDER BY consent_type, created_at DESC"
            ),
            {"uid": user_id},
        )
        rows = result.mappings().all()
        return {r["consent_type"]: r["granted"] for r in rows}
    except Exception:
        return {}


async def _check_can_send(
    db: AsyncSession, user_id: str, email_type: str
) -> tuple[bool, str | None]:
    """Check suppression and consent. Returns (can_send, skip_reason)."""
    # Check suppression (overrides all consent)
    row = (
        await db.execute(
            text(
                "SELECT suppressed_at, marketing_email, transactional_email "
                "FROM gdpr.email_preferences WHERE user_id = :uid"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if row and row["suppressed_at"] is not None:
        return False, "suppressed"

    # Check email type preference
    if row:
        if email_type == "marketing_email" and not row["marketing_email"]:
            return False, "no_consent"
        if email_type == "transactional_email" and not row["transactional_email"]:
            return False, "no_consent"
    else:
        # No preferences row — create defaults (transactional=true, marketing=false)
        await db.execute(
            text(
                "INSERT INTO gdpr.email_preferences "
                "(user_id, marketing_email, transactional_email) "
                "VALUES (:uid, false, true) "
                "ON CONFLICT (user_id) DO NOTHING"
            ),
            {"uid": user_id},
        )
        await db.commit()
        if email_type == "marketing_email":
            return False, "no_consent"

    return True, None


async def _log_email_event(
    db: AsyncSession,
    user_id: str,
    email_type: str,
    template_id: str,
    provider: str,
    provider_message_id: str | None,
    consent_snapshot: dict,
    status: str,
    skip_reason: str | None = None,
) -> str:
    """Insert a row into gdpr.email_events for GDPR audit trail."""
    event_id = str(uuid.uuid4())
    sent_at_value = "NOW()" if status == "sent" else "NULL"
    await db.execute(
        text(
            "INSERT INTO gdpr.email_events "
            "(id, user_id, email_type, template_id, provider, "
            "provider_message_id, consent_snapshot, status, skip_reason, "
            f"sent_at) "
            "VALUES (:id, :uid, :etype, :tid, :prov, :pmid, :snap, "
            f":status, :skip, {sent_at_value})"
        ),
        {
            "id": event_id,
            "uid": user_id,
            "etype": email_type,
            "tid": template_id,
            "prov": provider,
            "pmid": provider_message_id,
            "snap": json.dumps(consent_snapshot),
            "status": status,
            "skip": skip_reason,
        },
    )
    await db.commit()
    return event_id


async def _push_to_retry_queue(
    event_id: str,
    user_id: str,
    template_id: str,
    template_data: dict,
    email_type: str,
    to_email: str,
) -> None:
    """Push a failed send to the Redis retry queue."""
    try:
        from backend.core.redis import get_redis

        redis = await get_redis()
        payload = json.dumps({
            "event_id": event_id,
            "user_id": user_id,
            "template_id": template_id,
            "template_data": template_data,
            "email_type": email_type,
            "to_email": to_email,
        })
        await redis.rpush("email_retry_queue", payload)
        logger.info("Pushed email event %s to retry queue", event_id)
    except Exception:
        logger.exception("Failed to push event %s to retry queue", event_id)


async def send_email(
    db: AsyncSession,
    user_id: str,
    template_id: str,
    template_data: dict | None = None,
    email_type: str = "transactional_email",
    *,
    to_email: str | None = None,
    force: bool = False,
    subject_override: str | None = None,
) -> dict:
    """Send an email through the full consent-check + render + send pipeline.

    Args:
        db: Database session.
        user_id: Target user's ID.
        template_id: Template name (e.g. "welcome", "password_reset").
        template_data: Variables for the template.
        email_type: "transactional_email" or "marketing_email".
        to_email: Override recipient (if None, looked up from core.users).
        force: Skip consent checks (for critical system emails).
        subject_override: Override subject extracted from template.

    Returns:
        dict with status, event_id, provider_message_id.
    """
    template_data = template_data or {}

    # 1. Look up user email if not provided
    if not to_email:
        row = (
            await db.execute(
                text("SELECT email, first_name FROM core.users WHERE id = :uid"),
                {"uid": user_id},
            )
        ).mappings().first()
        if not row:
            logger.warning("send_email: user %s not found", user_id)
            return {"status": "error", "error": "User not found"}
        to_email = row["email"]
        if "first_name" not in template_data and row.get("first_name"):
            template_data["first_name"] = row["first_name"]

    # Default first_name fallback
    if "first_name" not in template_data:
        template_data["first_name"] = "there"

    # 2. Check consent (unless forced)
    consent_snapshot = await _get_consent_snapshot(db, user_id)

    if not force:
        can_send, skip_reason = await _check_can_send(db, user_id, email_type)
        if not can_send:
            event_id = await _log_email_event(
                db,
                user_id=user_id,
                email_type=email_type,
                template_id=template_id,
                provider="",
                provider_message_id=None,
                consent_snapshot=consent_snapshot,
                status="skipped",
                skip_reason=skip_reason,
            )
            logger.info(
                "Email skipped for user %s (template=%s, reason=%s)",
                user_id,
                template_id,
                skip_reason,
            )
            return {
                "status": "skipped",
                "skip_reason": skip_reason,
                "event_id": event_id,
            }

    # 3. Add unsubscribe URL for marketing emails
    if email_type == "marketing_email":
        from modules.gdpr.services.email_pref_service import (
            generate_unsubscribe_token,
        )

        unsub_token = generate_unsubscribe_token(user_id)
        template_data["unsubscribe_url"] = (
            f"{settings.backend_url}/api/gdpr/email-preferences/unsubscribe"
            f"?token={unsub_token}"
        )

    # 4. Render template
    from modules.gdpr.services.template_service import render_template

    try:
        html_content = render_template(template_id, template_data)
    except Exception:
        logger.exception("Template render failed: %s", template_id)
        return {"status": "error", "error": f"Template render failed: {template_id}"}

    # 5. Build subject
    subject = subject_override or _subject_for_template(template_id, template_data)

    # 6. Send via adapter
    from modules.gdpr.adapters import get_email_provider

    provider = get_email_provider(email_type)

    # Build headers for marketing emails (RFC 8058 one-click unsubscribe)
    extra_headers: dict[str, str] | None = None
    if email_type == "marketing_email" and template_data.get("unsubscribe_url"):
        extra_headers = {
            "List-Unsubscribe": f"<{template_data['unsubscribe_url']}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    result = await provider.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        from_email=settings.from_email,
        from_name=settings.from_name,
        headers=extra_headers,
        tags=[template_id, email_type],
    )

    # 7. Log to email_events
    event_id = await _log_email_event(
        db,
        user_id=user_id,
        email_type=email_type,
        template_id=template_id,
        provider=result.provider,
        provider_message_id=result.provider_message_id,
        consent_snapshot=consent_snapshot,
        status="sent" if result.success else "queued",
    )

    # 8. On failure, push to retry queue
    if not result.success:
        await _push_to_retry_queue(
            event_id, user_id, template_id,
            template_data, email_type, to_email,
        )

    return {
        "status": "sent" if result.success else "queued",
        "event_id": event_id,
        "provider_message_id": result.provider_message_id,
        "error": result.error,
    }


async def send_email_fire_and_forget(
    user_id: str,
    template_id: str,
    template_data: dict | None = None,
    email_type: str = "transactional_email",
    *,
    to_email: str | None = None,
    force: bool = False,
) -> None:
    """Fire-and-forget wrapper — sends email without blocking the caller.

    Creates its own DB session so it doesn't share the caller's transaction.
    Uses asyncio.create_task so the HTTP response isn't delayed by email sending.
    Failures are silently pushed to the retry queue.
    """

    async def _send() -> None:
        from backend.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            try:
                await send_email(
                    db,
                    user_id,
                    template_id,
                    template_data,
                    email_type,
                    to_email=to_email,
                    force=force,
                )
            except Exception:
                logger.exception(
                    "Background email send failed (template=%s, user=%s)",
                    template_id,
                    user_id,
                )

    try:
        asyncio.create_task(_send())
    except Exception:
        logger.exception(
            "Failed to create email task (template=%s, user=%s)",
            template_id,
            user_id,
        )


def _subject_for_template(template_id: str, data: dict) -> str:
    """Generate a default subject line based on template ID."""
    site = settings.site_name or settings.app_name
    subjects = {
        "welcome": f"Welcome to {site}",
        "password_reset": f"Reset your {site} password",
        "order_confirmation": f"Order confirmed — {site}",
        "payment_receipt": f"Payment receipt — {site}",
        "subscription_confirmation": f"Subscription confirmed — {site}",
        "subscription_cancelled": f"Subscription cancelled — {site}",
        "data_export_ready": "Your data export is ready",
        "account_deletion": "Account deletion confirmation",
    }
    return subjects.get(template_id, f"Message from {site}")
