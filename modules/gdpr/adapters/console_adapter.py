"""Console email adapter for development.

Logs emails to stdout instead of sending them. Useful for local development
and testing without an external email provider.
"""

import logging
import uuid

from modules.gdpr.interfaces.email_provider import (
    BatchRecipient,
    CampaignResult,
    CampaignStats,
    EmailProvider,
    SendResult,
    SyncResult,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


class ConsoleAdapter(EmailProvider):
    """Development adapter that logs emails to the console."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        *,
        to_name: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> SendResult:
        message_id = f"console_{uuid.uuid4().hex[:12]}"
        recipient = f"{to_name} <{to_email}>" if to_name else to_email

        logger.info(
            "=== EMAIL SENT (console) ===\n"
            "  Message-ID: %s\n"
            "  To: %s\n"
            "  From: %s <%s>\n"
            "  Subject: %s\n"
            "  Tags: %s\n"
            "  Headers: %s\n"
            "  HTML length: %d chars\n"
            "===========================",
            message_id,
            recipient,
            from_name or "(default)",
            from_email or "(default)",
            subject,
            tags or [],
            headers or {},
            len(html_content),
        )
        return SendResult(
            success=True,
            provider_message_id=message_id,
            provider="console",
        )

    async def send_batch(
        self,
        recipients: list[BatchRecipient],
        subject: str,
        html_content: str,
        *,
        from_email: str | None = None,
        from_name: str | None = None,
        tags: list[str] | None = None,
    ) -> list[SendResult]:
        results: list[SendResult] = []
        logger.info(
            "=== BATCH EMAIL (console) === %d recipients, subject: %s",
            len(recipients),
            subject,
        )
        for recipient in recipients:
            result = await self.send_email(
                to_email=recipient.to_email,
                subject=subject,
                html_content=html_content,
                to_name=recipient.to_name,
                from_email=from_email,
                from_name=from_name,
                tags=tags,
            )
            results.append(result)
        return results

    async def sync_suppression(
        self,
        suppressed_emails: list[str],
    ) -> SyncResult:
        logger.info(
            "=== SUPPRESSION SYNC (console) === %d emails suppressed",
            len(suppressed_emails),
        )
        return SyncResult(synced_count=len(suppressed_emails))

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        # Console adapter accepts all webhooks (for testing)
        import json

        data = json.loads(payload)
        return WebhookEvent(
            event_type=data.get("event", "unknown"),
            event_id=data.get("event_id", f"console_{uuid.uuid4().hex[:8]}"),
            provider_message_id=data.get("message_id"),
            recipient_email=data.get("email"),
            raw_data=data,
        )

    async def create_campaign(
        self,
        name: str,
        subject: str,
        html_content: str,
        *,
        list_ids: list[int] | None = None,
        scheduled_at: str | None = None,
    ) -> CampaignResult:
        campaign_id = f"console_campaign_{uuid.uuid4().hex[:8]}"
        logger.info(
            "=== CAMPAIGN CREATED (console) ===\n"
            "  Campaign-ID: %s\n"
            "  Name: %s\n"
            "  Subject: %s\n"
            "  Lists: %s\n"
            "  Scheduled: %s\n"
            "================================",
            campaign_id,
            name,
            subject,
            list_ids or [],
            scheduled_at or "immediate",
        )
        return CampaignResult(
            provider_campaign_id=campaign_id,
            status="sent" if not scheduled_at else "scheduled",
        )

    async def get_campaign_stats(
        self,
        provider_campaign_id: str,
    ) -> CampaignStats:
        logger.info(
            "=== CAMPAIGN STATS (console) === %s — returning zeros",
            provider_campaign_id,
        )
        return CampaignStats()
