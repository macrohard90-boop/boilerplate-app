"""SMS and WhatsApp webhook routes.

Handles incoming webhooks from Brevo (and other providers) for
SMS delivery/bounce and WhatsApp delivery/read events.
Always returns 200 to prevent provider retries.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["notifications-webhooks"])


@router.post("/sms")
async def sms_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Process SMS provider webhook events.

    Brevo SMS webhook events:
    - delivered: SMS delivered to handset
    - softBounce / hardBounce / blocked: delivery failure

    Always returns 200 to prevent retry storms.
    """
    try:
        payload = await request.body()
        signature = request.headers.get("X-Sib-Signature", "")

        from modules.notifications.adapters import get_sms_provider

        provider = get_sms_provider()
        event = await provider.verify_webhook(payload, signature)

        # Update campaign_recipients if this is a campaign message
        from modules.marketing.services.webhook_event_service import (
            update_sms_recipient_status,
        )

        if event.provider_message_id:
            await update_sms_recipient_status(
                db, event.provider_message_id, event.event_type
            )

        # Update notifications.message_log
        if event.provider_message_id:
            from sqlalchemy import text

            status_map = {"delivered": "delivered", "failed": "failed"}
            new_status = status_map.get(event.event_type)
            if new_status:
                await db.execute(
                    text(
                        "UPDATE notifications.message_log "
                        "SET status = :status "
                        "WHERE provider_message_id = :pmid AND channel = 'sms'"
                    ),
                    {"pmid": event.provider_message_id, "status": new_status},
                )

        await db.commit()
        logger.debug("SMS webhook processed: %s", event.event_type)

    except ValueError as e:
        logger.warning("SMS webhook signature verification failed: %s", e)
    except Exception:
        logger.exception("SMS webhook processing error")

    return Response(status_code=200, content='{"status":"ok"}')


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Process WhatsApp provider webhook events.

    Brevo WhatsApp webhook events:
    - delivered: message delivered to phone
    - read: message read (blue ticks) — reliable open signal
    - failed: delivery failure

    Always returns 200 to prevent retry storms.
    """
    try:
        payload = await request.body()
        signature = request.headers.get("X-Sib-Signature", "")

        from modules.notifications.adapters import get_whatsapp_provider

        provider = get_whatsapp_provider()
        event = await provider.verify_webhook(payload, signature)

        # Update campaign_recipients if this is a campaign message
        from modules.marketing.services.webhook_event_service import (
            update_whatsapp_recipient_status,
        )

        if event.provider_message_id:
            await update_whatsapp_recipient_status(
                db, event.provider_message_id, event.event_type
            )

        # Update notifications.message_log
        if event.provider_message_id:
            from sqlalchemy import text

            status_map = {"delivered": "delivered", "read": "delivered"}
            new_status = status_map.get(event.event_type)
            if new_status:
                await db.execute(
                    text(
                        "UPDATE notifications.message_log "
                        "SET status = :status "
                        "WHERE provider_message_id = :pmid AND channel = 'whatsapp'"
                    ),
                    {"pmid": event.provider_message_id, "status": new_status},
                )

        await db.commit()
        logger.debug("WhatsApp webhook processed: %s", event.event_type)

    except ValueError as e:
        logger.warning("WhatsApp webhook signature verification failed: %s", e)
    except Exception:
        logger.exception("WhatsApp webhook processing error")

    return Response(status_code=200, content='{"status":"ok"}')
