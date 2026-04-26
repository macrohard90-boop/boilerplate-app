"""Custom event capture and aggregation."""

import json
import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache for event definitions (refreshed every 60s)
# ---------------------------------------------------------------------------

_event_defs_cache: dict[str, bool] = {}
_cache_loaded_at: float = 0.0
_CACHE_TTL = 60  # seconds


async def _load_event_defs(db: AsyncSession) -> None:
    """Refresh the in-memory event definitions cache from DB."""
    global _event_defs_cache, _cache_loaded_at
    rows = (
        (
            await db.execute(
                text("SELECT name, is_enabled FROM analytics.event_definitions")
            )
        )
        .mappings()
        .all()
    )
    _event_defs_cache = {r["name"]: r["is_enabled"] for r in rows}
    _cache_loaded_at = time.monotonic()


async def _is_event_allowed(db: AsyncSession, event_type: str) -> bool:
    """Check if an event type exists and is enabled."""
    if time.monotonic() - _cache_loaded_at > _CACHE_TTL:
        await _load_event_defs(db)
    if event_type not in _event_defs_cache:
        logger.warning("Unknown event_type '%s' — skipping recording", event_type)
        return False
    if not _event_defs_cache[event_type]:
        logger.debug("Disabled event_type '%s' — skipping recording", event_type)
        return False
    return True


def invalidate_event_cache() -> None:
    """Force cache refresh on next event recording."""
    global _cache_loaded_at
    _cache_loaded_at = 0.0


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------


async def record_event(
    db: AsyncSession,
    session_id: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
    user_id: str | None = None,
    campaign_id: str | None = None,
) -> None:
    """Insert a single event record."""
    if not await _is_event_allowed(db, event_type):
        return
    await db.execute(
        text(
            "INSERT INTO analytics.events "
            "(user_id, session_id, event_type, event_data, campaign_id) "
            "VALUES (:uid, :sid, :etype, CAST(:edata AS jsonb), :cid)"
        ),
        {
            "uid": user_id,
            "sid": session_id,
            "etype": event_type,
            "edata": json.dumps(event_data or {}),
            "cid": campaign_id,
        },
    )
    await db.commit()


async def record_events_batch(
    db: AsyncSession,
    session_id: str,
    items: list[dict[str, Any]],
    user_id: str | None = None,
) -> int:
    """Insert multiple events. Returns count inserted."""
    count = 0
    for item in items:
        if not await _is_event_allowed(db, item["event_type"]):
            continue
        await db.execute(
            text(
                "INSERT INTO analytics.events "
                "(user_id, session_id, event_type, event_data) "
                "VALUES (:uid, :sid, :etype, CAST(:edata AS jsonb))"
            ),
            {
                "uid": user_id,
                "sid": session_id,
                "etype": item["event_type"],
                "edata": json.dumps(item.get("event_data", {})),
            },
        )
        count += 1
    await db.commit()
    return count


async def get_event_stats(
    db: AsyncSession,
    date_from: str | None = None,
    date_to: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    """Get aggregate event statistics for admin dashboard."""
    where_clauses = []
    params: dict[str, Any] = {}

    if date_from:
        where_clauses.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("created_at <= :date_to")
        params["date_to"] = date_to
    if event_type:
        where_clauses.append("event_type = :etype")
        params["etype"] = event_type

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Total
    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM analytics.events WHERE {where}"),
            params,
        )
    ).scalar() or 0

    # By type
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT event_type, COUNT(*) AS count "
                    f"FROM analytics.events WHERE {where} "
                    f"GROUP BY event_type ORDER BY count DESC LIMIT 50"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "total_events": total,
        "by_type": [{"event_type": r["event_type"], "count": r["count"]} for r in rows],
    }
