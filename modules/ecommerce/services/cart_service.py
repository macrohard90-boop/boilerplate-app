"""Shopping cart: guest (Redis) + authenticated (PostgreSQL) + merge."""

import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.ecommerce.services import discount_service, pricing_service

_GUEST_PREFIX = "cart:guest:"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_variant_info(db: AsyncSession, variant_id: str) -> dict[str, Any] | None:
    """Fetch variant + product info needed for cart operations."""
    row = (
        await db.execute(
            text(
                "SELECT v.id AS variant_id, v.product_id, v.name AS variant_name, "
                "v.price_override, v.stock_quantity, v.sku, "
                "p.name AS product_name, p.base_price, p.currency, p.status "
                "FROM ecommerce.product_variants v "
                "JOIN ecommerce.products p ON p.id = v.product_id "
                "WHERE v.id = :vid AND p.deleted_at IS NULL"
            ),
            {"vid": variant_id},
        )
    ).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["effective_price"] = d["price_override"] if d["price_override"] is not None else d["base_price"]
    return d


# ---------------------------------------------------------------------------
# Guest cart (Redis)
# ---------------------------------------------------------------------------


async def _get_guest_cart(redis: Redis, session_id: str) -> dict[str, Any]:
    """Get or initialize guest cart from Redis."""
    key = f"{_GUEST_PREFIX}{session_id}"
    raw = await redis.get(key)
    if raw:
        return json.loads(raw)
    return {"items": [], "discount_code_id": None, "discount_code": None}


async def _save_guest_cart(redis: Redis, session_id: str, cart: dict[str, Any]) -> None:
    key = f"{_GUEST_PREFIX}{session_id}"
    await redis.set(key, json.dumps(cart, default=str), ex=settings.cart_ttl)


async def _delete_guest_cart(redis: Redis, session_id: str) -> None:
    await redis.delete(f"{_GUEST_PREFIX}{session_id}")


# ---------------------------------------------------------------------------
# Authenticated cart (PostgreSQL)
# ---------------------------------------------------------------------------


