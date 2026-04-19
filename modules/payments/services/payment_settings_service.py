"""Payment settings service — admin-configurable payment method toggles."""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Canonical list of supported payment method types
SUPPORTED_METHODS = [
    "card",
    "link",
    "apple_pay",
    "google_pay",
    "klarna",
    "afterpay_clearpay",
    "paypal",
]


async def get_setting(db: AsyncSession, key: str) -> dict[str, Any] | None:
    """Fetch a payment setting by key. Returns the JSONB value or None."""
    row = (
        (
            await db.execute(
                text("SELECT value FROM ecommerce.payment_settings WHERE key = :key"),
                {"key": key},
            )
        )
        .mappings()
        .first()
    )
    return dict(row["value"]) if row else None


async def upsert_setting(
    db: AsyncSession, key: str, value: dict[str, Any]
) -> dict[str, Any]:
    """Insert or update a payment setting. Returns the stored value."""
    import json

    await db.execute(
        text(
            "INSERT INTO ecommerce.payment_settings (key, value, updated_at) "
            "VALUES (:key, CAST(:val AS jsonb), NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = CAST(:val AS jsonb), updated_at = NOW()"
        ),
        {"key": key, "val": json.dumps(value)},
    )
    await db.commit()
    return value


async def delete_setting(db: AsyncSession, key: str) -> None:
    """Delete a payment setting by key."""
    await db.execute(
        text("DELETE FROM ecommerce.payment_settings WHERE key = :key"),
        {"key": key},
    )
    await db.commit()


async def get_enabled_payment_methods(db: AsyncSession) -> list[str] | None:
    """Return list of enabled payment method type strings, or None if no customization.

    When None is returned, the caller should use automatic_payment_methods.
    When a list is returned, the caller should pass it as payment_method_types.
    """
    methods = await get_setting(db, "payment_methods")
    if methods is None:
        return None

    enabled = [k for k, v in methods.items() if v is True and k in SUPPORTED_METHODS]

    # If nothing is enabled (admin disabled everything), fall back to automatic
    if not enabled:
        return None

    return enabled
