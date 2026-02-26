"""Subscription service — create, cancel, and manage recurring subscriptions."""

import logging
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.adapters import get_payment_provider

logger = logging.getLogger(__name__)


async def get_or_create_stripe_customer(
    db: AsyncSession, user_id: str, email: str, *, name: str | None = None
) -> str:
    """Return the Stripe customer ID for a user, creating one if needed."""
    row = (
        await db.execute(
            text("SELECT stripe_customer_id FROM ecommerce.stripe_customers WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).mappings().first()

    if row:
        return str(row["stripe_customer_id"])

    provider = get_payment_provider()
    result = await provider.create_customer(email, name=name, metadata={"user_id": user_id})

    await db.execute(
        text(
            "INSERT INTO ecommerce.stripe_customers (user_id, stripe_customer_id) "
            "VALUES (:uid, :cid) ON CONFLICT (user_id) DO NOTHING"
        ),
        {"uid": user_id, "cid": result.provider_customer_id},
    )
    await db.commit()

    return result.provider_customer_id


async def create_subscription(
    db: AsyncSession,
    user_id: str,
    email: str,
    product_id: str,
    variant_id: str | None = None,
    discount_code: str | None = None,
) -> dict[str, Any]:
    """Create a subscription for a recurring product.

    Returns dict with subscription record and client_secret for payment confirmation.
    """
    # Validate product is recurring
    product = (
        await db.execute(
            text(
                "SELECT id, pricing_type, stripe_price_id, trial_period_days "
                "FROM ecommerce.products WHERE id = :pid AND deleted_at IS NULL"
            ),
            {"pid": product_id},
        )
    ).mappings().first()

    if not product:
        raise ValueError("Product not found")
    if product["pricing_type"] != "recurring":
        raise ValueError("Product is not a recurring subscription product")
    if not product["stripe_price_id"]:
        raise ValueError("Product has not been synced to Stripe yet")

    # Get or resolve variant price
    price_id = str(product["stripe_price_id"])
    if variant_id:
        variant = (
            await db.execute(
                text(
                    "SELECT stripe_price_id FROM ecommerce.product_variants "
                    "WHERE id = :vid AND product_id = :pid"
                ),
                {"vid": variant_id, "pid": product_id},
            )
        ).mappings().first()
        if variant and variant["stripe_price_id"]:
            price_id = str(variant["stripe_price_id"])

    # Get or create Stripe customer
    stripe_customer_id = await get_or_create_stripe_customer(db, user_id, email)

    # Handle discount code
    coupon_id: str | None = None
    discount_code_id: str | None = None
    if discount_code:
        from modules.ecommerce.services import discount_service

        discount = await discount_service.validate_discount(db, discount_code, 0)
        if discount.get("applies_to") and discount["applies_to"] == "one_time":
            raise ValueError("This coupon cannot be applied to recurring subscriptions")
        coupon_id = discount.get("stripe_coupon_id")
        discount_code_id = str(discount["id"])

    # Create Stripe subscription
    provider = get_payment_provider()
    trial_days = product["trial_period_days"]
    result = await provider.create_subscription(
        stripe_customer_id,
        price_id,
        coupon_id=coupon_id,
        trial_period_days=trial_days,
        metadata={"user_id": user_id, "product_id": product_id},
    )

    # Compute period timestamps and trial dates
    from datetime import datetime, timezone, timedelta

    period_start = None
    period_end = None
    if result.current_period_start:
        try:
            period_start = datetime.fromtimestamp(int(result.current_period_start), tz=timezone.utc)
        except (ValueError, TypeError):
            pass
    if result.current_period_end:
        try:
            period_end = datetime.fromtimestamp(int(result.current_period_end), tz=timezone.utc)
        except (ValueError, TypeError):
            pass

    now = datetime.now(timezone.utc)
    trial_start = now if trial_days else None
    trial_end = now + timedelta(days=trial_days) if trial_days else None

    # Insert subscription record
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.subscriptions "
                "(user_id, product_id, variant_id, stripe_subscription_id, stripe_customer_id, "
                " status, current_period_start, current_period_end, "
                " trial_start, trial_end, discount_code_id) "
                "VALUES (:uid, :pid, :vid, :ssid, :scid, :status, "
                " :ps, :pe, :trial_start, :trial_end, :dcid) "
                "RETURNING *"
            ),
            {
                "uid": user_id,
                "pid": product_id,
                "vid": variant_id,
                "ssid": result.provider_subscription_id,
                "scid": stripe_customer_id,
                "status": result.status,
                "ps": period_start,
                "pe": period_end,
                "trial_start": trial_start,
                "trial_end": trial_end,
                "dcid": discount_code_id,
            },
        )
    ).mappings().first()
    await db.commit()

    # Increment coupon usage
    if discount_code_id:
        from modules.ecommerce.services import discount_service
        await discount_service.increment_uses(db, discount_code_id)

    sub = dict(row)
    sub["client_secret"] = result.client_secret
    return sub


