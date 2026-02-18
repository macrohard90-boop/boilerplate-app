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

    # 3. Store addresses on the order
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

    # 4. Create Stripe PaymentIntent
    provider = get_payment_provider()
    try:
        result = await provider.create_payment(
            order_id=order_id,
            amount=order["total"],
            currency=order.get("currency", settings.default_currency),
            customer_id=user_id,
            metadata={"order_number": order["order_number"]},
        )
    except Exception as e:
        # Payment creation failed — release inventory and mark order rejected
        logger.error("Payment intent creation failed for order %s: %s", order_id, e)
        await _release_order_inventory(db, order_id)
        await order_service.update_order_status(db, order_id, "rejected")
        raise ValueError(f"Payment creation failed: {e}") from e

    # 5. Insert payment record
    await payment_service.create_payment_record(
        db,
        order_id=order_id,
        provider="stripe",
        provider_payment_id=result.provider_payment_id,
        amount=order["total"],
        currency=order.get("currency", "USD"),
        status="pending",
    )

    # 6. Update order status to processing
    await order_service.update_order_status(db, order_id, "processing")

    # 7. Return checkout response
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

    discount = await discount_service.validate_discount(db, discount_code, 0)
    if not discount:
        raise ValueError("Invalid or expired discount code")

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
