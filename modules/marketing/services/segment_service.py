"""Audience segment management — CRUD, filter-to-SQL engine, count refresh."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filter-to-SQL engine
# ---------------------------------------------------------------------------


def _build_segment_query(
    filters: dict[str, Any],
    *,
    count_only: bool = False,
    limit: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Translate a segment filters dict into a SQL query + params.

    Always applies base eligibility:
      - marketing email consent (gdpr.email_preferences.marketing_email = true)
      - not suppressed (suppressed_at IS NULL)
      - account active + not soft-deleted

    Returns (sql_string, params_dict).
    """
    select = "COUNT(*) AS cnt" if count_only else "u.id AS user_id, u.email"
    joins: list[str] = [
        "JOIN gdpr.email_preferences ep ON ep.user_id = u.id",
    ]
    wheres: list[str] = [
        "ep.marketing_email = TRUE",
        "ep.suppressed_at IS NULL",
        "u.is_active = TRUE",
        "u.deleted_at IS NULL",
    ]
    params: dict[str, Any] = {}

    # --- Ecommerce customer metrics filters ---
    needs_cm = any(
        k in filters
        for k in (
            "rfm_segment",
            "order_count_min",
            "order_count_max",
            "total_spent_min",
            "total_spent_max",
            "last_purchase_days_max",
            "has_orders",
        )
    )
    if needs_cm:
        joins.append("LEFT JOIN ecommerce.customer_metrics cm ON cm.user_id = u.id")

    if "rfm_segment" in filters and filters["rfm_segment"]:
        segments = filters["rfm_segment"]
        if isinstance(segments, str):
            segments = [segments]
        placeholders = ", ".join(f":rfm_{i}" for i in range(len(segments)))
        wheres.append(f"cm.rfm_segment IN ({placeholders})")
        for i, seg in enumerate(segments):
            params[f"rfm_{i}"] = seg

    if "order_count_min" in filters and filters["order_count_min"] is not None:
        wheres.append("COALESCE(cm.order_count, 0) >= :oc_min")
        params["oc_min"] = int(filters["order_count_min"])

    if "order_count_max" in filters and filters["order_count_max"] is not None:
        wheres.append("COALESCE(cm.order_count, 0) <= :oc_max")
        params["oc_max"] = int(filters["order_count_max"])

    if "total_spent_min" in filters and filters["total_spent_min"] is not None:
        wheres.append("COALESCE(cm.total_spent, 0) >= :ts_min")
        params["ts_min"] = int(filters["total_spent_min"])

    if "total_spent_max" in filters and filters["total_spent_max"] is not None:
        wheres.append("COALESCE(cm.total_spent, 0) <= :ts_max")
        params["ts_max"] = int(filters["total_spent_max"])

    if (
        "last_purchase_days_max" in filters
        and filters["last_purchase_days_max"] is not None
    ):
        wheres.append("cm.last_purchase_at >= NOW() - INTERVAL '1 day' * :lp_days")
        params["lp_days"] = int(filters["last_purchase_days_max"])

    if filters.get("has_orders"):
        wheres.append("COALESCE(cm.order_count, 0) > 0")

    # --- Signup age filters ---
    if "signup_days_min" in filters and filters["signup_days_min"] is not None:
        wheres.append("u.created_at <= NOW() - INTERVAL '1 day' * :su_min")
        params["su_min"] = int(filters["signup_days_min"])

    if "signup_days_max" in filters and filters["signup_days_max"] is not None:
        wheres.append("u.created_at >= NOW() - INTERVAL '1 day' * :su_max")
        params["su_max"] = int(filters["signup_days_max"])

    # --- Cart status filter ---
    if "cart_status" in filters and filters["cart_status"]:
        joins.append("JOIN ecommerce.carts cart ON cart.user_id = u.id")
        wheres.append("cart.status = :cart_st")
        params["cart_st"] = filters["cart_status"]

    # --- Wishlist filter ---
    if filters.get("has_wishlist"):
        joins.append("JOIN ecommerce.wishlists wl ON wl.user_id = u.id")

    # --- Communication type filter ---
    if "communication_type" in filters and filters["communication_type"]:
        joins.append(
            "JOIN marketing.communication_types ct "
            "ON ct.name = :ct_name AND ct.enabled = TRUE"
        )
        joins.append(
            "JOIN marketing.user_communication_preferences ucp "
            "ON ucp.user_id = u.id AND ucp.communication_type_id = ct.id "
            "AND ucp.allowed = TRUE"
        )
        params["ct_name"] = filters["communication_type"]

    # --- Email verification filter ---
    if "is_verified" in filters and filters["is_verified"] is not None:
        wheres.append("u.is_verified = :verified")
        params["verified"] = bool(filters["is_verified"])

    join_clause = "\n".join(joins)
    where_clause = " AND ".join(wheres)
    limit_clause = f" LIMIT {int(limit)}" if limit else ""

    sql = (
        f"SELECT {select} FROM core.users u\n"
        f"{join_clause}\n"
        f"WHERE {where_clause}"
        f"{limit_clause}"
    )
    return sql, params


