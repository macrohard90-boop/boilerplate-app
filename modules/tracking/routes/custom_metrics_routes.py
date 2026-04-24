"""Admin custom metrics — SQL editor for analytics data."""

import hashlib
import json
import logging
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, require_role
from backend.core.redis import get_redis
from modules.tracking.models.schemas import (
    MetricReorderRequest,
    QueryExecuteRequest,
    QueryExecuteResponse,
    SavedMetricCreate,
    SavedMetricList,
    SavedMetricResponse,
    SavedMetricUpdate,
)
from modules.tracking.services.sql_safety_service import (
    SQLValidationError,
    validate_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/metrics",
    tags=["admin-custom-metrics"],
    dependencies=[Depends(require_role("admin"))],
)

CACHE_TTL = 300  # 5 minutes


# ── Helpers ─────────────────────────────────────────────────────────


def _serialize_value(v: Any) -> Any:
    """Convert a DB value to something JSON-safe."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dict, list)):
        return v
    return v


def _cache_key(sql: str) -> str:
    h = hashlib.sha256(sql.encode()).hexdigest()[:16]
    return f"metrics:result:{h}"


async def _execute_query(
    db: AsyncSession,
    redis: Redis,
    sql: str,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Validate, execute and optionally cache a SQL query."""

    # Validate
    safe_sql = validate_query(sql)

    # Check cache
    key = _cache_key(safe_sql)
    if use_cache:
        cached = await redis.get(key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return data

    # Execute in read-only transaction with timeout
    start = time.monotonic()
    await db.execute(text("SET LOCAL statement_timeout = '10s'"))
    await db.execute(text("SET TRANSACTION READ ONLY"))
    result = await db.execute(text(safe_sql))
    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    columns = list(result.keys())
    rows_raw = result.fetchall()
    truncated = len(rows_raw) >= 1000

    rows = [[_serialize_value(v) for v in row] for row in rows_raw]

    response = {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "execution_time_ms": elapsed_ms,
        "truncated": truncated,
        "cached": False,
    }

    # Cache result
    await redis.set(key, json.dumps(response, default=str), ex=CACHE_TTL)

    return response


async def _validate_audience_query(
    db: AsyncSession,
    redis: Redis,
    sql: str,
) -> None:
    """Validate that a SQL query returns a user_id column (required for audience queries)."""
    result = await _execute_query(db, redis, sql, use_cache=True)
    columns_lower = [c.lower() for c in result["columns"]]
    if "user_id" not in columns_lower:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Audience queries must return a 'user_id' column. "
                f"Found columns: {', '.join(result['columns'])}"
            ),
        )


# ── Execute ad-hoc query ────────────────────────────────────────────


