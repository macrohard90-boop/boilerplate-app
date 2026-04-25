"""SMS and WhatsApp provider adapter factory.

Returns the configured provider instance based on SMS_PROVIDER / WHATSAPP_PROVIDER env vars.
"""

from modules.notifications.interfaces.sms_provider import SmsProvider
from modules.notifications.interfaces.whatsapp_provider import WhatsAppProvider


def get_sms_provider() -> SmsProvider:
    """Return the configured SMS provider."""
    from backend.core.config import settings

    provider_name = settings.sms_provider

    if provider_name == "console":
        from modules.notifications.adapters.console_sms_adapter import (
            ConsoleSmsAdapter,
        )

        return ConsoleSmsAdapter()
    elif provider_name == "brevo":
        from modules.notifications.adapters.brevo_sms_adapter import BrevoSmsAdapter

        return BrevoSmsAdapter()
    elif provider_name == "twilio":
        from modules.notifications.adapters.twilio_sms_adapter import TwilioSmsAdapter

        return TwilioSmsAdapter()

    raise ValueError(f"Unknown SMS provider: {provider_name}")


def get_whatsapp_provider() -> WhatsAppProvider:
    """Return the configured WhatsApp provider."""
    from backend.core.config import settings

    provider_name = settings.whatsapp_provider

    if provider_name == "console":
        from modules.notifications.adapters.console_whatsapp_adapter import (
            ConsoleWhatsAppAdapter,
        )

        return ConsoleWhatsAppAdapter()
    elif provider_name == "brevo":
        from modules.notifications.adapters.brevo_whatsapp_adapter import (
            BrevoWhatsAppAdapter,
        )

        return BrevoWhatsAppAdapter()
    elif provider_name == "twilio":
        from modules.notifications.adapters.twilio_whatsapp_adapter import (
            TwilioWhatsAppAdapter,
        )

        return TwilioWhatsAppAdapter()

    raise ValueError(f"Unknown WhatsApp provider: {provider_name}")
