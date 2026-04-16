"""Admin SEO management endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.seo.models.schemas import (
    AdminMetaListResponse,
    AdvisorAnalyzeRequest,
    AuditListResponse,
    AuditReportResponse,
    KeywordDiscoverRequest,
    KeywordSuggestionListResponse,
    MessageResponse,
    MetaTagsUpdate,
    PageRegistryCreate,
    PageScoreListResponse,
    ScoreTrendResponse,
    SEOConfigResponse,
    SnapshotListResponse,
    TargetKeywordCreate,
    TargetKeywordListResponse,
    TargetKeywordResponse,
    TargetKeywordUpdate,
)
from modules.seo.services.meta_service import (
    delete_meta_override,
    list_meta_overrides,
    set_meta_override,
)

router = APIRouter(
    prefix="/admin/seo",
    tags=["admin-seo"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("/meta/current/{path:path}")
async def admin_get_current_meta(
    path: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Get current meta tags for a path (override + auto-generated merged)."""
    from modules.seo.services.meta_service import get_meta_tags

    meta = await get_meta_tags(db, path)
    robots = meta.get("robots", "index, follow")
    return {
        "path": path,
        "title": meta.get("title"),
        "description": meta.get("description"),
        "canonical_url": meta.get("canonical_url"),
        "robots_index": "noindex" not in robots,
        "robots_follow": "nofollow" not in robots,
        "is_custom": meta.get("is_custom", False),
    }


