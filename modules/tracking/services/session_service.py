"""Analytics session management.

Creates and updates analytics_sessions records. Uses Redis for
session activity tracking with configurable timeout.
"""

import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings


async def get_or_create_session(
    db: AsyncSession,
    redis: Redis,
    session_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Get existing analytics session or create a new one.

    Returns the session_id (existing or newly generated).
    Uses Redis key with TTL for activity tracking.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    redis_key = f"analytics:session:{session_id}"
    timeout = settings.tracking_session_timeout * 60  # Convert minutes to seconds

    # Check if session is active in Redis
    exists = await redis.exists(redis_key)

    if exists:
        # Session active — update last_active and increment page count
        await redis.expire(redis_key, timeout)
        await db.execute(
            text(
                "UPDATE analytics.analytics_sessions "
                "SET page_count = page_count + 1, ended_at = NOW() "
                "WHERE session_id = :sid"
            ),
            {"sid": session_id},
        )
        await db.commit()
    else:
        # New session — create Redis key and DB record
        await redis.setex(redis_key, timeout, "1")

        # Check if session exists in DB (could be expired Redis key)
        existing = (
            (
                await db.execute(
                    text(
                        "SELECT id FROM analytics.analytics_sessions "
                        "WHERE session_id = :sid"
                    ),
                    {"sid": session_id},
                )
            )
            .mappings()
            .first()
        )

        if existing:
            # Re-activate existing session
            await db.execute(
                text(
                    "UPDATE analytics.analytics_sessions "
                    "SET page_count = page_count + 1, ended_at = NOW() "
                    "WHERE session_id = :sid"
                ),
                {"sid": session_id},
            )
        else:
            await db.execute(
                text(
                    "INSERT INTO analytics.analytics_sessions "
                    "(user_id, session_id, page_count) "
                    "VALUES (:uid, :sid, 1)"
                ),
                {"uid": user_id, "sid": session_id},
            )
        await db.commit()

    return session_id


async def get_session_stats(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Get aggregate session statistics for admin dashboard."""
    where_clauses = []
    params: dict[str, Any] = {}

    if date_from:
        where_clauses.append("started_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("started_at <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Totals
    row = (
        (
            await db.execute(
                text(
                    f"SELECT COUNT(*) AS total, COALESCE(AVG(page_count), 0) AS avg_pages "
                    f"FROM analytics.analytics_sessions WHERE {where}"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    # By day
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT DATE(started_at) AS date, COUNT(*) AS sessions "
                    f"FROM analytics.analytics_sessions WHERE {where} "
                    f"GROUP BY DATE(started_at) ORDER BY date DESC LIMIT 30"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "total_sessions": row["total"] if row else 0,
        "avg_page_count": round(float(row["avg_pages"]), 1) if row else 0,
        "by_day": [{"date": str(r["date"]), "sessions": r["sessions"]} for r in rows],
    }
