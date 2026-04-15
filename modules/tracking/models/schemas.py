"""Pydantic request/response models for tracking & analytics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Collection (inbound) ─────────────────────────────────

class PageViewCreate(BaseModel):
    path: str
    referrer: str | None = None
    duration_ms: int | None = None
    trigger: str | None = None


class PageViewBatch(BaseModel):
    items: list[PageViewCreate] = Field(..., max_length=100)


class EventCreate(BaseModel):
    event_type: str = Field(..., max_length=100)
    event_data: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    items: list[EventCreate] = Field(..., max_length=100)


# ── Responses ────────────────────────────────────────────

class TrackingResponse(BaseModel):
    recorded: int
    session_id: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Any = None


# ── Admin: Page View Stats ───────────────────────────────

class TopPage(BaseModel):
    path: str
    views: int
    unique_visitors: int
    total_duration_ms: int = 0


class PageViewStats(BaseModel):
    total_views: int
    unique_visitors: int
    date_from: str | None = None
    date_to: str | None = None
    top_pages: list[TopPage] = []


# ── Admin: Session Stats ────────────────────────────────

class SessionDayStat(BaseModel):
    date: str
    sessions: int


class SessionStats(BaseModel):
    total_sessions: int
    avg_page_count: float
    date_from: str | None = None
    date_to: str | None = None
    by_day: list[SessionDayStat] = []


# ── Admin: Event Stats ──────────────────────────────────

class EventTypeStat(BaseModel):
    event_type: str
    count: int


class EventStats(BaseModel):
    total_events: int
    date_from: str | None = None
    date_to: str | None = None
    by_type: list[EventTypeStat] = []


# ── Admin: Source Stats ──────────────────────────────────

class SourceStat(BaseModel):
    source: str
    medium: str | None = None
    sessions: int


class SourceStats(BaseModel):
    total_sources: int
    date_from: str | None = None
    date_to: str | None = None
    sources: list[SourceStat] = []


# ── Admin: UTM Stats ────────────────────────────────────

class UTMCampaignStat(BaseModel):
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    sessions: int


class UTMStats(BaseModel):
    total_campaigns: int
    date_from: str | None = None
    date_to: str | None = None
    campaigns: list[UTMCampaignStat] = []


# ── Admin: Device / Browser Stats ──────────────────────

class DeviceTypeStat(BaseModel):
    device_type: str
    count: int
    total_duration_ms: int = 0


class BrowserStat(BaseModel):
    browser: str
    count: int
    total_duration_ms: int = 0


class OSStat(BaseModel):
    os: str
    count: int
    total_duration_ms: int = 0


class DeviceStats(BaseModel):
    total_agents: int
    date_from: str | None = None
    date_to: str | None = None
    by_device_type: list[DeviceTypeStat] = []
    by_browser: list[BrowserStat] = []
    by_os: list[OSStat] = []


# ── Admin: Per-User Analytics ──────────────────────────

class TrackedUser(BaseModel):
    user_id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    total_pageviews: int


class TrackedUserList(BaseModel):
    users: list[TrackedUser] = []


class UserPageView(BaseModel):
    path: str
    duration_ms: int | None = None
    created_at: datetime


class UserSession(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: datetime | None = None
    page_count: int
    browser: str | None = None
    os: str | None = None
    device_type: str | None = None


class UserActivity(BaseModel):
    user_id: str
    email: str
    total_pageviews: int
    total_sessions: int
    first_visit: datetime | None = None
    last_visit: datetime | None = None
    total_time_sec: float | None = None
    avg_session_duration_sec: float | None = None
    total_session_time_sec: float | None = None
    live_session_count: int = 0
    avg_active_per_session_sec: float | None = None
    avg_engagement_all_pct: float | None = None
    avg_engagement_live_pct: float | None = None
    top_pages: list["UserTopPage"] = []
    recent_pageviews: list[UserPageView] = []
    sessions: list[UserSession] = []


# ── Admin: Dashboard KPI Summary ────────────────────────

class KPIMetric(BaseModel):
    current: float
    previous: float
    change_pct: float | None = None


class DashboardSummary(BaseModel):
    total_pageviews: KPIMetric
    unique_visitors: KPIMetric
    new_visitors: KPIMetric
    returning_visitors: KPIMetric
    avg_active_per_session: KPIMetric
    avg_pages_per_session: KPIMetric
    bounce_rate: KPIMetric
    date_from: str
    date_to: str
    compare_from: str
    compare_to: str


# ── Admin: Pageview Timeseries ───────────────────────────

class TimeseriesPoint(BaseModel):
    timestamp: str
    pageviews: int
    unique_visitors: int
    engagement_pct: float | None = None


class PageviewTimeSeries(BaseModel):
    points: list[TimeseriesPoint] = []
    granularity: str = "day"


# ── Heartbeat (inbound) ─────────────────────────────────

class HeartbeatCreate(BaseModel):
    path: str
    status: str = Field(default="active", pattern="^(active|idle)$")


# ── Admin: Active Sessions ──────────────────────────────

class ActiveSession(BaseModel):
    session_id: str
    user_email: str | None = None
    current_page: str | None = None
    device_type: str | None = None
    duration_sec: int = 0
    presence_status: str | None = None
    page_duration_sec: int | None = None
    idle_duration_sec: int | None = None
    last_heartbeat_ago_sec: int | None = None


class ActiveSessionsResponse(BaseModel):
    count: int
    sessions: list[ActiveSession] = []


# ── Admin: Page Engagement ───────────────────────────────

class PageEngagement(BaseModel):
    path: str
    views: int
    unique_visitors: int
    avg_duration_ms: float | None = None
    entry_count: int = 0
    bounce_count: int = 0


class PagesEngagementResponse(BaseModel):
    pages: list[PageEngagement] = []


# ── Admin: Enriched User List ────────────────────────────

class EnrichedUser(BaseModel):
    user_id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    total_pageviews: int
    total_sessions: int
    last_active: datetime | None = None
    avg_session_duration_sec: float | None = None
    top_page: str | None = None
    total_active_time_sec: float | None = None
    avg_engagement_pct: float | None = None
    is_live: bool = False


class EnrichedUserList(BaseModel):
    users: list[EnrichedUser] = []
    total_count: int = 0


# ── Admin: User Top Page ────────────────────────────────

class UserTopPage(BaseModel):
    path: str
    views: int


# ── Admin: Session Detail / Journey ─────────────────────

class SessionPageView(BaseModel):
    path: str
    duration_ms: int | None = None
    trigger: str | None = None
    created_at: datetime


class SessionDetail(BaseModel):
    session_id: str
    user_id: str | None = None
    user_email: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    is_active: bool = False
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    pages: list[SessionPageView] = []
    presence_status: str | None = None
    current_page_live: str | None = None
    current_page_duration_sec: int | None = None
    idle_duration_sec: int | None = None
    active_segment_duration_sec: int | None = None
