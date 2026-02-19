"""Discount code validation and calculation. Admin CRUD added in Wave 3."""

import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


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
# Stripe coupon sync helper
# ---------------------------------------------------------------------------

async def _sync_coupon_to_stripe(
    db: AsyncSession, discount: dict[str, Any]
) -> dict[str, Any]:
    """Create a Stripe Coupon + Promotion Code for a discount.

    Only syncs percentage and fixed types (free_shipping has no Stripe equivalent).
    Updates the discount row with stripe_coupon_id and stripe_promotion_code_id.
    """
    if discount["type"] == "free_shipping":
        return discount

    try:
        from modules.payments.adapters import get_payment_provider

        provider = get_payment_provider()

        coupon_result = await provider.create_coupon(
            coupon_type=discount["type"],
            value=discount["value"],
            currency=discount.get("currency", "USD"),
            duration=discount.get("stripe_duration", "once"),
            duration_in_months=discount.get("stripe_duration_in_months"),
            max_redemptions=discount.get("max_uses"),
            metadata={"local_discount_id": str(discount["id"])},
        )

        stripe_coupon_id = coupon_result["stripe_coupon_id"]

        promo_result = await provider.create_promotion_code(
            stripe_coupon_id, discount["code"]
        )

        await db.execute(
            text(
                "UPDATE ecommerce.discount_codes "
                "SET stripe_coupon_id = :scid, stripe_promotion_code_id = :spid "
                "WHERE id = :id"
            ),
            {
                "id": str(discount["id"]),
                "scid": stripe_coupon_id,
                "spid": promo_result["stripe_promotion_code_id"],
            },
        )
        await db.commit()

        discount["stripe_coupon_id"] = stripe_coupon_id
        discount["stripe_promotion_code_id"] = promo_result["stripe_promotion_code_id"]
        logger.info("Synced coupon %s to Stripe: %s", discount["code"], stripe_coupon_id)
    except Exception:
        logger.exception("Failed to sync coupon %s to Stripe", discount["code"])

    return discount


async def _delete_stripe_coupon(discount: dict[str, Any]) -> None:
    """Delete a Stripe Coupon if one exists."""
    stripe_coupon_id = discount.get("stripe_coupon_id")
    if not stripe_coupon_id:
        return

    try:
        from modules.payments.adapters import get_payment_provider

        provider = get_payment_provider()
        await provider.delete_coupon(stripe_coupon_id)
        logger.info("Deleted Stripe coupon %s", stripe_coupon_id)
    except Exception:
        logger.exception("Failed to delete Stripe coupon %s", stripe_coupon_id)


# ---------------------------------------------------------------------------
# Admin CRUD (Wave 3)
# ---------------------------------------------------------------------------

async def list_discounts(
    db: AsyncSession, *, page: int = 1, page_size: int = 20, status: str | None = None,
) -> dict[str, Any]:
    where = ""
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if status == "active":
        where = " WHERE active = TRUE"
    elif status == "archived":
        where = " WHERE active = FALSE"

    total = (await db.execute(text(f"SELECT COUNT(*) FROM ecommerce.discount_codes{where}"))).scalar() or 0
    rows = (
        await db.execute(
            text(f"SELECT * FROM ecommerce.discount_codes{where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            params,
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
                "(code, type, value, currency, min_order_amount, max_uses, "
                " valid_from, valid_until, applies_to, stripe_duration, stripe_duration_in_months) "
                "VALUES (:code, :type, :value, :currency, :min_order_amount, :max_uses, "
                " :valid_from, :valid_until, :applies_to, :stripe_duration, :stripe_duration_in_months) "
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
                "applies_to": data.get("applies_to", "all"),
                "stripe_duration": data.get("stripe_duration", "once"),
                "stripe_duration_in_months": data.get("stripe_duration_in_months"),
            },
        )
    ).mappings().first()
    await db.commit()

    discount = dict(row)

    # Sync to Stripe (creates Coupon + Promotion Code)
    discount = await _sync_coupon_to_stripe(db, discount)

    return discount


async def update_discount(db: AsyncSession, discount_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = await get_discount_by_id(db, discount_id)
    if not existing:
        raise ValueError("Discount not found")

    fields = {k: v for k, v in data.items() if v is not None}
    if "code" in fields:
        fields["code"] = fields["code"].upper()
    if not fields:
        return existing

    # Check if value/type changed — Stripe coupons are immutable, need to recreate
    value_changed = (
        ("value" in fields and fields["value"] != existing["value"])
        or ("type" in fields and fields["type"] != existing["type"])
    )

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = discount_id
    row = (
        await db.execute(
            text(f"UPDATE ecommerce.discount_codes SET {set_clause} WHERE id = :id RETURNING *"),
            fields,
        )
    ).mappings().first()
    await db.commit()

    discount = dict(row)

    # If value/type changed, recreate Stripe coupon
    if value_changed and existing.get("stripe_coupon_id"):
        await _delete_stripe_coupon(existing)
        discount = await _sync_coupon_to_stripe(db, discount)

    return discount


async def deactivate_discount(db: AsyncSession, discount_id: str) -> None:
    existing = await get_discount_by_id(db, discount_id)
    if not existing:
        raise ValueError("Discount not found")

    await db.execute(
        text("UPDATE ecommerce.discount_codes SET active = FALSE WHERE id = :id"),
        {"id": discount_id},
    )
    await db.commit()

    # Delete Stripe coupon
    await _delete_stripe_coupon(existing)
