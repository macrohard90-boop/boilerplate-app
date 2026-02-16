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


# ── Common ──────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
