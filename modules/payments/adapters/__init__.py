"""Payment and catalog provider factories.

Reads ``settings.payment_provider`` and returns the matching adapter.
To add a new provider, implement ``PaymentProvider`` (and optionally
``CatalogProvider``) and add a branch here.
"""

from modules.payments.interfaces.catalog_provider import CatalogProvider
from modules.payments.interfaces.payment_provider import PaymentProvider


def get_payment_provider() -> PaymentProvider:
    """Return the configured payment provider instance."""
    from backend.core.config import settings

    provider = settings.payment_provider
    if provider == "stripe":
        from modules.payments.adapters.stripe_provider import StripeProvider

        return StripeProvider()

    raise ValueError(f"Unknown payment provider: {provider}")


def get_catalog_provider() -> CatalogProvider | None:
    """Return the configured catalog provider, or None if unsupported.

    Not all payment providers support product catalogs. When this returns
    None, catalog sync operations are skipped (products remain local-only).
    """
    from backend.core.config import settings

    provider = settings.payment_provider
    if provider == "stripe":
        from modules.payments.adapters.stripe_provider import StripeProvider

        return StripeProvider()

    return None
