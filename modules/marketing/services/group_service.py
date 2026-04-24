"""Audience group & preset management — CRUD, reorder, move."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Groups CRUD
# ---------------------------------------------------------------------------


async def list_groups(db: AsyncSession) -> list[dict[str, Any]]:
    """List all groups with their presets, ordered by display_order."""
    group_rows = (
        (
            await db.execute(
                text(
                    "SELECT id, name, display_order, created_at, updated_at "
                    "FROM marketing.audience_groups "
                    "ORDER BY display_order, name"
                )
            )
        )
        .mappings()
        .all()
    )

    groups: list[dict[str, Any]] = []
    for g in group_rows:
        preset_rows = (
            (
                await db.execute(
                    text(
                        "SELECT id, group_id, preset_key, label, detail, color, "
                        "filters, is_dynamic, display_order, created_at, updated_at "
                        "FROM marketing.audience_group_presets "
                        "WHERE group_id = :gid "
                        "ORDER BY display_order, label"
                    ),
                    {"gid": str(g["id"])},
                )
            )
            .mappings()
            .all()
        )
        groups.append(
            {
                "id": str(g["id"]),
                "name": g["name"],
                "display_order": g["display_order"],
                "created_at": str(g["created_at"]),
                "updated_at": str(g["updated_at"]),
                "presets": [_preset_to_dict(p) for p in preset_rows],
            }
        )

    # Also include uncategorized presets (group_id IS NULL)
    uncategorized_rows = (
        (
            await db.execute(
                text(
                    "SELECT id, group_id, preset_key, label, detail, color, "
                    "filters, is_dynamic, display_order, created_at, updated_at "
                    "FROM marketing.audience_group_presets "
                    "WHERE group_id IS NULL "
                    "ORDER BY display_order, label"
                )
            )
        )
        .mappings()
        .all()
    )
    if uncategorized_rows:
        groups.append(
            {
                "id": None,
                "name": "Uncategorized",
                "display_order": 999,
                "created_at": None,
                "updated_at": None,
                "presets": [_preset_to_dict(p) for p in uncategorized_rows],
            }
        )

    return groups


async def create_group(
    db: AsyncSession, name: str, display_order: int = 0
) -> dict[str, Any]:
    """Create a new audience group."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.audience_groups (name, display_order) "
                    "VALUES (:name, :dorder) "
                    "RETURNING id, name, display_order, created_at, updated_at"
                ),
                {"name": name, "dorder": display_order},
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    logger.info("Audience group created: %s (%s)", row["id"], name)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "display_order": row["display_order"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "presets": [],
    }


async def update_group(
    db: AsyncSession,
    group_id: str,
    name: str | None = None,
    display_order: int | None = None,
) -> dict[str, Any]:
    """Update group name and/or display_order."""
    sets: list[str] = []
    params: dict[str, Any] = {"gid": group_id}

    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if display_order is not None:
        sets.append("display_order = :dorder")
        params["dorder"] = display_order

    if not sets:
        raise ValueError("No fields to update")

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE marketing.audience_groups SET {', '.join(sets)} "
                    f"WHERE id = :gid "
                    f"RETURNING id, name, display_order, created_at, updated_at"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Group not found")

    await db.commit()
    logger.info("Audience group updated: %s", group_id)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "display_order": row["display_order"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


async def delete_group(db: AsyncSession, group_id: str) -> None:
    """Delete group. Presets get group_id=NULL (ON DELETE SET NULL)."""
    result = await db.execute(
        text("DELETE FROM marketing.audience_groups WHERE id = :gid"),
        {"gid": group_id},
    )
    if result.rowcount == 0:
        raise ValueError("Group not found")
    await db.commit()
    logger.info("Audience group deleted: %s", group_id)


async def reorder_groups(db: AsyncSession, group_ids: list[str]) -> None:
    """Bulk reorder groups by setting display_order = index position."""
    for idx, gid in enumerate(group_ids):
        await db.execute(
            text(
                "UPDATE marketing.audience_groups "
                "SET display_order = :dorder WHERE id = :gid"
            ),
            {"dorder": idx, "gid": gid},
        )
    await db.commit()
    logger.info("Audience groups reordered: %d groups", len(group_ids))


# ---------------------------------------------------------------------------
# Preset operations
# ---------------------------------------------------------------------------


async def move_preset(
    db: AsyncSession, preset_id: str, target_group_id: str | None
) -> dict[str, Any]:
    """Move a preset to a different group (or null for uncategorized)."""
    row = (
        (
            await db.execute(
                text(
                    "UPDATE marketing.audience_group_presets "
                    "SET group_id = :tgid WHERE id = :pid "
                    "RETURNING id, group_id, preset_key, label, detail, color, "
                    "filters, is_dynamic, display_order, created_at, updated_at"
                ),
                {"tgid": target_group_id, "pid": preset_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Preset not found")

    await db.commit()
    logger.info(
        "Preset %s moved to group %s", preset_id, target_group_id or "(uncategorized)"
    )
    return _preset_to_dict(row)


async def reorder_presets(
    db: AsyncSession, group_id: str, preset_ids: list[str]
) -> None:
    """Reorder presets within a group."""
    for idx, pid in enumerate(preset_ids):
        await db.execute(
            text(
                "UPDATE marketing.audience_group_presets "
                "SET display_order = :dorder "
                "WHERE id = :pid AND group_id = :gid"
            ),
            {"dorder": idx, "pid": pid, "gid": group_id},
        )
    await db.commit()
    logger.info("Presets reordered in group %s: %d presets", group_id, len(preset_ids))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _preset_to_dict(r: Any) -> dict[str, Any]:
    """Convert a DB row mapping to a preset dict."""
    filters = r["filters"]
    if isinstance(filters, str):
        filters = json.loads(filters)
    return {
        "id": str(r["id"]),
        "group_id": str(r["group_id"]) if r["group_id"] else None,
        "preset_key": r["preset_key"],
        "label": r["label"],
        "detail": r["detail"],
        "color": r["color"],
        "filters": filters or {},
        "is_dynamic": r["is_dynamic"],
        "display_order": r["display_order"],
        "created_at": str(r["created_at"]),
        "updated_at": str(r["updated_at"]),
    }
