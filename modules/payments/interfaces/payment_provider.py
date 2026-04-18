"""PaymentProvider abstract base class and response models.

Any payment gateway (Stripe, PayPal, etc.) implements this interface.
Swap by implementing the ABC and setting PAYMENT_PROVIDER in .env.

To add a new provider:
1. Create ``modules/payments/adapters/your_provider.py``
2. Implement all abstract methods of ``PaymentProvider``
3. Add a branch in ``modules/payments/adapters/__init__.py``
4. Set ``PAYMENT_PROVIDER=your_provider`` in ``.env``
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaymentResult:
    """Returned by create_payment."""

    provider_payment_id: str
    client_secret: str | None = None
    status: str = "pending"
    amount: int = 0
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    """Returned by refund."""

    provider_refund_id: str
    status: str = "pending"
    amount: int = 0
    currency: str = "USD"


@dataclass
class PaymentStatus:
    """Returned by get_status."""

    provider_payment_id: str
    status: str = "unknown"
    amount: int = 0
    currency: str = "USD"
    client_secret: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MerchantAccount:
    """Returned by create_merchant."""

    provider_account_id: str
    onboarding_url: str | None = None
    status: str = "pending"
    charges_enabled: bool = False
    payouts_enabled: bool = False


@dataclass
class Transaction:
    """Returned by list_transactions."""

    provider_payment_id: str
    amount: int = 0
    currency: str = "USD"
    status: str = "unknown"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomerResult:
    """Returned by create_customer."""

    provider_customer_id: str
    email: str | None = None


@dataclass
class SubscriptionResult:
    """Returned by create_subscription."""

    provider_subscription_id: str
    client_secret: str | None = None
    status: str = "pending"
    current_period_start: str | None = None
    current_period_end: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """Abstract payment provider interface.

    Implementations must handle all monetary values as INT cents.
    """

    @abstractmethod
    async def create_payment(
        self,
        order_id: str,
        amount: int,
        currency: str,
        customer_id: str,
        *,
        merchant_account_id: str | None = None,
        fee_amount: int | None = None,
        metadata: dict[str, Any] | None = None,
        payment_method_types: list[str] | None = None,
        description: str | None = None,
        line_items: list[dict[str, Any]] | None = None,
    ) -> PaymentResult:
        """Create a payment intent/charge for an order.

        customer_id should be the provider's customer ID (e.g. Stripe cus_xxx).
        If line_items is provided (list of {"price": "price_xxx", "quantity": N}),
        the provider should create an itemized invoice/receipt where supported.
        If payment_method_types is provided, only those methods are accepted.
        If None, the provider decides which methods to offer (automatic).
        """
        ...

    @abstractmethod
    async def refund(
        self,
        payment_id: str,
        amount: int | None = None,
        *,
        reason: str | None = None,
    ) -> RefundResult:
        """Refund a payment. If amount is None, refund the full amount."""
        ...

    @abstractmethod
    async def get_status(self, payment_id: str) -> PaymentStatus:
        """Get the current status of a payment."""
        ...

    @abstractmethod
    async def create_merchant(
        self, merchant_data: dict[str, Any]
    ) -> MerchantAccount:
        """Create a merchant/connected account for payouts."""
        ...

    @abstractmethod
    async def cancel_payment(self, payment_id: str) -> None:
        """Cancel/void a pending payment."""
        ...

    @abstractmethod
    async def verify_webhook(
        self, payload: bytes, signature: str
    ) -> dict[str, Any]:
        """Verify webhook signature and return parsed event.

        Returns dict with keys: ``id`` (event ID), ``type`` (event type),
        ``data`` (provider-specific event payload, already unwrapped).
        Raises ``ValueError`` on invalid signature.
        """
        ...

    @abstractmethod
    async def create_account_link(
        self,
        account_id: str,
        *,
        refresh_url: str,
        return_url: str,
    ) -> str:
        """Generate an onboarding/update link for an existing merchant account.

        Returns the onboarding URL string.
        """
        ...

    @abstractmethod
    async def create_login_link(self, account_id: str) -> str:
        """Generate a dashboard login link for a merchant account.

        Returns the login URL string.
        """
        ...

    @abstractmethod
    async def list_transactions(
        self, filters: dict[str, Any] | None = None
    ) -> list[Transaction]:
        """List transactions matching filters."""
        ...

    # ------------------------------------------------------------------
    # Customer & Subscription (optional — providers that support recurring)
    # ------------------------------------------------------------------

    async def create_customer(
        self, email: str, *, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> CustomerResult:
        """Create a customer record in the provider."""
        raise NotImplementedError

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        *,
        coupon_id: str | None = None,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionResult:
        """Create a subscription for a customer."""
        raise NotImplementedError

    async def cancel_subscription(
        self, subscription_id: str, *, at_period_end: bool = True
    ) -> None:
        """Cancel a subscription."""
        raise NotImplementedError

    async def get_subscription(self, subscription_id: str) -> SubscriptionResult:
        """Get current status of a subscription."""
        raise NotImplementedError

    async def create_checkout_session(
        self,
        line_items: list[dict[str, Any]],
        *,
        mode: str = "subscription",
        customer_id: str | None = None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
        discounts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Create a hosted checkout session (e.g. Stripe Checkout).

        Returns dict with ``session_id`` and ``url``.
        """
        raise NotImplementedError
