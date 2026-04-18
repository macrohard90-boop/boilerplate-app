"""Email provider adapter factory.

Returns the configured email provider instance based on EMAIL_PROVIDER env var.
Supports split providers: TRANSACTIONAL_EMAIL_PROVIDER overrides for transactional,
MARKETING_EMAIL_PROVIDER overrides for marketing.
"""

from modules.gdpr.interfaces.email_provider import EmailProvider


def get_email_provider(
    email_type: str = "transactional_email",
) -> EmailProvider:
    """Return the configured email provider for the given email type.

    Args:
        email_type: "transactional_email" or "marketing_email". Used to select
            the correct provider when split providers are configured.
    """
    from backend.core.config import settings

    if email_type == "marketing_email" and settings.marketing_email_provider:
        provider_name = settings.marketing_email_provider
    elif (
        email_type == "transactional_email"
        and settings.transactional_email_provider
    ):
        provider_name = settings.transactional_email_provider
    else:
        provider_name = settings.email_provider

    if provider_name == "console":
        from modules.gdpr.adapters.console_adapter import ConsoleAdapter

        return ConsoleAdapter()
    elif provider_name == "brevo":
        from modules.gdpr.adapters.brevo_adapter import BrevoAdapter

        return BrevoAdapter()

    raise ValueError(f"Unknown email provider: {provider_name}")
