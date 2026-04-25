"""SmsProvider abstract base class and response models.

Any SMS service (Brevo, Twilio, Vonage, etc.) implements this interface.
Swap providers by implementing the ABC and setting SMS_PROVIDER in .env.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SmsSendResult:
    """Returned by send_sms."""

    success: bool
    provider_message_id: str | None = None
    provider: str = ""
    error: str | None = None


@dataclass
class SmsWebhookEvent:
    """Parsed webhook event from the SMS provider."""

    event_type: str  # delivered, failed, clicked
    event_id: str | None = None
    provider_message_id: str | None = None
    recipient_number: str | None = None
    timestamp: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


class SmsProvider(ABC):
    """Abstract SMS provider interface.

    Implementations must handle:
    - Single SMS sending (transactional)
    - Batch SMS sending (campaigns)
    - Webhook signature verification
    """

    @abstractmethod
    async def send_sms(
        self,
        to_number: str,
        content: str,
        *,
        sender: str | None = None,
        tags: list[str] | None = None,
    ) -> SmsSendResult:
        """Send a single SMS message."""
        ...

    @abstractmethod
    async def send_batch(
        self,
        messages: list[dict[str, str]],
        *,
        sender: str | None = None,
    ) -> list[SmsSendResult]:
        """Send SMS to multiple recipients.

        Each message dict has keys: to_number, content.
        """
        ...

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> SmsWebhookEvent:
        """Verify webhook signature and return parsed event.

        Raises ValueError on invalid signature.
        """
        ...
