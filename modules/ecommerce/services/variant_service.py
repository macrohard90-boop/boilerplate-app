"""Product variant CRUD with effective price calculation."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_variants(db: AsyncSession, product_id: str) -> list[dict[str, Any]]:
    """List all variants for a product with effective prices."""
    rows = (
        await db.execute(
            text(
                "SELECT v.*, p.base_price "
                "FROM ecommerce.product_variants v "
                "JOIN ecommerce.products p ON p.id = v.product_id "
                "WHERE v.product_id = :pid "
                "ORDER BY v.created_at"
            ),
            {"pid": product_id},
        )
    ).mappings().all()
    return [_with_effective_price(dict(r)) for r in rows]


async def get_variant(db: AsyncSession, variant_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                "SELECT v.*, p.base_price "
                "FROM ecommerce.product_variants v "
                "JOIN ecommerce.products p ON p.id = v.product_id "
                "WHERE v.id = :id"
            ),
            {"id": variant_id},
        )
    ).mappings().first()
    return _with_effective_price(dict(row)) if row else None


async def create_variant(db: AsyncSession, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
    attrs = json.dumps(data.get("attributes", {}))
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.product_variants "
                "(product_id, name, sku, price_override, stock_quantity, attributes) "
                "VALUES (:pid, :name, :sku, :price_override, :stock_quantity, CAST(:attributes AS jsonb)) "
                "RETURNING *"
            ),
            {
                "pid": product_id,
                "name": data["name"],
                "sku": data.get("sku"),
                "price_override": data.get("price_override"),
                "stock_quantity": data.get("stock_quantity", 0),
                "attributes": attrs,
            },
        )
    ).mappings().first()
    await db.commit()
    variant = dict(row)
    # Fetch base_price for effective price calc
    bp = (await db.execute(
        text("SELECT base_price FROM ecommerce.products WHERE id = :pid"),
        {"pid": product_id},
    )).scalar()
    variant["base_price"] = bp
    variant = _with_effective_price(variant)

    # Sync variant to catalog if parent product is active + synced
    product = (
        await db.execute(
            text("SELECT * FROM ecommerce.products WHERE id = :pid AND deleted_at IS NULL"),
            {"pid": product_id},
        )
    ).mappings().first()
    if product and product["status"] == "active" and product.get("stripe_product_id"):
        from modules.ecommerce.services import catalog_sync_service

        variant = await catalog_sync_service.sync_variant_to_catalog(
            db, variant, dict(product)
        )

    return variant


async def update_variant(db: AsyncSession, variant_id: str, data: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if data.get("name") is not None:
        fields["name"] = data["name"]
    if data.get("sku") is not None:
        fields["sku"] = data["sku"]
    if "price_override" in data:
        fields["price_override"] = data["price_override"]
    if data.get("stock_quantity") is not None:
        fields["stock_quantity"] = data["stock_quantity"]
    if data.get("attributes") is not None:
        fields["attributes"] = json.dumps(data["attributes"])

    if not fields:
        v = await get_variant(db, variant_id)
        if not v:
            raise ValueError("Variant not found")
        return v

    # Handle attributes cast
    set_parts = []
    for k in fields:
        if k == "attributes":
            set_parts.append(f"{k} = CAST(:{k} AS jsonb)")
        else:
            set_parts.append(f"{k} = :{k}")

    fields["id"] = variant_id
    row = (
        await db.execute(
            text(
                f"UPDATE ecommerce.product_variants SET {', '.join(set_parts)} "
                f"WHERE id = :id RETURNING *"
            ),
            fields,
        )
    ).mappings().first()
    if not row:
        raise ValueError("Variant not found")
    await db.commit()

    variant = dict(row)
    product_id = str(variant["product_id"])
    bp = (await db.execute(
        text("SELECT base_price FROM ecommerce.products WHERE id = :pid"),
        {"pid": product_id},
    )).scalar()
    variant["base_price"] = bp
    variant = _with_effective_price(variant)

    # Sync variant to catalog if price changed and parent product is active + synced
    if "price_override" in data:
        product = (
            await db.execute(
                text("SELECT * FROM ecommerce.products WHERE id = :pid AND deleted_at IS NULL"),
                {"pid": product_id},
            )
        ).mappings().first()
        if product and product["status"] == "active" and product.get("stripe_product_id"):
            from modules.ecommerce.services import catalog_sync_service

            variant = await catalog_sync_service.sync_variant_to_catalog(
                db, variant, dict(product)
            )

    return variant


async def delete_variant(db: AsyncSession, variant_id: str) -> None:
    result = await db.execute(
        text("DELETE FROM ecommerce.product_variants WHERE id = :id"),
        {"id": variant_id},
    )
    if result.rowcount == 0:
        raise ValueError("Variant not found")
    await db.commit()


def _with_effective_price(variant: dict[str, Any]) -> dict[str, Any]:
    """Add effective_price field: price_override if set, else product base_price."""
    base = variant.pop("base_price", 0) or 0
    variant["effective_price"] = variant["price_override"] if variant.get("price_override") is not None else base
    return variant
