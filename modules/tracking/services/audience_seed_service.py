"""Seed audience presets into analytics.saved_metrics.

Reads marketing.audience_group_presets and converts each preset's JSON
filters into a standalone SQL query, then upserts into analytics.saved_metrics
with is_audience=TRUE. Also creates linked marketing.audience_segments rows
so the /audience-metrics endpoint returns user counts.

This makes the Custom Metrics page and Campaign wizard share the same
audience CRUD — both read from analytics.saved_metrics.
"""

import json
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _inline_params(sql: str, params: dict[str, Any]) -> str:
    """Replace :param placeholders with literal SQL values.

    Produces a standalone SQL string without parameter bindings,
    suitable for storing in analytics.saved_metrics.sql_query.
    """
    result = sql
    # Sort keys by length descending to avoid partial replacements
    # e.g., :rfm_10 must be replaced before :rfm_1
    for key in sorted(params.keys(), key=len, reverse=True):
        val = params[key]
        if isinstance(val, str):
            escaped = val.replace("'", "''")
            literal = f"'{escaped}'"
        elif isinstance(val, bool):
            literal = "TRUE" if val else "FALSE"
        elif isinstance(val, (int, float)):
            literal = str(val)
        else:
            literal = f"'{val}'"
        result = re.sub(rf":{key}\b", literal, result)
    return result


def _filters_to_sql(filters: dict[str, Any]) -> str:
    """Convert a preset's JSON filters dict into a standalone SQL query.

    Uses segment_service._build_segment_query to generate the parameterized
    SQL, then inlines the parameters for storage.
    """
    from modules.marketing.services.segment_service import _build_segment_query

    sql_template, params = _build_segment_query(filters)
    return _inline_params(sql_template, params)


async def seed_audience_presets(
    db: AsyncSession,
    created_by: str,
) -> dict[str, Any]:
    """Seed all non-dynamic audience presets as saved metrics.

    Idempotent: uses preset_key to detect existing rows and updates them.

    Returns summary: {created: int, updated: int, skipped: int, details: list}
    """
    # Read all non-dynamic presets with their group names
    rows = (
        (
            await db.execute(
                text(
                    "SELECT p.id, p.preset_key, p.label, p.detail, p.color, "
                    "p.filters, p.display_order, g.name AS group_name "
                    "FROM marketing.audience_group_presets p "
                    "LEFT JOIN marketing.audience_groups g ON g.id = p.group_id "
                    "WHERE p.is_dynamic = FALSE "
                    "ORDER BY g.display_order NULLS LAST, p.display_order"
                )
            )
        )
        .mappings()
        .all()
    )

    created = 0
    updated = 0
    skipped = 0
    details: list[dict[str, str]] = []

    for row in rows:
        preset_key = row["preset_key"]
        label = row["label"]
        detail = row["detail"] or ""
        filters = row["filters"]
        group_name = row["group_name"]
        display_order = row["display_order"]

        if isinstance(filters, str):
            filters = json.loads(filters)

        # Generate SQL from filters
        try:
            sql_query = _filters_to_sql(filters or {})
        except Exception as e:
            logger.warning("Failed to generate SQL for preset %s: %s", preset_key, e)
            skipped += 1
            details.append(
                {"preset_key": preset_key, "status": "error", "error": str(e)}
            )
            continue

        # Check if a saved metric with this preset_key already exists
        existing = (
            await db.execute(
                text(
                    "SELECT id FROM analytics.saved_metrics " "WHERE preset_key = :pk"
                ),
                {"pk": preset_key},
            )
        ).fetchone()

        if existing:
            # Update existing metric
            await db.execute(
                text(
                    "UPDATE analytics.saved_metrics SET "
                    "name = :name, description = :desc, sql_query = :sql, "
                    "group_name = :gn, display_order = :dorder, "
                    "audience_filters = :af, updated_at = NOW() "
                    "WHERE preset_key = :pk"
                ),
                {
                    "name": label,
                    "desc": detail,
                    "sql": sql_query,
                    "gn": group_name,
                    "dorder": display_order,
                    "af": json.dumps(filters),
                    "pk": preset_key,
                },
            )
            metric_id = str(existing.id)
            updated += 1
            details.append({"preset_key": preset_key, "status": "updated"})
        else:
            # Insert new metric
            result = (
                await db.execute(
                    text(
                        "INSERT INTO analytics.saved_metrics "
                        "(name, description, sql_query, visualization_type, "
                        "created_by, group_name, display_order, is_audience, "
                        "audience_filters, preset_key) "
                        "VALUES (:name, :desc, :sql, 'table', :uid, :gn, "
                        ":dorder, TRUE, :af, :pk) "
                        "RETURNING id"
                    ),
                    {
                        "name": label,
                        "desc": detail,
                        "sql": sql_query,
                        "uid": created_by,
                        "gn": group_name,
                        "dorder": display_order,
                        "af": json.dumps(filters),
                        "pk": preset_key,
                    },
                )
            ).fetchone()
            metric_id = str(result.id)
            created += 1
            details.append({"preset_key": preset_key, "status": "created"})

        # Ensure a linked audience_segment exists
        seg_exists = (
            await db.execute(
                text(
                    "SELECT id FROM marketing.audience_segments "
                    "WHERE metric_id = :mid"
                ),
                {"mid": metric_id},
            )
        ).fetchone()

        if not seg_exists:
            await db.execute(
                text(
                    "INSERT INTO marketing.audience_segments "
                    "(name, description, filters, is_system, user_count, "
                    "last_computed_at, metric_id) "
                    "VALUES (:name, :desc, :filters, TRUE, 0, NULL, :mid)"
                ),
                {
                    "name": label,
                    "desc": detail,
                    "filters": json.dumps(filters),
                    "mid": metric_id,
                },
            )

    await db.commit()

    logger.info(
        "Audience preset seed: %d created, %d updated, %d skipped",
        created,
        updated,
        skipped,
    )

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "details": details,
    }
