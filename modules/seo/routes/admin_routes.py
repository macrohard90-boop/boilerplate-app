"""Admin SEO management endpoints."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.seo.models.schemas import (
    AdminMetaListResponse,
    MessageResponse,
    MetaTagsUpdate,
    SEOConfigResponse,
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