async def _get_or_create_auth_cart(db: AsyncSession, user_id: str) -> dict[str, Any]:
    """Get active cart for user, or create one."""
    row = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.cart "
                "WHERE user_id = :uid AND status = 'active' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    if row:
        return dict(row)

    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.cart (user_id, status) "
                "VALUES (:uid, 'active') RETURNING *"
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def _get_auth_cart_items(db: AsyncSession, cart_id: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT ci.*, p.name AS product_name, v.name AS variant_name, p.currency "
                "FROM ecommerce.cart_items ci "
                "JOIN ecommerce.products p ON p.id = ci.product_id "
                "JOIN ecommerce.product_variants v ON v.id = ci.variant_id "
                "WHERE ci.cart_id = :cid"
            ),
            {"cid": cart_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_cart(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Get cart for auth user or guest."""
    if user:
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        return _empty_cart()


async def add_item(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
    product_id: str,
    variant_id: str,
    quantity: int,
) -> dict[str, Any]:
    """Add item to cart (or update quantity if already present)."""
    info = await _get_variant_info(db, variant_id)
    if not info or str(info["product_id"]) != product_id:
        raise ValueError("Product/variant not found")
    if info["status"] != "active":
        raise ValueError("Product is not available")
    if info["stock_quantity"] < quantity:
        raise ValueError("Insufficient stock")

    unit_price = info["effective_price"]

    if user:
        await _add_auth_item(db, user["user_id"], product_id, variant_id, quantity, unit_price)
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        await _add_guest_item(redis, session_id, product_id, variant_id, quantity, unit_price, info)
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        raise ValueError("No user or session")


async def update_item(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
    product_id: str,
    variant_id: str,
    quantity: int,
) -> dict[str, Any]:
    """Update quantity of a cart item."""
    if user:
        cart = await _get_or_create_auth_cart(db, user["user_id"])
        result = await db.execute(
            text(
                "UPDATE ecommerce.cart_items SET quantity = :qty "
                "WHERE cart_id = :cid AND product_id = :pid AND variant_id = :vid"
            ),
            {"cid": str(cart["id"]), "pid": product_id, "vid": variant_id, "qty": quantity},
        )
        if result.rowcount == 0:
            raise ValueError("Item not in cart")
        await db.commit()
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        guest_cart = await _get_guest_cart(redis, session_id)
        found = False
        for item in guest_cart["items"]:
            if item["product_id"] == product_id and item["variant_id"] == variant_id:
                item["quantity"] = quantity
                found = True
                break
        if not found:
            raise ValueError("Item not in cart")
        await _save_guest_cart(redis, session_id, guest_cart)
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        raise ValueError("No user or session")


async def remove_item(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
    product_id: str,
    variant_id: str,
) -> dict[str, Any]:
    """Remove item from cart."""
    if user:
        cart = await _get_or_create_auth_cart(db, user["user_id"])
        result = await db.execute(
            text(
                "DELETE FROM ecommerce.cart_items "
                "WHERE cart_id = :cid AND product_id = :pid AND variant_id = :vid"
            ),
            {"cid": str(cart["id"]), "pid": product_id, "vid": variant_id},
        )
        if result.rowcount == 0:
            raise ValueError("Item not in cart")
        await db.commit()
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        guest_cart = await _get_guest_cart(redis, session_id)
        original_len = len(guest_cart["items"])
        guest_cart["items"] = [
            i for i in guest_cart["items"]
            if not (i["product_id"] == product_id and i["variant_id"] == variant_id)
        ]
        if len(guest_cart["items"]) == original_len:
            raise ValueError("Item not in cart")
        await _save_guest_cart(redis, session_id, guest_cart)
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        raise ValueError("No user or session")


async def apply_discount(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
    code: str,
) -> dict[str, Any]:
    """Apply a discount code to the cart."""
    # Get current subtotal to validate
    cart_data = await get_cart(db, redis, user, session_id)
    subtotal = cart_data["subtotal"]

    discount = await discount_service.validate_discount(db, code, subtotal)

    if user:
        cart = await _get_or_create_auth_cart(db, user["user_id"])
        await db.execute(
            text("UPDATE ecommerce.cart SET discount_code_id = :did WHERE id = :cid"),
            {"did": str(discount["id"]), "cid": str(cart["id"])},
        )
        await db.commit()
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        guest_cart = await _get_guest_cart(redis, session_id)
        guest_cart["discount_code_id"] = str(discount["id"])
        guest_cart["discount_code"] = discount["code"]
        await _save_guest_cart(redis, session_id, guest_cart)
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        raise ValueError("No user or session")


async def remove_discount(
    db: AsyncSession,
    redis: Redis,
    user: dict[str, Any] | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Remove discount from cart."""
    if user:
        cart = await _get_or_create_auth_cart(db, user["user_id"])
        await db.execute(
            text("UPDATE ecommerce.cart SET discount_code_id = NULL WHERE id = :cid"),
            {"cid": str(cart["id"])},
        )
        await db.commit()
        return await _get_auth_cart_response(db, user["user_id"])
    elif session_id:
        guest_cart = await _get_guest_cart(redis, session_id)
        guest_cart["discount_code_id"] = None
        guest_cart["discount_code"] = None
        await _save_guest_cart(redis, session_id, guest_cart)
        return await _get_guest_cart_response(db, redis, session_id)
    else:
        raise ValueError("No user or session")


async def merge_cart(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Merge guest cart into authenticated cart. Takes higher quantity for duplicates."""
    guest_cart = await _get_guest_cart(redis, session_id)
    if not guest_cart["items"]:
        return await _get_auth_cart_response(db, user_id)

    cart = await _get_or_create_auth_cart(db, user_id)
    cart_id = str(cart["id"])
    auth_items = await _get_auth_cart_items(db, cart_id)

    # Build lookup of existing auth items
    auth_lookup: dict[str, dict[str, Any]] = {}
    for item in auth_items:
        key = f"{item['product_id']}_{item['variant_id']}"
        auth_lookup[key] = item

    for guest_item in guest_cart["items"]:
        key = f"{guest_item['product_id']}_{guest_item['variant_id']}"
        if key in auth_lookup:
            # Take higher quantity
            existing = auth_lookup[key]
            new_qty = max(existing["quantity"], guest_item["quantity"])
            if new_qty != existing["quantity"]:
                await db.execute(
                    text(
                        "UPDATE ecommerce.cart_items SET quantity = :qty "
                        "WHERE cart_id = :cid AND product_id = :pid AND variant_id = :vid"
                    ),
                    {
                        "cid": cart_id,
                        "pid": guest_item["product_id"],
                        "vid": guest_item["variant_id"],
                        "qty": new_qty,
                    },
                )
        else:
            # Insert new item
            await db.execute(
                text(
                    "INSERT INTO ecommerce.cart_items "
                    "(cart_id, product_id, variant_id, quantity, unit_price_at_add) "
                    "VALUES (:cid, :pid, :vid, :qty, :price)"
                ),
                {
                    "cid": cart_id,
                    "pid": guest_item["product_id"],
                    "vid": guest_item["variant_id"],
                    "qty": guest_item["quantity"],
                    "price": guest_item["unit_price"],
                },
            )

    # Merge discount if guest has one and auth doesn't
    if guest_cart.get("discount_code_id") and not cart.get("discount_code_id"):
        await db.execute(
            text("UPDATE ecommerce.cart SET discount_code_id = :did WHERE id = :cid"),
            {"did": guest_cart["discount_code_id"], "cid": cart_id},
        )

    await db.commit()
    await _delete_guest_cart(redis, session_id)
    return await _get_auth_cart_response(db, user_id)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


async def _get_auth_cart_response(db: AsyncSession, user_id: str) -> dict[str, Any]:
    cart = await _get_or_create_auth_cart(db, user_id)
    items = await _get_auth_cart_items(db, str(cart["id"]))

    cart_items = []
    subtotal = 0
    for item in items:
        total = item["unit_price_at_add"] * item["quantity"]
        subtotal += total
        cart_items.append({
            "product_id": item["product_id"],
            "variant_id": item["variant_id"],
            "quantity": item["quantity"],
            "unit_price": item["unit_price_at_add"],
            "total_price": total,
            "product_name": item["product_name"],
            "variant_name": item["variant_name"],
            "currency": item.get("currency", "USD"),
        })

    discount_amount = 0
    discount_code = None
    if cart.get("discount_code_id"):
        d = await discount_service.get_discount_by_id(db, str(cart["discount_code_id"]))
        if d and d["active"]:
            discount_amount = discount_service.calculate_discount(d, subtotal)
            discount_code = d["code"]

    return {
        "items": cart_items,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "discount_code": discount_code,
        "total": max(subtotal - discount_amount, 0),
        "currency": "USD",
        "item_count": sum(i["quantity"] for i in cart_items),
    }


async def _get_guest_cart_response(
    db: AsyncSession, redis: Redis, session_id: str,
) -> dict[str, Any]:
    guest_cart = await _get_guest_cart(redis, session_id)
    items = guest_cart.get("items", [])

    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)

    discount_amount = 0
    discount_code = guest_cart.get("discount_code")
    if guest_cart.get("discount_code_id"):
        d = await discount_service.get_discount_by_id(db, guest_cart["discount_code_id"])
        if d and d["active"]:
            discount_amount = discount_service.calculate_discount(d, subtotal)
            discount_code = d["code"]

    cart_items = []
    for i in items:
        cart_items.append({
            "product_id": i["product_id"],
            "variant_id": i["variant_id"],
            "quantity": i["quantity"],
            "unit_price": i["unit_price"],
            "total_price": i["unit_price"] * i["quantity"],
            "product_name": i.get("product_name", ""),
            "variant_name": i.get("variant_name", ""),
            "currency": i.get("currency", "USD"),
        })

    return {
        "items": cart_items,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "discount_code": discount_code,
        "total": max(subtotal - discount_amount, 0),
        "currency": "USD",
        "item_count": sum(i["quantity"] for i in items),
    }


def _empty_cart() -> dict[str, Any]:
    return {
        "items": [],
        "subtotal": 0,
        "discount_amount": 0,
        "discount_code": None,
        "total": 0,
        "currency": "USD",
        "item_count": 0,
    }


# ---------------------------------------------------------------------------
# Internal add helpers
# ---------------------------------------------------------------------------


async def _add_auth_item(
    db: AsyncSession,
    user_id: str,
    product_id: str,
    variant_id: str,
    quantity: int,
    unit_price: int,
) -> None:
    cart = await _get_or_create_auth_cart(db, user_id)
    cart_id = str(cart["id"])

    # Check if item already in cart
    existing = (
        await db.execute(
            text(
                "SELECT quantity FROM ecommerce.cart_items "
                "WHERE cart_id = :cid AND product_id = :pid AND variant_id = :vid"
            ),
            {"cid": cart_id, "pid": product_id, "vid": variant_id},
        )
    ).first()

    if existing:
        await db.execute(
            text(
                "UPDATE ecommerce.cart_items SET quantity = quantity + :qty "
                "WHERE cart_id = :cid AND product_id = :pid AND variant_id = :vid"
            ),
            {"cid": cart_id, "pid": product_id, "vid": variant_id, "qty": quantity},
        )
    else:
        await db.execute(
            text(
                "INSERT INTO ecommerce.cart_items "
                "(cart_id, product_id, variant_id, quantity, unit_price_at_add) "
                "VALUES (:cid, :pid, :vid, :qty, :price)"
            ),
            {"cid": cart_id, "pid": product_id, "vid": variant_id, "qty": quantity, "price": unit_price},
        )
    await db.commit()


async def _add_guest_item(
    redis: Redis,
    session_id: str,
    product_id: str,
    variant_id: str,
    quantity: int,
    unit_price: int,
    info: dict[str, Any],
) -> None:
    guest_cart = await _get_guest_cart(redis, session_id)

    # Check if item already exists
    for item in guest_cart["items"]:
        if item["product_id"] == product_id and item["variant_id"] == variant_id:
            item["quantity"] += quantity
            await _save_guest_cart(redis, session_id, guest_cart)
            return

    guest_cart["items"].append({
        "product_id": product_id,
        "variant_id": variant_id,
        "quantity": quantity,
        "unit_price": unit_price,
        "product_name": info["product_name"],
        "variant_name": info["variant_name"],
        "currency": info.get("currency", "USD"),
    })
    await _save_guest_cart(redis, session_id, guest_cart)
