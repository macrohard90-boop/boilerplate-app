"""Twilio WhatsApp adapter.

Uses httpx async client against Twilio's REST API with WhatsApp channel.
Docs: https://www.twilio.com/docs/whatsapp/api

Twilio WhatsApp uses the same Messages API as SMS but with "whatsapp:" prefix
on phone numbers. Supports template messages, free-form text, and rich media.

Configuration:
  WHATSAPP_PROVIDER=twilio
  TWILIO_ACCOUNT_SID=ACxxx
  TWILIO_AUTH_TOKEN=xxx
  TWILIO_WHATSAPP_FROM=+1234567890  (Twilio-provisioned WhatsApp number)
"""

import json
import logging
import urllib.parse
from typing import Any

import httpx

from modules.notifications.interfaces.whatsapp_provider import (
    WhatsAppProvider,
    WhatsAppSendResult,
    WhatsAppWebhookEvent,
)

logger = logging.getLogger(__name__)


class TwilioWhatsAppAdapter(WhatsAppProvider):
    """Production WhatsApp adapter using Twilio REST API."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._account_sid = settings.twilio_account_sid
        self._auth_token = settings.twilio_auth_token
        self._from_number = settings.twilio_whatsapp_from

        if not self._account_sid or not self._auth_token:
            raise ValueError(
                "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required "
                "when WHATSAPP_PROVIDER=twilio"
            )

    @property
    def _base_url(self) -> str:
        return f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}"

    def _auth(self) -> tuple[str, str]:
        return (self._account_sid, self._auth_token)

    async def send_template(
        self,
        to_number: str,
        template_name: str,
        *,
        language: str = "en",
        parameters: dict[str, Any] | None = None,
        media_url: str | None = None,
    ) -> WhatsAppSendResult:
        """Send a WhatsApp template message via Twilio Content API.

        Twilio uses Content SID for pre-approved templates. The template_name
        is expected to be a Twilio Content SID (e.g., HXxxx) or a template name
        that maps to one.
        """
        form_data: dict[str, str] = {
            "To": f"whatsapp:{to_number}",
            "From": f"whatsapp:{self._from_number}",
        }

        # If template_name looks like a Content SID, use ContentSid
        if template_name.startswith("HX"):
            form_data["ContentSid"] = template_name
            if parameters:
                # Twilio Content API uses ContentVariables as JSON
                form_data["ContentVariables"] = json.dumps(parameters)
        else:
            # Fall back to body-based template (for Twilio sandbox/testing)
            body = template_name
            if parameters:
                for key, value in parameters.items():
                    body = body.replace(f"{{{{{key}}}}}", str(value))
            form_data["Body"] = body

        if media_url:
            form_data["MediaUrl"] = media_url

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/Messages.json",
                    data=form_data,
                    auth=self._auth(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_sid = data.get("sid", "")
                logger.info(
                    "Twilio WA: sent template '%s' to %s, sid=%s",
                    template_name,
                    to_number,
                    message_sid,
                )
                return WhatsAppSendResult(
                    success=True,
                    provider_message_id=message_sid,
                    provider="twilio",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Twilio WA: send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return WhatsAppSendResult(
                    success=False,
                    provider="twilio",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Twilio WA: send_template exception for %s", to_number)
            return WhatsAppSendResult(
                success=False,
                provider="twilio",
                error=str(e),
            )

    async def send_text(
        self,
        to_number: str,
        text: str,
    ) -> WhatsAppSendResult:
        """Send a free-form WhatsApp text message.

        Only works within Twilio's 24h conversation window.
        """
        form_data: dict[str, str] = {
            "To": f"whatsapp:{to_number}",
            "From": f"whatsapp:{self._from_number}",
            "Body": text,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/Messages.json",
                    data=form_data,
                    auth=self._auth(),
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                message_sid = data.get("sid", "")
                logger.info(
                    "Twilio WA: sent text to %s, sid=%s",
                    to_number,
                    message_sid,
                )
                return WhatsAppSendResult(
                    success=True,
                    provider_message_id=message_sid,
                    provider="twilio",
                )
            else:
                error_msg = resp.text
                logger.error(
                    "Twilio WA: text send failed (%d): %s",
                    resp.status_code,
                    error_msg,
                )
                return WhatsAppSendResult(
                    success=False,
                    provider="twilio",
                    error=f"HTTP {resp.status_code}: {error_msg}",
                )
        except Exception as e:
            logger.exception("Twilio WA: send_text exception for %s", to_number)
            return WhatsAppSendResult(
                success=False,
                provider="twilio",
                error=str(e),
            )

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WhatsAppWebhookEvent:
        """Parse Twilio WhatsApp status callback.

        Twilio WhatsApp uses the same callback format as SMS.
        """
        try:
            data = dict(urllib.parse.parse_qsl(payload.decode()))
        except Exception:
            data = json.loads(payload)

        # Twilio WhatsApp statuses: sent, delivered, read, failed, undelivered
        status = data.get("MessageStatus", "unknown")
        event_map = {
            "delivered": "delivered",
            "sent": "delivered",
            "read": "read",
            "failed": "failed",
            "undelivered": "failed",
        }

        return WhatsAppWebhookEvent(
            event_type=event_map.get(status, status),
            event_id=data.get("SmsSid", data.get("MessageSid")),
            provider_message_id=data.get("MessageSid"),
            recipient_number=data.get("To", "").replace("whatsapp:", ""),
            timestamp=None,
            raw_data=data,
        )
