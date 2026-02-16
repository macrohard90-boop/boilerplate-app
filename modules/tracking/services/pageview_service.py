"""Page view recording and aggregation queries."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_pageview(
    db: AsyncSession,
    session_id: str,
    path: str,
    user_id: str | None = None,
    referrer: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Insert a single page view record."""
    await db.execute(
        text(
            "INSERT INTO analytics.page_views "
            "(user_id, session_id, path, referrer, duration_ms) "
            "VALUES (:uid, :sid, :path, :ref, :dur)"
        ),
        {
            "uid": user_id,
            "sid": session_id,
            "path": path,
            "ref": referrer,
            "dur": duration_ms,
        },
    )
    await db.commit()


async def record_pageviews_batch(
    db: AsyncSession,
    session_id: str,
    items: list[dict[str, Any]],
    user_id: str | None = None,
) -> int:
    """Insert multiple page view records. Returns count inserted."""
    count = 0
    for item in items:
        await db.execute(
            text(
                "INSERT INTO analytics.page_views "
                "(user_id, session_id, path, referrer, duration_ms) "
                "VALUES (:uid, :sid, :path, :ref, :dur)"
            ),
            {
                "uid": user_id,
                "sid": session_id,
                "path": item["path"],
                "ref": item.get("referrer"),
                "dur": item.get("duration_ms"),
            },
        )
        count += 1
    await db.commit()
    return count


async def get_pageview_stats(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Get aggregate page view statistics for admin dashboard."""
    where_clauses = []
    params: dict[str, Any] = {"limit": limit}

    if date_from:
        where_clauses.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("created_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total views and unique visitors
    row = (
        await db.execute(
            text(
                f"SELECT COUNT(*) AS total_views, "
                f"COUNT(DISTINCT COALESCE(user_id::text, session_id)) AS unique_visitors "
                f"FROM analytics.page_views WHERE {where}"
            ),
            params,
        )
    ).mappings().first()

    # Top pages
    top = (
        await db.execute(
            text(
                f"SELECT path, COUNT(*) AS views, "
                f"COUNT(DISTINCT COALESCE(user_id::text, session_id)) AS unique_visitors "
                f"FROM analytics.page_views WHERE {where} "
                f"GROUP BY path ORDER BY views DESC LIMIT :limit"
            ),
            params,
        )
    ).mappings().all()

    return {
        "total_views": row["total_views"] if row else 0,
        "unique_visitors": row["unique_visitors"] if row else 0,
        "top_pages": [
            {"path": r["path"], "views": r["views"], "unique_visitors": r["unique_visitors"]}
            for r in top
        ],
    }