@router.get("/meta", response_model=AdminMetaListResponse)
async def admin_list_meta(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all custom meta tag overrides (paginated)."""
    return await list_meta_overrides(db, page, page_size)


@router.put("/meta/{path:path}", response_model=MessageResponse)
async def admin_set_meta(
    path: str,
    body: MetaTagsUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Create or update a custom meta tag override for a path."""
    return await set_meta_override(
        db,
        path,
        body.title,
        body.description,
        body.robots_index,
        body.robots_follow,
        body.canonical_url,
        user["user_id"],
    )


@router.delete("/meta/{path:path}", response_model=MessageResponse)
async def admin_delete_meta(
    path: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Remove a custom meta tag override (revert to auto-generated)."""
    try:
        return await delete_meta_override(db, path)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e))


@router.post("/verify/{path:path}")
async def admin_verify_page(
    path: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Verify that rendered HTML meta matches API meta for a page."""
    from modules.seo.services.verification_service import verify_and_compare

    try:
        return await verify_and_compare(db, path)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch page: {e}",
        )


@router.post("/sitemap/regenerate", response_model=MessageResponse)
async def admin_regenerate_sitemap(
    user: dict = Depends(require_role("admin")),
):
    """Force sitemap cache invalidation."""
    from modules.seo.services.sitemap_service import invalidate_cache

    await invalidate_cache()
    return {"message": "Sitemap cache invalidated. Next request will regenerate."}


# ── Page Registry endpoints ───────────────────────────────


@router.post("/pages/sync", response_model=MessageResponse)
async def admin_sync_pages(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Re-scan filesystem and sync page registry."""
    from modules.seo.services.page_discovery_service import sync_page_registry

    result = await sync_page_registry(db)
    return {
        "message": (
            f"Synced: {result['added']} upserted, {result['total']} total pages."
        )
    }


@router.get("/pages")
async def admin_list_pages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """List all registered pages with metadata."""
    from modules.seo.services.page_discovery_service import get_page_registry

    return await get_page_registry(db, page, page_size)


@router.post("/pages", response_model=MessageResponse)
async def admin_add_page(
    body: PageRegistryCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Manually register a page path."""
    from modules.seo.services.page_discovery_service import add_page

    return await add_page(db, body.path, body.changefreq, body.priority)


@router.delete("/pages/{path:path}", response_model=MessageResponse)
async def admin_remove_page(
    path: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    """Remove a page from the registry."""
    from modules.seo.services.page_discovery_service import remove_page

    removed = await remove_page(db, path)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Page not found: {path}")
    return {"message": f"Page '{path}' removed from registry."}


@router.get("/config", response_model=SEOConfigResponse)
async def admin_get_config(
    user: dict = Depends(require_role("admin")),
):
    """Get current SEO configuration."""
    social: dict[str, Any] = {}
    if settings.social_handles:
        try:
            social = json.loads(settings.social_handles)
        except (json.JSONDecodeError, TypeError):
            pass

    return SEOConfigResponse(
        site_name=settings.site_name,
        default_og_image=settings.default_og_image,
        social_handles=social,
        domain=settings.domain,
        sitemap_cache_ttl=settings.sitemap_cache_ttl,
    )


# ── Scoring endpoints (gated by enable_seo_scoring) ──────────

if settings.enable_seo_scoring:
    from modules.seo.services.scoring_service import (
        get_latest_scores,
        get_score_trend,
        score_all_pages,
        score_page,
    )

    @router.get("/html/{path:path}")
    async def admin_get_page_html(
        path: str,
        user: dict = Depends(require_role("admin")),
    ):
        """Fetch rendered HTML of a frontend page, prettified for the source viewer."""
        import httpx

        from modules.seo.services.html_prettifier import prettify_html

        base = settings.internal_frontend_url or settings.frontend_url
        url = f"{base}/{path}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15, follow_redirects=True)
            return {
                "html": prettify_html(response.text),
                "status_code": response.status_code,
            }
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Could not fetch page: {e}",
            )

    @router.get("/scores", response_model=PageScoreListResponse)
    async def admin_list_scores(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """List latest SEO scores for all pages."""
        return await get_latest_scores(db, page, page_size)

    @router.post("/scores/batch", response_model=MessageResponse)
    async def admin_score_batch(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Score all known pages."""
        results = await score_all_pages(db)
        return {"message": f"Scored {len(results)} pages."}

    @router.get("/scores/trend", response_model=ScoreTrendResponse)
    async def admin_score_trend(
        path: str = Query(..., description="Page path to get trend for"),
        days: int = Query(30, ge=1, le=365),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get score history for a single page."""
        return await get_score_trend(db, path, days)

    @router.post("/scores/{path:path}", response_model=MessageResponse)
    async def admin_score_page(
        path: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Score a single page's SEO quality."""
        result = await score_page(db, path)
        return {"message": f"Scored {path}: {result.score}/100"}


# ── Snapshot endpoints ────────────────────────────────────────

if settings.enable_seo_scoring:
    from modules.seo.services.snapshot_service import (
        get_snapshot,
        list_snapshots,
    )

    @router.get("/snapshots", response_model=SnapshotListResponse)
    async def admin_list_snapshots(
        path: str = Query(..., description="Page path"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List snapshot history for a page."""
        return await list_snapshots(db, path, page, page_size)

    @router.get("/snapshots/{snapshot_id}")
    async def admin_get_snapshot(
        snapshot_id: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get a single snapshot with diff."""
        result = await get_snapshot(db, snapshot_id)
        if not result:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return result


# ── Site Audit endpoints (gated by enable_seo_scoring) ───────

if settings.enable_seo_scoring:
    from modules.seo.services.audit_service import (
        get_latest_audit,
        list_audits,
        run_full_audit,
    )

    @router.post("/audit/run", response_model=AuditReportResponse)
    async def admin_run_audit(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Run a full site SEO audit."""
        report = await run_full_audit(db, user_id=user["user_id"])
        from dataclasses import asdict

        return {
            "checks": [asdict(c) for c in report.checks],
            "summary": report.summary,
            "score": report.score,
            "created_at": report.created_at,
        }

    @router.get("/audit/latest", response_model=AuditReportResponse)
    async def admin_latest_audit(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get the most recent site audit."""
        result = await get_latest_audit(db)
        if not result:
            raise HTTPException(status_code=404, detail="No audits found. Run an audit first.")
        return result

    @router.get("/audit/history", response_model=AuditListResponse)
    async def admin_audit_history(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List past site audits."""
        return await list_audits(db, page, page_size)


# ── Crawler endpoints (gated by enable_seo_crawler) ──────────

if settings.enable_seo_crawler:

    @router.post("/crawl/batch", response_model=MessageResponse)
    async def admin_crawl_batch(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Crawl all sitemap pages."""
        from modules.seo.services.crawler_service import crawl_all_pages

        results = await crawl_all_pages(db)
        return {"message": f"Crawled {len(results)} pages."}

    @router.get("/crawl/results")
    async def admin_list_crawl_results(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List crawl results."""
        from modules.seo.services.crawler_service import list_crawl_results

        return await list_crawl_results(db, page, page_size)

    @router.get("/crawl/results/{result_id}")
    async def admin_get_crawl_result(
        result_id: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get a single crawl result with mismatches."""
        from modules.seo.services.crawler_service import get_crawl_result

        result = await get_crawl_result(db, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Crawl result not found")
        return result

    @router.post("/crawl/{path:path}", response_model=MessageResponse)
    async def admin_crawl_page(
        path: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Crawl a single page and compare rendered HTML to API meta."""
        from modules.seo.services.crawler_service import crawl_page

        result = await crawl_page(db, path)
        mismatch_count = len(result.get("mismatches", []))
        return {
            "message": f"Crawled {path}: {mismatch_count} mismatch(es) found."
        }


# ── Keyword endpoints (gated by enable_seo_keywords) ─────

if settings.enable_seo_keywords:
    from modules.seo.services.keyword_service import (
        assign_keyword,
        discover_keywords,
        list_suggestions,
        list_target_keywords,
        remove_keyword,
        update_keyword,
    )

    @router.post("/keywords/discover")
    async def admin_discover_keywords(
        body: KeywordDiscoverRequest,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Discover keywords using the configured provider."""
        results = await discover_keywords(db, body.seed, body.depth, body.limit)
        return {"items": results, "seed": body.seed}

    @router.get("/keywords/targets", response_model=TargetKeywordListResponse)
    async def admin_list_targets(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List all target keywords."""
        return await list_target_keywords(db, page, page_size)

    @router.post("/keywords/targets", response_model=TargetKeywordResponse)
    async def admin_assign_keyword(
        body: TargetKeywordCreate,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Assign a target keyword to a page."""
        return await assign_keyword(
            db, body.keyword, body.path, body.priority, body.notes
        )

    @router.put("/keywords/targets/{keyword_id}", response_model=TargetKeywordResponse)
    async def admin_update_keyword(
        keyword_id: str,
        body: TargetKeywordUpdate,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Update a target keyword."""
        result = await update_keyword(
            db, keyword_id, body.priority, body.notes, body.path
        )
        if not result:
            raise HTTPException(status_code=404, detail="Keyword not found")
        return result

    @router.delete("/keywords/targets/{keyword_id}", response_model=MessageResponse)
    async def admin_remove_keyword(
        keyword_id: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Remove a target keyword."""
        removed = await remove_keyword(db, keyword_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Keyword not found")
        return {"message": "Keyword removed."}

    @router.get("/keywords/suggestions", response_model=KeywordSuggestionListResponse)
    async def admin_list_suggestions(
        seed: str | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List previously discovered keyword suggestions."""
        return await list_suggestions(db, seed, page, page_size)

    @router.get("/content/analyze")
    async def admin_analyze_content(
        path: str = Query(..., description="Page path to analyze"),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Analyze page content: readability + keyword density."""
        from modules.seo.services.keyword_service import (
            analyze_keyword_density,
            get_target_keywords,
        )
        from modules.seo.services.readability_service import analyze_content

        # Get crawl data for content
        crawl_data = await _get_crawl_content(db, path)
        content = crawl_data.get("content", "")
        keywords = await get_target_keywords(db, path)

        readability = analyze_content(content)
        density = analyze_keyword_density(content, keywords) if keywords else []

        return {
            "path": path,
            "readability": {
                "word_count": readability.word_count,
                "sentence_count": readability.sentence_count,
                "avg_sentence_length": readability.avg_sentence_length,
                "flesch_reading_ease": readability.flesch_reading_ease,
                "quality": readability.quality,
            },
            "keyword_density": density,
            "has_content": bool(content),
        }


async def _get_crawl_content(db: AsyncSession, path: str) -> dict:
    """Get latest crawl content for a page."""
    try:
        row = (
            await db.execute(
                text(
                    "SELECT rendered_meta FROM seo.crawl_results "
                    "WHERE path = :path ORDER BY crawled_at DESC LIMIT 1"
                ),
                {"path": path},
            )
        ).mappings().first()
        if row and row["rendered_meta"]:
            meta = row["rendered_meta"]
            return {"content": meta.get("body_text", "")}
    except Exception:
        pass
    return {"content": ""}


# ── SEO Advisor endpoints (gated by enable_seo_advisor) ───

if settings.enable_seo_advisor:

    @router.post("/advisor/{path:path}")
    async def admin_seo_advisor(
        path: str,
        body: AdvisorAnalyzeRequest | None = None,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get AI-powered SEO suggestions for a page."""
        import httpx
        from dataclasses import asdict

        from modules.seo.adapters import get_seo_advisor
        from modules.seo.services.scoring_service import score_page

        # 1. Score the page to get current rule results
        result = await score_page(db, path)
        rules_dicts = [asdict(r) for r in result.rules]

        # 2. Fetch HTML
        base = settings.internal_frontend_url or settings.frontend_url
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base}/{path}", timeout=15, follow_redirects=True
                )
            html = resp.text
        except Exception:
            html = ""

        # 3. Get target keywords
        try:
            kw_rows = (
                await db.execute(
                    text(
                        "SELECT keyword FROM seo.target_keywords "
                        "WHERE path = :path OR path IS NULL "
                        "ORDER BY priority DESC LIMIT 5"
                    ),
                    {"path": path},
                )
            ).scalars().all()
            keywords = list(kw_rows)
        except Exception:
            keywords = []

        # 4. Call advisor with business context and intent
        advisor = get_seo_advisor()
        advisor_result = await advisor.analyze(
            path=path,
            html=html,
            scores={"score": result.score, "provider": result.provider},
            rule_results=rules_dicts,
            target_keywords=keywords if keywords else None,
            business_context=body.business_context if body else None,
            intent=body.intent if body else None,
        )

        return {
            "path": path,
            "suggestions": [asdict(s) for s in advisor_result.suggestions],
            "provider": advisor_result.provider,
            "error": advisor_result.error,
        }


# ── SEO Analytics endpoints (gated by scoring + tracking) ─

if settings.enable_seo_scoring and settings.enable_tracking:
    from modules.seo.services.analytics_service import get_seo_traffic_report

    @router.get("/analytics/traffic")
    async def admin_seo_traffic(
        days: int = Query(30, ge=1, le=365),
        limit: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get SEO + traffic correlation report."""
        return await get_seo_traffic_report(db, days, limit)


# ── GEO Scoring endpoints ─────────────────────────────────

if settings.enable_geo_scoring:
    from modules.seo.services.geo_scoring_service import (
        get_geo_score_for_path,
        get_geo_score_trend,
        get_latest_geo_scores,
        score_all_pages_geo,
        score_page_geo,
    )

    @router.get("/geo/scores")
    async def admin_geo_scores(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """List latest GEO scores for all pages (paginated)."""
        return await get_latest_geo_scores(db, page, page_size)

    @router.get("/geo/scores/{path:path}/trend")
    async def admin_geo_score_trend(
        path: str,
        days: int = Query(30, ge=1, le=365),
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get GEO score history for a page."""
        return await get_geo_score_trend(db, path, days)

    @router.get("/geo/scores/{path:path}")
    async def admin_geo_score_detail(
        path: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get the latest GEO score for a specific page."""
        result = await get_geo_score_for_path(db, path)
        if not result:
            raise HTTPException(404, "No GEO score found for this page")
        return result

    @router.post("/geo/scores/batch")
    async def admin_geo_score_batch(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Score all pages for GEO (batch operation)."""
        results = await score_all_pages_geo(db)
        return {"items": results, "total": len(results)}


# ── GEO Advisor endpoints (gated by enable_geo_advisor + enable_geo_scoring) ──

if settings.enable_geo_advisor and settings.enable_geo_scoring:

    @router.post("/geo/advisor/{path:path}")
    async def admin_geo_advisor(
        path: str,
        body: AdvisorAnalyzeRequest | None = None,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Get AI-powered GEO suggestions for a page."""
        import httpx
        from dataclasses import asdict

        from modules.seo.adapters import get_geo_advisor
        from modules.seo.services.geo_scoring_service import score_page_geo

        # 1. Score the page for GEO to get current rule results
        result = await score_page_geo(db, path)
        rules_dicts = [asdict(r) for r in result.rules]

        # 2. Fetch HTML
        base = settings.internal_frontend_url or settings.frontend_url
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base}/{path}", timeout=15, follow_redirects=True
                )
            html = resp.text
        except Exception:
            html = ""

        # 3. Call GEO advisor
        advisor = get_geo_advisor()
        advisor_result = await advisor.analyze(
            path=path,
            html=html,
            scores={"score": result.score, "provider": result.provider},
            dimension_scores=result.dimension_scores or {},
            rule_results=rules_dicts,
            business_context=body.business_context if body else None,
            intent=body.intent if body else None,
        )

        return {
            "path": path,
            "suggestions": [asdict(s) for s in advisor_result.suggestions],
            "provider": advisor_result.provider,
            "model": advisor_result.model,
            "error": advisor_result.error,
        }
