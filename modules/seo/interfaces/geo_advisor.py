"""Abstract interface for GEO advisor providers.

GEO advisors analyze pages for Generative Engine Optimization and provide
actionable suggestions to improve AI citation likelihood.  The interface
supports a meta-question: asking the AI itself what it prioritises when
deciding which content to cite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GEOSuggestion:
    """A single actionable GEO suggestion."""

    dimension: str  # "extractability", "fact_density", "authority", "freshness", "metadata"
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    current_value: str | None = None
    suggested_value: str | None = None
    rule_id: str | None = None  # Links to existing GEO scoring rule
    ai_insight: bool = False  # True if from the meta-question about AI citation behaviour


@dataclass
class GEOAdvisorResult:
    """Result from a GEO advisor analysis."""

    suggestions: list[GEOSuggestion] = field(default_factory=list)
    provider: str = "placeholder"
    model: str | None = None  # Which LLM provided this analysis (multi-LLM readiness)
    error: str | None = None


class GEOAdvisorProvider(ABC):
    """Abstract GEO advisor.  Implement this to add new advisory backends
    (e.g., Claude SDK, Anthropic API, OpenAI, Gemini, etc.)."""

    @abstractmethod
    async def analyze(
        self,
        path: str,
        html: str,
        scores: dict,
        dimension_scores: dict[str, int],
        rule_results: list[dict],
        business_context: str | None = None,
        intent: str | None = None,
    ) -> GEOAdvisorResult:
        """Analyze a page and return actionable GEO suggestions.

        Args:
            path: The page path (e.g. "products/test").
            html: The rendered HTML source of the page.
            scores: Dict with "score" (int) and "provider" (str).
            dimension_scores: Per-dimension scores (extractability, etc.).
            rule_results: List of GEO rule result dicts from the scoring engine.
            business_context: Admin-provided description of business/industry.
            intent: What the admin wants to achieve for GEO.

        Returns:
            GEOAdvisorResult with suggestions and provider info.
        """
        ...
