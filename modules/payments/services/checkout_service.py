"""Checkout orchestration: cart → order → payment intent."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.ecommerce.services import order_service
from modules.payments.adapters import get_payment_provider
from modules.payments.services import payment_service

logger = logging.getLogger(__name__)


async def checkout(
    db: AsyncSession,
    user_id: str,
    shipping_address: dict[str, Any],
    billing_address: dict[str, Any] | None = None,
    discount_code: str | None = None,
) -> dict[str, Any]:
    """Full checkout flow: create order from cart, then create payment intent.

    1. Apply discount code to cart if provided
    2. Convert cart to order (stock reservation, pricing, snapshots)
    3. Store addresses on the order
    4. Create Stripe PaymentIntent
    5. Insert payment_records row
    6. Update order status to 'processing'
    7. Return order + client_secret
    """
    # 1. Apply discount code if provided
    if discount_code:
        await _apply_discount_to_cart(db, user_id, discount_code)

    # 2. Convert cart to order (handles stock reservation, pricing, snapshots)
    order = await order_service.create_order_from_cart(db, user_id)
    order_id = str(order["id"])

    # 3. Store addresses on the order (shipping optional for subscriptions)
    if shipping_address:
        if billing_address is None:
            billing_address = shipping_address

        await db.execute(
            text(
                "UPDATE ecommerce.orders "
                "SET shipping_address = CAST(:ship AS jsonb), "
                "billing_address = CAST(:bill AS jsonb) "
                "WHERE id = :oid"
            ),
            {
                "oid": order_id,
                "ship": json.dumps(shipping_address),
                "bill": json.dumps(billing_address),
            },
        )
        await db.commit()
    elif billing_address:
        await db.execute(
            text(
                "UPDATE ecommerce.orders "
                "SET billing_address = CAST(:bill AS jsonb) "
                "WHERE id = :oid"
            ),
            {
                "oid": order_id,
                "bill": json.dumps(billing_address),
            },
        )
        await db.commit()

    # 4. Handle zero-cost orders (e.g. 100% discount)
    if order["total"] <= 0:
        await order_service.update_order_status(db, order_id, "completed")
        return {
            "order_id": order_id,
            "order_number": order["order_number"],
            "client_secret": None,
            "subtotal": order["subtotal"],
            "discount_amount": order.get("discount_amount", 0),
            "tax_amount": order.get("tax_amount", 0),
            "total": 0,
            "currency": order.get("currency", "USD"),
        }

    # 5. Create Stripe PaymentIntent
    from modules.payments.services import payment_settings_service

    provider = get_payment_provider()
    enabled_methods = await payment_settings_service.get_enabled_payment_methods(db)
    try:
        result = await provider.create_payment(
            order_id=order_id,
            amount=order["total"],
            currency=order.get("currency", settings.default_currency),
            customer_id=user_id,
            metadata={"order_number": order["order_number"]},
            payment_method_types=enabled_methods,
        )
    except Exception as e:
        # Payment creation failed — release inventory and mark order rejected
        logger.error("Payment intent creation failed for order %s: %s", order_id, e)
        await _release_order_inventory(db, order_id)
        await order_service.update_order_status(db, order_id, "rejected")
        raise ValueError(f"Payment creation failed: {e}") from e

    # 6. Insert payment record
    await payment_service.create_payment_record(
        db,
        order_id=order_id,
        provider="stripe",
        provider_payment_id=result.provider_payment_id,
        amount=order["total"],
        currency=order.get("currency", "USD"),
        status="pending",
    )

    # 7. Update order status to processing
    await order_service.update_order_status(db, order_id, "processing")

    # 8. Return checkout response
    return {
        "order_id": order_id,
        "order_number": order["order_number"],
        "client_secret": result.client_secret,
        "subtotal": order["subtotal"],
        "discount_amount": order.get("discount_amount", 0),
        "tax_amount": order.get("tax_amount", 0),
        "total": order["total"],
        "currency": order.get("currency", "USD"),
    }


async def _apply_discount_to_cart(
    db: AsyncSession, user_id: str, discount_code: str
) -> None:
    """Apply a discount code to the user's active cart before checkout."""
    from modules.ecommerce.services import discount_service

    # Calculate actual cart subtotal for min_order_amount validation
    cart_subtotal_row = (
        await db.execute(
            text(
                "SELECT COALESCE(SUM("
                "  ci.quantity * COALESCE(v.price_override, p.base_price)"
                "), 0) AS subtotal "
                "FROM ecommerce.cart c "
                "JOIN ecommerce.cart_items ci ON ci.cart_id = c.id "
                "JOIN ecommerce.products p ON p.id = ci.product_id "
                "JOIN ecommerce.product_variants v ON v.id = ci.variant_id "
                "WHERE c.user_id = :uid AND c.status = 'active'"
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    cart_subtotal = int(cart_subtotal_row["subtotal"]) if cart_subtotal_row else 0

    # Get cart product IDs for restriction validation
    cart_pids_rows = (
        await db.execute(
            text(
                "SELECT DISTINCT ci.product_id FROM ecommerce.cart c "
                "JOIN ecommerce.cart_items ci ON ci.cart_id = c.id "
                "WHERE c.user_id = :uid AND c.status = 'active'"
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    cart_product_ids = [str(r["product_id"]) for r in cart_pids_rows]

    discount = await discount_service.validate_discount(
        db, discount_code, cart_subtotal,
        user_id=user_id, cart_product_ids=cart_product_ids,
    )
    if not discount:
        raise ValueError("Invalid or expired discount code")

    if discount.get("applies_to") == "recurring":
        raise ValueError("This coupon can only be used on recurring subscriptions")

    await db.execute(
        text(
            "UPDATE ecommerce.cart SET discount_code_id = :did "
            "WHERE user_id = :uid AND status = 'active'"
        ),
        {"did": str(discount["id"]), "uid": user_id},
    )
    await db.commit()


async def _release_order_inventory(db: AsyncSession, order_id: str) -> None:
    """Release reserved inventory for all items in an order."""
    from modules.ecommerce.services import inventory_service

    items = (
        await db.execute(
            text("SELECT variant_id, quantity FROM ecommerce.order_items WHERE order_id = :oid"),
            {"oid": order_id},
        )
    ).mappings().all()

    for item in items:
        await inventory_service.release_stock(
            db, str(item["variant_id"]), item["quantity"], reference_id=order_id
        )
    await db.commit()
