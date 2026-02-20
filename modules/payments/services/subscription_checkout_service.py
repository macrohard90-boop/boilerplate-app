"""Checkout flow for carts containing subscription (recurring) items.

Uses Stripe Checkout Sessions in ``mode=subscription`` which supports
both recurring and one-time line items in a single session.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.payments.adapters import get_payment_provider

logger = logging.getLogger(__name__)


async def create_subscription_checkout_session(
    db: AsyncSession,
    user_id: str,
    email: str,
    *,
    discount_code: str | None = None,
) -> dict[str, Any]:
    """Build a Stripe Checkout Session for a cart with subscription items.

    1. Fetch cart items with product + variant details (including stripe_price_id)
    2. Get or create a Stripe customer
    3. Build line_items array from stripe_price_id for each item
    4. Create Stripe Checkout Session in mode=subscription
    5. Return session URL for redirect
    """
    # 1. Get cart + items
    cart_row = (
        await db.execute(
            text(
                "SELECT id, discount_code_id FROM ecommerce.cart "
                "WHERE user_id = :uid AND status = 'active'"
            ),
            {"uid": user_id},
        )
    ).mappings().first()

    if not cart_row:
        raise ValueError("No active cart found")

    items = (
        await db.execute(
            text(
                "SELECT ci.product_id, ci.variant_id, ci.quantity, "
                "p.pricing_type, p.stripe_price_id AS product_price_id, "
                "v.stripe_price_id AS variant_price_id, "
                "p.name AS product_name "
                "FROM ecommerce.cart_items ci "
                "JOIN ecommerce.products p ON p.id = ci.product_id "
                "JOIN ecommerce.product_variants v ON v.id = ci.variant_id "
                "WHERE ci.cart_id = :cid"
            ),
            {"cid": str(cart_row["id"])},
        )
    ).mappings().all()

    if not items:
        raise ValueError("Cart is empty")

    # 2. Get or create Stripe customer
    from modules.ecommerce.services.subscription_service import (
        get_or_create_stripe_customer,
    )

    stripe_customer_id = await get_or_create_stripe_customer(db, user_id, email)

    # 3. Apply discount code if provided
    stripe_coupon_id = None
    if discount_code:
        from modules.ecommerce.services import discount_service

        discount = await discount_service.validate_discount(db, discount_code, 0)
        if discount and discount.get("stripe_coupon_id"):
            stripe_coupon_id = discount["stripe_coupon_id"]

    # 4. Build line_items — use variant stripe_price_id if available, else product
    line_items: list[dict[str, Any]] = []
    for item in items:
        price_id = item["variant_price_id"] or item["product_price_id"]
        if not price_id:
            raise ValueError(
                f"Product '{item['product_name']}' is not synced to Stripe. "
                "Please sync the product catalog first."
            )
        line_items.append({"price": price_id, "quantity": item["quantity"]})

    # 5. Create Checkout Session
    provider = get_payment_provider()
    success_url = f"{settings.frontend_url}/dashboard/orders?checkout=success"
    cancel_url = f"{settings.frontend_url}/checkout?canceled=1"

    session_params: dict[str, Any] = {
        "line_items": line_items,
        "mode": "subscription",
        "customer_id": stripe_customer_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": user_id},
    }

    # Apply discount coupon to checkout session
    if stripe_coupon_id:
        session_params["discounts"] = [{"coupon": stripe_coupon_id}]

    result = await provider.create_checkout_session(**session_params)

    return {
        "session_url": result["url"],
        "session_id": result["session_id"],
    }
