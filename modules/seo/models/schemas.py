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


# ── Site Audit ──────────────────────────────────────────────


class AuditCheckResponse(BaseModel):
    check_id: str
    category: str
    severity: str
    passed: bool
    title: str
    description: str
    recommendation: str | None = None
    affected_pages: list[str] | None = None


class AuditReportResponse(BaseModel):
    id: str | None = None
    checks: list[AuditCheckResponse]
    summary: dict
    score: int
    triggered_by: str | None = None
    created_at: str


class AuditListResponse(BaseModel):
    items: list[AuditReportResponse]
    total: int
    page: int
    page_size: int


# ── Keywords ───────────────────────────────────────────────


class TargetKeywordResponse(BaseModel):
    id: str
    keyword: str
    path: str | None = None
    priority: int = 5
    notes: str | None = None
    created_at: str
    updated_at: str


class TargetKeywordCreate(BaseModel):
    keyword: str = Field(..., max_length=200)
    path: str | None = Field(None, max_length=500)
    priority: int = Field(5, ge=1, le=10)
    notes: str | None = None


class TargetKeywordUpdate(BaseModel):
    priority: int | None = Field(None, ge=1, le=10)
    notes: str | None = None
    path: str | None = None


class TargetKeywordListResponse(BaseModel):
    items: list[TargetKeywordResponse]
    total: int
    page: int
    page_size: int


class KeywordSuggestionResponse(BaseModel):
    id: str | None = None
    keyword: str
    search_volume: int | None = None
    competition: float | None = None
    trend: str | None = None
    source: str
    depth_level: int = 1
    seed_keyword: str | None = None
    fetched_at: str | None = None


class KeywordSuggestionListResponse(BaseModel):
    items: list[KeywordSuggestionResponse]
    total: int
    page: int
    page_size: int


class KeywordDiscoverRequest(BaseModel):
    seed: str = Field(..., max_length=200)
    depth: int = Field(2, ge=1, le=3)
    limit: int = Field(50, ge=1, le=200)


# ── Advisor ─────────────────────────────────────────────────


class AdvisorAnalyzeRequest(BaseModel):
    business_context: str | None = Field(None, max_length=2000)
    intent: str | None = Field(None, max_length=500)


# ── Page Registry ──────────────────────────────────────────


class PageRegistryCreate(BaseModel):
    path: str = Field(..., max_length=500)
    changefreq: str = Field(
        "monthly",
        pattern=r"^(always|hourly|daily|weekly|monthly|yearly|never)$",
    )
    priority: float = Field(0.5, ge=0.0, le=1.0)


# ── Common ──────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message: str
