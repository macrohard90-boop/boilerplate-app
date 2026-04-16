"""Abstract interface for GEO (Generative Engine Optimization) scoring providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GEORuleResult:
    """Result of a single GEO scoring rule evaluation."""

    rule_id: str
    name: str
    passed: bool
    weight: int  # importance: 1-10
    points: int
    max_points: int
    category: str  # extractability, fact_density, authority, freshness, metadata
    recommendation: str | None = None


@dataclass
class GEOScoreResult:
    """Overall GEO scoring result for a page."""

    score: int  # 0-100
    rules: list[GEORuleResult] = field(default_factory=list)
    provider: str = "geo_rule_based"
    dimension_scores: dict[str, int] | None = None  # per-category 0-100


@dataclass
class PageGEOData:
    """All GEO-relevant data for a page, collected before scoring."""

    path: str
    body_text: str | None = None
    html: str | None = None
    title: str | None = None
    description: str | None = None
    h1_text: str | None = None
    headings: list[dict[str, str]] | None = None  # [{tag, text}]
    structured_data: list[dict[str, Any]] | None = None  # JSON-LD blocks
    external_links: int = 0
    outbound_domains: list[str] | None = None
    content_updated_at: str | None = None  # dateModified from schema or DB
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0

    # GEO-specific signals (populated by geo_html_analyzer)
    first_paragraph_text: str = ""
    first_paragraph_word_count: int = 0
    h2_headings: list[str] | None = None
    h2_question_count: int = 0
    h2_sections: list[dict[str, str]] | None = None  # [{heading, first_sentences}]
    stat_pattern_count: int = 0
    has_data_tables: bool = False
    has_blockquotes: bool = False
    quote_attribution_count: int = 0
    authority_domain_count: int = 0
    stale_year_references: list[str] | None = None

    # Schema detection
    has_faq_schema: bool = False
    faq_question_count: int = 0
    has_article_schema: bool = False
    article_has_author: bool = False
    article_has_date_published: bool = False
    article_has_date_modified: bool = False
    has_howto_schema: bool = False
    has_breadcrumb_schema: bool = False
    has_itemlist_schema: bool = False
    schema_type_count: int = 0


class GEOScoringProvider(ABC):
    """Abstract GEO scoring provider. Implement this to add new GEO scoring
    backends (e.g., LLM-based GEO analysis, external GEO tools)."""

    @abstractmethod
    async def score_page(self, data: PageGEOData) -> GEOScoreResult:
        """Score a page's GEO quality. Returns 0-100 with rule breakdown."""
        ...
