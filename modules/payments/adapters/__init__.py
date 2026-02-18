"""Payment provider factory.

Reads ``settings.payment_provider`` and returns the matching adapter.
To add a new provider, implement ``PaymentProvider`` and add a branch here.
"""

from modules.payments.interfaces.payment_provider import PaymentProvider


def get_payment_provider() -> PaymentProvider:
    """Return the configured payment provider instance."""
    from backend.core.config import settings

    provider = settings.payment_provider
    if provider == "stripe":
        from modules.payments.adapters.stripe_provider import StripeProvider

        return StripeProvider()

    raise ValueError(f"Unknown payment provider: {provider}")
