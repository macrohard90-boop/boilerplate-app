"""Product image CRUD with primary flag management."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_images(db: AsyncSession, product_id: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            text(
                "SELECT * FROM ecommerce.product_images "
                "WHERE product_id = :pid ORDER BY sort_order, created_at"
            ),
            {"pid": product_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def get_image(db: AsyncSession, image_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text("SELECT * FROM ecommerce.product_images WHERE id = :id"),
            {"id": image_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def create_image(db: AsyncSession, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
    # If marking as primary, unset existing primary for this product
    if data.get("is_primary"):
        await _clear_primary(db, product_id)

    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.product_images "
                "(product_id, variant_id, url, alt_text, sort_order, is_primary) "
                "VALUES (:pid, :vid, :url, :alt_text, :sort_order, :is_primary) "
                "RETURNING *"
            ),
            {
                "pid": product_id,
                "vid": str(data["variant_id"]) if data.get("variant_id") else None,
                "url": data["url"],
                "alt_text": data.get("alt_text"),
                "sort_order": data.get("sort_order", 0),
                "is_primary": data.get("is_primary", False),
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def update_image(db: AsyncSession, image_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = await get_image(db, image_id)
    if not existing:
        raise ValueError("Image not found")

    # If setting as primary, clear others
    if data.get("is_primary"):
        await _clear_primary(db, str(existing["product_id"]))

    fields: dict[str, Any] = {}
    if data.get("url") is not None:
        fields["url"] = data["url"]
    if "alt_text" in data:
        fields["alt_text"] = data["alt_text"]
    if data.get("sort_order") is not None:
        fields["sort_order"] = data["sort_order"]
    if data.get("is_primary") is not None:
        fields["is_primary"] = data["is_primary"]
    if "variant_id" in data:
        fields["variant_id"] = str(data["variant_id"]) if data["variant_id"] else None

    if not fields:
        return existing

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = image_id
    row = (
        await db.execute(
            text(f"UPDATE ecommerce.product_images SET {set_clause} WHERE id = :id RETURNING *"),
            fields,
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def delete_image(db: AsyncSession, image_id: str) -> None:
    result = await db.execute(
        text("DELETE FROM ecommerce.product_images WHERE id = :id"),
        {"id": image_id},
    )
    if result.rowcount == 0:
        raise ValueError("Image not found")
    await db.commit()


async def _clear_primary(db: AsyncSession, product_id: str) -> None:
    await db.execute(
        text(
            "UPDATE ecommerce.product_images SET is_primary = FALSE "
            "WHERE product_id = :pid AND is_primary = TRUE"
        ),
        {"pid": product_id},
    )
