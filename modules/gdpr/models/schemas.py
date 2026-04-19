"""Pydantic request/response models for GDPR module."""

from typing import Any

from pydantic import BaseModel, Field


# ── Consent ─────────────────────────────────────────────────

CONSENT_TYPES = [
    "marketing_email",
    "transactional_email",
    "third_party_sharing",
    "analytics",
    "cookies_analytics",
    "cookies_marketing",
]


class ConsentUpdate(BaseModel):
    consent_type: str = Field(..., description="One of the 6 consent types")
    granted: bool
    version: str = "1.0"


class ConsentTypeState(BaseModel):
    consent_type: str
    granted: bool
    updated_at: str | None = None


class ConsentState(BaseModel):
    consents: list[ConsentTypeState]


class ConsentHistoryItem(BaseModel):
    id: str
    consent_type: str
    granted: bool
    version: str
    ip_address: str | None = None
    created_at: str


class ConsentHistoryResponse(BaseModel):
    items: list[ConsentHistoryItem]
    total: int
    page: int
    page_size: int


# ── Cookie Preferences ──────────────────────────────────────


class CookiePreferencesUpdate(BaseModel):
    analytics: bool = False
    marketing: bool = False
    preferences: bool = False


class CookiePreferencesResponse(BaseModel):
    necessary: bool = True
    analytics: bool = False
    marketing: bool = False
    preferences: bool = False
    updated_at: str | None = None


# ── Data Export ──────────────────────────────────────────────


class ExportStatusResponse(BaseModel):
    id: str
    status: str
    requested_at: str
    completed_at: str | None = None
    expires_at: str | None = None
    data: dict[str, Any] | None = None


# ── Data Deletion ────────────────────────────────────────────


class DeletionStatusResponse(BaseModel):
    id: str
    status: str
    requested_at: str
    grace_period_ends: str | None = None
    completed_at: str | None = None


# ── Email Preferences ────────────────────────────────────────


class EmailPreferencesUpdate(BaseModel):
    marketing_email: bool = False
    transactional_email: bool = True


class EmailPreferencesResponse(BaseModel):
    marketing_email: bool
    transactional_email: bool
    suppressed_at: str | None = None
    suppression_reason: str | None = None


class UnsubscribeRequest(BaseModel):
    token: str


# ── Admin ────────────────────────────────────────────────────


class ExportListItem(BaseModel):
    id: str
    user_id: str
    status: str
    requested_at: str
    completed_at: str | None = None
    expires_at: str | None = None


class ExportListResponse(BaseModel):
    items: list[ExportListItem]
    total: int
    page: int
    page_size: int


class DeletionListItem(BaseModel):
    id: str
    user_id: str
    status: str
    requested_at: str
    grace_period_ends: str | None = None
    completed_at: str | None = None


class DeletionListResponse(BaseModel):
    items: list[DeletionListItem]
    total: int
    page: int
    page_size: int


class ConsentTypeStat(BaseModel):
    consent_type: str
    total_grants: int
    total_revokes: int


class ConsentStatsResponse(BaseModel):
    stats: list[ConsentTypeStat]


class AuditLogItem(BaseModel):
    id: str
    user_id: str
    action: str
    consent_type: str
    old_value: bool | None = None
    new_value: bool | None = None
    ip_address: str | None = None
    created_at: str


class AuditLogResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int


# ── Common ───────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Any = None
