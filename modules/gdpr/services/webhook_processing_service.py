"""Email webhook processing — handles bounce, complaint, delivery, open, click events.

Processes webhooks from email providers (Brevo, etc.) to:
- Auto-suppress users on hard bounces and spam complaints
- Update delivery status in email_events audit table
- Update campaign_recipients with delivery/open/click timestamps
- Record campaign link clicks with zone positions for heatmap
- Maintain webhook idempotency via gdpr.email_webhook_events
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.gdpr.interfaces.email_provider import WebhookEvent

logger = logging.getLogger(__name__)

# Map provider event types to normalized types
_BOUNCE_EVENTS = {"hard_bounce", "bounced", "invalid_email", "blocked", "soft_bounce"}
_COMPLAINT_EVENTS = {"complaint", "spam", "spam_report"}
_DELIVERY_EVENTS = {"delivered", "request", "sent"}
_OPEN_EVENTS = {"opened", "unique_opened"}
_CLICK_EVENTS = {"click", "unique_click"}
_UNSUBSCRIBE_EVENTS = {"unsubscribed", "unsubscribe"}
_PROXY_OPEN_EVENTS = {"proxy_open"}


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

    # 2. Record webhook event for idempotency (store full payload)
    if event_id:
        import json

        await db.execute(
            text(
                "INSERT INTO gdpr.email_webhook_events "
                "(event_id, event_type, provider, payload) "
                "VALUES (:eid, :etype, :prov, :payload)"
            ),
            {
                "eid": event_id,
                "etype": event_type,
                "prov": event.raw_data.get("provider", "unknown"),
                "payload": json.dumps(event.raw_data),
            },
        )

    # 3. Dispatch by event type
    if event_type in _BOUNCE_EVENTS:
        await _handle_bounce(db, event)
    elif event_type in _COMPLAINT_EVENTS:
        await _handle_complaint(db, event)
    elif event_type in _DELIVERY_EVENTS:
        await _handle_delivery(db, event)
    elif event_type in _OPEN_EVENTS:
        await _handle_open(db, event)
    elif event_type in _CLICK_EVENTS:
        await _handle_click(db, event)
    elif event_type in _UNSUBSCRIBE_EVENTS:
        await _handle_unsubscribe(db, event)
    elif event_type in _PROXY_OPEN_EVENTS:
        logger.info("Proxy open (Apple MPP): msg_id=%s", event.provider_message_id)
        # Don't count proxy opens as real opens
    else:
        logger.debug("Ignoring webhook event type: %s", event_type)

    await db.commit()
    return {"status": "processed", "event_type": event_type}


async def _handle_bounce(db: AsyncSession, event: WebhookEvent) -> None:
    """Hard bounce — suppress user's email, update campaign_recipients."""
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

        # Update campaign_recipients
        await _update_campaign_recipient(db, event.provider_message_id, "bounced")

    # Suppress user by email address
    if event.recipient_email:
        await _suppress_user_by_email(db, event.recipient_email, "bounce")


async def _handle_complaint(db: AsyncSession, event: WebhookEvent) -> None:
    """Spam complaint — suppress user's email, update campaign_recipients."""
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

        # Update campaign_recipients
        await _update_campaign_recipient(db, event.provider_message_id, "complained")

    # Suppress user by email address
    if event.recipient_email:
        await _suppress_user_by_email(db, event.recipient_email, "complaint")


async def _handle_delivery(db: AsyncSession, event: WebhookEvent) -> None:
    """Delivery confirmation — update email_events and campaign_recipients."""
    if event.provider_message_id:
        await db.execute(
            text(
                "UPDATE gdpr.email_events "
                "SET status = 'delivered', delivered_at = NOW() "
                "WHERE provider_message_id = :pmid AND status != 'delivered'"
            ),
            {"pmid": event.provider_message_id},
        )

        # Update campaign_recipients
        await db.execute(
            text(
                "UPDATE marketing.campaign_recipients "
                "SET status = CASE WHEN status = 'sent' THEN 'delivered' ELSE status END, "
                "delivered_at = COALESCE(delivered_at, NOW()) "
                "WHERE provider_message_id = :pmid"
            ),
            {"pmid": event.provider_message_id},
        )


