"""Category CRUD with tree building."""

import math
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def _unique_slug(db: AsyncSession, base_slug: str, exclude_id: str | None = None) -> str:
    slug = base_slug
    suffix = 1
    while True:
        q = "SELECT id FROM ecommerce.categories WHERE slug = :slug"
        params: dict[str, Any] = {"slug": slug}
        if exclude_id:
            q += " AND id != :eid"
            params["eid"] = exclude_id
        row = (await db.execute(text(q), params)).first()
        if not row:
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"


async def list_categories_tree(db: AsyncSession) -> list[dict[str, Any]]:
    """Return all categories as a nested tree."""
    rows = (
        await db.execute(
            text("SELECT * FROM ecommerce.categories ORDER BY sort_order, name")
        )
    ).mappings().all()
    categories = [dict(r) for r in rows]
    return _build_tree(categories)


def _build_tree(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(c["id"]): {**c, "children": []} for c in categories}
    roots: list[dict[str, Any]] = []
    for c in categories:
        cid = str(c["id"])
        pid = str(c["parent_id"]) if c.get("parent_id") else None
        if pid and pid in by_id:
            by_id[pid]["children"].append(by_id[cid])
        else:
            roots.append(by_id[cid])
    return roots


async def get_category_by_slug(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.categories WHERE slug = :slug"),
            {"slug": slug},
        )
    ).mappings().first()
    return dict(row) if row else None


async def get_category_by_id(db: AsyncSession, category_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.categories WHERE id = :id"),
            {"id": category_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def create_category(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    slug = await _unique_slug(db, _slugify(data["name"]))
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.categories (name, slug, parent_id, description, sort_order) "
                "VALUES (:name, :slug, :parent_id, :description, :sort_order) "
                "RETURNING *"
            ),
            {
                "name": data["name"],
                "slug": slug,
                "parent_id": str(data["parent_id"]) if data.get("parent_id") else None,
                "description": data.get("description"),
                "sort_order": data.get("sort_order", 0),
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def update_category(db: AsyncSession, category_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = await get_category_by_id(db, category_id)
    if not existing:
        raise ValueError("Category not found")

    fields: dict[str, Any] = {}
    if data.get("name") is not None:
        fields["name"] = data["name"]
        fields["slug"] = await _unique_slug(db, _slugify(data["name"]), exclude_id=category_id)
    if "parent_id" in data:
        fields["parent_id"] = str(data["parent_id"]) if data["parent_id"] else None
    if "description" in data:
        fields["description"] = data["description"]
    if data.get("sort_order") is not None:
        fields["sort_order"] = data["sort_order"]

    if not fields:
        return existing

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = category_id
    row = (
        await db.execute(
            text(f"UPDATE ecommerce.categories SET {set_clause} WHERE id = :id RETURNING *"),
            fields,
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def delete_category(db: AsyncSession, category_id: str) -> None:
    result = await db.execute(
        text("DELETE FROM ecommerce.categories WHERE id = :id"),
        {"id": category_id},
    )
    if result.rowcount == 0:
        raise ValueError("Category not found")
    await db.commit()


async def get_category_products(
    db: AsyncSession,
    category_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """List active products in a category with pagination."""
    count_q = (
        "SELECT COUNT(*) FROM ecommerce.products p "
        "JOIN ecommerce.product_categories pc ON pc.product_id = p.id "
        "WHERE pc.category_id = :cid AND p.deleted_at IS NULL AND p.status = 'active'"
    )
    total = (await db.execute(text(count_q), {"cid": category_id})).scalar() or 0

    offset = (page - 1) * page_size
    items_q = (
        "SELECT p.* FROM ecommerce.products p "
        "JOIN ecommerce.product_categories pc ON pc.product_id = p.id "
        "WHERE pc.category_id = :cid AND p.deleted_at IS NULL AND p.status = 'active' "
        "ORDER BY p.created_at DESC LIMIT :limit OFFSET :offset"
    )
    rows = (
        await db.execute(text(items_q), {"cid": category_id, "limit": page_size, "offset": offset})
    ).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }
