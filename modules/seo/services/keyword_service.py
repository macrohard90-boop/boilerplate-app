"""Keyword research and targeting service.

Manages keyword discovery, page targeting, and suggestion storage.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.seo.adapters import get_keyword_provider
from modules.seo.interfaces.keyword_provider import KeywordSuggestion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


async def discover_keywords(
    db: AsyncSession, seed: str, depth: int = 2, limit: int = 50
) -> list[dict[str, Any]]:
    """Discover keywords using the configured provider and store suggestions."""
    provider = get_keyword_provider()
    suggestions = await provider.expand_keywords(seed, depth=depth, limit=limit)

    # Store suggestions in DB
    for s in suggestions:
        await db.execute(
            text(
                "INSERT INTO seo.keyword_suggestions "
                "(keyword, search_volume, competition, trend, source, depth_level, seed_keyword) "
                "VALUES (:kw, :vol, :comp, :trend, :src, :depth, :seed) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "kw": s.keyword,
                "vol": s.search_volume,
                "comp": s.competition,
                "trend": s.trend,
                "src": s.source,
                "depth": s.depth_level,
                "seed": seed,
            },
        )
    await db.commit()

    return [_suggestion_to_dict(s) for s in suggestions]


# ---------------------------------------------------------------------------
# Target keywords CRUD
# ---------------------------------------------------------------------------


async def assign_keyword(
    db: AsyncSession,
    keyword: str,
    path: str | None = None,
    priority: int = 5,
    notes: str | None = None,
) -> dict[str, Any]:
    """Assign a target keyword to a page (or site-wide if path is None)."""
    result = await db.execute(
        text(
            "INSERT INTO seo.target_keywords (keyword, path, priority, notes) "
            "VALUES (:kw, :path, :pri, :notes) "
            "ON CONFLICT (keyword, COALESCE(path, '')) "
            "DO UPDATE SET priority = :pri, notes = :notes, updated_at = NOW() "
            "RETURNING id, keyword, path, priority, notes, created_at, updated_at"
        ),
        {"kw": keyword, "path": path, "pri": priority, "notes": notes},
    )
    row = result.mappings().first()
    await db.commit()
    return _target_row_to_dict(row)


async def remove_keyword(db: AsyncSession, keyword_id: str) -> bool:
    """Remove a target keyword by ID."""
    result = await db.execute(
        text("DELETE FROM seo.target_keywords WHERE id = :id RETURNING id"),
        {"id": keyword_id},
    )
    await db.commit()
    return result.rowcount > 0


async def get_target_keywords(db: AsyncSession, path: str) -> list[str]:
    """Get target keywords for a specific page (used by scoring engine).

    Returns keywords targeted to this specific path plus site-wide keywords.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT keyword FROM seo.target_keywords "
                    "WHERE path = :path OR path IS NULL "
                    "ORDER BY priority DESC"
                ),
                {"path": path},
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def list_target_keywords(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> dict[str, Any]:
    """List all target keywords (paginated)."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.target_keywords"))
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, keyword, path, priority, notes, created_at, updated_at "
                    "FROM seo.target_keywords ORDER BY priority DESC, keyword "
                    "LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [_target_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def update_keyword(
    db: AsyncSession,
    keyword_id: str,
    priority: int | None = None,
    notes: str | None = None,
    path: str | None = None,
) -> dict[str, Any] | None:
    """Update a target keyword's priority, notes, or path."""
    updates = []
    params: dict[str, Any] = {"id": keyword_id}

    if priority is not None:
        updates.append("priority = :pri")
        params["pri"] = priority
    if notes is not None:
        updates.append("notes = :notes")
        params["notes"] = notes
    if path is not None:
        updates.append("path = :path")
        params["path"] = path if path else None

    if not updates:
        return None

    updates.append("updated_at = NOW()")
    set_clause = ", ".join(updates)

    result = await db.execute(
        text(
            f"UPDATE seo.target_keywords SET {set_clause} WHERE id = :id "
            "RETURNING id, keyword, path, priority, notes, created_at, updated_at"
        ),
        params,
    )
    row = result.mappings().first()
    await db.commit()
    if not row:
        return None
    return _target_row_to_dict(row)


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


async def list_suggestions(
    db: AsyncSession,
    seed: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List keyword suggestions, optionally filtered by seed."""
    offset = (page - 1) * page_size
    where = ""
    params: dict[str, Any] = {"lim": page_size, "off": offset}

    if seed:
        where = "WHERE seed_keyword = :seed"
        params["seed"] = seed

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM seo.keyword_suggestions {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, keyword, search_volume, competition, trend, "
                    f"source, depth_level, seed_keyword, fetched_at "
                    f"FROM seo.keyword_suggestions {where} "
                    f"ORDER BY depth_level, keyword LIMIT :lim OFFSET :off"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [_suggestion_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Keyword density analysis
# ---------------------------------------------------------------------------


def analyze_keyword_density(content: str, keywords: list[str]) -> list[dict[str, Any]]:
    """Analyze keyword density in page content.

    Returns density info for each keyword:
    - count: number of occurrences
    - density: percentage of total words
    - status: "absent" (< 0.5%), "good" (0.5-2%), "high" (2-3%), "stuffing" (> 3%)
    """
    if not content or not keywords:
        return []

    words = content.lower().split()
    word_count = len(words)
    if word_count == 0:
        return [
            {"keyword": kw, "count": 0, "density": 0, "status": "absent"}
            for kw in keywords
        ]

    content_lower = content.lower()
    results: list[dict[str, Any]] = []

    for kw in keywords:
        kw_lower = kw.lower()
        # Count occurrences as substring (handles multi-word keywords)
        count = content_lower.count(kw_lower)
        # Density = (keyword word count * occurrences) / total words * 100
        kw_word_count = len(kw_lower.split())
        density = (count * kw_word_count / word_count) * 100 if word_count > 0 else 0

        if density < 0.5:
            status = "absent"
        elif density <= 2:
            status = "good"
        elif density <= 3:
            status = "high"
        else:
            status = "stuffing"

        results.append(
            {
                "keyword": kw,
                "count": count,
                "density": round(density, 2),
                "status": status,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suggestion_to_dict(s: KeywordSuggestion) -> dict[str, Any]:
    return {
        "keyword": s.keyword,
        "search_volume": s.search_volume,
        "competition": s.competition,
        "trend": s.trend,
        "source": s.source,
        "depth_level": s.depth_level,
    }


def _suggestion_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "keyword": row["keyword"],
        "search_volume": row["search_volume"],
        "competition": row["competition"],
        "trend": row["trend"],
        "source": row["source"],
        "depth_level": row["depth_level"],
        "seed_keyword": row["seed_keyword"],
        "fetched_at": str(row["fetched_at"]),
    }


def _target_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "keyword": row["keyword"],
        "path": row["path"],
        "priority": row["priority"],
        "notes": row["notes"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }
