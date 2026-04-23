"""Pydantic schemas for marketing module requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


# ── Campaigns ──


class CampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=255)
    template_id: str = Field(..., min_length=1, max_length=100)
    template_data: dict = Field(default_factory=dict)
    scheduled_at: str | None = None  # ISO 8601 datetime


class CampaignResponse(BaseModel):
    id: str
    name: str
    subject: str
    template_id: str
    status: str
    provider_campaign_id: str | None = None
    recipient_count: int = 0
    scheduled_at: str | None = None
    sent_at: str | None = None
    created_at: str
    stats: dict | None = None


class CampaignStatsResponse(BaseModel):
    sent: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    bounced: int = 0
    unsubscribed: int = 0
    fetched_at: str | None = None


# ── Communication Types ──


class CommunicationTypeResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    enabled: bool = True


class CommunicationTypeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    enabled: bool = True


# ── User Preferences ──


class UserPreferenceItem(BaseModel):
    communication_type_id: str
    allowed: bool


class UserPreferencesUpdateRequest(BaseModel):
    preferences: list[UserPreferenceItem]


class UserPreferenceResponse(BaseModel):
    communication_type_id: str
    communication_type_name: str
    description: str | None = None
    allowed: bool


# ── Email Templates ──


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(..., min_length=1, max_length=255)
    subject: str | None = Field(None, max_length=500)
    html_content: str = Field(..., min_length=1)
    category: str = Field("campaign", pattern=r"^(transactional|campaign|automation)$")
    description: str | None = None
    variables: list[dict] = Field(default_factory=list)


class TemplateUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    subject: str | None = Field(None, max_length=500)
    html_content: str | None = Field(None, min_length=1)
    category: str | None = Field(None, pattern=r"^(transactional|campaign|automation)$")
    description: str | None = None
    variables: list[dict] | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    display_name: str
    subject: str | None = None
    html_content: str | None = None
    category: str
    description: str | None = None
    variables: list[dict] = Field(default_factory=list)
    is_builtin: bool = False
    version: int = 1
    created_by: str | None = None
    created_at: str
    updated_at: str


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int
    page: int
    per_page: int


class TemplateCloneRequest(BaseModel):
    new_name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$"
    )
    new_display_name: str = Field(..., min_length=1, max_length=255)


class TemplatePreviewRequest(BaseModel):
    html_content: str = Field(..., min_length=1)
    template_data: dict = Field(default_factory=dict)


# ── Campaign Wizard (A/B Variants) ──


class VariantInput(BaseModel):
    label: str = Field(..., min_length=1, max_length=10)
    subject: str = Field(..., min_length=1, max_length=255)
    html_content: str = Field(..., min_length=1)
    source_template_id: str | None = None
    weight: int = Field(default=100, ge=1)


class CampaignSegmentInput(BaseModel):
    segment_id: str
    variant_label: str | None = None  # None = all variants


class CampaignWizardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    variants: list[VariantInput] = Field(..., min_length=1)
    segments: list[CampaignSegmentInput] = Field(default_factory=list)
    utm_source: str | None = None
    utm_medium: str | None = "email"
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    scheduled_at: str | None = None


class VariantResponse(BaseModel):
    id: str
    label: str
    subject: str
    html_content: str | None = None
    source_template_id: str | None = None
    weight: int = 100
    provider_campaign_id: str | None = None
    stats_cache: dict | None = None
    created_at: str


class VariantStatsResponse(BaseModel):
    label: str
    subject: str
    weight: int
    stats: dict[str, Any]


# ── Audience Segments ──


class SegmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class SegmentUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    filters: dict[str, Any] | None = None


class SegmentResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    is_system: bool = False
    user_count: int = 0
    last_computed_at: str | None = None
    created_at: str


class SegmentPreviewRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class SegmentPreviewResponse(BaseModel):
    count: int
    sample_users: list[dict[str, str]] = Field(default_factory=list)


# ── Insights ──


class InsightsGlobalResponse(BaseModel):
    total_eligible: int = 0
    by_rfm_segment: dict[str, int] = Field(default_factory=dict)
    avg_order_value: float = 0.0
    avg_orders_per_user: float = 0.0
    active_last_30_days: int = 0
    cart_abandonment_count: int = 0
    top_communication_types: list[dict[str, Any]] = Field(default_factory=list)


class InsightsSegmentRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class InsightsSegmentResponse(BaseModel):
    user_count: int = 0
    pct_of_total: float = 0.0
    avg_order_value: float = 0.0
    avg_orders_per_user: float = 0.0
    total_revenue: int = 0
    rfm_breakdown: dict[str, int] = Field(default_factory=dict)
    top_products: list[dict[str, Any]] = Field(default_factory=list)
    recent_email_stats: dict[str, int] = Field(default_factory=dict)


class SendTimeSuggestionResponse(BaseModel):
    suggested_hour: int = 10
    suggested_day: str = "Tuesday"
    confidence: str = "low"
    note: str | None = None


class BehaviorInsightsResponse(BaseModel):
    user_count: int = 0
    device_breakdown: dict[str, int] = Field(default_factory=dict)
    browser_breakdown: dict[str, int] = Field(default_factory=dict)
    os_breakdown: dict[str, int] = Field(default_factory=dict)
    top_pages: list[dict[str, Any]] = Field(default_factory=list)
    avg_sessions_per_user: float = 0.0
    avg_page_views_per_user: float = 0.0
