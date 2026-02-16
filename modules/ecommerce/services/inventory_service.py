"""Inventory management: stock checks, reservations, adjustments."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_stock(db: AsyncSession, variant_id: str, quantity: int) -> bool:
    """Return True if variant has enough stock."""
    row = (
        await db.execute(
            text("SELECT stock_quantity FROM ecommerce.product_variants WHERE id = :id"),
            {"id": variant_id},
        )
    ).first()
    if not row:
        return False
    return row[0] >= quantity


async def get_stock(db: AsyncSession, variant_id: str) -> int:
    row = (
        await db.execute(
            text("SELECT stock_quantity FROM ecommerce.product_variants WHERE id = :id"),
            {"id": variant_id},
        )
    ).first()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Stock reservation (Wave 3 — used during checkout)
# ---------------------------------------------------------------------------

async def reserve_stock(
    db: AsyncSession,
    variant_id: str,
    quantity: int,
    reference_id: str | None = None,
) -> None:
    """Reserve stock using SELECT FOR UPDATE to prevent oversell.

    Raises ValueError if insufficient stock.
    """
    row = (
        await db.execute(
            text(
                "SELECT stock_quantity FROM ecommerce.product_variants "
                "WHERE id = :id FOR UPDATE"
            ),
            {"id": variant_id},
        )
    ).first()

    if not row:
        raise ValueError(f"Variant {variant_id} not found")
    if row[0] < quantity:
        raise ValueError(f"Insufficient stock for variant {variant_id}: have {row[0]}, need {quantity}")

    await db.execute(
        text(
            "UPDATE ecommerce.product_variants "
            "SET stock_quantity = stock_quantity - :qty WHERE id = :id"
        ),
        {"id": variant_id, "qty": quantity},
    )

    await db.execute(
        text(
            "INSERT INTO ecommerce.inventory_records (variant_id, quantity_change, reason, reference_id) "
            "VALUES (:vid, :qty, :reason, :ref)"
        ),
        {
            "vid": variant_id,
            "qty": -quantity,
            "reason": "order_reservation",
            "ref": reference_id,
        },
    )


async def release_stock(
    db: AsyncSession,
    variant_id: str,
    quantity: int,
    reference_id: str | None = None,
) -> None:
    """Release previously reserved stock (e.g., on order cancellation)."""
    await db.execute(
        text(
            "UPDATE ecommerce.product_variants "
            "SET stock_quantity = stock_quantity + :qty WHERE id = :id"
        ),
        {"id": variant_id, "qty": quantity},
    )
    await db.execute(
        text(
            "INSERT INTO ecommerce.inventory_records (variant_id, quantity_change, reason, reference_id) "
            "VALUES (:vid, :qty, :reason, :ref)"
        ),
        {
            "vid": variant_id,
            "qty": quantity,
            "reason": "stock_release",
            "ref": reference_id,
        },
    )


async def adjust_stock(
    db: AsyncSession,
    variant_id: str,
    quantity_change: int,
    reason: str,
) -> dict[str, Any]:
    """Manual stock adjustment by admin."""
    await db.execute(
        text(
            "UPDATE ecommerce.product_variants "
            "SET stock_quantity = stock_quantity + :qty WHERE id = :id"
        ),
        {"id": variant_id, "qty": quantity_change},
    )
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.inventory_records (variant_id, quantity_change, reason) "
                "VALUES (:vid, :qty, :reason) RETURNING *"
            ),
            {"vid": variant_id, "qty": quantity_change, "reason": reason},
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def get_low_stock(db: AsyncSession, threshold: int = 10) -> list[dict[str, Any]]:
    """Return variants with stock below threshold."""
    rows = (
        await db.execute(
            text(
                "SELECT v.id AS variant_id, v.product_id, p.name AS product_name, "
                "v.name AS variant_name, v.stock_quantity, v.sku "
                "FROM ecommerce.product_variants v "
                "JOIN ecommerce.products p ON p.id = v.product_id "
                "WHERE v.stock_quantity < :threshold AND p.deleted_at IS NULL "
                "ORDER BY v.stock_quantity ASC"
            ),
            {"threshold": threshold},
        )
    ).mappings().all()
    return [dict(r) for r in rows]