async def _handle_open(db: AsyncSession, event: WebhookEvent) -> None:
    """Email opened — update campaign_recipients with bot detection."""
    if not event.provider_message_id:
        return

    # Bot/proxy detection: check user-agent for known bots
    raw = event.raw_data
    user_agent = raw.get("user-agent", raw.get("user_agent", ""))
    is_bot = _is_bot_open(user_agent, raw.get("ip", ""))

    if is_bot:
        logger.debug(
            "Bot/proxy open detected: msg_id=%s, ua=%s",
            event.provider_message_id,
            user_agent[:80],
        )
        return  # Don't count bot opens

    # Update campaign_recipients opened_at (only first open)
    await db.execute(
        text(
            "UPDATE marketing.campaign_recipients "
            "SET status = CASE "
            "  WHEN status IN ('sent', 'delivered') THEN 'opened' "
            "  ELSE status END, "
            "opened_at = COALESCE(opened_at, NOW()) "
            "WHERE provider_message_id = :pmid"
        ),
        {"pmid": event.provider_message_id},
    )


async def _handle_click(db: AsyncSession, event: WebhookEvent) -> None:
    """Email link clicked — update campaign_recipients and record click."""
    if not event.provider_message_id:
        return

    # Brevo sends "link" for transactional, "URL" for marketing
    raw = event.raw_data
    clicked_url = raw.get("link") or raw.get("URL") or raw.get("url", "")

    # Update campaign_recipients
    await db.execute(
        text(
            "UPDATE marketing.campaign_recipients "
            "SET status = CASE "
            "  WHEN status IN ('sent', 'delivered', 'opened') THEN 'clicked' "
            "  ELSE status END, "
            "clicked_at = COALESCE(clicked_at, NOW()) "
            "WHERE provider_message_id = :pmid"
        ),
        {"pmid": event.provider_message_id},
    )

    # Record the click in campaign_link_clicks
    if clicked_url:
        from modules.marketing.services.webhook_event_service import (
            record_email_click,
        )

        await record_email_click(
            db,
            provider_message_id=event.provider_message_id,
            url=clicked_url,
            ip_address=raw.get("ip"),
            user_agent=raw.get("user-agent", raw.get("user_agent")),
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


async def _update_campaign_recipient(
    db: AsyncSession, provider_message_id: str, status: str
) -> None:
    """Update campaign_recipients status by provider_message_id."""
    try:
        await db.execute(
            text(
                "UPDATE marketing.campaign_recipients "
                "SET status = :status "
                "WHERE provider_message_id = :pmid"
            ),
            {"pmid": provider_message_id, "status": status},
        )
    except Exception:
        # Table might not exist yet — non-critical
        pass


def _is_bot_open(user_agent: str, ip: str = "") -> bool:
    """Detect bot/proxy opens (Apple MPP, corporate proxies, etc.).

    Known indicators:
    - Apple Mail Privacy Protection uses Mozilla/5.0 with specific patterns
    - Google proxy opens from specific IP ranges
    - Missing or generic user agents
    """
    ua_lower = user_agent.lower() if user_agent else ""

    # Apple Mail Privacy Protection
    if "mozilla/5.0" in ua_lower and "applewebkit" in ua_lower:
        # Very early open (within seconds of send) + Apple WebKit = likely MPP
        # In practice, Brevo sends "proxy_open" event type for these
        pass

    # Known proxy/bot user agents
    bot_indicators = [
        "googleimageproxy",
        "yahoo! slurp",
        "bingpreview",
        "outlook-ios",
        "ms-office",
    ]
    for indicator in bot_indicators:
        if indicator in ua_lower:
            return True

    return False
