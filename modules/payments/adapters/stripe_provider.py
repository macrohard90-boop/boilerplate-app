"""Stripe implementation of PaymentProvider.

Uses Stripe Payment Intents API for payments and Stripe Connect Express
for merchant onboarding. All amounts are INT cents.
"""

import logging
from typing import Any

import stripe

from backend.core.config import settings
from modules.payments.interfaces.catalog_provider import (
    CatalogPrice,
    CatalogProduct,
    CatalogProvider,
)
from modules.payments.interfaces.payment_provider import (
    MerchantAccount,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    RefundResult,
    Transaction,
)

logger = logging.getLogger(__name__)

# Map Stripe statuses to our internal statuses
_STRIPE_STATUS_MAP = {
    "requires_payment_method": "pending",
    "requires_confirmation": "pending",
    "requires_action": "pending",
    "processing": "processing",
    "requires_capture": "processing",
    "canceled": "failed",
    "succeeded": "succeeded",
}


class StripeProvider(PaymentProvider, CatalogProvider):
    """Stripe payment provider using Payment Intents API."""

    def __init__(self) -> None:
        stripe.api_key = settings.stripe_secret_key
        self._platform_fee_percent = settings.platform_fee_percent

    async def create_payment(
        self,
        order_id: str,
        amount: int,
        currency: str,
        customer_id: str,
        *,
        merchant_account_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PaymentResult:
        intent_params: dict[str, Any] = {
            "amount": amount,
            "currency": currency.lower(),
            "metadata": {
                "order_id": order_id,
                "customer_id": customer_id,
                **(metadata or {}),
            },
            "automatic_payment_methods": {"enabled": True},
        }

        # If merchant account, use Connect with platform fee
        if merchant_account_id:
            fee = int(amount * self._platform_fee_percent / 100)
            intent_params["application_fee_amount"] = fee
            intent_params["stripe_account"] = merchant_account_id

        pi = stripe.PaymentIntent.create(**intent_params)

        return PaymentResult(
            provider_payment_id=pi.id,
            client_secret=pi.client_secret,
            status=_STRIPE_STATUS_MAP.get(pi.status, "pending"),
            amount=amount,
            currency=currency,
            metadata=pi.metadata or {},
        )

    async def refund(
        self,
        payment_id: str,
        amount: int | None = None,
        *,
        reason: str | None = None,
    ) -> RefundResult:
        params: dict[str, Any] = {"payment_intent": payment_id}
        if amount is not None:
            params["amount"] = amount
        if reason:
            params["reason"] = reason

        refund = stripe.Refund.create(**params)

        return RefundResult(
            provider_refund_id=refund.id,
            status="refunded" if refund.status == "succeeded" else refund.status,
            amount=refund.amount,
            currency=refund.currency.upper(),
        )

    async def get_status(self, payment_id: str) -> PaymentStatus:
        pi = stripe.PaymentIntent.retrieve(payment_id)

        return PaymentStatus(
            provider_payment_id=pi.id,
            status=_STRIPE_STATUS_MAP.get(pi.status, "unknown"),
            amount=pi.amount,
            currency=pi.currency.upper(),
            client_secret=pi.client_secret,
            metadata=pi.metadata or {},
        )

    async def create_merchant(
        self, merchant_data: dict[str, Any]
    ) -> MerchantAccount:
        account = stripe.Account.create(
            type="express",
            country=merchant_data.get("country", "US"),
            email=merchant_data.get("email"),
            business_type=merchant_data.get("business_type", "individual"),
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        )

        # Generate onboarding link
        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=merchant_data.get(
                "refresh_url", f"{settings.frontend_url}/merchant/onboard"
            ),
            return_url=merchant_data.get(
                "return_url", f"{settings.frontend_url}/merchant/dashboard"
            ),
            type="account_onboarding",
        )

        return MerchantAccount(
            provider_account_id=account.id,
            onboarding_url=link.url,
            status="onboarding",
            charges_enabled=account.charges_enabled or False,
            payouts_enabled=account.payouts_enabled or False,
        )

    async def cancel_payment(self, payment_id: str) -> None:
        stripe.PaymentIntent.cancel(payment_id)

    async def verify_webhook(
        self, payload: bytes, signature: str
    ) -> dict[str, Any]:
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )
        except stripe.SignatureVerificationError as e:
            raise ValueError("Invalid signature") from e
        except Exception as e:
            raise ValueError("Webhook verification failed") from e

        return {
            "id": event["id"],
            "type": event["type"],
            "data": event["data"]["object"],
        }

    async def create_account_link(
        self,
        account_id: str,
        *,
        refresh_url: str,
        return_url: str,
    ) -> str:
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return link.url

    async def create_login_link(self, account_id: str) -> str:
        link = stripe.Account.create_login_link(account_id)
        return link.url

    async def list_transactions(
        self, filters: dict[str, Any] | None = None
    ) -> list[Transaction]:
        params: dict[str, Any] = {"limit": 100}
        if filters:
            if filters.get("created_after"):
                params["created"] = {"gte": int(filters["created_after"])}
            if filters.get("limit"):
                params["limit"] = min(filters["limit"], 100)

        intents = stripe.PaymentIntent.list(**params)

        return [
            Transaction(
                provider_payment_id=pi.id,
                amount=pi.amount,
                currency=pi.currency.upper(),
                status=_STRIPE_STATUS_MAP.get(pi.status, "unknown"),
                created_at=str(pi.created),
                metadata=pi.metadata or {},
            )
            for pi in intents.data
        ]


    # -----------------------------------------------------------------------
    # CatalogProvider methods
    # -----------------------------------------------------------------------

    async def create_product(
        self,
        name: str,
        description: str | None = None,
        *,
        images: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogProduct:
        params: dict[str, Any] = {
            "name": name,
            "description": description or "",
            "metadata": metadata or {},
        }
        if images:
            params["images"] = images[:8]  # Stripe allows max 8 images
        product = stripe.Product.create(**params)
        return CatalogProduct(
            provider_product_id=product.id,
            name=product.name,
            active=product.active,
            metadata=product.metadata or {},
        )

    async def update_product(
        self,
        provider_product_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        images: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogProduct:
        params: dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        if description is not None:
            params["description"] = description
        if active is not None:
            params["active"] = active
        if images is not None:
            params["images"] = images[:8]
        if metadata is not None:
            params["metadata"] = metadata
        product = stripe.Product.modify(provider_product_id, **params)
        return CatalogProduct(
            provider_product_id=product.id,
            name=product.name,
            active=product.active,
            metadata=product.metadata or {},
        )

    async def archive_product(self, provider_product_id: str) -> None:
        stripe.Product.modify(provider_product_id, active=False)

    async def create_price(
        self,
        provider_product_id: str,
        unit_amount: int,
        currency: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogPrice:
        price = stripe.Price.create(
            product=provider_product_id,
            unit_amount=unit_amount,
            currency=currency.lower(),
            metadata=metadata or {},
        )
        return CatalogPrice(
            provider_price_id=price.id,
            provider_product_id=provider_product_id,
            unit_amount=price.unit_amount,
            currency=price.currency.upper(),
            active=price.active,
        )

    async def archive_price(self, provider_price_id: str) -> None:
        stripe.Price.modify(provider_price_id, active=False)


def get_stripe_provider() -> StripeProvider:
    """Factory function for the Stripe provider."""
    return StripeProvider()
