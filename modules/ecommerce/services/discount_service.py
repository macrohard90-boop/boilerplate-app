"""Discount code validation and calculation. Admin CRUD added in Wave 3."""

import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers for product restrictions and per-customer usage
# ---------------------------------------------------------------------------


async def get_restricted_product_ids(db: AsyncSession, discount_id: str) -> list[str]:
    """Return product IDs this discount is restricted to (empty = all products)."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT product_id FROM ecommerce.discount_product_restrictions "
                    "WHERE discount_code_id = :did"
                ),
                {"did": discount_id},
            )
        )
        .mappings()
        .all()
    )
    return [str(r["product_id"]) for r in rows]


async def get_restricted_product_names(
    db: AsyncSession, discount_id: str
) -> list[dict[str, str]]:
    """Return product id+name for restrictions (includes archived products)."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT p.id, p.name "
                    "FROM ecommerce.discount_product_restrictions dpr "
                    "JOIN ecommerce.products p ON p.id = dpr.product_id "
                    "WHERE dpr.discount_code_id = :did"
                ),
                {"did": discount_id},
            )
        )
        .mappings()
        .all()
    )
    return [{"id": str(r["id"]), "name": r["name"]} for r in rows]


async def increment_customer_uses(
    db: AsyncSession, discount_id: str, user_id: str
) -> None:
    """Increment per-customer usage count (UPSERT)."""
    await db.execute(
        text(
            "INSERT INTO ecommerce.discount_customer_uses "
            "(discount_code_id, user_id, uses_count) "
            "VALUES (:did, :uid, 1) "
            "ON CONFLICT (discount_code_id, user_id) "
            "DO UPDATE SET uses_count = ecommerce.discount_customer_uses.uses_count + 1"
        ),
        {"did": discount_id, "uid": user_id},
    )


