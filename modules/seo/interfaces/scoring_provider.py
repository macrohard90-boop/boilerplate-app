"""Abstract interface for SEO scoring providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleResult:
    """Result of a single scoring rule evaluation."""

    rule_id: str
    name: str
    passed: bool
    weight: int  # importance: 1-10
    points: int
    max_points: int
    category: str = "general"  # "technical", "content", "social", "performance"
    recommendation: str | None = None


@dataclass
class ScoreResult:
    """Overall scoring result for a page."""

    score: int  # 0-100
    rules: list[RuleResult] = field(default_factory=list)
    provider: str = "rule_based"


@dataclass
class PageSEOData:
    """All SEO-relevant data for a page, collected before scoring."""

    path: str
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    robots: str = "index, follow"
    og_tags: dict[str, Any] | None = None
    twitter_tags: dict[str, Any] | None = None
    structured_data: list[dict[str, Any]] | None = None
    headings: list[dict[str, str]] | None = None  # [{tag: "h1", text: "..."}]
    images_without_alt: list[str] | None = None
    internal_links: int = 0
    content_length: int = 0
    is_custom: bool = False
    target_keywords: list[str] | None = None

    # HTML analysis fields (populated when rendered HTML is available)
    has_viewport: bool | None = None
    has_lang: bool | None = None
    has_favicon: bool | None = None
    images_missing_dimensions: int | None = None
    total_images: int | None = None
    external_links: int | None = None
    body_text: str | None = None
    h1_text: str | None = None


class ScoringProvider(ABC):
    """Abstract scoring provider. Implement this to add new scoring backends
    (e.g., Google Lighthouse, Search Console integration)."""

    @abstractmethod
    async def score_page(self, data: PageSEOData) -> ScoreResult:
        """Score a page's SEO quality. Returns 0-100 with rule breakdown."""
        ...
