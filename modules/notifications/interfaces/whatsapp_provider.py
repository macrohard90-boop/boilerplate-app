"""WhatsAppProvider abstract base class and response models.

Any WhatsApp Business API provider (Brevo, Twilio, MessageBird, etc.)
implements this interface. Swap providers by setting WHATSAPP_PROVIDER in .env.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WhatsAppSendResult:
    """Returned by send_template / send_text."""

    success: bool
    provider_message_id: str | None = None
    provider: str = ""
    error: str | None = None


@dataclass
class WhatsAppWebhookEvent:
    """Parsed webhook event from the WhatsApp provider."""

    event_type: str  # delivered, read, failed
    event_id: str | None = None
    provider_message_id: str | None = None
    recipient_number: str | None = None
    timestamp: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


class WhatsAppProvider(ABC):
    """Abstract WhatsApp provider interface.

    Implementations must handle:
    - Template message sending (required for first contact)
    - Free-form text sending (within 24h conversation window)
    - Webhook signature verification
    """

    @abstractmethod
    async def send_template(
        self,
        to_number: str,
        template_name: str,
        *,
        language: str = "en",
        parameters: dict[str, Any] | None = None,
        media_url: str | None = None,
    ) -> WhatsAppSendResult:
        """Send a pre-approved WhatsApp template message.

        Required for initiating conversations (24h rule).
        """
        ...

    @abstractmethod
    async def send_text(
        self,
        to_number: str,
        text: str,
    ) -> WhatsAppSendResult:
        """Send a free-form text message.

        Only works within 24h of user's last message (conversation window).
        """
        ...

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WhatsAppWebhookEvent:
        """Verify webhook signature and return parsed event.

        Raises ValueError on invalid signature.
        """
        ...
