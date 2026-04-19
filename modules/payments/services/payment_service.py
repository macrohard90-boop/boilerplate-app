"""Payment lifecycle management: records, status updates, refunds."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_payment_record(
    db: AsyncSession,
    order_id: str,
    provider: str,
    provider_payment_id: str,
    amount: int,
    currency: str = "USD",
    status: str = "pending",
    method: str | None = None,
) -> dict[str, Any]:
    """Insert a payment_records row."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.payment_records "
                    "(order_id, provider, provider_payment_id, status, amount, currency, method) "
                    "VALUES (:oid, :prov, :ppid, :status, :amount, :currency, :method) "
                    "RETURNING *"
                ),
                {
                    "oid": order_id,
                    "prov": provider,
                    "ppid": provider_payment_id,
                    "status": status,
                    "amount": amount,
                    "currency": currency,
                    "method": method,
                },
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    return dict(row)


async def update_payment_status(
    db: AsyncSession,
    provider_payment_id: str,
    status: str,
) -> dict[str, Any] | None:
    """Update payment record status by provider_payment_id."""
    row = (
        (
            await db.execute(
                text(
                    "UPDATE ecommerce.payment_records SET status = :status "
                    "WHERE provider_payment_id = :ppid RETURNING *"
                ),
                {"ppid": provider_payment_id, "status": status},
            )
        )
        .mappings()
        .first()
    )
    if row:
        await db.commit()
        return dict(row)
    return None


async def get_payment_by_order(
    db: AsyncSession, order_id: str
) -> dict[str, Any] | None:
    """Get the most recent payment record for an order."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM ecommerce.payment_records "
                    "WHERE order_id = :oid ORDER BY created_at DESC LIMIT 1"
                ),
                {"oid": order_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def get_payment_by_provider_id(
    db: AsyncSession, provider_payment_id: str
) -> dict[str, Any] | None:
    """Get payment record by provider payment ID."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM ecommerce.payment_records "
                    "WHERE provider_payment_id = :ppid LIMIT 1"
                ),
                {"ppid": provider_payment_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def create_refund_record(
    db: AsyncSession,
    order_id: str,
    provider: str,
    provider_refund_id: str,
    amount: int,
    currency: str = "USD",
) -> dict[str, Any]:
    """Insert a refund record (negative amount in payment_records)."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.payment_records "
                    "(order_id, provider, provider_payment_id, status, amount, currency, method) "
                    "VALUES (:oid, :prov, :prid, 'refunded', :amount, :currency, 'refund') "
                    "RETURNING *"
                ),
                {
                    "oid": order_id,
                    "prov": provider,
                    "prid": provider_refund_id,
                    "amount": -abs(amount),
                    "currency": currency,
                },
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    return dict(row)
