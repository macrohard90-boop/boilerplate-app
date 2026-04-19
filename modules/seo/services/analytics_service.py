"""SEO analytics service — correlates traffic data with SEO scores.

Identifies:
- Top pages by views
- Opportunity pages: high SEO score but low traffic (content is ready, needs promotion)
- Urgent fix pages: low SEO score but high traffic (fix what people are already visiting)
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.seo.adapters import get_seo_analytics_provider

logger = logging.getLogger(__name__)


async def get_seo_traffic_report(
    db: AsyncSession, days: int = 30, limit: int = 20
) -> dict[str, Any]:
    """Build a combined SEO + traffic report.

    Returns:
        top_pages: highest traffic pages with their SEO scores
        opportunities: high score (>=70) + low traffic pages
        urgent_fixes: low score (<50) + high traffic pages
    """
    provider = get_seo_analytics_provider()

    # Get top pages by traffic
    top_pages = await provider.get_top_pages(db, days=days, limit=limit)

    # Get latest SEO scores for cross-referencing.
    # SEO scores use paths without leading "/" (e.g. "products/test"),
    # while page_views use paths with "/" (e.g. "/products/test").
    # Normalize both sides by stripping the leading "/" for lookups.
    raw_scores = await _get_latest_scores(db)
    scores = {_norm(k): v for k, v in raw_scores.items()}

    # Build report items
    top_items = []
    opportunities = []
    urgent_fixes = []

    for page in top_pages:
        score = scores.get(_norm(page.path))
        item = {
            "path": page.path,
            "views": page.views,
            "unique_sessions": page.unique_sessions,
            "avg_duration_ms": page.avg_duration_ms,
            "trend": page.trend,
            "seo_score": score,
        }
        top_items.append(item)

        # Urgent: lots of traffic but bad SEO
        if score is not None and score < 50 and page.views > 0:
            urgent_fixes.append(item)

    # Find opportunity pages: good SEO but not in top traffic
    top_paths = {_norm(p.path) for p in top_pages}
    for path, score in scores.items():
        if score >= 70 and path not in top_paths:
            opportunities.append(
                {
                    "path": path,
                    "views": 0,
                    "unique_sessions": 0,
                    "avg_duration_ms": None,
                    "trend": "stable",
                    "seo_score": score,
                }
            )

    # Also check scored pages that are in top traffic but have high score + low views
    median_views = _median([p.views for p in top_pages]) if top_pages else 0
    for item in top_items:
        if (
            item["seo_score"] is not None
            and item["seo_score"] >= 70
            and item["views"] < median_views * 0.3
        ):
            if item not in opportunities:
                opportunities.append(item)

    return {
        "top_pages": top_items[:limit],
        "opportunities": opportunities[:10],
        "urgent_fixes": urgent_fixes[:10],
        "period_days": days,
    }


async def _get_latest_scores(db: AsyncSession) -> dict[str, int]:
    """Get the most recent SEO score for each page."""
    try:
        rows = (
            (
                await db.execute(
                    text(
                        "SELECT DISTINCT ON (path) path, score "
                        "FROM seo.page_scores ORDER BY path, scored_at DESC"
                    )
                )
            )
            .mappings()
            .all()
        )
        return {r["path"]: r["score"] for r in rows}
    except Exception:
        return {}


def _norm(path: str) -> str:
    """Normalize a path by stripping the leading '/' for consistent comparison."""
    return path.lstrip("/")


def _median(values: list[int]) -> float:
    """Compute the median of a list of ints."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]
