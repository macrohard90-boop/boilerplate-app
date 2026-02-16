"""Pydantic request/response models for tracking & analytics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Collection (inbound) ─────────────────────────────────

class PageViewCreate(BaseModel):
    path: str
    referrer: str | None = None
    duration_ms: int | None = None


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
