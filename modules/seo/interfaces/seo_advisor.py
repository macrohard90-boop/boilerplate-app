"""Abstract interface for SEO advisor providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SEOSuggestion:
    """A single actionable SEO suggestion."""

    category: str  # "content", "technical", "social", "performance"
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    current_value: str | None = None
    suggested_value: str | None = None
    rule_id: str | None = None  # Links to existing scoring rule


@dataclass
class AdvisorResult:
    """Result from an SEO advisor analysis."""

    suggestions: list[SEOSuggestion] = field(default_factory=list)
    provider: str = "placeholder"
    error: str | None = None


class SEOAdvisorProvider(ABC):
    """Abstract SEO advisor. Implement this to add new advisory backends
    (e.g., Claude SDK, Anthropic API, OpenAI, etc.)."""

    @abstractmethod
    async def analyze(
        self,
        path: str,
        html: str,
        scores: dict,
        rule_results: list[dict],
        target_keywords: list[str] | None = None,
        business_context: str | None = None,
        intent: str | None = None,
    ) -> AdvisorResult:
        """Analyze a page and return actionable SEO suggestions.

        Args:
            path: The page path (e.g. "products/test").
            html: The rendered HTML source of the page.
            scores: Dict with "score" (int) and "provider" (str).
            rule_results: List of rule result dicts from the scoring engine.
            target_keywords: Target keywords assigned to the page.
            business_context: Admin-provided description of business/industry.
            intent: What the admin wants to achieve (e.g. "rank for X").

        Returns:
            AdvisorResult with suggestions and provider info.
        """
        ...
