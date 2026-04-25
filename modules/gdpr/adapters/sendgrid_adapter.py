"""SendGrid email adapter.

Uses httpx async client against SendGrid's Mail Send v3 API.
Docs: https://docs.sendgrid.com/api-reference/mail-send/mail-send

Cost: Free tier 100/day, then $20-90/mo for 50k-100k emails.
Similar feature set to Brevo — good drop-in alternative.

Configuration:
  EMAIL_PROVIDER=sendgrid
  SENDGRID_API_KEY=SG.xxx
  SENDGRID_WEBHOOK_SECRET=  (for webhook signature verification)
"""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from modules.gdpr.interfaces.email_provider import (
    BatchRecipient,
    EmailProvider,
    SendResult,
    SyncResult,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

SENDGRID_API_BASE = "https://api.sendgrid.com/v3"


class SendGridAdapter(EmailProvider):
    """Production email adapter using SendGrid HTTP API."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._api_key = settings.sendgrid_api_key
        self._webhook_secret = settings.sendgrid_webhook_secret
        self._from_email = settings.from_email
        self._from_name = settings.from_name

        if not self._api_key:
            raise ValueError(
                "SENDGRID_API_KEY is required when EMAIL_PROVIDER=sendgrid"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

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
        to_obj: dict[str, str] = {"email": to_email}
        if to_name:
            to_obj["name"] = to_name

        payload: dict[str, Any] = {
            "personalizations": [{"to": [to_obj]}],
            "from": {
                "email": from_email or self._from_email,
                "name": from_name or self._from_name,
            },
            "subject": subject,
            "content": [{"type": "text/html", "value": html_content}],
        }

        if reply_to:
            payload["reply_to"] = {"email": reply_to}
        if headers:
            payload["headers"] = headers
        if tags:
            payload["categories"] = tags[:10]  # SendGrid allows up to 10 categories

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SENDGRID_API_BASE}/mail/send",
                    json=payload,
                    headers=self._headers(),
                )
            # SendGrid returns 202 Accepted on success
            if resp.status_code in (200, 201, 202):
                # SendGrid returns message ID in X-Message-Id header
                message_id = resp.headers.get("X-Message-Id", "")
                logger.info(
                    "SendGrid: sent email to %s, MessageId=%s",
                    to_email,
                    message_id,
                )
                return SendResult(
                    success=True,
                    provider_message_id=message_id,
                    provider="sendgrid",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "SendGrid: send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return SendResult(
                    success=False,
                    provider="sendgrid",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("SendGrid: send_email exception for %s", to_email)
            return SendResult(
                success=False,
                provider="sendgrid",
                error=str(e),
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
        # SendGrid supports multiple personalizations in one call (up to 1000),
        # but for template-data-per-recipient we send individually like Brevo.
        results: list[SendResult] = []
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
        """Add emails to SendGrid global suppressions."""
        if not suppressed_emails:
            return SyncResult(synced_count=0)

        errors: list[str] = []
        synced = 0

        try:
            payload = {"recipient_emails": suppressed_emails}
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SENDGRID_API_BASE}/asm/suppressions/global",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                synced = len(suppressed_emails)
                logger.info("SendGrid: synced %d suppressed emails", synced)
            else:
                errors.append(f"HTTP {resp.status_code}: {resp.text}")
                logger.error("SendGrid: suppression sync failed: %s", resp.text)
        except Exception as e:
            errors.append(str(e))
            logger.exception("SendGrid: suppression sync exception")

        return SyncResult(synced_count=synced, errors=errors)

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """Verify SendGrid Event Webhook signature and parse the event.

        SendGrid signs webhooks using ECDSA (Signed Event Webhook) or HMAC.
        For simplicity, we support the verification key approach.
        """
        if self._webhook_secret:
            expected = hmac.new(
                self._webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid SendGrid webhook signature")

        # SendGrid sends an array of events
        events = json.loads(payload)
        if isinstance(events, list) and events:
            data = events[0]
        else:
            data = events

        # SendGrid event types: delivered, bounce, dropped, deferred,
        # open, click, spamreport, unsubscribe
        event_type_map = {
            "delivered": "delivered",
            "bounce": "bounced",
            "dropped": "bounced",
            "spamreport": "complained",
            "open": "opened",
            "click": "clicked",
            "unsubscribe": "complained",
        }

        raw_event = data.get("event", "unknown")
        event_type = event_type_map.get(raw_event, raw_event)

        return WebhookEvent(
            event_type=event_type,
            event_id=data.get("sg_event_id"),
            provider_message_id=data.get("sg_message_id"),
            recipient_email=data.get("email"),
            timestamp=str(data.get("timestamp", "")),
            raw_data=data,
        )
