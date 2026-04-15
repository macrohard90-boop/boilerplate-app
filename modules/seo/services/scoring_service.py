"""SEO scoring service — orchestrates meta fetching, scoring, and DB storage."""

import logging
from dataclasses import asdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.seo.adapters import get_scoring_provider
from modules.seo.interfaces.scoring_provider import PageSEOData, ScoreResult
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


async def score_page(db: AsyncSession, path: str) -> ScoreResult:
    """Score a page's SEO quality and store the result."""
    meta = await get_meta_tags(db, path)
    page_data = PageSEOData(
        path=path,
        title=meta.get("title"),
        description=meta.get("description"),
        canonical_url=meta.get("canonical_url"),
        robots=meta.get("robots", "index, follow"),
        og_tags=meta.get("og_tags"),
        twitter_tags=meta.get("twitter_tags"),
        structured_data=meta.get("structured_data"),
        is_custom=meta.get("is_custom", False),
    )

    provider = get_scoring_provider()
    result = await provider.score_page(page_data)

    # Store in DB
    rules_json = [asdict(r) for r in result.rules]
    await db.execute(
        text(
            "INSERT INTO seo.page_scores (path, score, rule_results, provider) "
            "VALUES (:path, :score, :rules::jsonb, :provider)"
        ),
        {
            "path": path,
            "score": result.score,
            "rules": _to_json(rules_json),
            "provider": result.provider,
        },
    )
    await db.commit()
    return result


async def score_all_pages(db: AsyncSession) -> list[dict[str, Any]]:
    """Score all known pages (from sitemap URLs + meta overrides)."""
    paths = await _collect_all_paths(db)
    results = []
    for path in paths:
        try:
            result = await score_page(db, path)
            results.append({"path": path, "score": result.score})
        except Exception:
            logger.exception("Failed to score path: %s", path)
    return results


async def get_latest_scores(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """Get the latest score for each page, paginated."""
    offset = (page - 1) * page_size

    # Use DISTINCT ON to get the latest score per path
    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT ON (path) id, path, score, rule_results, "
                "provider, scored_at "
                "FROM seo.page_scores ORDER BY path, scored_at DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"lim": page_size, "off": offset},
        )
    ).mappings().all()

    total = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT DISTINCT ON (path) path FROM seo.page_scores "
                "  ORDER BY path, scored_at DESC"
                ") sub"
            )
        )
    ).scalar() or 0

    return {
        "items": [
            {
                "id": str(r["id"]),
                "path": r["path"],
                "score": r["score"],
                "rule_results": r["rule_results"],
                "provider": r["provider"],
                "scored_at": str(r["scored_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_score_trend(
    db: AsyncSession, path: str, days: int = 30
) -> dict[str, Any]:
    """Get score history for a single page."""
    rows = (
        await db.execute(
            text(
                "SELECT score, scored_at FROM seo.page_scores "
                "WHERE path = :path "
                "AND scored_at >= NOW() - INTERVAL '1 day' * :days "
                "ORDER BY scored_at ASC"
            ),
            {"path": path, "days": days},
        )
    ).mappings().all()

    return {
        "path": path,
        "trend": [
            {"scored_at": str(r["scored_at"]), "score": r["score"]} for r in rows
        ],
    }


async def _collect_all_paths(db: AsyncSession) -> list[str]:
    """Collect all known page paths from products, categories, and overrides."""
    paths: set[str] = set()

    # Static pages
    paths.update(["", "products"])

    # Products
    product_rows = (
        await db.execute(
            text(
                "SELECT slug FROM ecommerce.products "
                "WHERE status = 'active' AND deleted_at IS NULL"
            )
        )
    ).scalars().all()
    for slug in product_rows:
        paths.add(f"products/{slug}")

    # Categories
    cat_rows = (
        await db.execute(text("SELECT slug FROM ecommerce.categories"))
    ).scalars().all()
    for slug in cat_rows:
        paths.add(f"categories/{slug}")

    # Custom overrides (may include paths not in products/categories)
    override_rows = (
        await db.execute(text("SELECT path FROM seo.meta_overrides"))
    ).scalars().all()
    paths.update(override_rows)

    return sorted(paths)


def _to_json(obj: Any) -> str:
    """Serialize to JSON string for JSONB columns."""
    import json

    return json.dumps(obj)
