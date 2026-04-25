"""AWS SES email adapter.

Uses boto3 async-compatible calls against SES v2 API.
Docs: https://docs.aws.amazon.com/ses/latest/APIReference/
Requires: pip install boto3 (included in requirements.txt)

Cost: ~$0.10 per 1,000 emails — significantly cheaper than Brevo at scale.
SLA: 99.9% uptime. Excellent deliverability when domain is verified.

Configuration:
  EMAIL_PROVIDER=ses
  AWS_ACCESS_KEY_ID=...
  AWS_SECRET_ACCESS_KEY=...
  AWS_REGION=us-east-1  (or eu-west-1, etc.)
  SES_CONFIGURATION_SET=  (optional, enables open/click tracking)
"""

import json
import logging
from typing import Any

from modules.gdpr.interfaces.email_provider import (
    BatchRecipient,
    EmailProvider,
    SendResult,
    SyncResult,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


class SesAdapter(EmailProvider):
    """Production email adapter using AWS SES v2 via boto3."""

    def __init__(self) -> None:
        from backend.core.config import settings

        self._region = settings.aws_region
        self._access_key = settings.aws_access_key_id
        self._secret_key = settings.aws_secret_access_key
        self._configuration_set = settings.ses_configuration_set
        self._from_email = settings.from_email
        self._from_name = settings.from_name

        if not self._access_key or not self._secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required "
                "when EMAIL_PROVIDER=ses"
            )

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Create a boto3 SES client. Created per-call to avoid thread issues."""
        import boto3

        return boto3.client(
            "sesv2",
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

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
        import asyncio

        sender = from_email or self._from_email
        sender_name = from_name or self._from_name
        from_addr = f"{sender_name} <{sender}>" if sender_name else sender

        destination: dict[str, Any] = {"ToAddresses": [to_email]}
        content: dict[str, Any] = {
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_content, "Charset": "UTF-8"}},
            }
        }

        kwargs: dict[str, Any] = {
            "FromEmailAddress": from_addr,
            "Destination": destination,
            "Content": content,
        }

        if reply_to:
            kwargs["ReplyToAddresses"] = [reply_to]
        if self._configuration_set:
            kwargs["ConfigurationSetName"] = self._configuration_set
        if tags:
            kwargs["EmailTags"] = [
                {"Name": "campaign", "Value": tags[0]} if tags else {}
            ]

        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()
            response = await loop.run_in_executor(
                None, lambda: client.send_email(**kwargs)
            )
            message_id = response.get("MessageId", "")
            logger.info("SES: sent email to %s, MessageId=%s", to_email, message_id)
            return SendResult(
                success=True,
                provider_message_id=message_id,
                provider="ses",
            )
        except Exception as e:
            logger.exception("SES: send_email exception for %s", to_email)
            return SendResult(
                success=False,
                provider="ses",
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
        # SES v2 supports BulkEmail, but per-recipient template data requires
        # SES templates. For simplicity, send individually like Brevo adapter.
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
        """Add emails to SES account-level suppression list."""
        import asyncio

        if not suppressed_emails:
            return SyncResult(synced_count=0)

        errors: list[str] = []
        synced = 0

        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()

            for email in suppressed_emails:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda e=email: client.put_suppressed_destination(
                            EmailAddress=e, Reason="COMPLAINT"
                        ),
                    )
                    synced += 1
                except Exception as e:
                    errors.append(f"{email}: {e}")

            logger.info("SES: synced %d suppressed emails", synced)
        except Exception as e:
            errors.append(str(e))
            logger.exception("SES: suppression sync exception")

        return SyncResult(synced_count=synced, errors=errors)

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """Parse AWS SNS notification for SES events.

        SES webhooks arrive via SNS. The signature is verified using the SNS
        certificate (X.509). For simplicity, we parse the event type from the
        SNS message body. In production, consider verifying the SNS signature
        using the certificate URL in the message.
        """
        data = json.loads(payload)

        # SNS wraps the SES event in a "Message" field
        message = data
        if "Message" in data:
            message = json.loads(data["Message"])

        # SES event types: Delivery, Bounce, Complaint, Open, Click
        event_type_map = {
            "Delivery": "delivered",
            "Bounce": "bounced",
            "Complaint": "complained",
            "Open": "opened",
            "Click": "clicked",
        }

        ses_event_type = message.get("eventType", message.get("notificationType", ""))
        event_type = event_type_map.get(ses_event_type, ses_event_type.lower())

        # Extract recipient from the mail object
        mail = message.get("mail", {})
        recipient = ""
        if "destination" in mail and mail["destination"]:
            recipient = mail["destination"][0]

        return WebhookEvent(
            event_type=event_type,
            event_id=mail.get("messageId"),
            provider_message_id=mail.get("messageId"),
            recipient_email=recipient,
            timestamp=mail.get("timestamp"),
            raw_data=message,
        )
