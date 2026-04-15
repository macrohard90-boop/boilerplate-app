"""SEO snapshot service — captures page SEO state, computes diffs, audit trail."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


async def take_snapshot(
    db: AsyncSession,
    path: str,
    trigger: str = "manual",
    changed_by: str | None = None,
) -> dict[str, Any]:
    """Capture current SEO state and compute diff from previous snapshot."""
    # Fetch current meta
    current_meta = await get_meta_tags(db, path)

    # Optionally score
    score = None
    if settings.enable_seo_scoring:
        try:
            from modules.seo.adapters import get_scoring_provider
            from modules.seo.interfaces.scoring_provider import PageSEOData

            page_data = PageSEOData(
                path=path,
                title=current_meta.get("title"),
                description=current_meta.get("description"),
                canonical_url=current_meta.get("canonical_url"),
                robots=current_meta.get("robots", "index, follow"),
                og_tags=current_meta.get("og_tags"),
                twitter_tags=current_meta.get("twitter_tags"),
                structured_data=current_meta.get("structured_data"),
                is_custom=current_meta.get("is_custom", False),
            )
            provider = get_scoring_provider()
            result = await provider.score_page(page_data)
            score = result.score
        except Exception:
            logger.exception("Failed to score during snapshot for %s", path)

    # Build snapshot
    snapshot = {
        "title": current_meta.get("title"),
        "description": current_meta.get("description"),
        "robots": current_meta.get("robots"),
        "canonical_url": current_meta.get("canonical_url"),
        "og_tags": current_meta.get("og_tags"),
        "twitter_tags": current_meta.get("twitter_tags"),
        "structured_data": current_meta.get("structured_data"),
        "score": score,
        "is_custom": current_meta.get("is_custom"),
    }

    # Get previous snapshot for diff
    prev = await _get_latest_snapshot(db, path)
    diff = _compute_diff(prev, snapshot) if prev else None

    # Store
    row = (
        await db.execute(
            text(
                "INSERT INTO seo.page_snapshots (path, snapshot, trigger, changed_by, diff) "
                "VALUES (:path, :snapshot::jsonb, :trigger, :changed_by, :diff::jsonb) "
                "RETURNING id"
            ),
            {
                "path": path,
                "snapshot": json.dumps(snapshot),
                "trigger": trigger,
                "changed_by": changed_by,
                "diff": json.dumps(diff) if diff else None,
            },
        )
    ).scalar()
    await db.commit()

    return {"snapshot_id": str(row), "diff": diff, "score": score}


async def list_snapshots(
    db: AsyncSession, path: str, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """List snapshot history for a page, newest first."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(
            text("SELECT COUNT(*) FROM seo.page_snapshots WHERE path = :path"),
            {"path": path},
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                "SELECT id, path, snapshot, trigger, changed_by, diff, created_at "
                "FROM seo.page_snapshots WHERE path = :path "
                "ORDER BY created_at DESC LIMIT :lim OFFSET :off"
            ),
            {"path": path, "lim": page_size, "off": offset},
        )
    ).mappings().all()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "path": r["path"],
                "snapshot": r["snapshot"],
                "trigger": r["trigger"],
                "changed_by": str(r["changed_by"]) if r["changed_by"] else None,
                "diff": r["diff"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_snapshot(db: AsyncSession, snapshot_id: str) -> dict[str, Any] | None:
    """Get a single snapshot by ID."""
    row = (
        await db.execute(
            text(
                "SELECT id, path, snapshot, trigger, changed_by, diff, created_at "
                "FROM seo.page_snapshots WHERE id = :id"
            ),
            {"id": snapshot_id},
        )
    ).mappings().first()

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "path": row["path"],
        "snapshot": row["snapshot"],
        "trigger": row["trigger"],
        "changed_by": str(row["changed_by"]) if row["changed_by"] else None,
        "diff": row["diff"],
        "created_at": str(row["created_at"]),
    }


async def _get_latest_snapshot(
    db: AsyncSession, path: str
) -> dict[str, Any] | None:
    """Get the most recent snapshot for a path."""
    row = (
        await db.execute(
            text(
                "SELECT snapshot FROM seo.page_snapshots "
                "WHERE path = :path ORDER BY created_at DESC LIMIT 1"
            ),
            {"path": path},
        )
    ).mappings().first()

    if not row:
        return None
    return row["snapshot"]


def _compute_diff(
    prev: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any] | None:
    """Compute field-level diff between two snapshots."""
    diff: dict[str, Any] = {}
    # Compare simple fields
    for field in ("title", "description", "robots", "canonical_url", "score", "is_custom"):
        old_val = prev.get(field)
        new_val = current.get(field)
        if old_val != new_val:
            diff[field] = {"old": old_val, "new": new_val}

    # Compare complex fields by JSON serialization
    for field in ("og_tags", "twitter_tags", "structured_data"):
        old_val = prev.get(field)
        new_val = current.get(field)
        if json.dumps(old_val, sort_keys=True) != json.dumps(new_val, sort_keys=True):
            diff[field] = {"old": old_val, "new": new_val}

    return diff if diff else None
