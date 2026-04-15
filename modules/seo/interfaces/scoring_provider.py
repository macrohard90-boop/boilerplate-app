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


class ScoringProvider(ABC):
    """Abstract scoring provider. Implement this to add new scoring backends
    (e.g., Google Lighthouse, Search Console integration)."""

    @abstractmethod
    async def score_page(self, data: PageSEOData) -> ScoreResult:
        """Score a page's SEO quality. Returns 0-100 with rule breakdown."""
        ...
