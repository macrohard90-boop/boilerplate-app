"""Stale order reaper: releases stock and cancels PaymentIntents for abandoned checkouts.

Orders stuck in 'processing' beyond CHECKOUT_TIMEOUT are considered abandoned.
The reaper runs as a background asyncio task inside the FastAPI process.
"""

import asyncio
import logging

from sqlalchemy import text

from backend.core.config import settings
from backend.core.database import get_session_factory
from modules.ecommerce.services import inventory_service

logger = logging.getLogger(__name__)

REAPER_INTERVAL_SECONDS = 300  # Run every 5 minutes


async def reap_stale_orders() -> int:
    """Find and expire stale processing orders. Returns count of reaped orders."""
    factory = get_session_factory()
    async with factory() as db:
        timeout_minutes = settings.checkout_timeout

        rows = (
            (
                await db.execute(
                    text(
                        "SELECT o.id AS order_id, pr.provider_payment_id "
                        "FROM ecommerce.orders o "
                        "LEFT JOIN ecommerce.payment_records pr ON pr.order_id = o.id "
                        "WHERE o.status = 'processing' "
                        "AND o.created_at < NOW() - MAKE_INTERVAL(mins => :timeout)"
                    ),
                    {"timeout": timeout_minutes},
                )
            )
            .mappings()
            .all()
        )

        reaped = 0
        for row in rows:
            order_id = str(row["order_id"])
            pi_id = row["provider_payment_id"]

            try:
                # 1. Release inventory
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
                        db,
                        str(item["variant_id"]),
                        item["quantity"],
                        reference_id=order_id,
                    )

                # 2. Update order status to 'expired'
                await db.execute(
                    text(
                        "UPDATE ecommerce.orders SET status = 'expired' WHERE id = :oid"
                    ),
                    {"oid": order_id},
                )

                # 3. Update payment record status
                if pi_id:
                    await db.execute(
                        text(
                            "UPDATE ecommerce.payment_records SET status = 'expired' "
                            "WHERE order_id = :oid"
                        ),
                        {"oid": order_id},
                    )

                await db.commit()

                # 4. Cancel payment via provider (best-effort, outside transaction)
                if pi_id:
                    try:
                        from modules.payments.adapters import get_payment_provider

                        provider = get_payment_provider()
                        await provider.cancel_payment(pi_id)
                        logger.info(
                            "Canceled payment %s for expired order %s", pi_id, order_id
                        )
                    except Exception as e:
                        logger.warning("Failed to cancel payment %s: %s", pi_id, e)

                reaped += 1
                logger.info(
                    "Reaped stale order %s (age > %d min)", order_id, timeout_minutes
                )

            except Exception:
                logger.exception("Error reaping order %s", order_id)
                await db.rollback()

        if reaped:
            logger.info("Order reaper: expired %d stale orders", reaped)
        return reaped


async def detect_abandoned_carts() -> int:
    """Find active carts untouched beyond cart_abandon_timeout and fire cart.abandoned events.

    Only fires once per cart — marks status='abandoned' after firing.
    """
    factory = get_session_factory()
    async with factory() as db:
        timeout_minutes = settings.cart_abandon_timeout

        # Find active carts with items that haven't been touched
        rows = (
            (
                await db.execute(
                    text(
                        "SELECT c.id AS cart_id, c.user_id "
                        "FROM ecommerce.cart c "
                        "WHERE c.status = 'active' "
                        "AND c.updated_at < NOW() - MAKE_INTERVAL(mins => :timeout) "
                        "AND EXISTS (SELECT 1 FROM ecommerce.cart_items ci WHERE ci.cart_id = c.id)"
                    ),
                    {"timeout": timeout_minutes},
                )
            )
            .mappings()
            .all()
        )

        fired = 0
        for row in rows:
            cart_id = str(row["cart_id"])
            user_id = str(row["user_id"])

            try:
                # Mark cart as abandoned to prevent re-firing
                await db.execute(
                    text(
                        "UPDATE ecommerce.cart SET status = 'abandoned' WHERE id = :cid"
                    ),
                    {"cid": cart_id},
                )
                await db.commit()

                # Fire flow trigger (non-blocking)
                try:
                    from modules.marketing.services.flow_execution_service import (
                        fire_event_for_flows,
                    )

                    await fire_event_for_flows(
                        db,
                        "cart.abandoned",
                        user_id,
                        {"cart_id": cart_id},
                    )
                except Exception:
                    logger.debug(
                        "Flow trigger for cart.abandoned failed for user=%s (non-fatal)",
                        user_id,
                        exc_info=True,
                    )

                fired += 1
                logger.info(
                    "Cart %s abandoned by user %s (age > %d min)",
                    cart_id,
                    user_id,
                    timeout_minutes,
                )
            except Exception:
                logger.exception("Error processing abandoned cart %s", cart_id)
                await db.rollback()

        if fired:
            logger.info("Cart abandonment: fired %d events", fired)
        return fired


async def reaper_loop() -> None:
    """Background loop that periodically reaps stale orders and detects abandoned carts."""
    logger.info(
        "Order reaper started (interval=%ds, checkout_timeout=%dmin, cart_abandon_timeout=%dmin)",
        REAPER_INTERVAL_SECONDS,
        settings.checkout_timeout,
        settings.cart_abandon_timeout,
    )
    while True:
        await asyncio.sleep(REAPER_INTERVAL_SECONDS)
        try:
            await reap_stale_orders()
        except Exception:
            logger.exception("Order reaper iteration failed")
        try:
            await detect_abandoned_carts()
        except Exception:
            logger.exception("Cart abandonment detection failed")
