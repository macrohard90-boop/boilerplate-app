"""GDPR email provider interfaces."""

from modules.gdpr.interfaces.email_provider import (
    BatchRecipient,
    CampaignResult,
    CampaignStats,
    EmailProvider,
    SendResult,
    SyncResult,
    WebhookEvent,
)

__all__ = [
    "EmailProvider",
    "SendResult",
    "BatchRecipient",
    "SyncResult",
    "WebhookEvent",
    "CampaignResult",
    "CampaignStats",
]
