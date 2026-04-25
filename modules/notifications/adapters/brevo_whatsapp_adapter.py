"""Brevo WhatsApp adapter.

Uses httpx async client against Brevo's WhatsApp API v3.
Endpoint: POST /v3/whatsapp/sendMessage
Docs: https://developers.brevo.com/reference/sendwhatsappmessage
"""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from modules.notifications.interfaces.whatsapp_provider import (
    WhatsAppProvider,
    WhatsAppSendResult,
    WhatsAppWebhookEvent,
)

logger = logging.getLogger(__name__)

BREVO_API_BASE = "https://api.brevo.com/v3"


class BrevoWhatsAppAdapter(WhatsAppProvider):
    """Production WhatsApp adapter using Brevo HTTP API."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._api_key = settings.brevo_api_key
        self._webhook_secret = settings.brevo_webhook_secret
        self._sender_number = settings.brevo_whatsapp_number

        if not self._api_key:
            raise ValueError("BREVO_API_KEY is required when WHATSAPP_PROVIDER=brevo")

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def send_template(
        self,
        to_number: str,
        template_name: str,
        *,
        language: str = "en",
        parameters: dict[str, Any] | None = None,
        media_url: str | None = None,
    ) -> WhatsAppSendResult:
        # Brevo uses numeric template IDs — template_name is resolved
        # to a Brevo template ID. For now, pass as-is (admin provides ID).
        payload: dict[str, Any] = {
            "senderNumber": self._sender_number,
            "contactNumbers": [to_number],
            "templateId": int(template_name) if template_name.isdigit() else 0,
        }
        if parameters:
            # Brevo expects body_variables as a list of strings
            body_vars = [str(v) for v in parameters.values()]
            payload["bodyVariables"] = body_vars
        if media_url:
            payload["mediaUrl"] = media_url

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/whatsapp/sendMessage",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_id = str(data.get("messageId", ""))
                logger.info(
                    "Brevo WA: sent template '%s' to %s, messageId=%s",
                    template_name,
                    to_number,
                    message_id,
                )
                return WhatsAppSendResult(
                    success=True,
                    provider_message_id=message_id,
                    provider="brevo",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Brevo WA: send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return WhatsAppSendResult(
                    success=False,
                    provider="brevo",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Brevo WA: send_template exception for %s", to_number)
            return WhatsAppSendResult(
                success=False,
                provider="brevo",
                error=str(e),
            )

    async def send_text(
        self,
        to_number: str,
        text: str,
    ) -> WhatsAppSendResult:
        # Brevo free-form text is sent via the same endpoint with "text" key
        payload: dict[str, Any] = {
            "senderNumber": self._sender_number,
            "contactNumbers": [to_number],
            "text": text,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{BREVO_API_BASE}/whatsapp/sendMessage",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_id = str(data.get("messageId", ""))
                logger.info(
                    "Brevo WA: sent text to %s, messageId=%s",
                    to_number,
                    message_id,
                )
                return WhatsAppSendResult(
                    success=True,
                    provider_message_id=message_id,
                    provider="brevo",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Brevo WA: text send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return WhatsAppSendResult(
                    success=False,
                    provider="brevo",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Brevo WA: send_text exception for %s", to_number)
            return WhatsAppSendResult(
                success=False,
                provider="brevo",
                error=str(e),
            )

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WhatsAppWebhookEvent:
        if self._webhook_secret:
            expected = hmac.new(
                self._webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid Brevo WhatsApp webhook signature")

        data = json.loads(payload)
        # Brevo WA webhook events: delivered, read, failed
        return WhatsAppWebhookEvent(
            event_type=data.get("event", "unknown"),
            provider_message_id=str(data.get("messageId", "")),
            recipient_number=data.get("phoneNumber"),
            timestamp=data.get("date"),
            raw_data=data,
        )