@router.post("/execute", response_model=QueryExecuteResponse)
async def execute_query(
    body: QueryExecuteRequest,
    nocache: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Execute an ad-hoc SQL query against analytics tables."""
    try:
        result = await _execute_query(db, redis, body.sql_query, use_cache=not nocache)
        return result
    except SQLValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("Custom metric query failed: %s", e)
        msg = str(e)
        # Surface PostgreSQL error message to admin
        if hasattr(e, "orig") and hasattr(e.orig, "pgerror"):
            msg = e.orig.pgerror
        raise HTTPException(status_code=400, detail=f"Query error: {msg}")


# ── CRUD: Saved Metrics ────────────────────────────────────────────


@router.get("/", response_model=SavedMetricList)
async def list_metrics(db: AsyncSession = Depends(get_db)):
    """List all saved metrics, grouped and ordered."""
    result = await db.execute(
        text(
            "SELECT id, name, description, sql_query, visualization_type, "
            "created_by, created_at, updated_at, group_name, display_order, "
            "is_audience "
            "FROM analytics.saved_metrics "
            "ORDER BY group_name NULLS LAST, display_order, created_at DESC"
        )
    )
    rows = result.fetchall()
    metrics = [
        SavedMetricResponse(
            id=str(r.id),
            name=r.name,
            description=r.description or "",
            sql_query=r.sql_query,
            visualization_type=r.visualization_type,
            created_by=str(r.created_by),
            created_at=r.created_at,
            updated_at=r.updated_at,
            group_name=r.group_name,
            display_order=r.display_order,
            is_audience=r.is_audience,
        )
        for r in rows
    ]
    return SavedMetricList(metrics=metrics, total=len(metrics))


@router.post("/", response_model=SavedMetricResponse, status_code=201)
async def create_metric(
    body: SavedMetricCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Create a saved metric (validates SQL first)."""
    try:
        validate_query(body.sql_query)
    except SQLValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate audience query returns user_id column
    if body.is_audience:
        await _validate_audience_query(db, redis, body.sql_query)

    # Auto-assign display_order as next in group
    order_result = await db.execute(
        text(
            "SELECT COALESCE(MAX(display_order), -1) + 1 AS next_order "
            "FROM analytics.saved_metrics "
            "WHERE group_name IS NOT DISTINCT FROM :gn"
        ),
        {"gn": body.group_name},
    )
    next_order = order_result.fetchone().next_order

    result = await db.execute(
        text(
            "INSERT INTO analytics.saved_metrics "
            "(name, description, sql_query, visualization_type, created_by, "
            "group_name, display_order, is_audience) "
            "VALUES (:name, :desc, :sql, :viz, :uid, :gn, :order, :is_aud) "
            "RETURNING id, name, description, sql_query, visualization_type, "
            "created_by, created_at, updated_at, group_name, display_order, "
            "is_audience"
        ),
        {
            "name": body.name,
            "desc": body.description,
            "sql": body.sql_query,
            "viz": body.visualization_type,
            "uid": user["user_id"],
            "gn": body.group_name,
            "order": next_order,
            "is_aud": body.is_audience,
        },
    )
    await db.commit()
    r = result.fetchone()
    return SavedMetricResponse(
        id=str(r.id),
        name=r.name,
        description=r.description or "",
        sql_query=r.sql_query,
        visualization_type=r.visualization_type,
        created_by=str(r.created_by),
        created_at=r.created_at,
        updated_at=r.updated_at,
        group_name=r.group_name,
        display_order=r.display_order,
        is_audience=r.is_audience,
    )


@router.put("/reorder")
async def reorder_metrics(
    body: MetricReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch update group_name and display_order for all metrics."""
    for item in body.items:
        await db.execute(
            text(
                "UPDATE analytics.saved_metrics "
                "SET group_name = :gn, display_order = :order, updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"id": item.id, "gn": item.group_name, "order": item.display_order},
        )
    await db.commit()
    return {"message": f"Reordered {len(body.items)} metrics"}


@router.get("/audience-metrics")
async def list_audience_metrics(db: AsyncSession = Depends(get_db)):
    """List saved metrics marked as audience queries, for the campaign wizard."""
    result = await db.execute(
        text(
            "SELECT sm.id, sm.name, sm.description, sm.group_name, "
            "sm.display_order, sm.created_at, sm.updated_at, "
            "COALESCE(seg.user_count, 0) AS user_count, "
            "seg.id AS segment_id "
            "FROM analytics.saved_metrics sm "
            "LEFT JOIN marketing.audience_segments seg ON seg.metric_id = sm.id "
            "WHERE sm.is_audience = TRUE "
            "ORDER BY sm.group_name NULLS LAST, sm.display_order, sm.created_at DESC"
        )
    )
    rows = result.mappings().all()
    metrics = [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "description": r["description"] or "",
            "group_name": r["group_name"],
            "display_order": r["display_order"],
            "user_count": r["user_count"],
            "segment_id": str(r["segment_id"]) if r["segment_id"] else None,
        }
        for r in rows
    ]
    return {"metrics": metrics, "total": len(metrics)}


@router.get("/{metric_id}", response_model=SavedMetricResponse)
async def get_metric(metric_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single saved metric."""
    result = await db.execute(
        text(
            "SELECT id, name, description, sql_query, visualization_type, "
            "created_by, created_at, updated_at, group_name, display_order, "
            "is_audience "
            "FROM analytics.saved_metrics WHERE id = :id"
        ),
        {"id": metric_id},
    )
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Metric not found")
    return SavedMetricResponse(
        id=str(r.id),
        name=r.name,
        description=r.description or "",
        sql_query=r.sql_query,
        visualization_type=r.visualization_type,
        created_by=str(r.created_by),
        created_at=r.created_at,
        updated_at=r.updated_at,
        group_name=r.group_name,
        display_order=r.display_order,
        is_audience=r.is_audience,
    )


@router.put("/{metric_id}", response_model=SavedMetricResponse)
async def update_metric(
    metric_id: str,
    body: SavedMetricUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Update a saved metric."""
    # Build SET clause dynamically
    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.sql_query is not None:
        try:
            validate_query(body.sql_query)
        except SQLValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        updates["sql_query"] = body.sql_query
    if body.visualization_type is not None:
        updates["visualization_type"] = body.visualization_type
    if body.group_name is not None:
        # Empty string means "remove from group" (set NULL)
        updates["group_name"] = body.group_name if body.group_name != "" else None
    if body.is_audience is not None:
        updates["is_audience"] = body.is_audience

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate audience query if toggling on or SQL changed while already audience
    needs_audience_check = body.is_audience is True
    if (
        not needs_audience_check
        and body.sql_query is not None
        and body.is_audience is None
    ):
        existing = await db.execute(
            text("SELECT is_audience FROM analytics.saved_metrics WHERE id = :id"),
            {"id": metric_id},
        )
        row = existing.fetchone()
        if row and row.is_audience:
            needs_audience_check = True
    if needs_audience_check:
        check_sql = body.sql_query
        if not check_sql:
            existing_q = await db.execute(
                text("SELECT sql_query FROM analytics.saved_metrics WHERE id = :id"),
                {"id": metric_id},
            )
            row = existing_q.fetchone()
            check_sql = row.sql_query if row else None
        if check_sql:
            await _validate_audience_query(db, redis, check_sql)

    updates["updated_at"] = "NOW()"
    set_parts = []
    params: dict[str, Any] = {"id": metric_id}
    for key, val in updates.items():
        if val == "NOW()":
            set_parts.append(f"{key} = NOW()")
        else:
            set_parts.append(f"{key} = :{key}")
            params[key] = val

    result = await db.execute(
        text(
            f"UPDATE analytics.saved_metrics SET {', '.join(set_parts)} "
            "WHERE id = :id "
            "RETURNING id, name, description, sql_query, visualization_type, "
            "created_by, created_at, updated_at, group_name, display_order, "
            "is_audience"
        ),
        params,
    )
    await db.commit()
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Invalidate old cache if SQL changed
    if body.sql_query is not None:
        await redis.delete(_cache_key(body.sql_query))

    return SavedMetricResponse(
        id=str(r.id),
        name=r.name,
        description=r.description or "",
        sql_query=r.sql_query,
        visualization_type=r.visualization_type,
        created_by=str(r.created_by),
        created_at=r.created_at,
        updated_at=r.updated_at,
        group_name=r.group_name,
        display_order=r.display_order,
        is_audience=r.is_audience,
    )


@router.delete("/{metric_id}")
async def delete_metric(
    metric_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a saved metric."""
    result = await db.execute(
        text("DELETE FROM analytics.saved_metrics WHERE id = :id RETURNING id"),
        {"id": metric_id},
    )
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Metric not found")
    return {"message": "Metric deleted"}


@router.post("/{metric_id}/run", response_model=QueryExecuteResponse)
async def run_metric(
    metric_id: str,
    nocache: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Execute a saved metric's query."""
    result = await db.execute(
        text("SELECT sql_query FROM analytics.saved_metrics WHERE id = :id"),
        {"id": metric_id},
    )
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Metric not found")

    try:
        data = await _execute_query(db, redis, r.sql_query, use_cache=not nocache)
        return data
    except SQLValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("Saved metric %s query failed: %s", metric_id, e)
        msg = str(e)
        if hasattr(e, "orig") and hasattr(e.orig, "pgerror"):
            msg = e.orig.pgerror
        raise HTTPException(status_code=400, detail=f"Query error: {msg}")
