"""Webhook processing with signature verification and idempotency.

Provider-agnostic: signature verification is delegated to the configured
PaymentProvider via ``verify_webhook()``.
"""

import json
import logging
import random
import string
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.ecommerce.services import (
    inventory_service,
    order_service,
    pricing_service,
    subscription_service,
)
from modules.payments.adapters import get_payment_provider
from modules.payments.services import payment_service

logger = logging.getLogger(__name__)


async def verify_and_process_webhook(
    db: AsyncSession,
    payload: bytes,
    sig_header: str,
) -> dict[str, Any]:
    """Verify signature, check idempotency, dispatch event.

    Always returns a dict with status info. Caller should return 200
    regardless of processing outcome (providers retry on non-2xx).
    """
    # 1. Verify signature via provider
    provider = get_payment_provider()
    try:
        event = await provider.verify_webhook(payload, sig_header)
    except ValueError:
        raise

    event_id = event["id"]
    event_type = event["type"]
    data = event["data"]

    # 2. Idempotency check
    existing = (
        (
            await db.execute(
                text("SELECT id FROM ecommerce.webhook_events WHERE event_id = :eid"),
                {"eid": event_id},
            )
        )
        .mappings()
        .first()
    )

    if existing:
        logger.info("Duplicate webhook event skipped: %s", event_id)
        return {"status": "duplicate", "event_id": event_id}

    # 3. Record event
    await db.execute(
        text(
            "INSERT INTO ecommerce.webhook_events (event_id, event_type) "
            "VALUES (:eid, :etype)"
        ),
        {"eid": event_id, "etype": event_type},
    )
    await db.commit()

    # 4. Dispatch
    try:
        if event_type == "payment_intent.succeeded":
            await _handle_payment_succeeded(db, data)
        elif event_type == "payment_intent.payment_failed":
            await _handle_payment_failed(db, data)
        elif event_type == "charge.succeeded":
            await _handle_charge_succeeded(db, data)
        elif event_type == "charge.refunded":
            await _handle_charge_refunded(db, data)
        elif event_type == "account.updated":
            await _handle_account_updated(db, data)
        elif event_type == "product.updated":
            await _handle_product_updated(db, data)
        elif event_type == "product.deleted":
            await _handle_product_deleted(db, data)
        elif event_type == "price.updated":
            await _handle_price_updated(db, data)
        elif event_type == "price.deleted":
            await _handle_price_deleted(db, data)
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            await _handle_subscription_event(db, data)
        elif event_type == "invoice.payment_failed":
            await _handle_invoice_payment_failed(db, data)
        elif event_type == "checkout.session.completed":
            await _handle_checkout_session_completed(db, data)
        else:
            logger.info("Unhandled webhook event type: %s", event_type)
    except Exception:
        logger.exception("Error processing webhook event %s (%s)", event_id, event_type)

    return {"status": "processed", "event_id": event_id, "event_type": event_type}


async def _handle_payment_succeeded(
    db: AsyncSession, payment_intent: dict[str, Any]
) -> None:
    """payment_intent.succeeded -> mark payment succeeded, order completed."""
    pi_id = payment_intent["id"]
    logger.info("Payment succeeded: %s", pi_id)

    # Update payment record
    await payment_service.update_payment_status(db, pi_id, "succeeded")

    # Update order status
    order_id = payment_intent.get("metadata", {}).get("order_id")
    if order_id:
        await order_service.update_order_status(db, order_id, "completed")

        # Record campaign attribution conversion (fire-and-forget)
        try:
            user_id = payment_intent.get("metadata", {}).get("user_id")
            if user_id:
                order_total = payment_intent.get("amount", 0)
                currency = (payment_intent.get("currency") or "usd").upper()
                from modules.marketing.services.conversion_service import (
                    record_conversion_fire_and_forget,
                )

                await record_conversion_fire_and_forget(
                    user_id,
                    conversion_event="order.completed",
                    conversion_value=order_total,
                    conversion_currency=currency,
                    order_id=order_id,
                )
        except Exception:
            logger.debug("Attribution conversion recording failed (non-fatal)")

        # Send order confirmation email (fire-and-forget — don't block webhook)
        try:
            user_id = payment_intent.get("metadata", {}).get("user_id")
            if user_id:
                email_data = await _build_order_email_data(db, order_id)
                from modules.gdpr.services.email_send_service import (
                    send_email_fire_and_forget,
                )

                await send_email_fire_and_forget(
                    user_id,
                    "order_confirmation",
                    email_data,
                    email_type="transactional_email",
                )
        except Exception:
            logger.exception("Failed to send order confirmation for %s", order_id)

        # Fire automation flow event (non-blocking)
        try:
            user_id = payment_intent.get("metadata", {}).get("user_id")
            if user_id:
                from modules.marketing.services.flow_execution_service import (
                    fire_event_for_flows,
                )

                await fire_event_for_flows(
                    db,
                    "order.completed",
                    user_id,
                    {"order_id": order_id, "amount": payment_intent.get("amount", 0)},
                )
        except Exception:
            logger.debug("Flow event fire failed (non-fatal)", exc_info=True)


