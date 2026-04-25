"""SMS send service — send, log to notifications.message_log, fire-and-forget wrapper.

Every SMS in the application goes through this service. It:
1. Sends via the configured SMS provider adapter
2. Logs the result to notifications.message_log for audit trail
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def send_sms(
    db: AsyncSession,
    user_id: str | None,
    to_number: str,
    content: str,
    *,
    sender: str | None = None,
    tags: list[str] | None = None,
    campaign_id: str | None = None,
) -> dict:
    """Send an SMS and log the result.

    Args:
        db: Database session.
        user_id: Sending to this user (for audit trail). None for anonymous.
        to_number: Recipient phone number (E.164 format).
        content: SMS body text.
        sender: Override sender name (3-11 alphanumeric).
        tags: Optional provider tags.
        campaign_id: Link to marketing campaign (for pressure log).

    Returns:
        Dict with status, provider_message_id, error.
    """
    if not settings.enable_sms:
        return {"status": "skipped", "error": "SMS is disabled"}

    from modules.notifications.adapters import get_sms_provider

    provider = get_sms_provider()
    result = await provider.send_sms(to_number, content, sender=sender, tags=tags)

    # Log to notifications.message_log
    try:
        await db.execute(
            text(
                "INSERT INTO notifications.message_log "
                "(user_id, channel, provider, provider_message_id, to_number, "
                " body_preview, status, error_message, sent_at) "
                "VALUES (:uid, 'sms', :provider, :pmid, :to_num, "
                " :preview, :status, :error, NOW())"
            ),
            {
                "uid": user_id,
                "provider": result.provider,
                "pmid": result.provider_message_id,
                "to_num": to_number,
                "preview": content[:500],
                "status": "sent" if result.success else "failed",
                "error": result.error,
            },
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to log SMS send to message_log")

    return {
        "status": "sent" if result.success else "failed",
        "provider_message_id": result.provider_message_id,
        "error": result.error,
    }


async def send_sms_fire_and_forget(
    user_id: str | None,
    to_number: str,
    content: str,
    *,
    sender: str | None = None,
    tags: list[str] | None = None,
    campaign_id: str | None = None,
) -> None:
    """Fire-and-forget wrapper — sends SMS without blocking the caller.

    Creates its own DB session so it doesn't share the caller's transaction.
    """

    async def _send() -> None:
        from backend.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            try:
                await send_sms(
                    db,
                    user_id,
                    to_number,
                    content,
                    sender=sender,
                    tags=tags,
                    campaign_id=campaign_id,
                )
            except Exception:
                logger.exception(
                    "Background SMS send failed (to=%s, user=%s)",
                    to_number,
                    user_id,
                )

    try:
        asyncio.create_task(_send())
    except Exception:
        logger.exception(
            "Failed to create SMS task (to=%s, user=%s)",
            to_number,
            user_id,
        )
