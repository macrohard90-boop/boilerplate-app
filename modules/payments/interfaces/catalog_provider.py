"""CatalogProvider abstract base class for product/price catalog management.

Payment providers that support product catalogs (Stripe, etc.) implement this.
Providers that don't (PayPal) simply don't implement it, and the sync service
skips catalog operations when ``get_catalog_provider()`` returns ``None``.

To add catalog support to a new provider:
1. Implement all abstract methods of ``CatalogProvider``
2. Have the provider class inherit from both ``PaymentProvider`` and ``CatalogProvider``
3. The factory in ``modules/payments/adapters/__init__.py`` will automatically
   detect the ``CatalogProvider`` interface and return the provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CatalogProduct:
    """Returned by create_product / update_product."""

    provider_product_id: str
    name: str
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CatalogPrice:
    """Returned by create_price."""

    provider_price_id: str
    provider_product_id: str
    unit_amount: int
    currency: str
    active: bool = True


class CatalogProvider(ABC):
    """Abstract catalog provider interface.

    All monetary values are INT cents.
    """

    @abstractmethod
    async def create_product(
        self,
        name: str,
        description: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogProduct:
        """Create a product in the provider's catalog."""
        ...

    @abstractmethod
    async def update_product(
        self,
        provider_product_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogProduct:
        """Update a product in the provider's catalog."""
        ...

    @abstractmethod
    async def archive_product(self, provider_product_id: str) -> None:
        """Archive/deactivate a product in the provider's catalog."""
        ...

    @abstractmethod
    async def create_price(
        self,
        provider_product_id: str,
        unit_amount: int,
        currency: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogPrice:
        """Create a price for a product. Prices are immutable in most providers."""
        ...

    @abstractmethod
    async def archive_price(self, provider_price_id: str) -> None:
        """Archive/deactivate a price."""
        ...
