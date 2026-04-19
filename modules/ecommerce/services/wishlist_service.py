"""Wishlist management: multiple wishlists per user, default auto-creation."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_create_default(db: AsyncSession, user_id: str) -> dict[str, Any]:
    """Get user's default wishlist, creating one if it doesn't exist."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM ecommerce.wishlists "
                    "WHERE user_id = :uid AND is_default = TRUE LIMIT 1"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    if row:
        return dict(row)

    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.wishlists (user_id, name, is_default) "
                    "VALUES (:uid, 'My Wishlist', TRUE) RETURNING *"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    return dict(row)


async def list_wishlists(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    """List all wishlists for a user with items."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT * FROM ecommerce.wishlists WHERE user_id = :uid ORDER BY created_at"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    wishlists = []
    for wl in rows:
        wl_dict = dict(wl)
        wl_dict["items"] = await _get_wishlist_items(db, str(wl["id"]))
        wishlists.append(wl_dict)
    return wishlists


async def create_wishlist(db: AsyncSession, user_id: str, name: str) -> dict[str, Any]:
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO ecommerce.wishlists (user_id, name, is_default) "
                    "VALUES (:uid, :name, FALSE) RETURNING *"
                ),
                {"uid": user_id, "name": name},
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    wl = dict(row)
    wl["items"] = []
    return wl


async def add_item(
    db: AsyncSession,
    user_id: str,
    wishlist_id: str | None,
    product_id: str,
    variant_id: str | None,
) -> dict[str, Any]:
    """Add item to wishlist. Uses default if wishlist_id not specified."""
    if not wishlist_id:
        wl = await get_or_create_default(db, user_id)
        wishlist_id = str(wl["id"])
    else:
        # Verify ownership
        wl = (
            await db.execute(
                text(
                    "SELECT id FROM ecommerce.wishlists WHERE id = :wid AND user_id = :uid"
                ),
                {"wid": wishlist_id, "uid": user_id},
            )
        ).first()
        if not wl:
            raise ValueError("Wishlist not found")

    await db.execute(
        text(
            "INSERT INTO ecommerce.wishlist_items (wishlist_id, product_id, variant_id) "
            "VALUES (:wid, :pid, :vid) ON CONFLICT (wishlist_id, product_id) DO NOTHING"
        ),
        {"wid": wishlist_id, "pid": product_id, "vid": variant_id},
    )
    await db.commit()

    items = await _get_wishlist_items(db, wishlist_id)
    row = (
        (
            await db.execute(
                text("SELECT * FROM ecommerce.wishlists WHERE id = :wid"),
                {"wid": wishlist_id},
            )
        )
        .mappings()
        .first()
    )
    result = dict(row)
    result["items"] = items
    return result


async def remove_item(
    db: AsyncSession,
    user_id: str,
    wishlist_id: str,
    product_id: str,
) -> None:
    # Verify ownership
    wl = (
        await db.execute(
            text(
                "SELECT id FROM ecommerce.wishlists WHERE id = :wid AND user_id = :uid"
            ),
            {"wid": wishlist_id, "uid": user_id},
        )
    ).first()
    if not wl:
        raise ValueError("Wishlist not found")

    result = await db.execute(
        text(
            "DELETE FROM ecommerce.wishlist_items "
            "WHERE wishlist_id = :wid AND product_id = :pid"
        ),
        {"wid": wishlist_id, "pid": product_id},
    )
    if result.rowcount == 0:
        raise ValueError("Item not in wishlist")
    await db.commit()


async def delete_wishlist(db: AsyncSession, user_id: str, wishlist_id: str) -> None:
    result = await db.execute(
        text(
            "DELETE FROM ecommerce.wishlists WHERE id = :wid AND user_id = :uid AND is_default = FALSE"
        ),
        {"wid": wishlist_id, "uid": user_id},
    )
    if result.rowcount == 0:
        raise ValueError("Wishlist not found or cannot delete default wishlist")
    await db.commit()


async def _get_wishlist_items(
    db: AsyncSession, wishlist_id: str
) -> list[dict[str, Any]]:
    rows = (
        (
            await db.execute(
                text(
                    "SELECT wi.product_id, wi.variant_id, wi.added_at, "
                    "p.name AS product_name, p.slug AS product_slug, p.base_price "
                    "FROM ecommerce.wishlist_items wi "
                    "JOIN ecommerce.products p ON p.id = wi.product_id "
                    "WHERE wi.wishlist_id = :wid ORDER BY wi.added_at"
                ),
                {"wid": wishlist_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