async def _build_order_email_data(db: AsyncSession, order_id: str) -> dict[str, Any]:
    """Fetch order details + items for the confirmation email template."""
    order = (
        (
            await db.execute(
                text(
                    "SELECT order_number, total, currency "
                    "FROM ecommerce.orders WHERE id = :oid"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .first()
    )

    items_rows = (
        (
            await db.execute(
                text(
                    "SELECT product_snapshot, quantity, unit_price "
                    "FROM ecommerce.order_items WHERE order_id = :oid"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .all()
    )

    items = []
    for row in items_rows:
        snap = (
            row["product_snapshot"] if isinstance(row["product_snapshot"], dict) else {}
        )
        name = snap.get("product_name", "Item")
        variant = snap.get("variant_name")
        label = f"{name} ({variant})" if variant else name
        items.append(
            {
                "name": label,
                "quantity": row["quantity"],
                "price": f"${row['unit_price'] / 100:.2f}",
            }
        )

    currency = (order["currency"] if order else "USD").upper()
    total_cents = order["total"] if order else 0
    order_number = order["order_number"] if order else order_id[:8]

    return {
        "order_id": order_number,
        "items": items,
        "total": f"${total_cents / 100:.2f} {currency}",
        "order_url": f"{settings.frontend_url}/dashboard/orders",
    }


async def _build_subscription_email_data(
    db: AsyncSession,
    recurring_items: list[Any],
    stripe_subscription_id: str | None,
) -> dict[str, Any]:
    """Build template data for the subscription_confirmation email.

    ``first_name`` is injected automatically by the email send service.
    """
    # Plan name(s) from cart items
    plan_names = [item["product_name"] for item in recurring_items]
    plan_name = ", ".join(plan_names)

    # Try to get next billing date from subscription record.
    # The customer.subscription.created webhook may not have fired yet,
    # so the record might not exist — next_billing_date stays None.
    next_billing_date = None
    if stripe_subscription_id:
        sub_row = (
            (
                await db.execute(
                    text(
                        "SELECT current_period_end FROM ecommerce.subscriptions "
                        "WHERE stripe_subscription_id = :ssid"
                    ),
                    {"ssid": stripe_subscription_id},
                )
            )
            .mappings()
            .first()
        )
        if sub_row and sub_row.get("current_period_end"):
            next_billing_date = sub_row["current_period_end"].strftime("%B %d, %Y")

    return {
        "plan_name": plan_name,
        "next_billing_date": next_billing_date,
        "dashboard_url": f"{settings.frontend_url}/dashboard",
    }


async def _create_order_from_session(
    db: AsyncSession,
    user_id: str,
    one_time_items: list[Any],
) -> str | None:
    """Create an order for one-time items paid via Stripe Checkout Session.

    Payment is already confirmed by Stripe, so the order is created with
    status ``completed``.  Stock is reserved for each item.
    """
    subtotal = 0
    order_items_data: list[dict[str, Any]] = []

    for item in one_time_items:
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
            "product_slug": item.get("product_slug"),
            "product_sku": item.get("product_sku"),
            "variant_name": item["variant_name"],
            "variant_sku": item.get("variant_sku"),
            "attributes": (
                item["attributes"] if isinstance(item.get("attributes"), dict) else {}
            ),
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

    # Reserve stock for each item
    for item in one_time_items:
        try:
            await inventory_service.reserve_stock(
                db, str(item["variant_id"]), item["quantity"]
            )
        except Exception:
            logger.warning(
                "Stock reservation failed for variant %s in checkout session",
                item["variant_id"],
            )

    total = subtotal

    # Generate order number
    now = datetime.now(timezone.utc)
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    order_number = f"ORD-{now.strftime('%Y%m%d')}-{rand}"

    # Create order — already paid via Stripe Checkout Session
    order_row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.orders "
                    "(user_id, order_number, status, currency, subtotal, "
                    "discount_amount, tax_amount, total) "
                    "VALUES (:uid, :num, 'completed', 'USD', :sub, 0, 0, :total) "
                    "RETURNING id"
                ),
                {
                    "uid": user_id,
                    "num": order_number,
                    "sub": subtotal,
                    "total": total,
                },
            )
        )
        .mappings()
        .first()
    )

    if not order_row:
        return None

    order_id = str(order_row["id"])

    for oi in order_items_data:
        await db.execute(
            text(
                "INSERT INTO ecommerce.order_items "
                "(order_id, product_id, variant_id, quantity, unit_price, "
                "total_price, product_snapshot) "
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

    # Update customer metrics
    await db.execute(
        text(
            "INSERT INTO ecommerce.customer_metrics "
            "(user_id, order_count, total_spent, last_purchase_at) "
            "VALUES (:uid, 1, :total, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "order_count = ecommerce.customer_metrics.order_count + 1, "
            "total_spent = ecommerce.customer_metrics.total_spent + :total, "
            "last_purchase_at = NOW()"
        ),
        {"uid": user_id, "total": total},
    )

    await db.commit()
    logger.info("Created order %s for one-time items in checkout session", order_id)
    return order_id


async def _handle_payment_failed(
    db: AsyncSession, payment_intent: dict[str, Any]
) -> None:
    """payment_intent.payment_failed -> mark failed, release inventory, reject order."""
    pi_id = payment_intent["id"]
    logger.info("Payment failed: %s", pi_id)

    # Update payment record
    await payment_service.update_payment_status(db, pi_id, "failed")

    # Get order ID and release inventory
    order_id = payment_intent.get("metadata", {}).get("order_id")
    if order_id:
        # Release inventory for all order items
        items = (
            (
                await db.execute(
                    text(
                        "SELECT variant_id, quantity FROM ecommerce.order_items "
                        "WHERE order_id = :oid"
                    ),
                    {"oid": order_id},
                )
            )
            .mappings()
            .all()
        )

        for item in items:
            await inventory_service.release_stock(
                db, str(item["variant_id"]), item["quantity"], reference_id=order_id
            )

        await order_service.update_order_status(db, order_id, "rejected")


async def _handle_charge_succeeded(db: AsyncSession, charge: dict[str, Any]) -> None:
    """charge.succeeded -> store charge_id and payment method on payment record."""
    charge_id = charge["id"]
    pi_id = charge.get("payment_intent")

    logger.info("Charge succeeded: %s (pi=%s)", charge_id, pi_id)

    if not pi_id:
        return

    # Extract payment method type (e.g. "card") and brand (e.g. "visa")
    pmd = charge.get("payment_method_details", {})
    method_type = pmd.get("type")  # "card", "bank_transfer", etc.
    method_str = method_type
    if method_type == "card":
        brand = pmd.get("card", {}).get("brand")
        if brand:
            method_str = f"{method_type} ({brand})"

    await db.execute(
        text(
            "UPDATE ecommerce.payment_records "
            "SET charge_id = :cid, method = :method "
            "WHERE provider_payment_id = :pid"
        ),
        {"cid": charge_id, "pid": pi_id, "method": method_str},
    )
    await db.commit()


async def _handle_charge_refunded(db: AsyncSession, charge: dict[str, Any]) -> None:
    """charge.refunded -> create refund record, update order status."""
    pi_id = charge.get("payment_intent")
    refund_amount = charge.get("amount_refunded", 0)
    currency = (charge.get("currency") or "usd").upper()

    logger.info("Charge refunded: pi=%s amount=%d", pi_id, refund_amount)

    if not pi_id:
        return

    # Find the payment record to get order_id
    payment = await payment_service.get_payment_by_provider_id(db, pi_id)
    if not payment:
        logger.warning("No payment record found for refunded charge: %s", pi_id)
        return

    order_id = str(payment["order_id"])

    # Create refund record
    refund_id = charge.get("id", f"re_{pi_id}")
    await payment_service.create_refund_record(
        db,
        order_id=order_id,
        provider="stripe",
        provider_refund_id=refund_id,
        amount=refund_amount,
        currency=currency,
    )

    await order_service.update_order_status(db, order_id, "refunded")


async def _handle_account_updated(db: AsyncSession, account: dict[str, Any]) -> None:
    """account.updated -> update merchant account status."""
    account_id = account["id"]
    charges_enabled = account.get("charges_enabled", False)
    payouts_enabled = account.get("payouts_enabled", False)

    status = "active" if charges_enabled and payouts_enabled else "restricted"
    if account.get("requirements", {}).get("disabled_reason"):
        status = "disabled"

    logger.info("Account updated: %s -> %s", account_id, status)

    await db.execute(
        text(
            "UPDATE ecommerce.merchant_accounts "
            "SET status = :status, charges_enabled = :ce, payouts_enabled = :pe, "
            "updated_at = NOW() "
            "WHERE stripe_account_id = :aid"
        ),
        {
            "aid": account_id,
            "status": status,
            "ce": charges_enabled,
            "pe": payouts_enabled,
        },
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Product catalog webhook handlers
# ---------------------------------------------------------------------------


async def _handle_product_updated(
    db: AsyncSession, product_data: dict[str, Any]
) -> None:
    """product.updated -> sync name/description/active status from Stripe."""
    stripe_product_id = product_data.get("id")
    if not stripe_product_id:
        return

    logger.info("Product updated in Stripe: %s", stripe_product_id)

    row = (
        (
            await db.execute(
                text(
                    "SELECT id, status FROM ecommerce.products WHERE stripe_product_id = :spid"
                ),
                {"spid": stripe_product_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        logger.warning("No local product for Stripe product %s", stripe_product_id)
        return

    product_id = str(row["id"])
    is_active_in_stripe = product_data.get("active", True)
    new_name = product_data.get("name")

    updates: dict[str, Any] = {"id": product_id}
    set_parts: list[str] = ["updated_at = NOW()"]

    if new_name:
        set_parts.append("name = :name")
        updates["name"] = new_name

    if product_data.get("description") is not None:
        set_parts.append("description = :description")
        updates["description"] = product_data["description"]

    # If archived on Stripe side, archive locally
    if not is_active_in_stripe and row["status"] == "active":
        set_parts.append("status = 'archived'")
        set_parts.append("synced_provider = NULL")
        logger.info("Product %s archived via Stripe webhook", product_id)

    await db.execute(
        text(f"UPDATE ecommerce.products SET {', '.join(set_parts)} WHERE id = :id"),
        updates,
    )
    await db.commit()


async def _handle_product_deleted(
    db: AsyncSession, product_data: dict[str, Any]
) -> None:
    """product.deleted -> archive the local product and clear sync fields."""
    stripe_product_id = product_data.get("id")
    if not stripe_product_id:
        return

    logger.info("Product deleted in Stripe: %s", stripe_product_id)

    await db.execute(
        text(
            "UPDATE ecommerce.products "
            "SET status = 'archived', stripe_sync_status = 'unsynced', "
            "    synced_provider = NULL, updated_at = NOW() "
            "WHERE stripe_product_id = :spid"
        ),
        {"spid": stripe_product_id},
    )
    await db.commit()


async def _handle_price_updated(db: AsyncSession, price_data: dict[str, Any]) -> None:
    """price.updated -> log the change. Prices are immutable so mainly tracks active status."""
    stripe_price_id = price_data.get("id")
    is_active = price_data.get("active", True)

    logger.info("Price updated in Stripe: %s active=%s", stripe_price_id, is_active)

    if not is_active:
        await _clear_stripe_price(db, stripe_price_id)


async def _handle_price_deleted(db: AsyncSession, price_data: dict[str, Any]) -> None:
    """price.deleted -> clear stripe_price_id from product/variant."""
    stripe_price_id = price_data.get("id")
    logger.info("Price deleted in Stripe: %s", stripe_price_id)
    await _clear_stripe_price(db, stripe_price_id)


async def _clear_stripe_price(db: AsyncSession, stripe_price_id: str | None) -> None:
    """Clear a Stripe price ID from products and variants tables."""
    if not stripe_price_id:
        return

    await db.execute(
        text(
            "UPDATE ecommerce.products "
            "SET stripe_price_id = NULL, stripe_sync_status = 'error', "
            "    stripe_sync_error = 'Price removed in Stripe' "
            "WHERE stripe_price_id = :sprice"
        ),
        {"sprice": stripe_price_id},
    )

    await db.execute(
        text(
            "UPDATE ecommerce.product_variants "
            "SET stripe_price_id = NULL, stripe_sync_status = 'error', "
            "    stripe_sync_error = 'Price removed in Stripe' "
            "WHERE stripe_price_id = :sprice"
        ),
        {"sprice": stripe_price_id},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Subscription webhook handlers
# ---------------------------------------------------------------------------


async def _handle_subscription_event(
    db: AsyncSession, sub_data: dict[str, Any]
) -> None:
    """Handle customer.subscription.created/updated/deleted events."""
    stripe_sub_id = sub_data.get("id")
    status = sub_data.get("status", "unknown")
    period_start = sub_data.get("current_period_start")
    period_end = sub_data.get("current_period_end")

    logger.info("Subscription event: %s -> %s", stripe_sub_id, status)

    if stripe_sub_id:
        await subscription_service.update_subscription_from_webhook(
            db,
            stripe_sub_id,
            status,
            current_period_start=period_start,
            current_period_end=period_end,
        )


async def _handle_invoice_payment_failed(
    db: AsyncSession, invoice_data: dict[str, Any]
) -> None:
    """Handle invoice.payment_failed — mark subscription as past_due."""
    stripe_sub_id = invoice_data.get("subscription")
    if not stripe_sub_id:
        return

    logger.info("Invoice payment failed for subscription: %s", stripe_sub_id)
    await subscription_service.update_subscription_from_webhook(
        db,
        stripe_sub_id,
        "past_due",
    )


async def _handle_checkout_session_completed(
    db: AsyncSession, session: dict[str, Any]
) -> None:
    """checkout.session.completed -> send confirmation emails, clear cart.

    Stripe Checkout Sessions are used when the cart contains subscriptions.
    The cart may also contain one-time products (mixed cart).

    - Recurring items  -> send ``subscription_confirmation`` email
    - One-time items   -> create order record + send ``order_confirmation`` email
    - Both             -> send both emails
    """
    session_id = session.get("id")
    mode = session.get("mode")
    subscription_stripe_id = session.get("subscription")
    customer_id = session.get("customer")
    user_id = (session.get("metadata") or {}).get("user_id")

    logger.info(
        "Checkout session completed: %s mode=%s subscription=%s customer=%s",
        session_id,
        mode,
        subscription_stripe_id,
        customer_id,
    )

    if not user_id:
        return

    # Fetch cart + items BEFORE marking as converted
    cart_row = (
        (
            await db.execute(
                text(
                    "SELECT id, discount_code_id FROM ecommerce.cart "
                    "WHERE user_id = :uid AND status = 'active'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not cart_row:
        logger.info("No active cart for user %s — already converted?", user_id)
        return

    cart_id = str(cart_row["id"])

    cart_items = (
        (
            await db.execute(
                text(
                    "SELECT ci.product_id, ci.variant_id, ci.quantity, "
                    "p.pricing_type, p.name AS product_name, p.base_price, "
                    "p.currency, p.slug AS product_slug, p.sku AS product_sku, "
                    "v.name AS variant_name, v.sku AS variant_sku, "
                    "v.price_override, v.attributes "
                    "FROM ecommerce.cart_items ci "
                    "JOIN ecommerce.products p ON p.id = ci.product_id "
                    "JOIN ecommerce.product_variants v ON v.id = ci.variant_id "
                    "WHERE ci.cart_id = :cid"
                ),
                {"cid": cart_id},
            )
        )
        .mappings()
        .all()
    )

    recurring_items = [i for i in cart_items if i["pricing_type"] == "recurring"]
    one_time_items = [i for i in cart_items if i["pricing_type"] != "recurring"]

    from modules.gdpr.services.email_send_service import send_email_fire_and_forget

    # ── One-time items: create order + send order_confirmation ──
    if one_time_items:
        try:
            order_id = await _create_order_from_session(db, user_id, one_time_items)
            if order_id:
                email_data = await _build_order_email_data(db, order_id)
                await send_email_fire_and_forget(
                    user_id,
                    "order_confirmation",
                    email_data,
                    email_type="transactional_email",
                )
        except Exception:
            logger.exception(
                "Failed to create order / send email for session %s one-time items",
                session_id,
            )

    # ── Recurring items: send subscription_confirmation ──
    if recurring_items:
        try:
            email_data = await _build_subscription_email_data(
                db, recurring_items, subscription_stripe_id
            )
            await send_email_fire_and_forget(
                user_id,
                "subscription_confirmation",
                email_data,
                email_type="transactional_email",
            )
        except Exception:
            logger.exception(
                "Failed to send subscription confirmation for session %s",
                session_id,
            )

    # ── Mark cart as converted ──
    await db.execute(
        text("UPDATE ecommerce.cart SET status = 'converted' WHERE id = :cid"),
        {"cid": cart_id},
    )
    await db.commit()
