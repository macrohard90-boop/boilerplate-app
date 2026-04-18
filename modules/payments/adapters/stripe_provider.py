"""Stripe implementation of PaymentProvider.

Uses Stripe Payment Intents API for payments and Stripe Connect Express
for merchant onboarding. All amounts are INT cents.
"""

import json
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
    CustomerResult,
    MerchantAccount,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    RefundResult,
    SubscriptionResult,
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
        fee_amount: int | None = None,
        metadata: dict[str, Any] | None = None,
        payment_method_types: list[str] | None = None,
        description: str | None = None,
        line_items: list[dict[str, Any]] | None = None,
    ) -> PaymentResult:
        merged_metadata = {"order_id": order_id, **(metadata or {})}

        # When line items with Stripe price IDs are provided, use Invoice flow
        # so Stripe has full product-level detail on the customer's record.
        if line_items and customer_id:
            return await self._create_invoice_payment(
                customer_id=customer_id,
                line_items=line_items,
                currency=currency,
                metadata=merged_metadata,
                description=description,
                payment_method_types=payment_method_types,
            )

        # Fallback: bare PaymentIntent (no product detail in Stripe)
        intent_params: dict[str, Any] = {
            "amount": amount,
            "currency": currency.lower(),
            "customer": customer_id,
            "metadata": merged_metadata,
        }

        if description:
            intent_params["description"] = description

        # Explicit method list vs automatic
        if payment_method_types:
            intent_params["payment_method_types"] = payment_method_types
        else:
            intent_params["automatic_payment_methods"] = {"enabled": True}

        # If merchant account, use Connect with platform fee
        if merchant_account_id:
            fee = fee_amount if fee_amount is not None else int(amount * self._platform_fee_percent / 100)
            if fee > 0:
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

    async def _create_invoice_payment(
        self,
        customer_id: str,
        line_items: list[dict[str, Any]],
        currency: str,
        metadata: dict[str, Any],
        description: str | None = None,
        payment_method_types: list[str] | None = None,
    ) -> PaymentResult:
        """Create an Invoice with line items, finalize it, and return the
        auto-generated PaymentIntent's client_secret for embedded payment."""

        # 1. Create invoice items (attached to the customer's upcoming invoice)
        for item in line_items:
            params: dict[str, Any] = {
                "customer": customer_id,
                "price": item["price"],
                "quantity": item.get("quantity", 1),
                "currency": currency.lower(),
            }
            stripe.InvoiceItem.create(**params)

        # 2. Create the invoice
        invoice_params: dict[str, Any] = {
            "customer": customer_id,
            "currency": currency.lower(),
            "metadata": metadata,
            "auto_advance": False,  # Don't auto-send; we control the flow
        }
        if description:
            invoice_params["description"] = description

        # Configure payment methods on the invoice
        payment_settings: dict[str, Any] = {}
        if payment_method_types:
            payment_settings["payment_method_types"] = payment_method_types
        invoice_params["payment_settings"] = payment_settings

        invoice = stripe.Invoice.create(**invoice_params)

        # 3. Finalize the invoice — this creates the PaymentIntent
        invoice = stripe.Invoice.finalize_invoice(invoice.id)

        # 4. Copy our metadata onto the PaymentIntent so webhook handlers
        #    can read order_id/user_id (PI doesn't inherit invoice metadata)
        pi = stripe.PaymentIntent.modify(
            invoice.payment_intent,
            metadata=metadata,
        )

        return PaymentResult(
            provider_payment_id=pi.id,
            client_secret=pi.client_secret,
            status=_STRIPE_STATUS_MAP.get(pi.status, "pending"),
            amount=pi.amount,
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

        # Convert StripeObject to plain dict so handlers can use .get()
        # str() on StripeObject returns its JSON representation
        data_obj = event["data"]["object"]
        data_dict = json.loads(str(data_obj))
        return {
            "id": event["id"],
            "type": event["type"],
            "data": data_dict,
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
    # Customer & Subscription methods
    # -----------------------------------------------------------------------

    async def create_customer(
        self, email: str, *, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> CustomerResult:
        params: dict[str, Any] = {"email": email, "metadata": metadata or {}}
        if name:
            params["name"] = name
        customer = stripe.Customer.create(**params)
        return CustomerResult(provider_customer_id=customer.id, email=email)

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        *,
        coupon_id: str | None = None,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionResult:
        params: dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "payment_settings": {"save_default_payment_method": "on_subscription"},
            "expand": ["latest_invoice.confirmation_secret"],
            "metadata": metadata or {},
        }
        if coupon_id:
            params["discounts"] = [{"coupon": coupon_id}]
        if trial_period_days:
            params["trial_period_days"] = trial_period_days

        sub = stripe.Subscription.create(**params)

        client_secret = None
        if sub.latest_invoice:
            cs = getattr(sub.latest_invoice, "confirmation_secret", None)
            if cs:
                client_secret = cs.client_secret

        # Period info moved to subscription items in Stripe API 2025-03-31+
        period_start = ""
        period_end = ""
        try:
            sub_items = sub["items"]["data"]
            if sub_items:
                period_start = str(sub_items[0].get("current_period_start", ""))
                period_end = str(sub_items[0].get("current_period_end", ""))
        except (KeyError, TypeError, IndexError):
            pass

        return SubscriptionResult(
            provider_subscription_id=sub.id,
            client_secret=client_secret,
            status=sub.status,
            current_period_start=period_start,
            current_period_end=period_end,
        )

    async def cancel_subscription(
        self, subscription_id: str, *, at_period_end: bool = True
    ) -> None:
        if at_period_end:
            stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        else:
            stripe.Subscription.cancel(subscription_id)

    async def get_subscription(self, subscription_id: str) -> SubscriptionResult:
        sub = stripe.Subscription.retrieve(subscription_id)
        period_start = ""
        period_end = ""
        try:
            sub_items = sub["items"]["data"]
            if sub_items:
                period_start = str(sub_items[0].get("current_period_start", ""))
                period_end = str(sub_items[0].get("current_period_end", ""))
        except (KeyError, TypeError, IndexError):
            pass
        return SubscriptionResult(
            provider_subscription_id=sub.id,
            status=sub.status,
            current_period_start=period_start,
            current_period_end=period_end,
        )

    # -----------------------------------------------------------------------
    # Coupon methods (for subscription discounts)
    # -----------------------------------------------------------------------

    async def create_coupon(
        self,
        *,
        coupon_type: str,
        value: int,
        currency: str = "USD",
        duration: str = "once",
        duration_in_months: int | None = None,
        max_redemptions: int | None = None,
        metadata: dict[str, Any] | None = None,
        applies_to_products: list[str] | None = None,
    ) -> dict[str, str]:
        """Create a Stripe Coupon. Returns dict with stripe_coupon_id."""
        params: dict[str, Any] = {"duration": duration, "metadata": metadata or {}}
        if coupon_type == "percentage":
            params["percent_off"] = value
        elif coupon_type == "fixed":
            params["amount_off"] = value
            params["currency"] = currency.lower()
        if duration == "repeating" and duration_in_months:
            params["duration_in_months"] = duration_in_months
        if max_redemptions:
            params["max_redemptions"] = max_redemptions
        if applies_to_products:
            params["applies_to"] = {"products": applies_to_products}
        coupon = stripe.Coupon.create(**params)
        return {"stripe_coupon_id": coupon.id}

    async def create_promotion_code(
        self,
        coupon_id: str,
        code: str,
        *,
        customer: str | None = None,
        first_time_transaction: bool = False,
    ) -> dict[str, str]:
        """Create a Stripe Promotion Code linked to a coupon."""
        params: dict[str, Any] = {
            "promotion": {"type": "coupon", "coupon": coupon_id},
            "code": code,
        }
        if customer:
            params["customer"] = customer
        restrictions: dict[str, Any] = {}
        if first_time_transaction:
            restrictions["first_time_transaction"] = True
        if restrictions:
            params["restrictions"] = restrictions
        promo = stripe.PromotionCode.create(**params)
        return {"stripe_promotion_code_id": promo.id}

    async def delete_coupon(self, coupon_id: str) -> None:
        """Delete a Stripe Coupon."""
        try:
            stripe.Coupon.delete(coupon_id)
        except Exception as e:
            logger.warning("Failed to delete Stripe coupon %s: %s", coupon_id, e)

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
            "metadata": metadata or {},
        }
        if description:
            params["description"] = description
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
        if description:
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
        nickname: str | None = None,
        recurring_interval: str | None = None,
        recurring_interval_count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> CatalogPrice:
        params: dict[str, Any] = {
            "product": provider_product_id,
            "unit_amount": unit_amount,
            "currency": currency.lower(),
            "metadata": metadata or {},
        }
        if nickname:
            params["nickname"] = nickname
        if recurring_interval:
            params["recurring"] = {
                "interval": recurring_interval,
                "interval_count": recurring_interval_count,
            }
        price = stripe.Price.create(**params)
        return CatalogPrice(
            provider_price_id=price.id,
            provider_product_id=provider_product_id,
            unit_amount=price.unit_amount,
            currency=price.currency.upper(),
            active=price.active,
        )

    async def archive_price(self, provider_price_id: str) -> None:
        stripe.Price.modify(provider_price_id, active=False)

    # -----------------------------------------------------------------------
    # Checkout Session (for subscriptions and mixed carts)
    # -----------------------------------------------------------------------

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
        params: dict[str, Any] = {
            "line_items": line_items,
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
        }
        if customer_id:
            params["customer"] = customer_id
        if discounts:
            params["discounts"] = discounts
        session = stripe.checkout.Session.create(**params)
        return {"session_id": session.id, "url": session.url}


def get_stripe_provider() -> StripeProvider:
    """Factory function for the Stripe provider."""
    return StripeProvider()
