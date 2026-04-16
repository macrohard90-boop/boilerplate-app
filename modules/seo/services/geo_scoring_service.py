"""GEO scoring service — orchestrates HTML fetching, GEO analysis, scoring, and DB storage."""

import json
import logging
from dataclasses import asdict
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.seo.adapters.geo_rule_scoring_provider import GEORuleScoringProvider
from modules.seo.interfaces.geo_scoring_provider import GEOScoreResult, PageGEOData
from modules.seo.services.geo_html_analyzer import analyze_geo_html
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


async def score_page_geo(db: AsyncSession, path: str) -> GEOScoreResult:
    """Score a page's GEO quality and store the result."""
    meta = await get_meta_tags(db, path)
    structured_data = meta.get("structured_data") or []

    # Fetch rendered HTML
    html = await _fetch_html(path)

    # Extract GEO-specific signals from HTML
    geo_signals = analyze_geo_html(html, settings.domain) if html else None

    # Analyze structured data for schema type detection
    schema_info = _analyze_structured_data(structured_data)

    # Find content_updated_at from schema or DB
    content_updated_at = _get_date_modified(structured_data)
    if not content_updated_at:
        content_updated_at = await _get_meta_updated_at(db, path)

    page_data = PageGEOData(
        path=path,
        body_text=geo_signals.first_paragraph_text if geo_signals else None,
        html=html,
        title=meta.get("title"),
        description=meta.get("description"),
        h1_text=None,
        headings=None,
        structured_data=structured_data,
        external_links=len(geo_signals.outbound_domains) if geo_signals else 0,
        outbound_domains=geo_signals.outbound_domains if geo_signals else [],
        content_updated_at=content_updated_at,
        word_count=geo_signals.word_count if geo_signals else 0,
        sentence_count=geo_signals.sentence_count if geo_signals else 0,
        paragraph_count=geo_signals.paragraph_count if geo_signals else 0,
        # Extractability
        first_paragraph_text=geo_signals.first_paragraph_text if geo_signals else "",
        first_paragraph_word_count=geo_signals.first_paragraph_word_count if geo_signals else 0,
        h2_headings=geo_signals.h2_headings if geo_signals else [],
        h2_question_count=geo_signals.h2_question_count if geo_signals else 0,
        h2_sections=geo_signals.h2_sections if geo_signals else [],
        # Fact density
        stat_pattern_count=geo_signals.stat_pattern_count if geo_signals else 0,
        has_data_tables=geo_signals.has_data_tables if geo_signals else False,
        # Authority
        has_blockquotes=geo_signals.has_blockquotes if geo_signals else False,
        quote_attribution_count=geo_signals.quote_attribution_count if geo_signals else 0,
        authority_domain_count=geo_signals.authority_domain_count if geo_signals else 0,
        stale_year_references=geo_signals.stale_year_references if geo_signals else [],
        # Schema detection
        **schema_info,
    )

    provider = GEORuleScoringProvider()
    result = await provider.score_page(page_data)

    # Store in DB
    rules_json = [asdict(r) for r in result.rules]
    await db.execute(
        text(
            "INSERT INTO seo.geo_page_scores "
            "(path, score, dimension_scores, rule_results, provider) "
            "VALUES (:path, :score, CAST(:dims AS jsonb), CAST(:rules AS jsonb), :provider)"
        ),
        {
            "path": path,
            "score": result.score,
            "dims": json.dumps(result.dimension_scores),
            "rules": json.dumps(rules_json),
            "provider": result.provider,
        },
    )
    await db.commit()
    return result


async def score_all_pages_geo(db: AsyncSession) -> list[dict[str, Any]]:
    """Score all known pages for GEO and store results."""
    from modules.seo.services.page_discovery_service import collect_all_paths

    paths = await collect_all_paths(db)
    results = []
    for path in paths:
        try:
            result = await score_page_geo(db, path)
            results.append({"path": path, "score": result.score})
        except Exception:
            logger.exception("Failed to GEO-score path: %s", path)
    return results


