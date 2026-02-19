"""Fee tier service — volume-based platform fees with per-merchant overrides."""

import logging
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global fee tiers CRUD
# ---------------------------------------------------------------------------


async def list_default_tiers(db: AsyncSession) -> list[dict[str, Any]]:
    """List all global default fee tiers sorted by sort_order."""
    rows = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.fee_tiers "
                "WHERE is_default = TRUE "
                "ORDER BY sort_order"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def create_tier(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Create a global fee tier."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.fee_tiers "
                "(name, min_volume, max_volume, fee_percent, fee_flat, sort_order, is_default) "
                "VALUES (:name, :min_volume, :max_volume, :fee_percent, :fee_flat, :sort_order, TRUE) "
                "RETURNING *"
            ),
            {
                "name": data["name"],
                "min_volume": data.get("min_volume", 0),
                "max_volume": data.get("max_volume"),
                "fee_percent": data["fee_percent"],
                "fee_flat": data.get("fee_flat", 0),
                "sort_order": data.get("sort_order", 0),
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def update_tier(
    db: AsyncSession, tier_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Update a global fee tier."""
    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        raise ValueError("No fields to update")

    fields["updated_at"] = text("NOW()")
    set_parts = []
    params: dict[str, Any] = {"tid": tier_id}
    for k, v in fields.items():
        if k == "updated_at":
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    row = (
        await db.execute(
            text(
                f"UPDATE ecommerce.fee_tiers SET {', '.join(set_parts)} "
                "WHERE id = :tid RETURNING *"
            ),
            params,
        )
    ).mappings().first()
    if not row:
        raise ValueError("Fee tier not found")
    await db.commit()
    return dict(row)


async def delete_tier(db: AsyncSession, tier_id: str) -> None:
    """Delete a global fee tier."""
    result = await db.execute(
        text("DELETE FROM ecommerce.fee_tiers WHERE id = :tid AND is_default = TRUE"),
        {"tid": tier_id},
    )
    if result.rowcount == 0:
        raise ValueError("Fee tier not found")
    await db.commit()


# ---------------------------------------------------------------------------
# Per-merchant overrides
# ---------------------------------------------------------------------------


async def get_merchant_overrides(
    db: AsyncSession, merchant_account_id: str
) -> list[dict[str, Any]]:
    """Get custom fee tiers for a specific merchant."""
    rows = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.merchant_fee_overrides "
                "WHERE merchant_account_id = :mid "
                "ORDER BY sort_order"
            ),
            {"mid": merchant_account_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def set_merchant_overrides(
    db: AsyncSession, merchant_account_id: str, tiers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace all custom fee tiers for a merchant."""
    await db.execute(
        text(
            "DELETE FROM ecommerce.merchant_fee_overrides "
            "WHERE merchant_account_id = :mid"
        ),
        {"mid": merchant_account_id},
    )

    results = []
    for i, tier in enumerate(tiers):
        row = (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.merchant_fee_overrides "
                    "(merchant_account_id, fee_percent, fee_flat, min_volume, max_volume, sort_order) "
                    "VALUES (:mid, :fp, :ff, :minv, :maxv, :so) "
                    "RETURNING *"
                ),
                {
                    "mid": merchant_account_id,
                    "fp": tier["fee_percent"],
                    "ff": tier.get("fee_flat", 0),
                    "minv": tier.get("min_volume", 0),
                    "maxv": tier.get("max_volume"),
                    "so": i + 1,
                },
            )
        ).mappings().first()
        results.append(dict(row))

    await db.commit()
    return results


async def clear_merchant_overrides(
    db: AsyncSession, merchant_account_id: str
) -> None:
    """Remove all custom fee overrides for a merchant (revert to global defaults)."""
    await db.execute(
        text(
            "DELETE FROM ecommerce.merchant_fee_overrides "
            "WHERE merchant_account_id = :mid"
        ),
        {"mid": merchant_account_id},
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Fee calculation
# ---------------------------------------------------------------------------


async def calculate_fee(
    db: AsyncSession, merchant_account_id: str, amount: int
) -> dict[str, Any]:
    """Calculate the platform fee for a transaction.

    Uses per-merchant overrides if they exist, otherwise falls back to
    global default tiers. Matches the tier based on the merchant's
    total_sales_volume.

    Returns: {"fee_percent": float, "fee_flat": int, "total_fee": int}
    """
    # Get merchant's current sales volume
    row = (
        await db.execute(
            text(
                "SELECT total_sales_volume FROM ecommerce.merchant_accounts "
                "WHERE id = :mid"
            ),
            {"mid": merchant_account_id},
        )
    ).mappings().first()

    volume = int(row["total_sales_volume"]) if row else 0

    # Try merchant overrides first
    overrides = await get_merchant_overrides(db, merchant_account_id)
    tiers = overrides if overrides else await list_default_tiers(db)

    # Find matching tier
    matched_percent = 10.0  # fallback
    matched_flat = 0
    for tier in tiers:
        tier_min = tier.get("min_volume", 0) or 0
        tier_max = tier.get("max_volume")
        if volume >= tier_min and (tier_max is None or volume <= tier_max):
            matched_percent = float(tier["fee_percent"])
            matched_flat = int(tier.get("fee_flat", 0))
            break

    total_fee = int(amount * matched_percent / 100) + matched_flat
    if total_fee < 0:
        total_fee = 0

    return {
        "fee_percent": matched_percent,
        "fee_flat": matched_flat,
        "total_fee": total_fee,
    }


async def increment_merchant_volume(
    db: AsyncSession, merchant_account_id: str, amount: int
) -> None:
    """Add to a merchant's aggregate sales volume after a successful payment."""
    await db.execute(
        text(
            "UPDATE ecommerce.merchant_accounts "
            "SET total_sales_volume = total_sales_volume + :amt "
            "WHERE id = :mid"
        ),
        {"mid": merchant_account_id, "amt": amount},
    )
    await db.commit()
