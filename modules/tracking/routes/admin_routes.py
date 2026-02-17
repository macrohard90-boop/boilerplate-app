"""Admin analytics endpoints — pageviews, sessions, events, sources, UTM."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role
from modules.tracking.models.schemas import (
    BrowserStat,
    DeviceStats,
    DeviceTypeStat,
    EventStats,
    EventTypeStat,
    OSStat,
    PageViewStats,
    SessionDayStat,
    SessionStats,
    SourceStat,
    SourceStats,
    TopPage,
    UTMCampaignStat,
    UTMStats,
)

router = APIRouter(
    prefix="/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_role("admin"))],
)


def _date_range(
    date_from: date | None, date_to: date | None
) -> tuple[datetime, datetime, str, str]:
    """Return (ts_from, ts_end, label_from, label_to) as tz-aware datetimes."""
    if date_to is None:
        date_to = date.today()
    if date_from is None:
        date_from = date_to - timedelta(days=30)
    ts_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
    ts_end = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
    return ts_from, ts_end, str(date_from), str(date_to)


# ── Pageview Stats ─────────────────────────────────────────

@router.get("/pageviews", response_model=PageViewStats)
async def get_pageview_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page_size: int = Query(10, ge=1, le=100),
):
    """Page view stats: total views, unique visitors, top pages."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    totals = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS total_views, "
                "COUNT(DISTINCT COALESCE(CAST(user_id AS text), session_id)) AS unique_visitors "
                "FROM analytics.page_views "
                "WHERE created_at >= :ts_from AND created_at < :ts_end"
            ),
            {"ts_from": ts_from, "ts_end": ts_end},
        )
    ).mappings().first()

    top_rows = (
        await db.execute(
            text(
                "SELECT path, COUNT(*) AS views, "
                "COUNT(DISTINCT COALESCE(CAST(user_id AS text), session_id)) AS unique_visitors "
                "FROM analytics.page_views "
                "WHERE created_at >= :ts_from AND created_at < :ts_end "
                "GROUP BY path ORDER BY views DESC LIMIT :lim"
            ),
            {"ts_from": ts_from, "ts_end": ts_end, "lim": page_size},
        )
    ).mappings().all()

    return PageViewStats(
        total_views=totals["total_views"],
        unique_visitors=totals["unique_visitors"],
        date_from=lbl_from,
        date_to=lbl_to,
        top_pages=[TopPage(**r) for r in top_rows],
    )


# ── Session Stats ──────────────────────────────────────────

@router.get("/sessions", response_model=SessionStats)
async def get_session_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """Session stats: total sessions, avg page count, sessions by day."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    totals = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS total_sessions, "
                "COALESCE(AVG(page_count), 0) AS avg_page_count "
                "FROM analytics.analytics_sessions "
                "WHERE started_at >= :ts_from AND started_at < :ts_end"
            ),
            {"ts_from": ts_from, "ts_end": ts_end},
        )
    ).mappings().first()

    by_day = (
        await db.execute(
            text(
                "SELECT CAST(started_at AS date) AS date, COUNT(*) AS sessions "
                "FROM analytics.analytics_sessions "
                "WHERE started_at >= :ts_from AND started_at < :ts_end "
                "GROUP BY CAST(started_at AS date) ORDER BY date"
            ),
            {"ts_from": ts_from, "ts_end": ts_end},
        )
    ).mappings().all()

    return SessionStats(
        total_sessions=totals["total_sessions"],
        avg_page_count=float(totals["avg_page_count"]),
        date_from=lbl_from,
        date_to=lbl_to,
        by_day=[SessionDayStat(date=str(r["date"]), sessions=r["sessions"]) for r in by_day],
    )


# ── Event Stats ────────────────────────────────────────────

@router.get("/events", response_model=EventStats)
async def get_event_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    event_type: str | None = Query(None),
):
    """Event counts by type, with optional type filter."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    where = "WHERE created_at >= :ts_from AND created_at < :ts_end"
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if event_type:
        where += " AND event_type = :etype"
        params["etype"] = event_type

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total_events FROM analytics.events {where}"),
            params,
        )
    ).mappings().first()

    by_type = (
        await db.execute(
            text(
                f"SELECT event_type, COUNT(*) AS count "
                f"FROM analytics.events {where} "
                f"GROUP BY event_type ORDER BY count DESC LIMIT 50"
            ),
            params,
        )
    ).mappings().all()

    return EventStats(
        total_events=total["total_events"],
        date_from=lbl_from,
        date_to=lbl_to,
        by_type=[EventTypeStat(**r) for r in by_type],
    )


