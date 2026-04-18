"""Email provider webhook routes.

Handles incoming webhooks from Brevo (and other email providers) for
bounce, complaint, delivery, and unsubscribe events.
"""

import logging

from fastapi import APIRouter, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from backend.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["gdpr-webhooks"])


@router.post("")
async def email_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Process email provider webhook events.

    Always returns 200 to prevent the provider from retrying.
    No auth required — uses signature verification instead.
    """
    try:
        payload = await request.body()
        signature = request.headers.get("X-Sib-Signature", "")

        # Verify signature and parse event
        from modules.gdpr.adapters import get_email_provider

        provider = get_email_provider()
        event = await provider.verify_webhook(payload, signature)

        # Process the event
        from modules.gdpr.services.webhook_processing_service import (
            process_webhook,
        )

        result = await process_webhook(db, event)
        logger.debug("Webhook processed: %s", result)

    except ValueError as e:
        logger.warning("Webhook signature verification failed: %s", e)
        # Still return 200 to avoid retries for bad signatures
    except Exception:
        logger.exception("Webhook processing error")

    # Always return 200 — email providers retry on non-2xx
    return Response(status_code=200, content='{"status":"ok"}')
