"""Console SMS adapter for development.

Logs SMS messages to stdout instead of sending them.
Useful for local development and testing without an external SMS provider.
"""

import json
import logging
import uuid

from modules.notifications.interfaces.sms_provider import (
    SmsProvider,
    SmsSendResult,
    SmsWebhookEvent,
)

logger = logging.getLogger(__name__)


class ConsoleSmsAdapter(SmsProvider):
    """Development adapter that logs SMS to the console."""

    async def send_sms(
        self,
        to_number: str,
        content: str,
        *,
        sender: str | None = None,
        tags: list[str] | None = None,
    ) -> SmsSendResult:
        message_id = f"console_sms_{uuid.uuid4().hex[:12]}"

        logger.info(
            "=== SMS SENT (console) ===\n"
            "  Message-ID: %s\n"
            "  To: %s\n"
            "  Sender: %s\n"
            "  Tags: %s\n"
            "  Content: %s\n"
            "=========================",
            message_id,
            to_number,
            sender or "(default)",
            tags or [],
            content[:200],
        )
        return SmsSendResult(
            success=True,
            provider_message_id=message_id,
            provider="console",
        )

    async def send_batch(
        self,
        messages: list[dict[str, str]],
        *,
        sender: str | None = None,
    ) -> list[SmsSendResult]:
        results: list[SmsSendResult] = []
        logger.info(
            "=== BATCH SMS (console) === %d messages",
            len(messages),
        )
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
        data = json.loads(payload)
        return SmsWebhookEvent(
            event_type=data.get("event", "unknown"),
            event_id=data.get("event_id", f"console_{uuid.uuid4().hex[:8]}"),
            provider_message_id=data.get("message_id"),
            recipient_number=data.get("to_number"),
            raw_data=data,
        )