async def cancel_subscription(
    db: AsyncSession, subscription_id: str, user_id: str
) -> dict[str, Any]:
    """Cancel a subscription at period end."""
    row = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.subscriptions "
                "WHERE id = :sid AND user_id = :uid"
            ),
            {"sid": subscription_id, "uid": user_id},
        )
    ).mappings().first()

    if not row:
        raise ValueError("Subscription not found")

    sub = dict(row)
    if sub["status"] in ("canceled",):
        raise ValueError("Subscription is already canceled")

    provider = get_payment_provider()
    await provider.cancel_subscription(sub["stripe_subscription_id"], at_period_end=True)

    updated = (
        await db.execute(
            text(
                "UPDATE ecommerce.subscriptions "
                "SET cancel_at_period_end = TRUE, canceled_at = NOW() "
                "WHERE id = :sid RETURNING *"
            ),
            {"sid": subscription_id},
        )
    ).mappings().first()
    await db.commit()

    return dict(updated)


async def admin_cancel_subscription(
    db: AsyncSession, subscription_id: str
) -> dict[str, Any]:
    """Cancel a subscription at period end (admin — no user_id check)."""
    row = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.subscriptions "
                "WHERE id = :sid"
            ),
            {"sid": subscription_id},
        )
    ).mappings().first()

    if not row:
        raise ValueError("Subscription not found")

    sub = dict(row)
    if sub["status"] in ("canceled",):
        raise ValueError("Subscription is already canceled")

    provider = get_payment_provider()
    await provider.cancel_subscription(sub["stripe_subscription_id"], at_period_end=True)

    updated = (
        await db.execute(
            text(
                "UPDATE ecommerce.subscriptions "
                "SET cancel_at_period_end = TRUE, canceled_at = NOW() "
                "WHERE id = :sid RETURNING *"
            ),
            {"sid": subscription_id},
        )
    ).mappings().first()
    await db.commit()

    return dict(updated)


async def list_user_subscriptions(
    db: AsyncSession, user_id: str
) -> list[dict[str, Any]]:
    """List all subscriptions for a user."""
    rows = (
        await db.execute(
            text(
                "SELECT s.*, p.name as product_name, p.base_price, p.currency, "
                "p.recurring_interval, p.recurring_interval_count "
                "FROM ecommerce.subscriptions s "
                "JOIN ecommerce.products p ON s.product_id = p.id "
                "WHERE s.user_id = :uid "
                "ORDER BY s.created_at DESC"
            ),
            {"uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def list_all_subscriptions(
    db: AsyncSession, *, page: int = 1, page_size: int = 20, status: str | None = None
) -> dict[str, Any]:
    """List all subscriptions (admin)."""
    where = ""
    params: dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if status:
        where = " WHERE s.status = :status"
        params["status"] = status

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM ecommerce.subscriptions s{where}"), params
        )
    ).scalar() or 0
    rows = (
        await db.execute(
            text(
                f"SELECT s.*, p.name as product_name, u.email as user_email "
                f"FROM ecommerce.subscriptions s "
                f"JOIN ecommerce.products p ON s.product_id = p.id "
                f"JOIN core.users u ON s.user_id = u.id"
                f"{where} "
                f"ORDER BY s.created_at DESC "
                f"LIMIT :limit OFFSET :offset"
            ),
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


async def update_subscription_from_webhook(
    db: AsyncSession,
    stripe_subscription_id: str,
    status: str,
    current_period_start: int | None = None,
    current_period_end: int | None = None,
) -> None:
    """Update subscription record from webhook event."""
    set_parts = ["status = :status", "updated_at = NOW()"]
    params: dict[str, Any] = {
        "ssid": stripe_subscription_id,
        "status": status,
    }

    if current_period_start is not None:
        set_parts.append("current_period_start = to_timestamp(:ps)")
        params["ps"] = current_period_start
    if current_period_end is not None:
        set_parts.append("current_period_end = to_timestamp(:pe)")
        params["pe"] = current_period_end

    if status == "canceled":
        set_parts.append("canceled_at = NOW()")

    await db.execute(
        text(
            f"UPDATE ecommerce.subscriptions SET {', '.join(set_parts)} "
            "WHERE stripe_subscription_id = :ssid"
        ),
        params,
    )
    await db.commit()
