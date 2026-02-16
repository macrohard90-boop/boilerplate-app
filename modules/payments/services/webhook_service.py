"""Stripe webhook processing with signature verification and idempotency."""

import logging
from typing import Any

import stripe

from backend.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ecommerce.services import inventory_service, order_service
from modules.payments.services import payment_service

logger = logging.getLogger(__name__)


async def verify_and_process_webhook(
    db: AsyncSession,
    payload: bytes,
    sig_header: str,
) -> dict[str, Any]:
    """Verify Stripe signature, check idempotency, dispatch event.

    Always returns a dict with status info. Caller should return 200 to Stripe
    regardless of processing outcome (Stripe retries on non-2xx).
    """
    # 1. Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError as e:
        logger.warning("Invalid webhook signature: %s", e)
        raise ValueError("Invalid signature") from e
    except Exception as e:
        logger.error("Webhook verification error: %s", e)
        raise ValueError("Webhook verification failed") from e

    event_id = event["id"]
    event_type = event["type"]

    # 2. Idempotency check
    existing = (
        await db.execute(
            text("SELECT id FROM ecommerce.webhook_events WHERE event_id = :eid"),
            {"eid": event_id},
        )
    ).mappings().first()

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
            await _handle_payment_succeeded(db, event["data"]["object"])
        elif event_type == "payment_intent.payment_failed":
            await _handle_payment_failed(db, event["data"]["object"])
        elif event_type == "charge.refunded":
            await _handle_charge_refunded(db, event["data"]["object"])
        elif event_type == "account.updated":
            await _handle_account_updated(db, event["data"]["object"])
        else:
            logger.info("Unhandled webhook event type: %s", event_type)
    except Exception:
        logger.exception("Error processing webhook event %s (%s)", event_id, event_type)

    return {"status": "processed", "event_id": event_id, "event_type": event_type}


async def _handle_payment_succeeded(
    db: AsyncSession, payment_intent: dict[str, Any]
) -> None:
    """payment_intent.succeeded → mark payment succeeded, order completed."""
    pi_id = payment_intent["id"]
    logger.info("Payment succeeded: %s", pi_id)

    # Update payment record
    await payment_service.update_payment_status(db, pi_id, "succeeded")

    # Update order status
    order_id = payment_intent.get("metadata", {}).get("order_id")
    if order_id:
        await order_service.update_order_status(db, order_id, "completed")


async def _handle_payment_failed(
    db: AsyncSession, payment_intent: dict[str, Any]
) -> None:
    """payment_intent.payment_failed → mark failed, release inventory, reject order."""
    pi_id = payment_intent["id"]
    logger.info("Payment failed: %s", pi_id)

    # Update payment record
    await payment_service.update_payment_status(db, pi_id, "failed")

    # Get order ID and release inventory
    order_id = payment_intent.get("metadata", {}).get("order_id")
    if order_id:
        # Release inventory for all order items
        items = (
            await db.execute(
                text(
                    "SELECT variant_id, quantity FROM ecommerce.order_items "
                    "WHERE order_id = :oid"
                ),
                {"oid": order_id},
            )
        ).mappings().all()

        for item in items:
            await inventory_service.release_stock(
                db, str(item["variant_id"]), item["quantity"], reference_id=order_id
            )

        await order_service.update_order_status(db, order_id, "rejected")


async def _handle_charge_refunded(
    db: AsyncSession, charge: dict[str, Any]
) -> None:
    """charge.refunded → create refund record, update order status."""
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


async def _handle_account_updated(
    db: AsyncSession, account: dict[str, Any]
) -> None:
    """account.updated → update merchant account status."""
    account_id = account["id"]
    charges_enabled = account.get("charges_enabled", False)
    payouts_enabled = account.get("payouts_enabled", False)

    status = "active" if charges_enabled and payouts_enabled else "restricted"
    if account.get("requirements", {}).get("disabled_reason"):
        status = "disabled"

    logger.info("Account updated: %s → %s", account_id, status)

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
