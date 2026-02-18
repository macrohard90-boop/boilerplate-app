"""Product CRUD with slug generation, pagination, search, and filtering."""

import math
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _unique_slug(db: AsyncSession, base_slug: str, exclude_id: str | None = None) -> str:
    """Generate a unique slug, appending -2, -3, etc. if taken."""
    slug = base_slug
    suffix = 1
    while True:
        q = "SELECT id FROM ecommerce.products WHERE slug = :slug"
        params: dict[str, Any] = {"slug": slug}
        if exclude_id:
            q += " AND id != :eid"
            params["eid"] = exclude_id
        row = (await db.execute(text(q), params)).first()
        if not row:
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"


async def list_products(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    category_id: str | None = None,
    search: str | None = None,
    product_type: str | None = None,
) -> dict[str, Any]:
    """List products with pagination, filtering, and search."""
    where_clauses = ["p.deleted_at IS NULL"]
    params: dict[str, Any] = {}

    if status:
        where_clauses.append("p.status = :status")
        params["status"] = status
    if product_type:
        where_clauses.append("p.type = :ptype")
        params["ptype"] = product_type
    if search:
        where_clauses.append("(p.name ILIKE :search OR p.description ILIKE :search)")
        params["search"] = f"%{search}%"
    if category_id:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM ecommerce.product_categories pc "
            "WHERE pc.product_id = p.id AND pc.category_id = :cat_id)"
        )
        params["cat_id"] = category_id

    where = " AND ".join(where_clauses)

    count_q = f"SELECT COUNT(*) FROM ecommerce.products p WHERE {where}"
    total = (await db.execute(text(count_q), params)).scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    items_q = (
        f"SELECT p.* FROM ecommerce.products p WHERE {where} "
        f"ORDER BY p.created_at DESC LIMIT :limit OFFSET :offset"
    )
    rows = (await db.execute(text(items_q), params)).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def get_product_by_slug(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    """Get a single product by slug (not soft-deleted)."""
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.products WHERE slug = :slug AND deleted_at IS NULL"),
            {"slug": slug},
        )
    ).mappings().first()
    return dict(row) if row else None


async def get_product_by_id(db: AsyncSession, product_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.products WHERE id = :id AND deleted_at IS NULL"),
            {"id": product_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def create_product(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Create a product with auto-generated slug."""
    slug = await _unique_slug(db, _slugify(data["name"]))
    category_ids = data.pop("category_ids", [])

    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.products (name, slug, description, sku, base_price, currency, status, type) "
                "VALUES (:name, :slug, :description, :sku, :base_price, :currency, :status, :type) "
                "RETURNING *"
            ),
            {
                "name": data["name"],
                "slug": slug,
                "description": data.get("description"),
                "sku": data.get("sku"),
                "base_price": data["base_price"],
                "currency": data.get("currency", "USD"),
                "status": data.get("status", "draft"),
                "type": data.get("type", "physical"),
            },
        )
    ).mappings().first()
    product = dict(row)

    if category_ids:
        await _set_categories(db, str(product["id"]), category_ids)

    await db.commit()

    # Sync to catalog if product is active
    if product.get("status") == "active":
        from modules.ecommerce.services import catalog_sync_service

        product = await catalog_sync_service.sync_product_to_catalog(db, product)

    return product


async def update_product(db: AsyncSession, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update a product. Only non-None fields are changed."""
    existing = await get_product_by_id(db, product_id)
    if not existing:
        raise ValueError("Product not found")

    category_ids = data.pop("category_ids", None)
    fields = {k: v for k, v in data.items() if v is not None}

    if "name" in fields:
        fields["slug"] = await _unique_slug(db, _slugify(fields["name"]), exclude_id=product_id)

    if fields:
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = product_id
        row = (
            await db.execute(
                text(f"UPDATE ecommerce.products SET {set_clause} WHERE id = :id RETURNING *"),
                fields,
            )
        ).mappings().first()
        product = dict(row)
    else:
        product = existing

    if category_ids is not None:
        await _set_categories(db, product_id, category_ids)

    await db.commit()

    # Catalog sync logic
    from modules.ecommerce.services import catalog_sync_service

    was_active = existing.get("status") == "active"
    is_active = product.get("status") == "active"
    sync_fields_changed = any(k in fields for k in ("name", "description", "base_price"))

    if is_active and (not was_active or sync_fields_changed):
        product = await catalog_sync_service.sync_product_to_catalog(db, product)
    elif was_active and not is_active:
        await catalog_sync_service.archive_product_in_catalog(db, product)

    return product


async def delete_product(db: AsyncSession, product_id: str) -> None:
    """Soft-delete a product and archive in catalog provider."""
    product = await get_product_by_id(db, product_id)
    if not product:
        raise ValueError("Product not found")

    result = await db.execute(
        text("UPDATE ecommerce.products SET deleted_at = NOW() WHERE id = :id AND deleted_at IS NULL"),
        {"id": product_id},
    )
    if result.rowcount == 0:
        raise ValueError("Product not found")
    await db.commit()

    # Archive in catalog provider if synced
    from modules.ecommerce.services import catalog_sync_service

    await catalog_sync_service.archive_product_in_catalog(db, product)


async def get_product_categories(db: AsyncSession, product_id: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT c.* FROM ecommerce.categories c "
                "JOIN ecommerce.product_categories pc ON pc.category_id = c.id "
                "WHERE pc.product_id = :pid ORDER BY c.sort_order"
            ),
            {"pid": product_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def _set_categories(db: AsyncSession, product_id: str, category_ids: list) -> None:
    """Replace product categories."""
    await db.execute(
        text("DELETE FROM ecommerce.product_categories WHERE product_id = :pid"),
        {"pid": product_id},
    )
    for cid in category_ids:
        await db.execute(
            text(
                "INSERT INTO ecommerce.product_categories (product_id, category_id) "
                "VALUES (:pid, :cid) ON CONFLICT DO NOTHING"
            ),
            {"pid": product_id, "cid": str(cid)},
        )
