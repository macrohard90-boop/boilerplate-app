"""Admin analytics endpoints — pageviews, sessions, events, sources, UTM."""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import require_role
from backend.core.redis import get_redis
from modules.tracking.models.schemas import (
    ActiveSession,
    ActiveSessionsResponse,
    BrowserStat,
    DashboardSummary,
    DeviceStats,
    DeviceTypeStat,
    EnrichedUser,
    EnrichedUserList,
    EventStats,
    EventTypeStat,
    KPIMetric,
    OSStat,
    PageEngagement,
    PagesEngagementResponse,
    PageViewStats,
    PageviewTimeSeries,
    SessionDayStat,
    SessionDetail,
    SessionPageView,
    SessionStats,
    SourceStat,
    SourceStats,
    TimeseriesPoint,
    TopPage,
    TrackedUser,
    TrackedUserList,
    UserActivity,
    UserPageView,
    UserSession,
    UserTopPage,
    UTMCampaignStat,
    UTMStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_role("admin"))],
)


def _bot_filter(alias: str, exclude: bool) -> str:
    """SQL fragment to exclude bot sessions when exclude=True."""
    if not exclude:
        return ""
    return (
        f" AND {alias}.session_id NOT IN "
        "(SELECT session_id FROM analytics.user_agents WHERE device_type = 'bot')"
    )


def _date_range(
    date_from: datetime | None, date_to: datetime | None
) -> tuple[datetime, datetime, str, str]:
    """Return (ts_from, ts_end, label_from, label_to) as tz-aware datetimes."""
    now = datetime.now(timezone.utc)
    if date_to is None:
        ts_end = now
    else:
        # Cap at current time — can't query the future
        ts_end = min(
            date_to.replace(tzinfo=timezone.utc) if date_to.tzinfo is None else date_to,
            now,
        )
    if date_from is None:
        ts_from = ts_end - timedelta(days=30)
    else:
        ts_from = date_from.replace(tzinfo=timezone.utc) if date_from.tzinfo is None else date_from
    return ts_from, ts_end, ts_from.isoformat(), ts_end.isoformat()


# ── Pageview Stats ─────────────────────────────────────────

