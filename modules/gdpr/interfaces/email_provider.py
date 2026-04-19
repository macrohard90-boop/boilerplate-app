"""EmailProvider abstract base class and response models.

Any email service (Brevo, SendGrid, Postmark, etc.) implements this interface.
Swap providers by implementing the ABC and setting EMAIL_PROVIDER in .env.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SendResult:
    """Returned by send_email."""

    success: bool
    provider_message_id: str | None = None
    provider: str = ""
    error: str | None = None


@dataclass
class BatchRecipient:
    """A single recipient in a batch send."""

    to_email: str
    to_name: str | None = None
    template_data: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None  # For audit trail


@dataclass
class SyncResult:
    """Returned by sync_suppression."""

    synced_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class WebhookEvent:
    """Parsed webhook event from the email provider."""

    event_type: str  # delivered, bounced, complained, opened, clicked
    event_id: str | None = None
    provider_message_id: str | None = None
    recipient_email: str | None = None
    timestamp: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CampaignResult:
    """Returned by create_campaign."""

    provider_campaign_id: str
    status: str = "created"


@dataclass
class CampaignStats:
    """Campaign statistics pulled from ESP API."""

    sent: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    bounced: int = 0
    unsubscribed: int = 0
    fetched_at: str | None = None


class EmailProvider(ABC):
    """Abstract email provider interface.

    Implementations must handle:
    - Single email sending (transactional + marketing)
    - Batch sending for campaigns
    - Suppression list synchronization
    - Webhook signature verification

    Campaign methods are optional — not all providers support them.
    """

    @abstractmethod
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
        """Send a single email with pre-rendered HTML content."""
        ...

    @abstractmethod
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
        """Send the same email to multiple recipients."""
        ...

    @abstractmethod
    async def sync_suppression(
        self,
        suppressed_emails: list[str],
    ) -> SyncResult:
        """Push local suppression list to the ESP."""
        ...

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """Verify webhook signature and return parsed event.

        Raises ValueError on invalid signature.
        """
        ...

    # Campaign methods (optional — not all providers support them)

    async def create_campaign(
        self,
        name: str,
        subject: str,
        html_content: str,
        *,
        list_ids: list[int] | None = None,
        scheduled_at: str | None = None,
    ) -> CampaignResult:
        """Create a marketing campaign in the ESP."""
        raise NotImplementedError("Campaign management not supported by this provider")

    async def get_campaign_stats(
        self,
        provider_campaign_id: str,
    ) -> CampaignStats:
        """Pull campaign statistics from the ESP API."""
        raise NotImplementedError("Campaign stats not supported by this provider")
