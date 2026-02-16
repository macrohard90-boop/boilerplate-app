"""Pricing tier lookup for quantity-based discounts."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_effective_unit_price(
    db: AsyncSession,
    product_id: str,
    variant_id: str,
    quantity: int,
    base_price: int,
) -> int:
    """Return the effective unit price considering pricing tiers.

    Checks variant-specific tiers first, then product-level tiers.
    Returns base_price if no tier matches.
    """
    # Check variant-specific tier
    row = (
        await db.execute(
            text(
                "SELECT price_per_unit FROM ecommerce.pricing_tiers "
                "WHERE product_id = :pid AND variant_id = :vid AND min_quantity <= :qty "
                "ORDER BY min_quantity DESC LIMIT 1"
            ),
            {"pid": product_id, "vid": variant_id, "qty": quantity},
        )
    ).first()
    if row:
        return row[0]

    # Check product-level tier (variant_id IS NULL)
    row = (
        await db.execute(
            text(
                "SELECT price_per_unit FROM ecommerce.pricing_tiers "
                "WHERE product_id = :pid AND variant_id IS NULL AND min_quantity <= :qty "
                "ORDER BY min_quantity DESC LIMIT 1"
            ),
            {"pid": product_id, "qty": quantity},
        )
    ).first()
    if row:
        return row[0]

    return base_price
