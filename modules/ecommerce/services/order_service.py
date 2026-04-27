"""Order management: checkout from cart, status management."""

import json
import math
import random
import string
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ecommerce.services import (
    discount_service,
    inventory_service,
    pricing_service,
)


async def create_order_from_cart(
    db: AsyncSession,
    user_id: str,
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Convert active cart into an order with stock reservation.

    1. Get user's active cart + items
    2. Lock variant rows (sorted to prevent deadlocks)
    3. Verify stock, deduct, create inventory records
    4. Apply discount + pricing tiers
    5. Build order + order_items with product snapshots
    6. Mark cart as converted, update customer metrics
    """
    # 1. Get active cart
    cart_row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM ecommerce.cart "
                    "WHERE user_id = :uid AND status = 'active' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    if not cart_row:
        raise ValueError("No active cart")

    cart = dict(cart_row)
    cart_id = str(cart["id"])

    items = (
        (
            await db.execute(
                text(
                    "SELECT ci.*, p.name AS product_name, p.slug AS product_slug, "
                    "p.base_price, p.currency, p.sku AS product_sku, p.type AS product_type, "
                    "v.name AS variant_name, v.sku AS variant_sku, v.price_override, v.attributes, "
                    "COALESCE("
                    "  (SELECT url FROM ecommerce.product_images"
                    "   WHERE variant_id = ci.variant_id"
                    "   ORDER BY is_primary DESC, sort_order LIMIT 1),"
                    "  (SELECT url FROM ecommerce.product_images"
                    "   WHERE product_id = ci.product_id AND variant_id IS NULL"
                    "   ORDER BY is_primary DESC, sort_order LIMIT 1)"
                    ") AS image_url "
                    "FROM ecommerce.cart_items ci "
                    "JOIN ecommerce.products p ON p.id = ci.product_id "
                    "JOIN ecommerce.product_variants v ON v.id = ci.variant_id "
                    "WHERE ci.cart_id = :cid "
                    "ORDER BY ci.variant_id"  # Sorted for consistent locking order
                ),
                {"cid": cart_id},
            )
        )
        .mappings()
        .all()
    )

    if not items:
        raise ValueError("Cart is empty")

    # 2 & 3. Lock and verify stock for each item
    for item in items:
        await inventory_service.reserve_stock(
            db,
            str(item["variant_id"]),
            item["quantity"],
        )

    # 4. Calculate totals with pricing tiers
    subtotal = 0
    order_items_data = []
    for item in items:
        effective_price = (
            item["price_override"]
            if item["price_override"] is not None
            else item["base_price"]
        )
        unit_price = await pricing_service.get_effective_unit_price(
            db,
            str(item["product_id"]),
            str(item["variant_id"]),
            item["quantity"],
            effective_price,
        )
        line_total = unit_price * item["quantity"]
        subtotal += line_total

        snapshot = {
            "product_name": item["product_name"],
            "product_slug": item["product_slug"],
            "product_sku": item.get("product_sku"),
            "variant_name": item["variant_name"],
            "variant_sku": item.get("variant_sku"),
            "attributes": (
                item["attributes"] if isinstance(item["attributes"], dict) else {}
            ),
            "product_type": item.get("product_type", "physical"),
            "image_url": item.get("image_url"),
        }

        order_items_data.append(
            {
                "product_id": str(item["product_id"]),
                "variant_id": str(item["variant_id"]),
                "quantity": item["quantity"],
                "unit_price": unit_price,
                "total_price": line_total,
                "product_snapshot": json.dumps(snapshot),
            }
        )

    # Apply discount
    discount_amount = 0
    discount_code_id = None
    if cart.get("discount_code_id"):
        d = await discount_service.get_discount_by_id(db, str(cart["discount_code_id"]))
        if d and d["active"]:
            discount_code_id = str(d["id"])
            # For product-restricted coupons, only apply to qualifying items
            restricted_pids = d.get("product_ids", [])
            if restricted_pids:
                restricted_set = set(str(p) for p in restricted_pids)
                applicable_subtotal = sum(
                    oi["total_price"]
                    for oi in order_items_data
                    if oi["product_id"] in restricted_set
                )
            else:
                applicable_subtotal = subtotal
            discount_amount = discount_service.calculate_discount(
                d, applicable_subtotal
            )
            await discount_service.increment_uses(
                db, str(d["id"]), session_id=session_id, user_id=user_id
            )
            await discount_service.increment_customer_uses(db, str(d["id"]), user_id)

    total = max(subtotal - discount_amount, 0)

    # 5. Generate order number and create order
    order_number = _generate_order_number()
    order_row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.orders "
                    "(user_id, order_number, status, currency, subtotal, discount_amount, tax_amount, total, discount_code_id) "
                    "VALUES (:uid, :num, 'pending', 'USD', :sub, :disc, 0, :total, :dcid) "
                    "RETURNING *"
                ),
                {
                    "uid": user_id,
                    "num": order_number,
                    "sub": subtotal,
                    "disc": discount_amount,
                    "total": total,
                    "dcid": discount_code_id,
                },
            )
        )
        .mappings()
        .first()
    )
    order = dict(order_row)
    order_id = str(order["id"])

    # Set reference_id on inventory records created during this checkout
    # (The reserve_stock calls above didn't have order_id yet)

    # Insert order items
    for oi in order_items_data:
        await db.execute(
            text(
                "INSERT INTO ecommerce.order_items "
                "(order_id, product_id, variant_id, quantity, unit_price, total_price, product_snapshot) "
                "VALUES (:oid, :pid, :vid, :qty, :up, :tp, CAST(:snap AS jsonb))"
            ),
            {
                "oid": order_id,
                "pid": oi["product_id"],
                "vid": oi["variant_id"],
                "qty": oi["quantity"],
                "up": oi["unit_price"],
                "tp": oi["total_price"],
                "snap": oi["product_snapshot"],
            },
        )

    # 6. Mark cart as converted
    await db.execute(
        text("UPDATE ecommerce.cart SET status = 'converted' WHERE id = :cid"),
        {"cid": cart_id},
    )

    # Update customer metrics
    await db.execute(
        text(
            "INSERT INTO ecommerce.customer_metrics (user_id, order_count, total_spent, last_purchase_at) "
            "VALUES (:uid, 1, :total, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "order_count = ecommerce.customer_metrics.order_count + 1, "
            "total_spent = ecommerce.customer_metrics.total_spent + :total, "
            "last_purchase_at = NOW()"
        ),
        {"uid": user_id, "total": total},
    )

    await db.commit()
    return order


async def get_order(
    db: AsyncSession, order_id: str, user_id: str | None = None
) -> dict[str, Any] | None:
    """Get order with items. If user_id provided, scope to that user."""
    q = "SELECT * FROM ecommerce.orders WHERE id = :oid"
    params: dict[str, Any] = {"oid": order_id}
    if user_id:
        q += " AND user_id = :uid"
        params["uid"] = user_id

    row = (await db.execute(text(q), params)).mappings().first()
    if not row:
        return None

    order = dict(row)
    items = (
        (
            await db.execute(
                text("SELECT * FROM ecommerce.order_items WHERE order_id = :oid"),
                {"oid": order_id},
            )
        )
        .mappings()
        .all()
    )
    order["items"] = [dict(i) for i in items]
    return order


async def list_orders(
    db: AsyncSession,
    user_id: str | None = None,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    where = "1=1"
    params: dict[str, Any] = {}
    if user_id:
        where = "user_id = :uid"
        params["uid"] = user_id

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM ecommerce.orders WHERE {where}"), params
        )
    ).scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT * FROM ecommerce.orders WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def update_order_status(
    db: AsyncSession, order_id: str, status: str
) -> dict[str, Any]:
    row = (
        (
            await db.execute(
                text(
                    "UPDATE ecommerce.orders SET status = :status WHERE id = :oid RETURNING *"
                ),
                {"oid": order_id, "status": status},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Order not found")
    await db.commit()
    return dict(row)


def _generate_order_number() -> str:
    now = datetime.now(timezone.utc)
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"ORD-{now.strftime('%Y%m%d')}-{rand}"
