"""Brevo (Sendinblue) email adapter.

Uses httpx async client against Brevo's REST API v3.
Docs: https://developers.brevo.com/reference
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

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

BREVO_API_BASE = "https://api.brevo.com/v3"


class BrevoAdapter(EmailProvider):
    """Production email adapter using Brevo HTTP API."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._api_key = settings.brevo_api_key
        self._webhook_secret = settings.brevo_webhook_secret
        self._from_email = settings.from_email
        self._from_name = settings.from_name

        if not self._api_key:
            raise ValueError("BREVO_API_KEY is required when EMAIL_PROVIDER=brevo")

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
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
        payload: dict[str, Any] = {
            "sender": {
                "email": from_email or self._from_email,
                "name": from_name or self._from_name,
            },
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
        }
        if to_name:
            payload["to"][0]["name"] = to_name
        if reply_to:
            payload["replyTo"] = {"email": reply_to}
        if headers:
            payload["headers"] = headers
        if tags:
            payload["tags"] = tags

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/smtp/email",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_id = data.get("messageId", "")
                logger.info(
                    "Brevo: sent email to %s, messageId=%s",
                    to_email,
                    message_id,
                )
                return SendResult(
                    success=True,
                    provider_message_id=message_id,
                    provider="brevo",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Brevo: send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return SendResult(
                    success=False,
                    provider="brevo",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Brevo: send_email exception for %s", to_email)
            return SendResult(
                success=False,
                provider="brevo",
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
        # Brevo doesn't have a true batch endpoint for transactional.
        # Send individually. For large campaigns, use create_campaign instead.
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
        """Add emails to Brevo's blocklist."""
        if not suppressed_emails:
            return SyncResult(synced_count=0)

        errors: list[str] = []
        synced = 0

        try:
            # Brevo blocklist API: POST /contacts/import with listIds=[] and
            # emailBlacklisted=true
            payload = {
                "emailBlacklisted": True,
                "jsonBody": [{"email": email} for email in suppressed_emails],
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/contacts/import",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201, 202):
                synced = len(suppressed_emails)
                logger.info("Brevo: synced %d suppressed emails", synced)
            else:
                errors.append(f"HTTP {resp.status_code}: {resp.text}")
                logger.error("Brevo: suppression sync failed: %s", resp.text)
        except Exception as e:
            errors.append(str(e))
            logger.exception("Brevo: suppression sync exception")

        return SyncResult(synced_count=synced, errors=errors)

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """Verify Brevo webhook signature and parse the event."""
        if self._webhook_secret:
            expected = hmac.new(
                self._webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid Brevo webhook signature")

        data = json.loads(payload)
        event_type = data.get("event", "unknown")

        return WebhookEvent(
            event_type=event_type,
            event_id=data.get("message-id", data.get("ts", "")),
            provider_message_id=data.get("message-id"),
            recipient_email=data.get("email"),
            timestamp=data.get("ts"),
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
        """Create and optionally schedule a Brevo email campaign."""
        payload: dict[str, Any] = {
            "name": name,
            "subject": subject,
            "sender": {
                "email": self._from_email,
                "name": self._from_name,
            },
            "htmlContent": html_content,
            "type": "classic",
        }
        if list_ids:
            payload["recipients"] = {"listIds": list_ids}
        if scheduled_at:
            payload["scheduledAt"] = scheduled_at

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/emailCampaigns",
                    json=payload,
                    headers=self._headers(),
                )

                if resp.status_code in (200, 201):
                    data = resp.json()
                    campaign_id = str(data.get("id", ""))
                    logger.info("Brevo: created campaign %s (%s)", campaign_id, name)

                    # Send immediately if not scheduled
                    if not scheduled_at:
                        send_resp = await client.post(
                            f"{BREVO_API_BASE}/emailCampaigns/{campaign_id}/sendNow",
                            headers=self._headers(),
                        )
                        if send_resp.status_code not in (200, 201, 204):
                            logger.error(
                                "Brevo: campaign send failed: %s",
                                send_resp.text,
                            )

                    return CampaignResult(
                        provider_campaign_id=campaign_id,
                        status="scheduled" if scheduled_at else "sent",
                    )
                else:
                    logger.error(
                        "Brevo: create campaign failed (%d): %s",
                        resp.status_code,
                        resp.text,
                    )
                    raise RuntimeError(f"Campaign creation failed: {resp.status_code}")
        except httpx.HTTPError as e:
            logger.exception("Brevo: create_campaign exception")
            raise RuntimeError(f"Campaign creation failed: {e}") from e

    async def get_campaign_stats(
        self,
        provider_campaign_id: str,
    ) -> CampaignStats:
        """Pull campaign statistics from Brevo API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{BREVO_API_BASE}/emailCampaigns/{provider_campaign_id}",
                    headers=self._headers(),
                )

            if resp.status_code == 200:
                data = resp.json()
                stats = data.get("statistics", {}).get("globalStats", {})
                return CampaignStats(
                    sent=stats.get("sent", 0),
                    delivered=stats.get("delivered", 0),
                    opened=stats.get("uniqueOpens", 0),
                    clicked=stats.get("uniqueClicks", 0),
                    bounced=(stats.get("hardBounces", 0) + stats.get("softBounces", 0)),
                    unsubscribed=stats.get("unsubscriptions", 0),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
            else:
                logger.error(
                    "Brevo: get campaign stats failed (%d): %s",
                    resp.status_code,
                    resp.text,
                )
                return CampaignStats()
        except Exception:
            logger.exception("Brevo: get_campaign_stats exception")
            return CampaignStats()
