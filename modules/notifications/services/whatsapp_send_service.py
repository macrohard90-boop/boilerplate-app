"""WhatsApp send service — send, log to notifications.message_log, fire-and-forget wrapper.

Every WhatsApp message in the application goes through this service. It:
1. Sends via the configured WhatsApp provider adapter
2. Logs the result to notifications.message_log for audit trail
"""

import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def send_whatsapp_template(
    db: AsyncSession,
    user_id: str | None,
    to_number: str,
    template_name: str,
    *,
    language: str = "en",
    parameters: dict[str, Any] | None = None,
    media_url: str | None = None,
    campaign_id: str | None = None,
) -> dict:
    """Send a WhatsApp template message and log the result.

    Args:
        db: Database session.
        user_id: Sending to this user (for audit trail). None for anonymous.
        to_number: Recipient phone number (E.164 format).
        template_name: Brevo template ID or name.
        language: Template language code.
        parameters: Template variable values.
        media_url: Optional media attachment URL.
        campaign_id: Link to marketing campaign.

    Returns:
        Dict with status, provider_message_id, error.
    """
    if not settings.enable_whatsapp:
        return {"status": "skipped", "error": "WhatsApp is disabled"}

    from modules.notifications.adapters import get_whatsapp_provider

    provider = get_whatsapp_provider()
    result = await provider.send_template(
        to_number,
        template_name,
        language=language,
        parameters=parameters,
        media_url=media_url,
    )

    # Log to notifications.message_log
    try:
        await db.execute(
            text(
                "INSERT INTO notifications.message_log "
                "(user_id, channel, provider, provider_message_id, to_number, "
                " template_id, body_preview, status, error_message, sent_at) "
                "VALUES (:uid, 'whatsapp', :provider, :pmid, :to_num, "
                " :tmpl, :preview, :status, :error, NOW())"
            ),
            {
                "uid": user_id,
                "provider": result.provider,
                "pmid": result.provider_message_id,
                "to_num": to_number,
                "tmpl": template_name,
                "preview": f"template:{template_name} params:{parameters}",
                "status": "sent" if result.success else "failed",
                "error": result.error,
            },
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to log WhatsApp send to message_log")

    return {
        "status": "sent" if result.success else "failed",
        "provider_message_id": result.provider_message_id,
        "error": result.error,
    }


async def send_whatsapp_text(
    db: AsyncSession,
    user_id: str | None,
    to_number: str,
    text_content: str,
    *,
    campaign_id: str | None = None,
) -> dict:
    """Send a free-form WhatsApp text message and log the result.

    Only works within 24h of user's last message (conversation window).
    """
    if not settings.enable_whatsapp:
        return {"status": "skipped", "error": "WhatsApp is disabled"}

    from modules.notifications.adapters import get_whatsapp_provider

    provider = get_whatsapp_provider()
    result = await provider.send_text(to_number, text_content)

    try:
        await db.execute(
            text(
                "INSERT INTO notifications.message_log "
                "(user_id, channel, provider, provider_message_id, to_number, "
                " body_preview, status, error_message, sent_at) "
                "VALUES (:uid, 'whatsapp', :provider, :pmid, :to_num, "
                " :preview, :status, :error, NOW())"
            ),
            {
                "uid": user_id,
                "provider": result.provider,
                "pmid": result.provider_message_id,
                "to_num": to_number,
                "preview": text_content[:500],
                "status": "sent" if result.success else "failed",
                "error": result.error,
            },
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to log WhatsApp text send to message_log")

    return {
        "status": "sent" if result.success else "failed",
        "provider_message_id": result.provider_message_id,
        "error": result.error,
    }


async def send_whatsapp_fire_and_forget(
    user_id: str | None,
    to_number: str,
    template_name: str,
    *,
    language: str = "en",
    parameters: dict[str, Any] | None = None,
    campaign_id: str | None = None,
) -> None:
    """Fire-and-forget wrapper — sends WhatsApp without blocking the caller."""

    async def _send() -> None:
        from backend.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            try:
                await send_whatsapp_template(
                    db,
                    user_id,
                    to_number,
                    template_name,
                    language=language,
                    parameters=parameters,
                    campaign_id=campaign_id,
                )
            except Exception:
                logger.exception(
                    "Background WhatsApp send failed (to=%s, user=%s)",
                    to_number,
                    user_id,
                )

    try:
        asyncio.create_task(_send())
    except Exception:
        logger.exception(
            "Failed to create WhatsApp task (to=%s, user=%s)",
            to_number,
            user_id,
        )


async def send_whatsapp_text_fire_and_forget(
    user_id: str | None,
    to_number: str,
    text_content: str,
    *,
    campaign_id: str | None = None,
) -> None:
    """Fire-and-forget wrapper for free-text WhatsApp messages."""

    async def _send() -> None:
        from backend.core.database import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            try:
                await send_whatsapp_text(
                    db,
                    user_id,
                    to_number,
                    text_content,
                    campaign_id=campaign_id,
                )
            except Exception:
                logger.exception(
                    "Background WhatsApp text send failed (to=%s, user=%s)",
                    to_number,
                    user_id,
                )

    try:
        asyncio.create_task(_send())
    except Exception:
        logger.exception(
            "Failed to create WhatsApp text task (to=%s, user=%s)",
            to_number,
            user_id,
        )
