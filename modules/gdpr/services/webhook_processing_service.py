"""Email webhook processing — handles bounce, complaint, delivery events.

Processes webhooks from email providers (Brevo, etc.) to:
- Auto-suppress users on hard bounces and spam complaints
- Update delivery status in email_events audit table
- Maintain webhook idempotency via gdpr.email_webhook_events
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.gdpr.interfaces.email_provider import WebhookEvent

logger = logging.getLogger(__name__)

# Map provider event types to normalized types
_BOUNCE_EVENTS = {"hard_bounce", "bounced", "invalid_email", "blocked"}
_COMPLAINT_EVENTS = {"complaint", "spam", "spam_report"}
_DELIVERY_EVENTS = {"delivered", "request", "sent"}
_UNSUBSCRIBE_EVENTS = {"unsubscribed", "unsubscribe"}


async def process_webhook(
    db: AsyncSession,
    event: WebhookEvent,
) -> dict:
    """Process a verified webhook event from an email provider.

    Args:
        db: Database session.
        event: Parsed and signature-verified webhook event.

    Returns:
        dict with processing status.
    """
    event_type = event.event_type.lower()
    event_id = event.event_id or ""

    # 1. Idempotency check
    if event_id:
        existing = (
            await db.execute(
                text(
                    "SELECT id FROM gdpr.email_webhook_events " "WHERE event_id = :eid"
                ),
                {"eid": event_id},
            )
        ).first()
        if existing:
            logger.debug("Duplicate webhook event: %s", event_id)
            return {"status": "duplicate", "event_id": event_id}

    # 2. Record webhook event for idempotency
    if event_id:
        await db.execute(
            text(
                "INSERT INTO gdpr.email_webhook_events "
                "(event_id, event_type, provider) "
                "VALUES (:eid, :etype, :prov)"
            ),
            {
                "eid": event_id,
                "etype": event_type,
                "prov": event.raw_data.get("provider", "unknown"),
            },
        )

    # 3. Dispatch by event type
    if event_type in _BOUNCE_EVENTS:
        await _handle_bounce(db, event)
    elif event_type in _COMPLAINT_EVENTS:
        await _handle_complaint(db, event)
    elif event_type in _DELIVERY_EVENTS:
        await _handle_delivery(db, event)
    elif event_type in _UNSUBSCRIBE_EVENTS:
        await _handle_unsubscribe(db, event)
    else:
        logger.debug("Ignoring webhook event type: %s", event_type)

    await db.commit()
    return {"status": "processed", "event_type": event_type}


async def _handle_bounce(db: AsyncSession, event: WebhookEvent) -> None:
    """Hard bounce — suppress user's email."""
    logger.info(
        "Bounce webhook: email=%s, msg_id=%s",
        event.recipient_email,
        event.provider_message_id,
    )

    # Update email_events status
    if event.provider_message_id:
        await db.execute(
            text(
                "UPDATE gdpr.email_events SET status = 'bounced' "
                "WHERE provider_message_id = :pmid"
            ),
            {"pmid": event.provider_message_id},
        )

    # Suppress user by email address
    if event.recipient_email:
        await _suppress_user_by_email(db, event.recipient_email, "bounce")


async def _handle_complaint(db: AsyncSession, event: WebhookEvent) -> None:
    """Spam complaint — suppress user's email."""
    logger.info(
        "Complaint webhook: email=%s, msg_id=%s",
        event.recipient_email,
        event.provider_message_id,
    )

    # Update email_events status
    if event.provider_message_id:
        await db.execute(
            text(
                "UPDATE gdpr.email_events SET status = 'complained' "
                "WHERE provider_message_id = :pmid"
            ),
            {"pmid": event.provider_message_id},
        )

    # Suppress user by email address
    if event.recipient_email:
        await _suppress_user_by_email(db, event.recipient_email, "complaint")


async def _handle_delivery(db: AsyncSession, event: WebhookEvent) -> None:
    """Delivery confirmation — update email_events."""
    if event.provider_message_id:
        await db.execute(
            text(
                "UPDATE gdpr.email_events "
                "SET status = 'delivered', delivered_at = NOW() "
                "WHERE provider_message_id = :pmid AND status != 'delivered'"
            ),
            {"pmid": event.provider_message_id},
        )


async def _handle_unsubscribe(db: AsyncSession, event: WebhookEvent) -> None:
    """Provider-side unsubscribe — update email_preferences."""
    logger.info(
        "Unsubscribe webhook: email=%s",
        event.recipient_email,
    )
    if event.recipient_email:
        # Look up user and disable marketing
        user = (
            (
                await db.execute(
                    text("SELECT id FROM core.users WHERE email = :email"),
                    {"email": event.recipient_email},
                )
            )
            .mappings()
            .first()
        )

        if user:
            await db.execute(
                text(
                    "UPDATE gdpr.email_preferences "
                    "SET marketing_email = false "
                    "WHERE user_id = :uid"
                ),
                {"uid": str(user["id"])},
            )


async def _suppress_user_by_email(db: AsyncSession, email: str, reason: str) -> None:
    """Suppress a user by their email address."""
    user = (
        (
            await db.execute(
                text("SELECT id FROM core.users WHERE email = :email"),
                {"email": email},
            )
        )
        .mappings()
        .first()
    )

    if not user:
        logger.warning("Webhook: user not found for email %s", email)
        return

    user_id = str(user["id"])

    # Check if already suppressed
    existing = (
        (
            await db.execute(
                text(
                    "SELECT suppressed_at FROM gdpr.email_preferences "
                    "WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if existing and existing["suppressed_at"]:
        return  # Already suppressed

    if existing:
        await db.execute(
            text(
                "UPDATE gdpr.email_preferences "
                "SET suppressed_at = NOW(), suppression_reason = :reason "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id, "reason": reason},
        )
    else:
        await db.execute(
            text(
                "INSERT INTO gdpr.email_preferences "
                "(user_id, marketing_email, transactional_email, "
                "suppressed_at, suppression_reason) "
                "VALUES (:uid, false, true, NOW(), :reason) "
                "ON CONFLICT (user_id) DO UPDATE "
                "SET suppressed_at = NOW(), suppression_reason = :reason"
            ),
            {"uid": user_id, "reason": reason},
        )

    logger.info("User %s suppressed (reason=%s)", user_id, reason)