async def _save_product_restrictions(
    db: AsyncSession,
    discount_id: str,
    product_ids: list[str],
) -> None:
    """Replace product restrictions for a discount."""
    await db.execute(
        text(
            "DELETE FROM ecommerce.discount_product_restrictions WHERE discount_code_id = :did"
        ),
        {"did": discount_id},
    )
    for pid in product_ids:
        await db.execute(
            text(
                "INSERT INTO ecommerce.discount_product_restrictions "
                "(discount_code_id, product_id) VALUES (:did, :pid)"
            ),
            {"did": discount_id, "pid": pid},
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def validate_discount(
    db: AsyncSession,
    code: str,
    subtotal: int,
    *,
    user_id: str | None = None,
    cart_product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Validate a discount code and return discount info.

    Raises ValueError if the code is invalid, expired, or doesn't meet
    any restriction (customer, first-time, per-customer usage, products).
    """
    row = (
        (
            await db.execute(
                text("SELECT * FROM ecommerce.discount_codes WHERE code = :code"),
                {"code": code.upper()},
            )
        )
        .mappings()
        .first()
    )

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
        raise ValueError(
            f"Minimum order amount of {d['min_order_amount']} cents required"
        )

    # --- New restriction checks ---

    # Customer restriction
    if d.get("restricted_to_customer_id"):
        if not user_id or user_id != str(d["restricted_to_customer_id"]):
            raise ValueError("This coupon is not available for your account")

    # First-time transaction only
    if d.get("first_time_transaction_only") and user_id:
        order_count = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM ecommerce.orders "
                    "WHERE user_id = :uid AND status IN ('completed', 'accepted')"
                ),
                {"uid": user_id},
            )
        ).scalar() or 0
        if order_count > 0:
            raise ValueError("This coupon is only for first-time purchases")

    # Per-customer usage limit
    if d.get("max_uses_per_customer") is not None and user_id:
        cust_uses_row = (
            (
                await db.execute(
                    text(
                        "SELECT uses_count FROM ecommerce.discount_customer_uses "
                        "WHERE discount_code_id = :did AND user_id = :uid"
                    ),
                    {"did": str(d["id"]), "uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        cust_uses = cust_uses_row["uses_count"] if cust_uses_row else 0
        if cust_uses >= d["max_uses_per_customer"]:
            raise ValueError(
                "You have already used this coupon the maximum number of times"
            )

    # Product restriction
    restricted_pids = await get_restricted_product_ids(db, str(d["id"]))
    if restricted_pids and cart_product_ids is not None:
        restricted_set = set(restricted_pids)
        cart_set = set(cart_product_ids)
        if not cart_set.issubset(restricted_set):
            raise ValueError("This coupon is not valid for all items in your cart")

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


async def get_discount_by_id(
    db: AsyncSession, discount_id: str
) -> dict[str, Any] | None:
    row = (
        (
            await db.execute(
                text("SELECT * FROM ecommerce.discount_codes WHERE id = :id"),
                {"id": discount_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    d = dict(row)
    d["product_ids"] = await get_restricted_product_ids(db, discount_id)
    return d


async def increment_uses(db: AsyncSession, discount_id: str) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.discount_codes SET uses_count = uses_count + 1 WHERE id = :id"
        ),
        {"id": discount_id},
    )


# ---------------------------------------------------------------------------
# Stripe coupon sync helper
# ---------------------------------------------------------------------------


async def _sync_coupon_to_stripe(
    db: AsyncSession, discount: dict[str, Any]
) -> dict[str, Any]:
    """Create a Stripe Coupon + Promotion Code for a discount.

    On failure, records the error in stripe_sync_status/stripe_sync_error
    but does NOT raise — the local discount is preserved regardless.
    """
    if discount["type"] == "free_shipping":
        await _mark_discount_synced(db, str(discount["id"]))
        discount["stripe_sync_status"] = "synced"
        discount["stripe_sync_error"] = None
        return discount

    try:
        from modules.payments.adapters import get_payment_provider

        provider = get_payment_provider()

        # Look up Stripe product IDs for product restrictions
        restricted_pids = discount.get(
            "product_ids"
        ) or await get_restricted_product_ids(db, str(discount["id"]))
        stripe_product_ids: list[str] = []
        if restricted_pids:
            for pid in restricted_pids:
                prod_row = (
                    (
                        await db.execute(
                            text(
                                "SELECT stripe_product_id FROM ecommerce.products WHERE id = :pid"
                            ),
                            {"pid": str(pid)},
                        )
                    )
                    .mappings()
                    .first()
                )
                if prod_row and prod_row["stripe_product_id"]:
                    stripe_product_ids.append(prod_row["stripe_product_id"])

        coupon_result = await provider.create_coupon(
            coupon_type=discount["type"],
            value=discount["value"],
            currency=discount.get("currency", "USD"),
            duration=discount.get("stripe_duration", "once"),
            duration_in_months=discount.get("stripe_duration_in_months"),
            max_redemptions=discount.get("max_uses"),
            metadata={"local_discount_id": str(discount["id"])},
            applies_to_products=stripe_product_ids or None,
        )

        stripe_coupon_id = coupon_result["stripe_coupon_id"]

        # Create promotion code — if this fails, clean up the orphaned coupon
        try:
            stripe_customer_id = None
            if discount.get("restricted_to_customer_id"):
                cust_row = (
                    (
                        await db.execute(
                            text(
                                "SELECT stripe_customer_id FROM ecommerce.stripe_customers "
                                "WHERE user_id = :uid"
                            ),
                            {"uid": str(discount["restricted_to_customer_id"])},
                        )
                    )
                    .mappings()
                    .first()
                )
                if cust_row:
                    stripe_customer_id = cust_row["stripe_customer_id"]
                else:
                    raise ValueError(
                        "Customer has no Stripe account yet. "
                        "They must complete a checkout first before you can restrict a coupon to them."
                    )

            promo_result = await provider.create_promotion_code(
                stripe_coupon_id,
                discount["code"],
                customer=stripe_customer_id,
                first_time_transaction=discount.get(
                    "first_time_transaction_only", False
                ),
            )
        except Exception:
            # Clean up orphaned coupon before re-raising
            logger.warning(
                "Promo code failed; cleaning up orphaned coupon %s", stripe_coupon_id
            )
            try:
                await provider.delete_coupon(stripe_coupon_id)
            except Exception:
                logger.exception(
                    "Failed to clean up orphaned Stripe coupon %s", stripe_coupon_id
                )
            raise

        # Success: update DB with Stripe IDs and sync status
        await db.execute(
            text(
                "UPDATE ecommerce.discount_codes "
                "SET stripe_coupon_id = :scid, stripe_promotion_code_id = :spid, "
                "    stripe_sync_status = 'synced', stripe_sync_error = NULL "
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
        discount["stripe_sync_status"] = "synced"
        discount["stripe_sync_error"] = None
        logger.info(
            "Synced coupon %s to Stripe: %s", discount["code"], stripe_coupon_id
        )

    except Exception as e:
        error_msg = str(e)
        logger.exception("Failed to sync coupon %s to Stripe", discount["code"])
        await _mark_discount_error(db, str(discount["id"]), error_msg)
        discount["stripe_sync_status"] = "error"
        discount["stripe_sync_error"] = error_msg

    return discount


async def _mark_discount_synced(db: AsyncSession, discount_id: str) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.discount_codes "
            "SET stripe_sync_status = 'synced', stripe_sync_error = NULL "
            "WHERE id = :id"
        ),
        {"id": discount_id},
    )
    await db.commit()


async def _mark_discount_error(db: AsyncSession, discount_id: str, error: str) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.discount_codes "
            "SET stripe_sync_status = 'error', stripe_sync_error = :err "
            "WHERE id = :id"
        ),
        {"id": discount_id, "err": error},
    )
    await db.commit()


async def _delete_stripe_coupon(discount: dict[str, Any]) -> None:
    """Delete a Stripe Coupon if one exists. Stripe auto-deactivates promo codes."""
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
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    where = ""
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if status == "active":
        where = " WHERE active = TRUE"
    elif status == "archived":
        where = " WHERE active = FALSE"

    total = (
        await db.execute(text(f"SELECT COUNT(*) FROM ecommerce.discount_codes{where}"))
    ).scalar() or 0
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT * FROM ecommerce.discount_codes{where} "
                    f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    items = []
    for r in rows:
        d = dict(r)
        d["product_ids"] = await get_restricted_product_ids(db, str(d["id"]))
        d["product_names"] = await get_restricted_product_names(db, str(d["id"]))
        items.append(d)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def create_discount(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    # Duration is only meaningful for subscriptions — force "once" for one-time-only coupons
    applies_to = data.get("applies_to", "all")
    if applies_to == "one_time":
        data["stripe_duration"] = "once"
        data["stripe_duration_in_months"] = None

    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.discount_codes "
                    "(code, type, value, currency, min_order_amount, max_uses, "
                    " valid_from, valid_until, applies_to, stripe_duration, stripe_duration_in_months, "
                    " restricted_to_customer_id, first_time_transaction_only, max_uses_per_customer) "
                    "VALUES (:code, :type, :value, :currency, :min_order_amount, :max_uses, "
                    " :valid_from, :valid_until, :applies_to, :stripe_duration, :stripe_duration_in_months, "
                    " :restricted_to_customer_id, :first_time_transaction_only, :max_uses_per_customer) "
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
                    "applies_to": applies_to,
                    "stripe_duration": data.get("stripe_duration", "once"),
                    "stripe_duration_in_months": data.get("stripe_duration_in_months"),
                    "restricted_to_customer_id": data.get("restricted_to_customer_id"),
                    "first_time_transaction_only": data.get(
                        "first_time_transaction_only", False
                    ),
                    "max_uses_per_customer": data.get("max_uses_per_customer"),
                },
            )
        )
        .mappings()
        .first()
    )
    await db.commit()

    discount = dict(row)

    # Save product restrictions
    product_ids = data.get("product_ids", [])
    if product_ids:
        await _save_product_restrictions(
            db, str(discount["id"]), [str(p) for p in product_ids]
        )
        await db.commit()
    discount["product_ids"] = [str(p) for p in product_ids]

    # Sync to Stripe (creates Coupon + Promotion Code)
    discount = await _sync_coupon_to_stripe(db, discount)

    return discount


async def update_discount(
    db: AsyncSession, discount_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    existing = await get_discount_by_id(db, discount_id)
    if not existing:
        raise ValueError("Discount not found")

    # Separate product_ids from scalar fields
    product_ids = data.pop("product_ids", None)

    # Duration is only meaningful for subscriptions — force "once" for one-time-only coupons
    effective_applies_to = data.get("applies_to", existing.get("applies_to"))
    if effective_applies_to == "one_time":
        data["stripe_duration"] = "once"
        data["stripe_duration_in_months"] = None

    # data comes from model_dump(exclude_unset=True) so every key present was
    # explicitly sent by the client — including None values (e.g. clearing a field).
    # We must preserve None values so nullable fields can be cleared.
    fields = dict(data)
    if "code" in fields and fields["code"] is not None:
        fields["code"] = fields["code"].upper()

    # Check if value/type/currency changed — Stripe coupons are immutable
    value_changed = (
        ("value" in fields and fields["value"] != existing["value"])
        or ("type" in fields and fields["type"] != existing["type"])
        or ("currency" in fields and fields.get("currency") != existing.get("currency"))
    )

    products_changed = False
    if product_ids is not None:
        old_pids = set(existing.get("product_ids", []))
        new_pids = set(str(p) for p in product_ids)
        products_changed = old_pids != new_pids

    # Check if promotion code restrictions changed — Stripe promo codes are also immutable
    restrictions_changed = (
        (
            "restricted_to_customer_id" in fields
            and str(fields["restricted_to_customer_id"] or "")
            != str(existing.get("restricted_to_customer_id") or "")
        )
        or (
            "first_time_transaction_only" in fields
            and fields["first_time_transaction_only"]
            != existing.get("first_time_transaction_only", False)
        )
        or (
            "max_uses_per_customer" in fields
            and fields["max_uses_per_customer"] != existing.get("max_uses_per_customer")
        )
        or ("code" in fields and fields.get("code") != existing.get("code"))
    )

    if fields:
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = discount_id
        row = (
            (
                await db.execute(
                    text(
                        f"UPDATE ecommerce.discount_codes SET {set_clause} WHERE id = :id RETURNING *"
                    ),
                    fields,
                )
            )
            .mappings()
            .first()
        )
        await db.commit()
        discount = dict(row)
    else:
        discount = dict(existing)

    # Update product restrictions if changed
    if product_ids is not None:
        await _save_product_restrictions(db, discount_id, [str(p) for p in product_ids])
        await db.commit()
        discount["product_ids"] = [str(p) for p in product_ids]
    else:
        discount["product_ids"] = existing.get("product_ids", [])

    # Determine if Stripe sync is needed
    needs_recreate = (
        value_changed or products_changed or restrictions_changed
    ) and existing.get("stripe_coupon_id")
    needs_initial_sync = (
        existing.get("stripe_sync_status") in ("error", "unsynced")
        and discount["type"] != "free_shipping"
        and not existing.get("stripe_coupon_id")
    )

    if needs_recreate:
        # Delete old coupon, clear stale IDs, then re-sync
        await _delete_stripe_coupon(existing)
        await db.execute(
            text(
                "UPDATE ecommerce.discount_codes "
                "SET stripe_coupon_id = NULL, stripe_promotion_code_id = NULL "
                "WHERE id = :id"
            ),
            {"id": discount_id},
        )
        await db.commit()
        discount["stripe_coupon_id"] = None
        discount["stripe_promotion_code_id"] = None
        discount = await _sync_coupon_to_stripe(db, discount)
    elif needs_initial_sync:
        # Previous sync failed or never attempted — retry
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
