"""Product review management: one per user per product, moderation."""

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_reviews(
    db: AsyncSession,
    product_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = "approved",
) -> dict[str, Any]:
    """List reviews for a product. Public view shows only approved."""
    where = "product_id = :pid"
    params: dict[str, Any] = {"pid": product_id}
    if status:
        where += " AND status = :status"
        params["status"] = status

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM ecommerce.product_reviews WHERE {where}"), params
        )
    ).scalar() or 0

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = (
        await db.execute(
            text(
                f"SELECT * FROM ecommerce.product_reviews WHERE {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
    }


async def create_review(
    db: AsyncSession,
    product_id: str,
    user_id: str,
    rating: int,
    title: str | None,
    body: str | None,
) -> dict[str, Any]:
    """Create a review. One per user per product."""
    # Check for existing review
    existing = (
        await db.execute(
            text(
                "SELECT id FROM ecommerce.product_reviews "
                "WHERE product_id = :pid AND user_id = :uid"
            ),
            {"pid": product_id, "uid": user_id},
        )
    ).first()
    if existing:
        raise ValueError("You have already reviewed this product")

    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.product_reviews "
                "(product_id, user_id, rating, title, body, status) "
                "VALUES (:pid, :uid, :rating, :title, :body, 'pending') "
                "RETURNING *"
            ),
            {
                "pid": product_id,
                "uid": user_id,
                "rating": rating,
                "title": title,
                "body": body,
            },
        )
    ).mappings().first()
    await db.commit()
    return dict(row)


async def moderate_review(
    db: AsyncSession, review_id: str, status: str,
) -> dict[str, Any]:
    row = (
        await db.execute(
            text(
                "UPDATE ecommerce.product_reviews SET status = :status "
                "WHERE id = :rid RETURNING *"
            ),
            {"rid": review_id, "status": status},
        )
    ).mappings().first()
    if not row:
        raise ValueError("Review not found")
    await db.commit()
    return dict(row)
