"""Product catalog sync service.

Orchestrates syncing local products/variants to the configured payment
provider's product catalog (e.g. Stripe Products + Prices).  All
provider-specific logic lives in the adapter; this service only talks to
the ``CatalogProvider`` interface.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.payments.adapters import get_catalog_provider

logger = logging.getLogger(__name__)

# Provider name for synced_provider column
_PROVIDER_NAME = settings.payment_provider  # e.g. "stripe"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def sync_product_to_catalog(
    db: AsyncSession,
    product: dict[str, Any],
) -> dict[str, Any]:
    """Sync a product to the catalog provider (Stripe Product only, no Price).

    Prices are created per-variant via ``sync_variant_to_catalog()``.
    After all variants are synced the caller should call
    ``_copy_default_variant_price()`` to set the product-level
    ``stripe_price_id`` for backward compatibility.

    Called when:
    - Product status transitions to ``active``
    - An already-active product's name, description, or base_price changes.

    Returns the product dict with stripe_* fields updated.
    """
    provider = get_catalog_provider()
    if provider is None:
        logger.info("No catalog provider configured; skipping product sync")
        return product

    product_id = str(product["id"])

    # Build image URLs for provider if public_url is configured
    image_urls = await _get_product_image_urls(db, product_id)

    try:
        if product.get("stripe_product_id"):
            # Update existing catalog product (metadata only, no price)
            await provider.update_product(
                product["stripe_product_id"],
                name=product["name"],
                description=product.get("description"),
                active=product["status"] == "active",
                images=image_urls or None,
                metadata={"local_product_id": product_id},
            )
        else:
            # Create new catalog product (no price — variants own the prices)
            catalog_product = await provider.create_product(
                name=product["name"],
                description=product.get("description"),
                images=image_urls or None,
                metadata={"local_product_id": product_id},
            )
            await db.execute(
                text(
                    "UPDATE ecommerce.products "
                    "SET stripe_product_id = :spid, "
                    "    stripe_sync_status = 'synced', stripe_sync_error = NULL "
                    "WHERE id = :id"
                ),
                {
                    "id": product_id,
                    "spid": catalog_product.provider_product_id,
                },
            )
            await db.commit()

        # Mark synced and update in-memory dict
        await _mark_product_synced(db, product_id)
        product["stripe_sync_status"] = "synced"
        product["stripe_sync_error"] = None
        if not product.get("stripe_product_id"):
            row = (
                (
                    await db.execute(
                        text(
                            "SELECT stripe_product_id FROM ecommerce.products WHERE id = :id"
                        ),
                        {"id": product_id},
                    )
                )
                .mappings()
                .first()
            )
            if row:
                product["stripe_product_id"] = row["stripe_product_id"]

    except Exception as e:
        logger.error("Catalog sync failed for product %s: %s", product_id, e)
        await _mark_product_error(db, product_id, str(e))
        product["stripe_sync_status"] = "error"
        product["stripe_sync_error"] = str(e)

    return product


async def copy_default_variant_price(
    db: AsyncSession,
    product: dict[str, Any],
) -> dict[str, Any]:
    """Copy the first variant's stripe_price_id to the product row.

    This keeps ``product.stripe_price_id`` populated for backward compat
    (subscription service uses it as the default price).
    """
    product_id = str(product["id"])
    row = (
        (
            await db.execute(
                text(
                    "SELECT stripe_price_id FROM ecommerce.product_variants "
                    "WHERE product_id = :pid AND stripe_price_id IS NOT NULL "
                    "ORDER BY created_at LIMIT 1"
                ),
                {"pid": product_id},
            )
        )
        .mappings()
        .first()
    )
    if row and row["stripe_price_id"]:
        await db.execute(
            text(
                "UPDATE ecommerce.products SET stripe_price_id = :sprice WHERE id = :id"
            ),
            {"id": product_id, "sprice": row["stripe_price_id"]},
        )
        await db.commit()
        product["stripe_price_id"] = row["stripe_price_id"]
    return product


async def sync_product_images_to_catalog(
    db: AsyncSession,
    product_id: str,
) -> None:
    """Sync a product's images to the catalog provider (e.g. Stripe).

    Called after image upload or deletion.  No-op if the product isn't
    synced yet or ``public_url`` is not configured.
    """
    provider = get_catalog_provider()
    if provider is None:
        return

    row = (
        (
            await db.execute(
                text("SELECT stripe_product_id FROM ecommerce.products WHERE id = :id"),
                {"id": product_id},
            )
        )
        .mappings()
        .first()
    )
    if not row or not row["stripe_product_id"]:
        return

    image_urls = await _get_product_image_urls(db, product_id)
    try:
        await provider.update_product(
            row["stripe_product_id"],
            images=image_urls if image_urls else [],
        )
    except Exception as e:
        logger.warning("Failed to sync images for product %s: %s", product_id, e)


async def sync_variant_to_catalog(
    db: AsyncSession,
    variant: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    """Sync a variant's price to the catalog provider.

    Each variant gets its own catalog Price under the parent product's
    catalog Product.  Called when a variant is created or its
    ``price_override`` changes on an active, synced product.
    """
    provider = get_catalog_provider()
    if provider is None:
        return variant

    # Can only sync if parent product is synced
    stripe_product_id = product.get("stripe_product_id")
    if not stripe_product_id:
        return variant

    variant_id = str(variant["id"])
    variant_name = variant.get("name", "Variant")
    effective_price = variant.get("price_override") or product["base_price"]
    price_metadata = {
        "local_variant_id": variant_id,
        "local_product_id": str(product["id"]),
        "variant_name": variant_name,
        "type": "variant_price",
    }
    price_nickname = f"{product.get('name', 'Product')} — {variant_name}"

    try:
        if variant.get("stripe_price_id"):
            rotate_kwargs: dict[str, Any] = {
                "nickname": price_nickname,
                "metadata": price_metadata,
            }
            if product.get("pricing_type") == "recurring" and product.get(
                "recurring_interval"
            ):
                rotate_kwargs["recurring_interval"] = product["recurring_interval"]
                rotate_kwargs["recurring_interval_count"] = product.get(
                    "recurring_interval_count", 1
                )
            new_price = await _rotate_price(
                provider,
                stripe_product_id,
                variant["stripe_price_id"],
                effective_price,
                product.get("currency", "USD"),
                **rotate_kwargs,
            )
            if new_price:
                await db.execute(
                    text(
                        "UPDATE ecommerce.product_variants "
                        "SET stripe_price_id = :sprice, stripe_sync_status = 'synced', "
                        "    stripe_sync_error = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": variant_id, "sprice": new_price.provider_price_id},
                )
                variant["stripe_price_id"] = new_price.provider_price_id
        else:
            price_kwargs: dict[str, Any] = {
                "nickname": price_nickname,
                "metadata": price_metadata,
            }
            if product.get("pricing_type") == "recurring" and product.get(
                "recurring_interval"
            ):
                price_kwargs["recurring_interval"] = product["recurring_interval"]
                price_kwargs["recurring_interval_count"] = product.get(
                    "recurring_interval_count", 1
                )
            catalog_price = await provider.create_price(
                stripe_product_id,
                effective_price,
                product.get("currency", "USD"),
                **price_kwargs,
            )
            await db.execute(
                text(
                    "UPDATE ecommerce.product_variants "
                    "SET stripe_price_id = :sprice, stripe_sync_status = 'synced', "
                    "    stripe_sync_error = NULL "
                    "WHERE id = :id"
                ),
                {"id": variant_id, "sprice": catalog_price.provider_price_id},
            )
            variant["stripe_price_id"] = catalog_price.provider_price_id

        await db.commit()
        variant["stripe_sync_status"] = "synced"

    except Exception as e:
        logger.error("Catalog sync failed for variant %s: %s", variant_id, e)
        await db.execute(
            text(
                "UPDATE ecommerce.product_variants "
                "SET stripe_sync_status = 'error', stripe_sync_error = :err "
                "WHERE id = :id"
            ),
            {"id": variant_id, "err": str(e)},
        )
        await db.commit()
        variant["stripe_sync_status"] = "error"

    return variant


async def archive_product_in_catalog(
    db: AsyncSession,
    product: dict[str, Any],
) -> None:
    """Archive a product in the catalog provider.

    Called when a product is soft-deleted or status changes away from active.
    """
    provider = get_catalog_provider()
    if provider is None or not product.get("stripe_product_id"):
        return

    try:
        await provider.archive_product(product["stripe_product_id"])
        # Clear synced_provider since product is no longer active in catalog
        await db.execute(
            text(
                "UPDATE ecommerce.products "
                "SET stripe_sync_status = 'synced', stripe_sync_error = NULL, "
                "    synced_provider = NULL "
                "WHERE id = :id"
            ),
            {"id": str(product["id"])},
        )
        await db.commit()
    except Exception as e:
        logger.error("Catalog archive failed for product %s: %s", product["id"], e)


async def retry_sync(db: AsyncSession, product_id: str) -> dict[str, Any]:
    """Admin-initiated retry of a failed catalog sync.

    Re-syncs the product and all its variants.
    """
    from modules.ecommerce.services import product_service, variant_service

    product = await product_service.get_product_by_id(db, product_id)
    if not product:
        raise ValueError("Product not found")

    if product["status"] != "active":
        raise ValueError("Only active products can be synced to catalog")

    product = await sync_product_to_catalog(db, product)

    # Also sync all variants
    variants = await variant_service.list_variants(db, product_id)
    for v in variants:
        await sync_variant_to_catalog(db, v, product)

    product = await copy_default_variant_price(db, product)
    return product


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _rotate_price(
    provider,
    stripe_product_id: str,
    old_price_id: str | None,
    amount: int,
    currency: str,
    *,
    nickname: str | None = None,
    metadata: dict | None = None,
    recurring_interval: str | None = None,
    recurring_interval_count: int = 1,
):
    """Archive old price and create a new one.

    Returns the new CatalogPrice, or None if no rotation was needed.
    Always creates a new price (caller decides when to call this).
    """
    if old_price_id:
        try:
            await provider.archive_price(old_price_id)
        except Exception as e:
            logger.warning("Failed to archive old price %s: %s", old_price_id, e)

    return await provider.create_price(
        stripe_product_id,
        amount,
        currency,
        nickname=nickname,
        metadata=metadata,
        recurring_interval=recurring_interval,
        recurring_interval_count=recurring_interval_count,
    )


async def _mark_product_synced(db: AsyncSession, product_id: str) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.products "
            "SET stripe_sync_status = 'synced', stripe_sync_error = NULL, "
            "    synced_provider = :provider "
            "WHERE id = :id"
        ),
        {"id": product_id, "provider": _PROVIDER_NAME},
    )
    await db.commit()


async def _mark_product_error(
    db: AsyncSession, product_id: str, error_msg: str
) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.products "
            "SET stripe_sync_status = 'error', stripe_sync_error = :err, "
            "    synced_provider = NULL "
            "WHERE id = :id"
        ),
        {"id": product_id, "err": error_msg},
    )
    await db.commit()


async def _get_product_image_urls(db: AsyncSession, product_id: str) -> list[str]:
    """Build public image URLs for a product.

    Only returns URLs when ``public_url`` is configured (Stripe needs
    publicly accessible URLs to fetch images).
    """
    if not settings.public_url:
        return []

    rows = (
        (
            await db.execute(
                text(
                    "SELECT url FROM ecommerce.product_images "
                    "WHERE product_id = :pid ORDER BY sort_order, created_at "
                    "LIMIT 8"
                ),
                {"pid": product_id},
            )
        )
        .mappings()
        .all()
    )

    base = settings.public_url.rstrip("/")
    urls: list[str] = []
    for r in rows:
        url = r["url"]
        if url.startswith("/"):
            urls.append(f"{base}{url}")
        else:
            urls.append(url)
    return urls
