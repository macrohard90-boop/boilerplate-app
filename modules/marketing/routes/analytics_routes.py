"""Campaign analytics API routes.

Provides endpoints for:
- Campaign-level funnel + variant comparison + time series
- Click heatmap
- User timeline
- Cross-campaign effectiveness + rankings + fatigue
- Revenue attribution (5 models)
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role

router = APIRouter(prefix="/analytics", tags=["marketing-analytics"])


# ---------------------------------------------------------------------------
# Campaign-level analytics
# ---------------------------------------------------------------------------


@router.get("/campaigns/{campaign_id}/funnel")
async def campaign_funnel(
    campaign_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get conversion funnel for a campaign."""
    from modules.marketing.services.campaign_analytics_service import (
        get_campaign_funnel,
    )

    return await get_campaign_funnel(db, campaign_id)


@router.get("/campaigns/{campaign_id}/variants")
async def campaign_variants(
    campaign_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get A/B variant comparison for a campaign."""
    from modules.marketing.services.campaign_analytics_service import (
        get_variant_comparison,
    )

    return await get_variant_comparison(db, campaign_id)


@router.get("/campaigns/{campaign_id}/time-series")
async def campaign_time_series(
    campaign_id: str,
    interval: str = Query("hour", regex="^(hour|day)$"),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get time-series engagement data for a campaign."""
    from modules.marketing.services.campaign_analytics_service import get_time_series

    return await get_time_series(db, campaign_id, interval=interval)


@router.get("/campaigns/{campaign_id}/attribution")
async def campaign_attribution(
    campaign_id: str,
    model: str = Query("last_click"),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get revenue attribution for a campaign under a specific model."""
    from modules.marketing.services.campaign_analytics_service import (
        get_revenue_attribution,
    )

    return await get_revenue_attribution(db, campaign_id, model=model)


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------


@router.get("/campaigns/{campaign_id}/heatmap")
async def campaign_heatmap(
    campaign_id: str,
    variant_id: str | None = Query(None),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get click heatmap data for a campaign."""
    from modules.marketing.services.heatmap_service import get_click_heatmap

    return await get_click_heatmap(db, campaign_id, variant_id=variant_id)


# ---------------------------------------------------------------------------
# User timeline
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}/timeline")
async def user_timeline(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get unified event timeline for a user."""
    from modules.marketing.services.user_timeline_service import get_user_timeline

    return await get_user_timeline(db, user_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Cross-campaign effectiveness
# ---------------------------------------------------------------------------


@router.get("/effectiveness/rankings")
async def effectiveness_rankings(
    model: str = Query("last_click"),
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(90, ge=1, le=365),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get campaigns ranked by attributed revenue."""
    from modules.marketing.services.effectiveness_service import (
        get_campaign_rankings,
    )

    return await get_campaign_rankings(db, model=model, limit=limit, days=days)


@router.get("/effectiveness/trends")
async def effectiveness_trends(
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("day", regex="^(day|week)$"),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get rolling engagement trends across all campaigns."""
    from modules.marketing.services.effectiveness_service import (
        get_engagement_trends,
    )

    return await get_engagement_trends(db, days=days, interval=interval)


@router.get("/effectiveness/fatigue")
async def effectiveness_fatigue(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get list fatigue metrics."""
    from modules.marketing.services.effectiveness_service import get_fatigue_metrics

    return await get_fatigue_metrics(db, days=days)
