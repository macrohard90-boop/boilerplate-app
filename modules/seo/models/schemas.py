"""Pydantic request/response models for the SEO module."""

from pydantic import BaseModel, Field


# ── Meta Tags ───────────────────────────────────────────────

class MetaTagsResponse(BaseModel):
    path: str
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    robots: str = "index, follow"
    og_tags: dict | None = None
    twitter_tags: dict | None = None
    structured_data: list[dict] | None = None
    is_custom: bool = False


class MetaTagsUpdate(BaseModel):
    title: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=160)
    robots_index: bool = True
    robots_follow: bool = True
    canonical_url: str | None = None


# ── Admin Meta Overrides ────────────────────────────────────

class AdminMetaListItem(BaseModel):
    id: str
    path: str
    title: str | None = None
    description: str | None = None
    robots_index: bool = True
    robots_follow: bool = True
    canonical_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AdminMetaListResponse(BaseModel):
    items: list[AdminMetaListItem]
    total: int
    page: int
    page_size: int


# ── SEO Config ──────────────────────────────────────────────

class SEOConfigResponse(BaseModel):
    site_name: str
    default_og_image: str
    social_handles: dict
    domain: str
    sitemap_cache_ttl: int


class SEOConfigUpdate(BaseModel):
    site_name: str | None = None
    default_og_image: str | None = None
    social_handles: dict | None = None


# ── Scoring ─────────────────────────────────────────────────

class ScoreRuleResult(BaseModel):
    rule_id: str
    name: str
    passed: bool
    weight: int
    points: int
    max_points: int
    recommendation: str | None = None


class PageScoreResponse(BaseModel):
    id: str
    path: str
    score: int
    rule_results: list[ScoreRuleResult]
    provider: str
    scored_at: str


class PageScoreListResponse(BaseModel):
    items: list[PageScoreResponse]
    total: int
    page: int
    page_size: int


class ScoreTrendPoint(BaseModel):
    scored_at: str
    score: int


class ScoreTrendResponse(BaseModel):
    path: str
    trend: list[ScoreTrendPoint]


# ── Snapshots ───────────────────────────────────────────────

class PageSnapshotResponse(BaseModel):
    id: str
    path: str
    snapshot: dict
    trigger: str
    changed_by: str | None = None
    diff: dict | None = None
    created_at: str


class SnapshotListResponse(BaseModel):
    items: list[PageSnapshotResponse]
    total: int
    page: int
    page_size: int


# ── Crawler ─────────────────────────────────────────────────

class CrawlMismatch(BaseModel):
    field: str
    expected: str | None = None
    actual: str | None = None
    severity: str  # "critical", "warning", "info"


class CrawlResultResponse(BaseModel):
    id: str
    path: str
    status_code: int | None = None
    rendered_meta: dict | None = None
    api_meta: dict | None = None
    mismatches: list[CrawlMismatch]
    crawled_at: str


class CrawlResultListResponse(BaseModel):
    items: list[CrawlResultResponse]
    total: int
    page: int
    page_size: int


# ── Common ──────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
