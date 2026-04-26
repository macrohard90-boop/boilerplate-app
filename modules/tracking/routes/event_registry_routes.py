"""Event Registry admin endpoints — browse, detail, toggle event definitions."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/events",
    tags=["admin-event-registry"],
    dependencies=[Depends(require_role("admin"))],
)


# ---------------------------------------------------------------------------
# GET /admin/events — list all definitions with 30-day stats
# ---------------------------------------------------------------------------


@router.get("")
async def list_event_definitions(
    category: str | None = Query(None),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all event definitions with fire count, last fired, and automation count."""
    where_parts = []
    params: dict = {}

    if category:
        where_parts.append("ed.category = :cat")
        params["cat"] = category
    if q:
        where_parts.append("ed.name ILIKE :q")
        params["q"] = f"%{q}%"

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    rows = (
        (
            await db.execute(
                text(
                    f"""
                SELECT
                    CAST(ed.id AS text) AS id,
                    ed.name,
                    ed.description,
                    ed.category,
                    ed.is_system,
                    ed.is_enabled,
                    ed.created_at,
                    COALESCE(es.fire_count, 0) AS fire_count_30d,
                    es.last_fired,
                    COALESCE(ac.auto_count, 0) AS automation_count
                FROM analytics.event_definitions ed
                LEFT JOIN (
                    SELECT event_type,
                           COUNT(*) AS fire_count,
                           MAX(created_at) AS last_fired
                    FROM analytics.events
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY event_type
                ) es ON es.event_type = ed.name
                LEFT JOIN (
                    SELECT trigger_event, COUNT(*) AS auto_count
                    FROM marketing.automation_flows
                    WHERE status IN ('active', 'paused', 'draft')
                    GROUP BY trigger_event
                ) ac ON ac.trigger_event = ed.name
                WHERE {where_clause}
                ORDER BY ed.category, ed.name
            """
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "definitions": [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "category": r["category"],
                "is_system": r["is_system"],
                "is_enabled": r["is_enabled"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "fire_count_30d": r["fire_count_30d"],
                "last_fired": (
                    r["last_fired"].isoformat() if r["last_fired"] else None
                ),
                "automation_count": r["automation_count"],
            }
            for r in rows
        ],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# GET /admin/events/by-name/{event_name} — single event detail
# ---------------------------------------------------------------------------


@router.get("/by-name/{event_name}")
async def get_event_by_name(
    event_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full detail for a single event definition by name."""
    row = (
        (
            await db.execute(
                text(
                    """
                SELECT
                    CAST(id AS text) AS id, name, description, category,
                    payload_schema, source_locations,
                    is_system, is_enabled, created_at
                FROM analytics.event_definitions
                WHERE name = :name
            """
                ),
                {"name": event_name},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Event definition not found")

    # Stats: total fires, 30d fires, unique users 30d
    stats = (
        (
            await db.execute(
                text(
                    """
                SELECT
                    COUNT(*) AS fire_count_total,
                    COUNT(*) FILTER (
                        WHERE created_at >= NOW() - INTERVAL '30 days'
                    ) AS fire_count_30d,
                    COUNT(DISTINCT user_id) FILTER (
                        WHERE created_at >= NOW() - INTERVAL '30 days'
                    ) AS unique_users_30d
                FROM analytics.events
                WHERE event_type = :name
            """
                ),
                {"name": event_name},
            )
        )
        .mappings()
        .first()
    )

    # Linked automations
    automations = (
        (
            await db.execute(
                text(
                    """
                SELECT CAST(id AS text) AS id, name, status
                FROM marketing.automation_flows
                WHERE trigger_event = :name
                  AND status IN ('active', 'paused', 'draft')
                ORDER BY status, name
            """
                ),
                {"name": event_name},
            )
        )
        .mappings()
        .all()
    )

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "payload_schema": row["payload_schema"] or [],
        "source_locations": row["source_locations"] or [],
        "is_system": row["is_system"],
        "is_enabled": row["is_enabled"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "fire_count_total": stats["fire_count_total"] if stats else 0,
        "fire_count_30d": stats["fire_count_30d"] if stats else 0,
        "unique_users_30d": stats["unique_users_30d"] if stats else 0,
        "automation_count": len(automations),
        "automations": [
            {"id": a["id"], "name": a["name"], "status": a["status"]}
            for a in automations
        ],
    }


# ---------------------------------------------------------------------------
# GET /admin/events/{event_id}/history — paginated fire history
# ---------------------------------------------------------------------------


@router.get("/{event_id}/history")
async def get_event_history(
    event_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Paginated fire history for a specific event definition."""
    # Resolve event name from ID
    ev = (
        (
            await db.execute(
                text(
                    "SELECT name FROM analytics.event_definitions WHERE id = CAST(:eid AS uuid)"
                ),
                {"eid": event_id},
            )
        )
        .mappings()
        .first()
    )

    if not ev:
        raise HTTPException(status_code=404, detail="Event definition not found")

    event_name = ev["name"]

    where_parts = ["e.event_type = :ename"]
    params: dict = {"ename": event_name}

    if date_from:
        where_parts.append("e.created_at >= CAST(:dfrom AS timestamptz)")
        params["dfrom"] = date_from
    if date_to:
        where_parts.append("e.created_at <= CAST(:dto AS timestamptz)")
        params["dto"] = date_to

    where_clause = " AND ".join(where_parts)
    offset = (page - 1) * page_size

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM analytics.events e WHERE {where_clause}"),
            params,
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    f"""
                SELECT
                    CAST(e.id AS text) AS id,
                    e.event_type,
                    e.event_data,
                    e.created_at,
                    e.session_id,
                    u.email AS user_email,
                    pv.path AS page_path
                FROM analytics.events e
                LEFT JOIN core.users u ON u.id = e.user_id
                LEFT JOIN LATERAL (
                    SELECT path FROM analytics.page_views
                    WHERE session_id = e.session_id
                      AND created_at <= e.created_at
                    ORDER BY created_at DESC LIMIT 1
                ) pv ON true
                WHERE {where_clause}
                ORDER BY e.created_at DESC
                LIMIT :lim OFFSET :off
            """
                ),
                {**params, "lim": page_size, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "event_data": r["event_data"] or {},
                "created_at": (
                    r["created_at"].isoformat() if r["created_at"] else None
                ),
                "session_id": r["session_id"],
                "user_email": r["user_email"],
                "page_path": r["page_path"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# PATCH /admin/events/{event_id}/toggle — enable/disable with validation
# ---------------------------------------------------------------------------


@router.patch("/{event_id}/toggle")
async def toggle_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle is_enabled. Refuses if active automations depend on this event."""
    from modules.tracking.services.event_service import invalidate_event_cache

    ev = (
        (
            await db.execute(
                text(
                    "SELECT CAST(id AS text) AS id, name, is_enabled "
                    "FROM analytics.event_definitions WHERE id = CAST(:eid AS uuid)"
                ),
                {"eid": event_id},
            )
        )
        .mappings()
        .first()
    )

    if not ev:
        raise HTTPException(status_code=404, detail="Event definition not found")

    new_enabled = not ev["is_enabled"]

    # If disabling, check for active automations
    if not new_enabled:
        active_flows = (
            (
                await db.execute(
                    text(
                        """
                    SELECT CAST(id AS text) AS id, name
                    FROM marketing.automation_flows
                    WHERE trigger_event = :ename AND status = 'active'
                """
                    ),
                    {"ename": ev["name"]},
                )
            )
            .mappings()
            .all()
        )

        if active_flows:
            flow_names = [f["name"] for f in active_flows]
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "cannot_disable",
                    "message": (
                        f"Cannot disable event '{ev['name']}': "
                        f"{len(active_flows)} active automation(s) depend on it. "
                        "Pause them first."
                    ),
                    "flows": flow_names,
                },
            )

    await db.execute(
        text(
            "UPDATE analytics.event_definitions "
            "SET is_enabled = :enabled WHERE id = CAST(:eid AS uuid)"
        ),
        {"enabled": new_enabled, "eid": event_id},
    )
    await db.commit()

    invalidate_event_cache()

    return {"id": ev["id"], "name": ev["name"], "is_enabled": new_enabled}
