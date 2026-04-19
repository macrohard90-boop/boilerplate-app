"""Pydantic schemas for marketing module requests and responses."""

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
