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

    # Enrich with crawl data if available (latest crawl result for this path)
    crawl_data = await _get_latest_crawl_data(db, path)

    # Fetch target keywords for this page
    target_keywords = await _get_target_keywords(db, path)

    page_data = PageSEOData(
        path=path,
        title=meta.get("title"),
        description=meta.get("description"),
        canonical_url=meta.get("canonical_url"),
        robots=meta.get("robots", "index, follow"),
        og_tags=meta.get("og_tags"),
        twitter_tags=meta.get("twitter_tags"),
        structured_data=meta.get("structured_data"),
        headings=crawl_data.get("headings") if crawl_data else None,
        images_without_alt=crawl_data.get("images_without_alt") if crawl_data else None,
        internal_links=crawl_data.get("internal_links", 0) if crawl_data else 0,
        content_length=crawl_data.get("content_length", 0) if crawl_data else 0,
        is_custom=meta.get("is_custom", False),
        target_keywords=target_keywords if target_keywords else None,
    )

    # Enrich with HTML analysis signals (lightweight httpx fetch)
    html_signals = await _fetch_and_analyze_html(path)
    if html_signals:
        page_data.has_viewport = html_signals.has_viewport
        page_data.has_lang = html_signals.has_lang
        page_data.has_favicon = html_signals.has_favicon
        page_data.images_missing_dimensions = html_signals.images_missing_dimensions
        page_data.total_images = html_signals.total_images
        page_data.external_links = html_signals.external_links
        page_data.body_text = html_signals.body_text
        page_data.h1_text = html_signals.h1_text

    provider = get_scoring_provider()
    result = await provider.score_page(page_data)

    # Store in DB
    rules_json = [asdict(r) for r in result.rules]
    await db.execute(
        text(
            "INSERT INTO seo.page_scores (path, score, rule_results, provider) "
            "VALUES (:path, :score, CAST(:rules AS jsonb), :provider)"
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
        (
            await db.execute(
                text(
                    "SELECT DISTINCT ON (path) id, path, score, rule_results, "
                    "provider, scored_at "
                    "FROM seo.page_scores ORDER BY path, scored_at DESC "
                    "LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
        )
        .mappings()
        .all()
    )

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
        (
            await db.execute(
                text(
                    "SELECT score, scored_at FROM seo.page_scores "
                    "WHERE path = :path "
                    "AND scored_at >= NOW() - INTERVAL '1 day' * :days "
                    "ORDER BY scored_at ASC"
                ),
                {"path": path, "days": days},
            )
        )
        .mappings()
        .all()
    )

    return {
        "path": path,
        "trend": [
            {"scored_at": str(r["scored_at"]), "score": r["score"]} for r in rows
        ],
    }


async def _collect_all_paths(db: AsyncSession) -> list[str]:
    """Collect all known page paths from the page registry."""
    from modules.seo.services.page_discovery_service import collect_all_paths

    return await collect_all_paths(db)


async def _get_latest_crawl_data(db: AsyncSession, path: str) -> dict[str, Any] | None:
    """Get the latest crawl result's rendered_meta for a path."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT rendered_meta FROM seo.crawl_results "
                    "WHERE path = :path ORDER BY crawled_at DESC LIMIT 1"
                ),
                {"path": path},
            )
        )
        .mappings()
        .first()
    )
    if row and row["rendered_meta"]:
        return row["rendered_meta"]
    return None


async def _get_target_keywords(db: AsyncSession, path: str) -> list[str]:
    """Get target keywords assigned to this page (or site-wide)."""
    try:
        rows = (
            (
                await db.execute(
                    text(
                        "SELECT keyword FROM seo.target_keywords "
                        "WHERE path = :path OR path IS NULL "
                        "ORDER BY priority DESC, created_at ASC"
                    ),
                    {"path": path},
                )
            )
            .scalars()
            .all()
        )
        return list(rows)
    except Exception:
        # Table may not exist yet (migration not run)
        return []


async def _fetch_and_analyze_html(path: str):
    """Fetch rendered HTML from Next.js and extract SEO signals.

    Returns ``None`` on any failure so scoring proceeds without HTML data.
    """
    try:
        import httpx

        from backend.core.config import settings
        from modules.seo.services.html_analyzer import analyze_html

        base = settings.internal_frontend_url or settings.frontend_url
        url = f"{base}/{path}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10, follow_redirects=True)
        return analyze_html(response.text, settings.domain)
    except Exception:
        logger.debug("HTML analysis failed for %s", path, exc_info=True)
        return None


def _to_json(obj: Any) -> str:
    """Serialize to JSON string for JSONB columns."""
    import json

    return json.dumps(obj)