async def get_latest_geo_scores(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """Get the latest GEO score for each page, paginated."""
    offset = (page - 1) * page_size

    rows = (
        await db.execute(
            text(
                "SELECT DISTINCT ON (path) id, path, score, dimension_scores, "
                "rule_results, provider, scored_at "
                "FROM seo.geo_page_scores ORDER BY path, scored_at DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"lim": page_size, "off": offset},
        )
    ).mappings().all()

    total = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT DISTINCT ON (path) path FROM seo.geo_page_scores "
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
                "dimension_scores": r["dimension_scores"],
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


async def get_geo_score_for_path(
    db: AsyncSession, path: str
) -> dict[str, Any] | None:
    """Get the latest GEO score for a specific page."""
    row = (
        await db.execute(
            text(
                "SELECT id, path, score, dimension_scores, rule_results, "
                "provider, scored_at "
                "FROM seo.geo_page_scores "
                "WHERE path = :path ORDER BY scored_at DESC LIMIT 1"
            ),
            {"path": path},
        )
    ).mappings().first()

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "path": row["path"],
        "score": row["score"],
        "dimension_scores": row["dimension_scores"],
        "rule_results": row["rule_results"],
        "provider": row["provider"],
        "scored_at": str(row["scored_at"]),
    }


async def get_geo_score_trend(
    db: AsyncSession, path: str, days: int = 30
) -> dict[str, Any]:
    """Get GEO score history for a single page."""
    rows = (
        await db.execute(
            text(
                "SELECT score, dimension_scores, scored_at "
                "FROM seo.geo_page_scores "
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
            {
                "scored_at": str(r["scored_at"]),
                "score": r["score"],
                "dimension_scores": r["dimension_scores"],
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_html(path: str) -> str | None:
    """Fetch rendered HTML from the Next.js frontend."""
    try:
        base = settings.internal_frontend_url or settings.frontend_url
        url = f"{base}/{path}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10, follow_redirects=True)
        return response.text
    except Exception:
        logger.debug("Failed to fetch HTML for GEO scoring: %s", path, exc_info=True)
        return None


def _analyze_structured_data(structured_data: list[dict]) -> dict[str, Any]:
    """Analyze JSON-LD blocks for GEO-relevant schema types."""
    info: dict[str, Any] = {
        "has_faq_schema": False,
        "faq_question_count": 0,
        "has_article_schema": False,
        "article_has_author": False,
        "article_has_date_published": False,
        "article_has_date_modified": False,
        "has_howto_schema": False,
        "has_breadcrumb_schema": False,
        "has_itemlist_schema": False,
        "schema_type_count": 0,
    }

    seen_types: set[str] = set()

    for block in structured_data:
        schema_type = block.get("@type", "")
        if isinstance(schema_type, list):
            types = schema_type
        else:
            types = [schema_type]

        for t in types:
            t_lower = t.lower() if isinstance(t, str) else ""

            if t_lower == "faqpage":
                info["has_faq_schema"] = True
                seen_types.add("faq")
                # Count questions
                main_entity = block.get("mainEntity", [])
                if isinstance(main_entity, list):
                    info["faq_question_count"] = len(main_entity)

            elif t_lower in ("article", "newsarticle", "blogposting", "technicalarticle"):
                info["has_article_schema"] = True
                seen_types.add("article")
                info["article_has_author"] = bool(block.get("author"))
                info["article_has_date_published"] = bool(block.get("datePublished"))
                info["article_has_date_modified"] = bool(block.get("dateModified"))

            elif t_lower == "howto":
                info["has_howto_schema"] = True
                seen_types.add("howto")

            elif t_lower == "breadcrumblist":
                info["has_breadcrumb_schema"] = True
                seen_types.add("breadcrumb")

            elif t_lower == "itemlist":
                info["has_itemlist_schema"] = True
                seen_types.add("itemlist")

    info["schema_type_count"] = len(seen_types)
    return info


def _get_date_modified(structured_data: list[dict]) -> str | None:
    """Extract dateModified from Article/BlogPosting schema."""
    for block in structured_data:
        schema_type = block.get("@type", "")
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        for t in types:
            if isinstance(t, str) and t.lower() in (
                "article", "newsarticle", "blogposting", "technicalarticle"
            ):
                dm = block.get("dateModified")
                if dm:
                    return str(dm)
    return None


async def _get_meta_updated_at(db: AsyncSession, path: str) -> str | None:
    """Fallback: get last meta override update time from DB."""
    try:
        row = (
            await db.execute(
                text(
                    "SELECT updated_at FROM seo.meta_overrides "
                    "WHERE path = :path ORDER BY updated_at DESC LIMIT 1"
                ),
                {"path": path},
            )
        ).scalars().first()
        return str(row) if row else None
    except Exception:
        return None
