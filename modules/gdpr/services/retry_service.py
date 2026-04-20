"""Email retry queue — background loop that retries failed email sends.

Uses Redis list (email_retry_queue) as a work queue. Failed sends from
email_send_service push items here. This loop pops and retries them,
respecting max_attempts from config.
"""

import asyncio
import json
import logging

from backend.core.config import settings
from backend.core.database import get_session_factory

logger = logging.getLogger(__name__)


async def retry_failed_emails() -> int:
    """Pop items from the retry queue and attempt to resend.

    Returns count of successfully retried emails.
    """
    from backend.core.redis import get_redis

    redis = await get_redis()
    processed = 0

    # Process up to 10 items per iteration
    for _ in range(10):
        raw = await redis.lpop("email_retry_queue")
        if not raw:
            break

        try:
            item = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid retry queue item: %s", raw)
            continue

        event_id = item.get("event_id", "")
        template_id = item.get("template_id", "")
        template_data = item.get("template_data", {})
        email_type = item.get("email_type", "transactional_email")
        to_email = item.get("to_email", "")

        # Check attempt count
        attempt_key = f"email_retry:{event_id}:count"
        attempt_count = await redis.incr(attempt_key)
        await redis.expire(attempt_key, 86400)  # 24h TTL

        if attempt_count > settings.email_retry_max_attempts:
            logger.warning(
                "Email retry exhausted for event %s (%d attempts)",
                event_id,
                attempt_count,
            )
            # Mark as failed in email_events
            factory = get_session_factory()
            async with factory() as db:
                from sqlalchemy import text

                await db.execute(
                    text(
                        "UPDATE gdpr.email_events SET status = 'failed' "
                        "WHERE id = :eid AND status = 'queued'"
                    ),
                    {"eid": event_id},
                )
                await db.commit()
            continue

        # Retry the send
        try:
            from modules.gdpr.services.template_service import render_template_db
            from modules.gdpr.adapters import get_email_provider

            factory = get_session_factory()
            async with factory() as db:
                html_content, subject = await render_template_db(
                    db, template_id, template_data
                )

            if not subject:
                site = settings.site_name or settings.app_name
                subject = f"Message from {site}"

            provider = get_email_provider(email_type)

            result = await provider.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                from_email=settings.from_email,
                from_name=settings.from_name,
                tags=[template_id, email_type, "retry"],
            )

            if result.success:
                # Update email_events to sent
                factory = get_session_factory()
                async with factory() as db:
                    from sqlalchemy import text

                    await db.execute(
                        text(
                            "UPDATE gdpr.email_events "
                            "SET status = 'sent', sent_at = NOW(), "
                            "provider_message_id = :pmid, provider = :prov "
                            "WHERE id = :eid"
                        ),
                        {
                            "eid": event_id,
                            "pmid": result.provider_message_id,
                            "prov": result.provider,
                        },
                    )
                    await db.commit()
                processed += 1
                logger.info(
                    "Retry succeeded for event %s (attempt %d)",
                    event_id,
                    attempt_count,
                )
            else:
                # Re-queue for next attempt
                await redis.rpush("email_retry_queue", raw)
                logger.info(
                    "Retry failed for event %s (attempt %d): %s",
                    event_id,
                    attempt_count,
                    result.error,
                )
        except Exception:
            # Re-queue on exception
            await redis.rpush("email_retry_queue", raw)
            logger.exception(
                "Retry exception for event %s (attempt %d)",
                event_id,
                attempt_count,
            )

    return processed


async def retry_loop() -> None:
    """Background loop that processes the email retry queue."""
    interval = settings.email_retry_interval
    logger.info(
        "Email retry loop started (interval=%ds, max_attempts=%d)",
        interval,
        settings.email_retry_max_attempts,
    )
    while True:
        await asyncio.sleep(interval)
        try:
            count = await retry_failed_emails()
            if count > 0:
                logger.info("Email retry: processed %d emails", count)
        except Exception:
            logger.exception("Email retry loop iteration failed")
