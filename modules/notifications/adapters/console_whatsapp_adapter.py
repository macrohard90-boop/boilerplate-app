"""Console WhatsApp adapter for development.

Logs WhatsApp messages to stdout instead of sending them.
Useful for local development and testing without an external WhatsApp provider.
"""

import json
import logging
import uuid
from typing import Any

from modules.notifications.interfaces.whatsapp_provider import (
    WhatsAppProvider,
    WhatsAppSendResult,
    WhatsAppWebhookEvent,
)

logger = logging.getLogger(__name__)


class ConsoleWhatsAppAdapter(WhatsAppProvider):
    """Development adapter that logs WhatsApp messages to the console."""

    async def send_template(
        self,
        to_number: str,
        template_name: str,
        *,
        language: str = "en",
        parameters: dict[str, Any] | None = None,
        media_url: str | None = None,
    ) -> WhatsAppSendResult:
        message_id = f"console_wa_{uuid.uuid4().hex[:12]}"

        logger.info(
            "=== WHATSAPP TEMPLATE SENT (console) ===\n"
            "  Message-ID: %s\n"
            "  To: %s\n"
            "  Template: %s (lang=%s)\n"
            "  Parameters: %s\n"
            "  Media: %s\n"
            "========================================",
            message_id,
            to_number,
            template_name,
            language,
            parameters or {},
            media_url or "(none)",
        )
        return WhatsAppSendResult(
            success=True,
            provider_message_id=message_id,
            provider="console",
        )

    async def send_text(
        self,
        to_number: str,
        text: str,
    ) -> WhatsAppSendResult:
        message_id = f"console_wa_{uuid.uuid4().hex[:12]}"

        logger.info(
            "=== WHATSAPP TEXT SENT (console) ===\n"
            "  Message-ID: %s\n"
            "  To: %s\n"
            "  Text: %s\n"
            "===================================",
            message_id,
            to_number,
            text[:200],
        )
        return WhatsAppSendResult(
            success=True,
            provider_message_id=message_id,
            provider="console",
        )

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WhatsAppWebhookEvent:
        data = json.loads(payload)
        return WhatsAppWebhookEvent(
            event_type=data.get("event", "unknown"),
            event_id=data.get("event_id", f"console_{uuid.uuid4().hex[:8]}"),
            provider_message_id=data.get("message_id"),
            recipient_number=data.get("to_number"),
            raw_data=data,
        )