@router.get("/pageviews", response_model=PageViewStats)
async def get_pageview_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page_size: int = Query(10, ge=1, le=100),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """Page view stats: total views, unique visitors, top pages."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)
    bot = _bot_filter("pv", exclude_bots)
    user_filter = " AND pv.user_id = :user_id" if user_id else ""
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if user_id:
        params["user_id"] = user_id

    totals = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS total_views, "
                "COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors "
                "FROM analytics.page_views pv "
                f"WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot}{user_filter}"
            ),
            params,
        )
    ).mappings().first()

    top_rows = (
        await db.execute(
            text(
                "SELECT pv.path, COUNT(*) AS views, "
                "COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors, "
                "COALESCE(SUM(pv.duration_ms), 0) AS total_duration_ms "
                "FROM analytics.page_views pv "
                f"WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot}{user_filter} "
                "GROUP BY pv.path ORDER BY views DESC LIMIT :lim"
            ),
            {**params, "lim": page_size},
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
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """Session stats: total sessions, avg page count, sessions by day."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)
    bot = _bot_filter("s", exclude_bots)
    user_filter = " AND s.user_id = :user_id" if user_id else ""
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if user_id:
        params["user_id"] = user_id

    totals = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS total_sessions, "
                "COALESCE(AVG(page_count), 0) AS avg_page_count "
                "FROM analytics.analytics_sessions s "
                f"WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot}{user_filter}"
            ),
            params,
        )
    ).mappings().first()

    by_day = (
        await db.execute(
            text(
                "SELECT CAST(s.started_at AS date) AS date, COUNT(*) AS sessions "
                "FROM analytics.analytics_sessions s "
                f"WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot}{user_filter} "
                "GROUP BY CAST(s.started_at AS date) ORDER BY date"
            ),
            params,
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
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    event_type: str | None = Query(None),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """Event counts by type, with optional type filter."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    where = "WHERE e.created_at >= :ts_from AND e.created_at < :ts_end"
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if event_type:
        where += " AND e.event_type = :etype"
        params["etype"] = event_type
    bot = _bot_filter("e", exclude_bots)
    where += bot
    if user_id:
        where += " AND e.user_id = :user_id"
        params["user_id"] = user_id

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total_events FROM analytics.events e {where}"),
            params,
        )
    ).mappings().first()

    by_type = (
        await db.execute(
            text(
                f"SELECT e.event_type, COUNT(*) AS count "
                f"FROM analytics.events e {where} "
                f"GROUP BY e.event_type ORDER BY count DESC LIMIT 50"
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
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """Traffic sources: referral source breakdown."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)
    bot = _bot_filter("s", exclude_bots)
    user_filter = " AND s.user_id = :user_id" if user_id else ""
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if user_id:
        params["user_id"] = user_id

    rows = (
        await db.execute(
            text(
                "SELECT rs.source, rs.medium, COUNT(*) AS sessions "
                "FROM analytics.referral_sources rs "
                "JOIN analytics.analytics_sessions s ON rs.session_id = s.session_id "
                f"WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot}{user_filter} "
                "GROUP BY rs.source, rs.medium ORDER BY sessions DESC LIMIT 50"
            ),
            params,
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
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """UTM campaign performance: sessions per campaign."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)
    bot = _bot_filter("s", exclude_bots)
    user_filter = " AND s.user_id = :user_id" if user_id else ""
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if user_id:
        params["user_id"] = user_id

    rows = (
        await db.execute(
            text(
                "SELECT u.utm_source, u.utm_medium, u.utm_campaign, COUNT(*) AS sessions "
                "FROM analytics.utm_tracking u "
                "JOIN analytics.analytics_sessions s ON u.session_id = s.session_id "
                f"WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot}{user_filter} "
                "GROUP BY u.utm_source, u.utm_medium, u.utm_campaign "
                "ORDER BY sessions DESC LIMIT 50"
            ),
            params,
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
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    user_id: str | None = Query(None),
):
    """Device, browser, and OS breakdown from user-agent data."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)

    bot_clause = " AND ua.device_type != 'bot'" if exclude_bots else ""
    user_filter = " AND s.user_id = :user_id" if user_id else ""
    # Join user_agents to sessions for date filtering, plus page_views for duration
    base_from = (
        "FROM analytics.user_agents ua "
        "JOIN analytics.analytics_sessions s ON ua.session_id = s.session_id "
        "LEFT JOIN ("
        "  SELECT session_id, SUM(COALESCE(duration_ms, 0)) AS total_ms"
        "  FROM analytics.page_views GROUP BY session_id"
        ") pv_dur ON pv_dur.session_id = s.session_id"
    )
    base_where = f"WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot_clause}{user_filter}"
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    if user_id:
        params["user_id"] = user_id

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) AS total_agents {base_from} {base_where}"),
            params,
        )
    ).mappings().first()

    by_device = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.device_type, 'unknown') AS device_type, COUNT(*) AS count, "
                f"COALESCE(SUM(pv_dur.total_ms), 0) AS total_duration_ms "
                f"{base_from} {base_where} "
                f"GROUP BY ua.device_type ORDER BY count DESC"
            ),
            params,
        )
    ).mappings().all()

    by_browser = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.browser, 'Unknown') AS browser, COUNT(*) AS count, "
                f"COALESCE(SUM(pv_dur.total_ms), 0) AS total_duration_ms "
                f"{base_from} {base_where} "
                f"GROUP BY ua.browser ORDER BY count DESC LIMIT 10"
            ),
            params,
        )
    ).mappings().all()

    by_os = (
        await db.execute(
            text(
                f"SELECT COALESCE(ua.os, 'Unknown') AS os, COUNT(*) AS count, "
                f"COALESCE(SUM(pv_dur.total_ms), 0) AS total_duration_ms "
                f"{base_from} {base_where} "
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


# ── Dashboard KPI Summary ────────────────────────────────

def _compute_change_pct(current: float, previous: float) -> float | None:
    if previous == 0:
        return 100.0 if current > 0 else None
    return round(((current - previous) / previous) * 100, 1)


@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
):
    """KPI summary with period-over-period comparison."""
    ts_from, ts_end, lbl_from, lbl_to = _date_range(date_from, date_to)
    period_length = ts_end - ts_from
    prev_end = ts_from
    prev_start = prev_end - period_length
    bot_pv = _bot_filter("pv", exclude_bots)
    bot_s = _bot_filter("s", exclude_bots)

    async def _kpi_for_range(
        start: datetime, end: datetime
    ) -> dict[str, float]:
        params: dict[str, Any] = {"ts_from": start, "ts_end": end}

        pv = (await db.execute(text(
            "SELECT COUNT(*) AS total_views, "
            "COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors "
            f"FROM analytics.page_views pv WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot_pv}"
        ), params)).mappings().first()

        sess = (await db.execute(text(
            "SELECT COUNT(*) AS total_sessions, "
            "COALESCE(AVG(s.page_count), 0) AS avg_pages "
            f"FROM analytics.analytics_sessions s WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot_s}"
        ), params)).mappings().first()

        bounce = (await db.execute(text(
            "SELECT COUNT(*) FILTER (WHERE s.page_count = 1) AS bounced, "
            "COUNT(*) AS total "
            f"FROM analytics.analytics_sessions s WHERE s.started_at >= :ts_from AND s.started_at < :ts_end{bot_s}"
        ), params)).mappings().first()

        # New vs returning visitors
        nr = (await db.execute(text(
            "WITH user_firsts AS ("
            "  SELECT user_id, MIN(created_at) AS first_visit "
            "  FROM analytics.page_views WHERE user_id IS NOT NULL GROUP BY user_id"
            ") "
            "SELECT "
            "  COUNT(DISTINCT CASE WHEN uf.first_visit >= :ts_from AND uf.first_visit < :ts_end THEN uf.user_id END) AS new_visitors, "
            "  COUNT(DISTINCT CASE WHEN uf.first_visit < :ts_from THEN pv.user_id END) AS returning_visitors "
            "FROM user_firsts uf "
            "LEFT JOIN analytics.page_views pv ON pv.user_id = uf.user_id "
            f"  AND pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot_pv.replace('pv.', 'pv.')}"
        ), params)).mappings().first()

        # Avg active time per session (based on duration_ms from pageviews)
        active = (await db.execute(text(
            "SELECT COALESCE(SUM(pv.duration_ms), 0) / 1000.0 AS total_active_sec "
            f"FROM analytics.page_views pv WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot_pv}"
        ), params)).mappings().first()
        total_sessions = float(sess["total_sessions"]) if sess["total_sessions"] else 0
        avg_active = float(active["total_active_sec"]) / total_sessions if total_sessions > 0 else 0

        total_sess = bounce["total"] if bounce["total"] else 1
        return {
            "total_pageviews": float(pv["total_views"]),
            "unique_visitors": float(pv["unique_visitors"]),
            "new_visitors": float(nr["new_visitors"]),
            "returning_visitors": float(nr["returning_visitors"]),
            "avg_active_per_session": round(avg_active, 1),
            "avg_pages_per_session": float(sess["avg_pages"]),
            "bounce_rate": round(float(bounce["bounced"]) / total_sess * 100, 1),
        }

    current = await _kpi_for_range(ts_from, ts_end)
    previous = await _kpi_for_range(prev_start, prev_end)

    metrics = {}
    for key in current:
        metrics[key] = KPIMetric(
            current=current[key],
            previous=previous[key],
            change_pct=_compute_change_pct(current[key], previous[key]),
        )

    return DashboardSummary(
        **metrics,
        date_from=lbl_from,
        date_to=lbl_to,
        compare_from=prev_start.isoformat(),
        compare_to=prev_end.isoformat(),
    )


# ── Pageview Timeseries ──────────────────────────────────

@router.get("/pageviews/timeseries", response_model=PageviewTimeSeries)
async def get_pageview_timeseries(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    granularity: str = Query("day", regex="^(hour|day|week|month|year)$"),
):
    """Pageviews + unique visitors bucketed by granularity."""
    ts_from, ts_end, _, _ = _date_range(date_from, date_to)
    bot = _bot_filter("pv", exclude_bots)

    # Bucket sizes chosen so each view shows ~50-60 data points
    # hour=1min(60), day=30min(48), week=3hr(56), month=12hr(60), year=1wk(52)
    bucket_secs_map = {
        "hour":  60,       # 1-minute buckets
        "day":   1800,     # 30-minute buckets
        "week":  10800,    # 3-hour buckets
        "month": 43200,    # 12-hour buckets
        "year":  604800,   # 1-week buckets
    }
    fmt_map = {
        "hour":  "YYYY-MM-DD HH24:MI",
        "day":   "YYYY-MM-DD HH24:MI",
        "week":  "YYYY-MM-DD HH24:00",
        "month": "YYYY-MM-DD HH24:00",
        "year":  "YYYY-MM-DD",
    }
    bsec = bucket_secs_map[granularity]
    fmt = fmt_map[granularity]
    trunc_tpl = f"TO_TIMESTAMP(FLOOR(EXTRACT(EPOCH FROM {{a}}.{{c}}) / {bsec}) * {bsec})"
    trunc = trunc_tpl.format(a="pv", c="created_at")

    rows = (await db.execute(text(
        # Pageviews + unique visitors (unchanged)
        f"WITH pv_data AS ("
        f"  SELECT {trunc} AS bucket, "
        "  COUNT(*) AS pageviews, "
        "  COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors "
        f"  FROM analytics.page_views pv WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot} "
        f"  GROUP BY bucket"
        "), "
        # Step 1: per-session active time in each bucket
        f"pv_sess AS ("
        f"  SELECT {trunc} AS bucket, pv.session_id, "
        "  COALESCE(CAST(pv.user_id AS text), pv.session_id) AS uid, "
        "  SUM(COALESCE(pv.duration_ms, 0)) / 1000.0 AS active_sec "
        f"  FROM analytics.page_views pv WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot} "
        f"  GROUP BY bucket, pv.session_id, uid"
        "), "
        # Step 2: wall-time overlap = min(session_end, bucket_end) - max(session_start, bucket_start)
        "sess_wall AS ("
        "  SELECT ps.bucket, ps.session_id, ps.uid, ps.active_sec, "
        "  GREATEST(0, EXTRACT(EPOCH FROM ("
        f"    LEAST(COALESCE(s.ended_at, CURRENT_TIMESTAMP), TO_TIMESTAMP(EXTRACT(EPOCH FROM ps.bucket) + {bsec})) "
        "    - GREATEST(s.started_at, ps.bucket)"
        "  ))) AS wall_sec "
        "  FROM pv_sess ps "
        "  JOIN analytics.analytics_sessions s ON s.session_id = ps.session_id"
        "), "
        # Step 3: per-session engagement capped at 100%
        "sess_eng AS ("
        "  SELECT bucket, uid, "
        "  CASE WHEN wall_sec > 0 THEN LEAST(active_sec / wall_sec * 100, 100) ELSE NULL END AS eng "
        "  FROM sess_wall"
        "), "
        # Step 4: average sessions per user per bucket
        "user_eng AS ("
        "  SELECT bucket, uid, AVG(eng) AS eng "
        "  FROM sess_eng WHERE eng IS NOT NULL "
        "  GROUP BY bucket, uid"
        "), "
        # Step 5: average users per bucket
        "bucket_eng AS ("
        "  SELECT bucket, ROUND(AVG(eng)::numeric, 1) AS engagement_pct "
        "  FROM user_eng GROUP BY bucket"
        ") "
        f"SELECT TO_CHAR(p.bucket, '{fmt}') AS ts, p.pageviews, p.unique_visitors, "
        "be.engagement_pct "
        "FROM pv_data p LEFT JOIN bucket_eng be ON be.bucket = p.bucket "
        "ORDER BY p.bucket"
    ), {"ts_from": ts_from, "ts_end": ts_end})).mappings().all()

    return PageviewTimeSeries(
        points=[TimeseriesPoint(
            timestamp=r["ts"], pageviews=r["pageviews"],
            unique_visitors=r["unique_visitors"],
            engagement_pct=float(r["engagement_pct"]) if r["engagement_pct"] is not None else None,
        ) for r in rows],
        granularity=granularity,
    )


# ── Active Sessions (Redis) ─────────────────────────────

@router.get("/active-sessions", response_model=ActiveSessionsResponse)
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict = Depends(require_role("admin")),
):
    """Live visitors: scan Redis for active session keys."""
    sessions: list[ActiveSession] = []
    cursor = 0
    all_keys: list[str] = []

    # Scan for active session keys
    while True:
        cursor, keys = await redis.scan(cursor, match="analytics:session:*", count=100)
        all_keys.extend(k if isinstance(k, str) else k.decode() for k in keys)
        if cursor == 0:
            break

    if not all_keys:
        return ActiveSessionsResponse(count=0, sessions=[])

    # Extract session IDs
    session_ids = [k.split(":")[-1] for k in all_keys]

    # Batch query DB for session details
    placeholders = ", ".join(f":sid_{i}" for i in range(len(session_ids)))
    params = {f"sid_{i}": sid for i, sid in enumerate(session_ids)}
    rows = (await db.execute(text(
        "SELECT s.session_id, "
        "u.email AS user_email, "
        "ua.device_type, "
        "s.started_at, "
        "(SELECT pv.path FROM analytics.page_views pv "
        "  WHERE pv.session_id = s.session_id ORDER BY pv.created_at DESC LIMIT 1) AS current_page "
        "FROM analytics.analytics_sessions s "
        "LEFT JOIN core.users u ON s.user_id = u.id "
        "LEFT JOIN analytics.user_agents ua ON ua.session_id = s.session_id "
        f"WHERE s.session_id IN ({placeholders})"
    ), params)).mappings().all()

    # Pipeline-fetch all presence hashes
    pipe = redis.pipeline()
    for sid in session_ids:
        pipe.hgetall(f"analytics:presence:{sid}")
    presence_results = await pipe.execute()
    presence_map: dict[str, dict[str, str]] = {}
    for sid, pdata in zip(session_ids, presence_results):
        if pdata:
            presence_map[sid] = {
                (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                for k, v in pdata.items()
            }

    now = datetime.now(timezone.utc)
    now_ms = int(time.time() * 1000)
    for r in rows:
        duration = int((now - r["started_at"].replace(tzinfo=timezone.utc)).total_seconds()) if r["started_at"] else 0
        sid = r["session_id"]
        pres = presence_map.get(sid)

        presence_status = None
        page_duration_sec = None
        idle_duration_sec = None
        last_heartbeat_ago_sec = None
        current_page = r["current_page"]

        if pres:
            presence_status = pres.get("status")
            # Prefer presence path (more up-to-date than DB subquery)
            if pres.get("path"):
                current_page = pres["path"]
            entered = int(pres.get("page_entered_at", "0"))
            if entered > 0:
                page_duration_sec = max(0, (now_ms - entered) // 1000)
            idle_since = int(pres.get("idle_since", "0"))
            if idle_since > 0 and presence_status == "idle":
                idle_duration_sec = max(0, (now_ms - idle_since) // 1000)
            last_hb = int(pres.get("last_heartbeat", "0"))
            if last_hb > 0:
                last_heartbeat_ago_sec = max(0, (now_ms - last_hb) // 1000)

        sessions.append(ActiveSession(
            session_id=sid,
            user_email=r["user_email"],
            current_page=current_page,
            device_type=r["device_type"],
            duration_sec=duration,
            presence_status=presence_status,
            page_duration_sec=page_duration_sec,
            idle_duration_sec=idle_duration_sec,
            last_heartbeat_ago_sec=last_heartbeat_ago_sec,
        ))

    return ActiveSessionsResponse(count=len(sessions), sessions=sessions)


# ── Pages Engagement ────────────────────────────────────

@router.get("/pages/engagement", response_model=PagesEngagementResponse)
async def get_pages_engagement(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    page_size: int = Query(20, ge=1, le=100),
):
    """Top pages with engagement metrics: avg duration, entry count, bounce rate."""
    ts_from, ts_end, _, _ = _date_range(date_from, date_to)
    bot = _bot_filter("pv", exclude_bots)
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end, "lim": page_size}

    rows = (await db.execute(text(
        "WITH entry_pages AS ("
        "  SELECT pv2.session_id, MIN(pv2.path) AS entry_path "
        "  FROM analytics.page_views pv2 "
        "  WHERE pv2.created_at >= :ts_from AND pv2.created_at < :ts_end "
        "  AND pv2.created_at = ("
        "    SELECT MIN(pv3.created_at) FROM analytics.page_views pv3 "
        "    WHERE pv3.session_id = pv2.session_id "
        "    AND pv3.created_at >= :ts_from AND pv3.created_at < :ts_end"
        "  ) GROUP BY pv2.session_id"
        "), bounced_sessions AS ("
        "  SELECT s.session_id FROM analytics.analytics_sessions s "
        "  WHERE s.started_at >= :ts_from AND s.started_at < :ts_end AND s.page_count = 1"
        ") "
        "SELECT pv.path, COUNT(*) AS views, "
        "COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors, "
        "AVG(pv.duration_ms) AS avg_duration_ms, "
        "COUNT(DISTINCT CASE WHEN ep.entry_path = pv.path THEN ep.session_id END) AS entry_count, "
        "COUNT(DISTINCT CASE WHEN ep.entry_path = pv.path AND bs.session_id IS NOT NULL "
        "  THEN ep.session_id END) AS bounce_count "
        "FROM analytics.page_views pv "
        "LEFT JOIN entry_pages ep ON ep.session_id = pv.session_id AND ep.entry_path = pv.path "
        "LEFT JOIN bounced_sessions bs ON bs.session_id = pv.session_id "
        f"WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot} "
        "GROUP BY pv.path ORDER BY views DESC LIMIT :lim"
    ), params)).mappings().all()

    return PagesEngagementResponse(
        pages=[PageEngagement(
            path=r["path"], views=r["views"], unique_visitors=r["unique_visitors"],
            avg_duration_ms=float(r["avg_duration_ms"]) if r["avg_duration_ms"] else None,
            entry_count=r["entry_count"], bounce_count=r["bounce_count"],
        ) for r in rows]
    )


# ── Enriched User List ──────────────────────────────────

def _compute_engagement(total_sessions: int, avg_duration: float, last_active: datetime | None) -> str:
    now = datetime.now(timezone.utc)
    recent = last_active and (now - last_active.replace(tzinfo=timezone.utc)).days <= 7 if last_active else False
    if total_sessions >= 5 and avg_duration > 120 and recent:
        return "high"
    if total_sessions >= 2 or (total_sessions >= 1 and avg_duration > 60):
        return "medium"
    return "low"


@router.get("/users/enriched", response_model=EnrichedUserList)
async def get_enriched_users(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict = Depends(require_role("admin")),
    q: str = Query("", min_length=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
    sort_by: str = Query("last_active", regex="^(last_active|pageviews|sessions|active_time|engagement)$"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    segment: str = Query("all", regex="^(all|active_today|active_week|inactive)$"),
    page_size: int = Query(30, ge=1, le=100),
):
    """Enriched user list with engagement scoring."""
    ts_from, ts_end, _, _ = _date_range(date_from, date_to)
    bot = _bot_filter("pv", exclude_bots)
    params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end, "lim": page_size}

    search_clause = ""
    if q:
        search_clause = "AND u.email ILIKE :q"
        params["q"] = f"%{q}%"

    # Segment filter
    now = datetime.now(timezone.utc)
    segment_clause = ""
    if segment == "active_today":
        segment_clause = "HAVING MAX(pv.created_at) >= :seg_start"
        params["seg_start"] = now - timedelta(days=1)
    elif segment == "active_week":
        segment_clause = "HAVING MAX(pv.created_at) >= :seg_start"
        params["seg_start"] = now - timedelta(days=7)
    elif segment == "inactive":
        segment_clause = "HAVING MAX(pv.created_at) < :seg_start OR MAX(pv.created_at) IS NULL"
        params["seg_start"] = now - timedelta(days=7)

    sort_map = {
        "last_active": "last_active",
        "pageviews": "total_pageviews",
        "sessions": "total_sessions",
        "active_time": "total_active_sec",
        "engagement": "engagement_pct",
    }
    order_col = sort_map.get(sort_by, "last_active")
    order = f"{order_col} {sort_dir.upper()} NULLS LAST"

    # Use correlated subqueries for active time and wall time to avoid
    # cross-join inflation from the many-to-many users↔pageviews↔sessions join
    rows = (await db.execute(text(
        "SELECT CAST(u.id AS text) AS user_id, u.email, u.first_name, u.last_name, "
        "COALESCE(COUNT(DISTINCT pv.id), 0) AS total_pageviews, "
        "COALESCE(COUNT(DISTINCT s.session_id), 0) AS total_sessions, "
        "MAX(pv.created_at) AS last_active, "
        "COALESCE(AVG(EXTRACT(EPOCH FROM (s.ended_at - s.started_at))), 0) AS avg_session_duration_sec, "
        "(SELECT pv2.path FROM analytics.page_views pv2 WHERE pv2.user_id = u.id "
        "  GROUP BY pv2.path ORDER BY COUNT(*) DESC LIMIT 1) AS top_page, "
        "(SELECT COALESCE(SUM(pv3.duration_ms), 0) / 1000.0 FROM analytics.page_views pv3 "
        f"  WHERE pv3.user_id = u.id AND pv3.created_at >= :ts_from AND pv3.created_at < :ts_end{bot.replace('pv.', 'pv3.')}) AS total_active_sec, "
        "(SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (s2.ended_at - s2.started_at))), 0) FROM analytics.analytics_sessions s2 "
        "  WHERE s2.user_id = u.id AND s2.started_at >= :ts_from AND s2.started_at < :ts_end) AS total_wall_sec, "
        "CASE WHEN (SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (s3.ended_at - s3.started_at))), 0) FROM analytics.analytics_sessions s3 "
        "  WHERE s3.user_id = u.id AND s3.started_at >= :ts_from AND s3.started_at < :ts_end) > 0 "
        "THEN LEAST((SELECT COALESCE(SUM(pv4.duration_ms), 0) / 1000.0 FROM analytics.page_views pv4 "
        f"  WHERE pv4.user_id = u.id AND pv4.created_at >= :ts_from AND pv4.created_at < :ts_end{bot.replace('pv.', 'pv4.')}) / "
        "(SELECT SUM(EXTRACT(EPOCH FROM (s4.ended_at - s4.started_at))) FROM analytics.analytics_sessions s4 "
        "  WHERE s4.user_id = u.id AND s4.started_at >= :ts_from AND s4.started_at < :ts_end) * 100, 100) "
        "ELSE NULL END AS engagement_pct "
        "FROM core.users u "
        f"LEFT JOIN analytics.page_views pv ON u.id = pv.user_id AND pv.created_at >= :ts_from AND pv.created_at < :ts_end{bot} "
        "LEFT JOIN analytics.analytics_sessions s ON u.id = s.user_id AND s.started_at >= :ts_from AND s.started_at < :ts_end "
        f"WHERE u.is_active = true {search_clause} "
        f"GROUP BY u.id, u.email, u.first_name, u.last_name {segment_clause} "
        f"ORDER BY {order} LIMIT :lim"
    ), params)).mappings().all()

    # Count total matching users
    count_params: dict[str, Any] = {"ts_from": ts_from, "ts_end": ts_end}
    count_search = ""
    if q:
        count_search = "AND u.email ILIKE :q"
        count_params["q"] = f"%{q}%"
    total_row = (await db.execute(text(
        f"SELECT COUNT(*) AS cnt FROM core.users u WHERE u.is_active = true {count_search}"
    ), count_params)).mappings().first()

    # Live detection: single Redis SCAN for all active sessions,
    # then query which user_ids own those sessions
    live_user_ids: set[str] = set()
    live_sids: list[str] = []
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="analytics:session:*", count=200)
        for k in keys:
            sid = k.decode() if isinstance(k, bytes) else k
            live_sids.append(sid.replace("analytics:session:", ""))
        if cursor == 0:
            break
    if live_sids:
        sid_result = (await db.execute(text(
            "SELECT DISTINCT CAST(user_id AS text) AS uid "
            "FROM analytics.analytics_sessions "
            "WHERE session_id = ANY(:sids) AND user_id IS NOT NULL"
        ), {"sids": live_sids})).mappings().all()
        live_user_ids = {r["uid"] for r in sid_result}

    users = []
    for r in rows:
        avg_dur = float(r["avg_session_duration_sec"])
        active_sec = float(r["total_active_sec"]) if r["total_active_sec"] else None
        eng_pct = round(float(r["engagement_pct"]), 1) if r["engagement_pct"] is not None else None
        users.append(EnrichedUser(
            user_id=r["user_id"], email=r["email"],
            first_name=r["first_name"], last_name=r["last_name"],
            total_pageviews=r["total_pageviews"], total_sessions=r["total_sessions"],
            last_active=r["last_active"],
            avg_session_duration_sec=round(avg_dur, 1),
            top_page=r["top_page"],
            total_active_time_sec=round(active_sec, 1) if active_sec else None,
            avg_engagement_pct=eng_pct,
            is_live=r["user_id"] in live_user_ids,
        ))

    return EnrichedUserList(users=users, total_count=total_row["cnt"])


# ── Session Detail / Journey ────────────────────────────

@router.get("/session/{session_id}/pages", response_model=SessionDetail)
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict = Depends(require_role("admin")),
):
    """Session journey: all pageviews within a session, chronological."""
    # Check Redis for active status
    is_active = await redis.exists(f"analytics:session:{session_id}")

    # Session info
    sess = (await db.execute(text(
        "SELECT s.session_id, CAST(s.user_id AS text) AS user_id, s.started_at, s.ended_at, "
        "u.email AS user_email, ua.device_type, ua.browser, ua.os "
        "FROM analytics.analytics_sessions s "
        "LEFT JOIN core.users u ON s.user_id = u.id "
        "LEFT JOIN analytics.user_agents ua ON ua.session_id = s.session_id "
        "WHERE s.session_id = :sid"
    ), {"sid": session_id})).mappings().first()

    if not sess:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Session not found", "details": None})

    # Pageviews in this session
    pages = (await db.execute(text(
        "SELECT path, duration_ms, trigger, created_at "
        "FROM analytics.page_views WHERE session_id = :sid "
        "ORDER BY created_at ASC"
    ), {"sid": session_id})).mappings().all()

    # Presence data from Redis
    presence_status = None
    current_page_live = None
    current_page_duration_sec = None
    idle_duration_sec = None
    active_segment_duration_sec = None

    pres_raw = await redis.hgetall(f"analytics:presence:{session_id}")
    if pres_raw:
        pres = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in pres_raw.items()
        }
        now_ms = int(time.time() * 1000)
        presence_status = pres.get("status")
        current_page_live = pres.get("path")
        entered = int(pres.get("page_entered_at", "0"))
        if entered > 0:
            current_page_duration_sec = max(0, (now_ms - entered) // 1000)
        idle_since = int(pres.get("idle_since", "0"))
        if idle_since > 0 and presence_status == "idle":
            idle_duration_sec = max(0, (now_ms - idle_since) // 1000)
        active_since = int(pres.get("active_since", "0"))
        if active_since > 0 and presence_status == "active":
            active_segment_duration_sec = max(0, (now_ms - active_since) // 1000)

    return SessionDetail(
        session_id=sess["session_id"],
        user_id=sess["user_id"],
        user_email=sess["user_email"],
        started_at=sess["started_at"],
        ended_at=sess["ended_at"],
        is_active=bool(is_active),
        device_type=sess["device_type"],
        browser=sess["browser"],
        os=sess["os"],
        pages=[SessionPageView(**p) for p in pages],
        presence_status=presence_status,
        current_page_live=current_page_live,
        current_page_duration_sec=current_page_duration_sec,
        idle_duration_sec=idle_duration_sec,
        active_segment_duration_sec=active_segment_duration_sec,
    )


# ── User Search ──────────────────────────────────────────

@router.get("/users", response_model=TrackedUserList)
async def search_tracked_users(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
    q: str = Query("", min_length=0),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    exclude_bots: bool = Query(True),
):
    """Search users filtered by email, with pageview counts in date range."""
    ts_from, ts_end, _, _ = _date_range(date_from, date_to)
    params: dict[str, Any] = {"lim": 20, "ts_from": ts_from, "ts_end": ts_end}
    search_clause = ""
    if q:
        search_clause = "AND u.email ILIKE :q"
        params["q"] = f"%{q}%"

    bot = _bot_filter("pv", exclude_bots)
    date_filter = "AND pv.created_at >= :ts_from AND pv.created_at < :ts_end"

    rows = (
        await db.execute(
            text(
                "SELECT CAST(u.id AS text) AS user_id, u.email, "
                "u.first_name, u.last_name, COALESCE(COUNT(pv.id), 0) AS total_pageviews "
                "FROM core.users u "
                f"LEFT JOIN analytics.page_views pv ON u.id = pv.user_id {date_filter}{bot} "
                f"WHERE u.is_active = true {search_clause} "
                "GROUP BY u.id, u.email, u.first_name, u.last_name "
                "ORDER BY total_pageviews DESC, u.email LIMIT :lim"
            ),
            params,
        )
    ).mappings().all()

    return TrackedUserList(users=[TrackedUser(**r) for r in rows])


# ── User Activity Detail ─────────────────────────────────

@router.get("/user/{target_user_id}/activity", response_model=UserActivity)
async def get_user_activity(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    user: dict = Depends(require_role("admin")),
):
    """Consolidated activity for a single user."""
    # Look up user info
    user_row = (
        await db.execute(
            text(
                "SELECT CAST(id AS text) AS user_id, email "
                "FROM core.users WHERE id = CAST(:uid AS uuid)"
            ),
            {"uid": target_user_id},
        )
    ).mappings().first()

    email = user_row["email"] if user_row else "Unknown"

    # Recent pageviews
    pv_rows = (
        await db.execute(
            text(
                "SELECT path, duration_ms, created_at "
                "FROM analytics.page_views "
                "WHERE user_id = CAST(:uid AS uuid) "
                "ORDER BY created_at DESC LIMIT 100"
            ),
            {"uid": target_user_id},
        )
    ).mappings().all()

    # Sessions with device info (LEFT JOIN user_agents)
    sess_rows = (
        await db.execute(
            text(
                "SELECT s.session_id, s.started_at, s.ended_at, s.page_count, "
                "ua.browser, ua.os, ua.device_type "
                "FROM analytics.analytics_sessions s "
                "LEFT JOIN analytics.user_agents ua ON ua.session_id = s.session_id "
                "WHERE s.user_id = CAST(:uid AS uuid) "
                "ORDER BY s.started_at DESC LIMIT 50"
            ),
            {"uid": target_user_id},
        )
    ).mappings().all()

    # Extended totals with first/last visit, total time, avg session duration
    totals = (
        await db.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM analytics.page_views WHERE user_id = CAST(:uid AS uuid)) AS pv, "
                "(SELECT COUNT(*) FROM analytics.analytics_sessions WHERE user_id = CAST(:uid AS uuid)) AS sess, "
                "(SELECT MIN(created_at) FROM analytics.page_views WHERE user_id = CAST(:uid AS uuid)) AS first_visit, "
                "(SELECT MAX(created_at) FROM analytics.page_views WHERE user_id = CAST(:uid AS uuid)) AS last_visit, "
                "(SELECT COALESCE(SUM(duration_ms), 0) / 1000.0 FROM analytics.page_views WHERE user_id = CAST(:uid AS uuid)) AS total_time_sec, "
                "(SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (ended_at - started_at))), 0) "
                "  FROM analytics.analytics_sessions WHERE user_id = CAST(:uid AS uuid) AND ended_at IS NOT NULL) AS avg_sess_dur, "
                "(SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (ended_at - started_at))), 0) "
                "  FROM analytics.analytics_sessions WHERE user_id = CAST(:uid AS uuid) AND ended_at IS NOT NULL) AS total_session_time_sec, "
                "(SELECT COALESCE(SUM(pv.duration_ms), 0) / 1000.0 / NULLIF("
                "  (SELECT COUNT(*) FROM analytics.analytics_sessions WHERE user_id = CAST(:uid AS uuid)), 0) "
                "  FROM analytics.page_views pv "
                "  JOIN analytics.analytics_sessions s ON pv.session_id = s.session_id "
                "  WHERE s.user_id = CAST(:uid AS uuid)) AS avg_active_per_session"
            ),
            {"uid": target_user_id},
        )
    ).mappings().first()

    # Detect live sessions via Redis (not DB — ended_at is always set)
    all_session_ids = [r["session_id"] for r in sess_rows]
    live_session_ids: list[str] = []
    for sid in all_session_ids:
        if await redis.exists(f"analytics:session:{sid}"):
            live_session_ids.append(sid)
    live_count = len(live_session_ids)

    # Add live session wall time to total_session_time
    # Ended sessions: SUM(ended_at - started_at) from DB
    # Live sessions: SUM(now - started_at) computed here
    total_session_sec = float(totals["total_session_time_sec"])
    for sr in sess_rows:
        if sr["session_id"] in live_session_ids:
            live_wall = (datetime.now(timezone.utc) - sr["started_at"].replace(tzinfo=timezone.utc)).total_seconds()
            total_session_sec += live_wall

    # Top pages for this user
    top_pages_rows = (
        await db.execute(
            text(
                "SELECT path, COUNT(*) AS views "
                "FROM analytics.page_views WHERE user_id = CAST(:uid AS uuid) "
                "GROUP BY path ORDER BY views DESC LIMIT 5"
            ),
            {"uid": target_user_id},
        )
    ).mappings().all()

    avg_dur = float(totals["avg_sess_dur"])

    # Compute engagement percentages
    total_active_sec = float(totals["total_time_sec"])
    avg_eng_all = round(total_active_sec / total_session_sec * 100, 1) if total_session_sec > 0 else 0.0

    # Live-session engagement via Redis-detected sessions
    avg_eng_live = None
    if live_count > 0:
        placeholders = ", ".join(f":sid_{i}" for i in range(live_count))
        params = {f"sid_{i}": sid for i, sid in enumerate(live_session_ids)}
        live_row = (
            await db.execute(
                text(
                    f"SELECT COALESCE(SUM(pv.duration_ms), 0) / 1000.0 AS active_sec "
                    f"FROM analytics.page_views pv "
                    f"WHERE pv.session_id IN ({placeholders})"
                ),
                params,
            )
        ).mappings().first()
        if live_row:
            live_active = float(live_row["active_sec"])
            live_wall = sum(
                (datetime.now(timezone.utc) - sr["started_at"].replace(tzinfo=timezone.utc)).total_seconds()
                for sr in sess_rows if sr["session_id"] in live_session_ids
            )
            if live_wall > 0:
                avg_eng_live = round(live_active / live_wall * 100, 1)

    return UserActivity(
        user_id=target_user_id,
        email=email,
        total_pageviews=totals["pv"],
        total_sessions=totals["sess"],
        first_visit=totals["first_visit"],
        last_visit=totals["last_visit"],
        total_time_sec=total_active_sec,
        avg_session_duration_sec=round(avg_dur, 1),
        total_session_time_sec=round(total_session_sec, 1),
        live_session_count=live_count,
        avg_active_per_session_sec=round(float(totals["avg_active_per_session"]), 1) if totals["avg_active_per_session"] else 0.0,
        avg_engagement_all_pct=avg_eng_all,
        avg_engagement_live_pct=avg_eng_live,
        top_pages=[UserTopPage(path=r["path"], views=r["views"]) for r in top_pages_rows],
        recent_pageviews=[UserPageView(**r) for r in pv_rows],
        sessions=[UserSession(**r) for r in sess_rows],
    )