# ---------------------------------------------------------------------------
# Segment user queries
# ---------------------------------------------------------------------------


async def compute_segment_users(
    db: AsyncSession,
    filters: dict[str, Any],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return matching users for the given filter criteria."""
    sql, params = _build_segment_query(filters, limit=limit)
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [{"user_id": str(r["user_id"]), "email": r["email"]} for r in rows]


async def compute_segment_count(db: AsyncSession, filters: dict[str, Any]) -> int:
    """Fast COUNT(*) for the given filter criteria."""
    sql, params = _build_segment_query(filters, count_only=True)
    row = (await db.execute(text(sql), params)).mappings().first()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_segments(
    db: AsyncSession, include_system: bool = True
) -> list[dict[str, Any]]:
    """List audience segments."""
    where = "" if include_system else "WHERE is_system = FALSE"
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, name, description, filters, is_system, "
                    f"user_count, last_computed_at, created_at "
                    f"FROM marketing.audience_segments {where} "
                    f"ORDER BY is_system DESC, name"
                )
            )
        )
        .mappings()
        .all()
    )
    return [_row_to_dict(r) for r in rows]


async def get_segment(db: AsyncSession, segment_id: str) -> dict[str, Any]:
    """Get a single segment by ID."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, name, description, filters, is_system, "
                    "user_count, last_computed_at, created_at "
                    "FROM marketing.audience_segments WHERE id = :sid"
                ),
                {"sid": segment_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Segment not found")
    return _row_to_dict(row)


async def create_segment(
    db: AsyncSession,
    name: str,
    description: str | None,
    filters: dict[str, Any],
    created_by: str,
) -> dict[str, Any]:
    """Create a custom audience segment."""
    user_count = await compute_segment_count(db, filters)

    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.audience_segments "
                    "(name, description, filters, is_system, user_count, "
                    "last_computed_at, created_by) "
                    "VALUES (:name, :desc, :filters, FALSE, :cnt, NOW(), :uid) "
                    "RETURNING id, name, description, filters, is_system, "
                    "user_count, last_computed_at, created_at"
                ),
                {
                    "name": name,
                    "desc": description,
                    "filters": json.dumps(filters),
                    "cnt": user_count,
                    "uid": created_by,
                },
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    logger.info("Segment created: %s (%s) — %d users", row["id"], name, user_count)
    return _row_to_dict(row)


async def update_segment(
    db: AsyncSession,
    segment_id: str,
    name: str | None = None,
    description: str | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update a custom audience segment. Cannot update system segments."""
    existing = await get_segment(db, segment_id)
    if existing["is_system"]:
        raise ValueError("Cannot update system segments")

    sets: list[str] = []
    params: dict[str, Any] = {"sid": segment_id}

    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = description
    if filters is not None:
        sets.append("filters = :filters")
        params["filters"] = json.dumps(filters)
        user_count = await compute_segment_count(db, filters)
        sets.append("user_count = :cnt")
        sets.append("last_computed_at = NOW()")
        params["cnt"] = user_count

    if not sets:
        raise ValueError("No fields to update")

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE marketing.audience_segments SET {', '.join(sets)} "
                    f"WHERE id = :sid "
                    f"RETURNING id, name, description, filters, is_system, "
                    f"user_count, last_computed_at, created_at"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Segment not found")

    await db.commit()
    return _row_to_dict(row)


async def delete_segment(db: AsyncSession, segment_id: str) -> None:
    """Delete a custom segment. System segments cannot be deleted."""
    existing = await get_segment(db, segment_id)
    if existing["is_system"]:
        raise ValueError("Cannot delete system segments")

    await db.execute(
        text("DELETE FROM marketing.audience_segments WHERE id = :sid"),
        {"sid": segment_id},
    )
    await db.commit()
    logger.info("Segment deleted: %s", segment_id)


async def refresh_segment_counts(db: AsyncSession) -> int:
    """Recompute user_count for all segments. Returns number updated."""
    segments = await list_segments(db)
    updated = 0
    for seg in segments:
        filters = seg["filters"] if isinstance(seg["filters"], dict) else {}
        count = await compute_segment_count(db, filters)
        await db.execute(
            text(
                "UPDATE marketing.audience_segments "
                "SET user_count = :cnt, last_computed_at = NOW() "
                "WHERE id = :sid"
            ),
            {"cnt": count, "sid": seg["id"]},
        )
        updated += 1
    await db.commit()
    return updated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(r: Any) -> dict[str, Any]:
    """Convert a DB row mapping to a segment dict."""
    filters = r["filters"]
    if isinstance(filters, str):
        filters = json.loads(filters)
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "description": r["description"],
        "filters": filters or {},
        "is_system": r["is_system"],
        "user_count": r["user_count"] or 0,
        "last_computed_at": (
            str(r["last_computed_at"]) if r["last_computed_at"] else None
        ),
        "created_at": str(r["created_at"]),
    }
