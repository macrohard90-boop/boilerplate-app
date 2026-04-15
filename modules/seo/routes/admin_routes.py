"""Admin SEO management endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.seo.models.schemas import (
    AdminMetaListResponse,
    MessageResponse,
    MetaTagsUpdate,
    PageScoreListResponse,
    ScoreTrendResponse,
    SEOConfigResponse,
    SnapshotListResponse,
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


@router.post("/sitemap/regenerate", response_model=MessageResponse)
async def admin_regenerate_sitemap(
    user: dict = Depends(require_role("admin")),
):
    """Force sitemap cache invalidation."""
    from modules.seo.services.sitemap_service import invalidate_cache

    await invalidate_cache()
    return {"message": "Sitemap cache invalidated. Next request will regenerate."}


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

    @router.get("/scores", response_model=PageScoreListResponse)
    async def admin_list_scores(
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """List latest SEO scores for all pages."""
        return await get_latest_scores(db, page, page_size)

    @router.post("/scores/{path:path}", response_model=MessageResponse)
    async def admin_score_page(
        path: str,
        db: AsyncSession = Depends(get_db),
        user: dict = Depends(require_role("admin")),
    ):
        """Score a single page's SEO quality."""
        result = await score_page(db, path)
        return {"message": f"Scored {path}: {result.score}/100"}

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


# ── Crawler endpoints (gated by enable_seo_crawler) ──────────

if settings.enable_seo_crawler:

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
