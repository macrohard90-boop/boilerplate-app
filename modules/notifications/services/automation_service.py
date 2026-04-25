"""Simple notification automation — event-driven channel dispatch.

Looks up automation_rules in the database and dispatches SMS/WhatsApp
messages when events fire. This is the simple rules-based system
(separate from the full flow engine in marketing module).

Example: user.registered → send welcome SMS if rule enabled.
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def fire_notification_event(
    event_name: str,
    user_id: str,
    payload: dict | None = None,
) -> None:
    """Fire a notification event — dispatches per automation_rules.

    Non-blocking: creates a background task with its own DB session.
    Called from trigger points (auth, payments, etc.).
    """

    async def _task() -> None:
        try:
            from backend.core.database import get_session_factory

            async with get_session_factory()() as db:
                await _dispatch_rules(db, event_name, user_id, payload)
        except Exception:
            logger.debug("Notification event dispatch error (non-fatal)", exc_info=True)

    try:
        asyncio.create_task(_task())
    except Exception:
        pass


async def _dispatch_rules(
    db: AsyncSession,
    event_name: str,
    user_id: str,
    payload: dict | None,
) -> None:
    """Look up enabled rules for the event and dispatch per channel."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, channel, template_id, delay_seconds "
                    "FROM notifications.automation_rules "
                    "WHERE event_name = :evt AND enabled = true"
                ),
                {"evt": event_name},
            )
        )
        .mappings()
        .all()
    )

    if not rows:
        return

    # Get user's phone/whatsapp number
    user_row = (
        (
            await db.execute(
                text(
                    "SELECT email, phone, whatsapp_number "
                    "FROM core.users WHERE id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not user_row:
        return

    for rule in rows:
        channel = rule["channel"]
        template_id = rule["template_id"]

        if channel == "sms" and settings.enable_sms:
            phone = user_row.get("phone")
            if phone:
                from modules.notifications.services.sms_send_service import (
                    send_sms_fire_and_forget,
                )

                content = _resolve_template(template_id, payload or {})
                await send_sms_fire_and_forget(user_id, phone, content)

        elif channel == "whatsapp" and settings.enable_whatsapp:
            wa_number = user_row.get("whatsapp_number")
            if wa_number:
                from modules.notifications.services.whatsapp_send_service import (
                    send_whatsapp_text_fire_and_forget,
                )

                await send_whatsapp_text_fire_and_forget(
                    user_id,
                    wa_number,
                    _resolve_template(template_id, payload or {}),
                )

        elif channel == "email":
            from modules.gdpr.services.email_send_service import (
                send_email_fire_and_forget,
            )

            await send_email_fire_and_forget(user_id, template_id, payload or {})


def _resolve_template(template_id: str, data: dict) -> str:
    """Simple template resolution for SMS/WhatsApp messages.

    For now, uses a hardcoded mapping. In production, this would
    look up template content from the database.
    """
    templates = {
        "welcome_sms": "Welcome to {app_name}! Your account is ready.",
        "welcome_whatsapp": "Welcome to {app_name}! Start exploring.",
        "order_confirmation_sms": "Your order #{order_id} has been confirmed!",
    }

    template = templates.get(template_id, template_id)
    try:
        return template.format(app_name=settings.app_name, **data)
    except (KeyError, IndexError):
        return template
