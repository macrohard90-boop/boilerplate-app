"""Discount code validation and calculation. Admin CRUD added in Wave 3."""

import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def validate_discount(db: AsyncSession, code: str, subtotal: int) -> dict[str, Any]:
    """Validate a discount code and return discount info.

    Raises ValueError if the code is invalid, expired, or doesn't meet minimum.
    """
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.discount_codes WHERE code = :code"),
            {"code": code.upper()},
        )
    ).mappings().first()

    if not row:
        raise ValueError("Invalid discount code")

    d = dict(row)
    if not d["active"]:
        raise ValueError("Discount code is no longer active")

    now = datetime.now(timezone.utc)
    if d.get("valid_until") and d["valid_until"] < now:
        raise ValueError("Discount code has expired")
    if d.get("valid_from") and d["valid_from"] > now:
        raise ValueError("Discount code is not yet valid")

    if d.get("max_uses") is not None and d["uses_count"] >= d["max_uses"]:
        raise ValueError("Discount code has reached maximum uses")

    if subtotal < d["min_order_amount"]:
        raise ValueError(f"Minimum order amount of {d['min_order_amount']} cents required")

    return d


def calculate_discount(discount: dict[str, Any], subtotal: int) -> int:
    """Calculate discount amount in cents."""
    if discount["type"] == "percentage":
        return int(subtotal * discount["value"] / 100)
    elif discount["type"] == "fixed":
        return min(discount["value"], subtotal)
    elif discount["type"] == "free_shipping":
        return 0  # Handled at shipping level
    return 0


async def get_discount_by_id(db: AsyncSession, discount_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.discount_codes WHERE id = :id"),
            {"id": discount_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def increment_uses(db: AsyncSession, discount_id: str) -> None:
    await db.execute(
        text("UPDATE ecommerce.discount_codes SET uses_count = uses_count + 1 WHERE id = :id"),
        {"id": discount_id},
    )


# ---------------------------------------------------------------------------
# Admin CRUD (Wave 3)
# ---------------------------------------------------------------------------

async def list_discounts(
    db: AsyncSession, *, page: int = 1, page_size: int = 20,
) -> dict[str, Any]:
    total = (await db.execute(text("SELECT COUNT(*) FROM ecommerce.discount_codes"))).scalar() or 0
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            text("SELECT * FROM ecommerce.discount_codes ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {"limit": page_size, "offset": offset},
        )
    ).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def create_discount(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.discount_codes "
                "(code, type, value, currency, min_order_amount, max_uses, valid_from, valid_until) "
                "VALUES (:code, :type, :value, :currency, :min_order_amount, :max_uses, :valid_from, :valid_until) "
                "RETURNING *"
            ),
            {
                "code": data["code"].upper(),
                "type": data["type"],
                "value": data["value"],
                "currency": data.get("currency", "USD"),
                "min_order_amount": data.get("min_order_amount", 0),
                "max_uses": data.get("max_uses"),
                "valid_from": data.get("valid_from") or datetime.now(timezone.utc),
                "valid_until": data.get("valid_until"),
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def update_discount(db: AsyncSession, discount_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = await get_discount_by_id(db, discount_id)
    if not existing:
        raise ValueError("Discount not found")

    fields = {k: v for k, v in data.items() if v is not None}
    if "code" in fields:
        fields["code"] = fields["code"].upper()
    if not fields:
        return existing

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = discount_id
    row = (
        await db.execute(
            text(f"UPDATE ecommerce.discount_codes SET {set_clause} WHERE id = :id RETURNING *"),
            fields,
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def deactivate_discount(db: AsyncSession, discount_id: str) -> None:
    result = await db.execute(
        text("UPDATE ecommerce.discount_codes SET active = FALSE WHERE id = :id"),
        {"id": discount_id},
    )
    if result.rowcount == 0:
        raise ValueError("Discount not found")
    await db.commit()
