"""Brevo SMS adapter.

Uses httpx async client against Brevo's transactional SMS API v3.
Endpoint: POST /v3/transactionalSMS/send (150 RPS rate limit)
Docs: https://developers.brevo.com/reference/sendtransacsms
"""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from modules.notifications.interfaces.sms_provider import (
    SmsProvider,
    SmsSendResult,
    SmsWebhookEvent,
)

logger = logging.getLogger(__name__)

BREVO_API_BASE = "https://api.brevo.com/v3"


class BrevoSmsAdapter(SmsProvider):
    """Production SMS adapter using Brevo HTTP API."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._api_key = settings.brevo_api_key
        self._webhook_secret = settings.brevo_webhook_secret
        self._default_sender = settings.brevo_sms_sender

        if not self._api_key:
            raise ValueError("BREVO_API_KEY is required when SMS_PROVIDER=brevo")

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def send_sms(
        self,
        to_number: str,
        content: str,
        *,
        sender: str | None = None,
        tags: list[str] | None = None,
    ) -> SmsSendResult:
        payload: dict[str, Any] = {
            "sender": sender or self._default_sender,
            "recipient": to_number,
            "content": content,
            "type": "transactional",
        }
        if tags:
            payload["tag"] = tags[0]  # Brevo SMS supports a single tag string

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/transactionalSMS/send",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_id = str(data.get("messageId", ""))
                logger.info(
                    "Brevo SMS: sent to %s, messageId=%s",
                    to_number,
                    message_id,
                )
                return SmsSendResult(
                    success=True,
                    provider_message_id=message_id,
                    provider="brevo",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Brevo SMS: send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return SmsSendResult(
                    success=False,
                    provider="brevo",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Brevo SMS: send_sms exception for %s", to_number)
            return SmsSendResult(
                success=False,
                provider="brevo",
                error=str(e),
            )

    async def send_batch(
        self,
        messages: list[dict[str, str]],
        *,
        sender: str | None = None,
    ) -> list[SmsSendResult]:
        # Brevo has no batch SMS endpoint — send individually
        results: list[SmsSendResult] = []
        for msg in messages:
            result = await self.send_sms(
                to_number=msg["to_number"],
                content=msg["content"],
                sender=sender,
            )
            results.append(result)
        return results

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> SmsWebhookEvent:
        # Verify HMAC signature if webhook secret is configured
        if self._webhook_secret:
            expected = hmac.new(
                self._webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid Brevo SMS webhook signature")

        data = json.loads(payload)
        # Brevo SMS webhook events: delivered, softBounce, hardBounce, blocked
        event_map = {
            "delivered": "delivered",
            "softBounce": "failed",
            "hardBounce": "failed",
            "blocked": "failed",
        }
        raw_event = data.get("event", "unknown")

        return SmsWebhookEvent(
            event_type=event_map.get(raw_event, raw_event),
            provider_message_id=str(data.get("messageId", "")),
            recipient_number=data.get("phoneNumber"),
            timestamp=data.get("date"),
            raw_data=data,
        )
