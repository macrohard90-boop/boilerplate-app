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
        ).mappings().all()

        reaped = 0
        for row in rows:
            order_id = str(row["order_id"])
            pi_id = row["provider_payment_id"]

            try:
                # 1. Release inventory
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

                # 2. Update order status to 'expired'
                await db.execute(
                    text("UPDATE ecommerce.orders SET status = 'expired' WHERE id = :oid"),
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
                        logger.info("Canceled payment %s for expired order %s", pi_id, order_id)
                    except Exception as e:
                        logger.warning("Failed to cancel payment %s: %s", pi_id, e)

                reaped += 1
                logger.info("Reaped stale order %s (age > %d min)", order_id, timeout_minutes)

            except Exception:
                logger.exception("Error reaping order %s", order_id)
                await db.rollback()

        if reaped:
            logger.info("Order reaper: expired %d stale orders", reaped)
        return reaped


async def reaper_loop() -> None:
    """Background loop that periodically reaps stale orders."""
    logger.info(
        "Order reaper started (interval=%ds, timeout=%dmin)",
        REAPER_INTERVAL_SECONDS,
        settings.checkout_timeout,
    )
    while True:
        await asyncio.sleep(REAPER_INTERVAL_SECONDS)
        try:
            await reap_stale_orders()
        except Exception:
            logger.exception("Order reaper iteration failed")