# ── Source Stats ───────────────────────────────────────────

@router.get("/sources", response_model=SourceStats)
async def get_source_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """Traffic sources: referral source breakdown."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    rows = (
        await db.execute(
            text(
                "SELECT rs.source, rs.medium, COUNT(*) AS sessions "
                "FROM analytics.referral_sources rs "
                "JOIN analytics.analytics_sessions s ON rs.session_id = s.session_id "
                "WHERE s.started_at >= :ts_from AND s.started_at < :ts_end "
                "GROUP BY rs.source, rs.medium ORDER BY sessions DESC LIMIT 50"
            ),
            {"ts_from": ts_from, "ts_end": ts_end},
        )
    ).mappings().all()

    return SourceStats(
        total_sources=len(rows),
        date_from=lbl_from,
        date_to=lbl_to,
        sources=[SourceStat(**r) for r in rows],
    )


# ── UTM Stats ─────────────────────────────────────────────

@router.get("/utm", response_model=UTMStats)
async def get_utm_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """UTM campaign performance: sessions per campaign."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    rows = (
        await db.execute(
            text(
                "SELECT u.utm_source, u.utm_medium, u.utm_campaign, COUNT(*) AS sessions "
                "FROM analytics.utm_tracking u "
                "JOIN analytics.analytics_sessions s ON u.session_id = s.session_id "
                "WHERE s.started_at >= :ts_from AND s.started_at < :ts_end "
                "GROUP BY u.utm_source, u.utm_medium, u.utm_campaign "
                "ORDER BY sessions DESC LIMIT 50"
            ),
            {"ts_from": ts_from, "ts_end": ts_end},
        )
    ).mappings().all()

    return UTMStats(
        total_campaigns=len(rows),
        date_from=lbl_from,
        date_to=lbl_to,
        campaigns=[UTMCampaignStat(**r) for r in rows],
    )


# ── Device / Browser Stats ───────────────────────────────

@router.get("/devices", response_model=DeviceStats)
async def get_device_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """Device, browser, and OS breakdown from user-agent data."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    # Join user_agents to sessions for date filtering
    base_where = (
        "FROM analytics.user_agents ua "
        "JOIN analytics.analytics_sessions s ON ua.session_id = s.session_id "
        "WHERE s.started_at >= :ts_from AND s.started_at < :ts_end"
    )
    params = {"ts_from": ts_from, "ts_end": ts_end}

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total_agents {base_where}"),
            params,
        )
    ).mappings().first()

    by_device = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.device_type, 'unknown') AS device_type, COUNT(*) AS count "
                f"{base_where} "
                f"GROUP BY ua.device_type ORDER BY count DESC"
            ),
            params,
        )
    ).mappings().all()

    by_browser = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.browser, 'Unknown') AS browser, COUNT(*) AS count "
                f"{base_where} "
                f"GROUP BY ua.browser ORDER BY count DESC LIMIT 10"
            ),
            params,
        )
    ).mappings().all()

    by_os = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.os, 'Unknown') AS os, COUNT(*) AS count "
                f"{base_where} "
                f"GROUP BY ua.os ORDER BY count DESC LIMIT 10"
            ),
            params,
        )
    ).mappings().all()

    return DeviceStats(
        total_agents=total["total_agents"],
        date_from=lbl_from,
        date_to=lbl_to,
        by_device_type=[DeviceTypeStat(**r) for r in by_device],
        by_browser=[BrowserStat(**r) for r in by_browser],
        by_os=[OSStat(**r) for r in by_os],
    )
