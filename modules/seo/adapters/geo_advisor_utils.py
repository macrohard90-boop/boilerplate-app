"""Shared utilities for GEO advisor adapters.

GEO-specific prompt construction and response parsing.
Reuses ``truncate_html`` from ``advisor_utils`` (DRY).
"""

import json
import logging

from backend.core.config import settings
from modules.seo.adapters.advisor_utils import truncate_html  # Reuse, don't duplicate
from modules.seo.interfaces.geo_advisor import GEOSuggestion

logger = logging.getLogger(__name__)

VALID_DIMENSIONS = {
    "extractability",
    "fact_density",
    "authority",
    "freshness",
    "metadata",
}

GEO_SYSTEM_PROMPT = """\
You are an expert in Generative Engine Optimization (GEO) — the practice of \
optimizing web content to be cited by AI engines like ChatGPT, Perplexity, \
Google AI Overviews, and Gemini. You understand that GEO is fundamentally \
different from traditional SEO: while SEO optimizes for ranking in search \
result pages, GEO optimizes for sentence-level extraction and citation by \
AI-powered answer engines.

Your expertise spans 5 GEO dimensions:
1. Extractability — Can AI engines easily pull citable sentences from this \
content? Direct answer openings, question-format headings, self-contained \
sections.
2. Fact Density — Does the content contain concrete statistics, data \
tables, and verifiable numbers that AI engines prefer to cite?
3. Authority — Does the content reference credible sources (.edu, .gov, \
Wikipedia, academic journals)? Are there expert quotes with attribution?
4. Freshness — Is the content recently updated? Does it avoid stale year \
references? Is dateModified present in schema markup?
5. Structural Metadata — Does the page have a rich schema stack (FAQPage, \
Article, HowTo, BreadcrumbList) that makes extraction trivial?

CRITICAL SECTION — AI Citation Self-Reflection:
Before providing your suggestions, reflect on your own behaviour as an AI \
language model. Consider:
- When you decide which sources to cite in your answers, what makes you \
choose one source over another?
- What content patterns make you most likely to quote a specific paragraph?
- What structural signals help you identify the most citable section of a \
page?
- When you encounter multiple pages on the same topic, what causes you to \
prefer one over the others for citation?

Include at least 1-2 suggestions that come directly from this self-reflection, \
marked with "ai_insight": true. These are uniquely valuable because they come \
from an AI explaining its own citation preferences.

You always respond with a JSON array of suggestions. Each suggestion has:
- "dimension": one of "extractability", "fact_density", "authority", \
"freshness", "metadata"
- "priority": "high", "medium", or "low"
- "title": short title (under 60 chars)
- "description": detailed explanation of why this matters for AI citation \
and what to do — include your perspective as an AI where relevant
- "current_value": what the page currently has (null if not applicable)
- "suggested_value": specific text/code to use (null if not applicable)
- "rule_id": matching rule_id from the failing GEO rules list (null if new)
- "ai_insight": true if this suggestion comes from your self-reflection \
on AI citation behaviour, false otherwise

Respond with ONLY the JSON array. No markdown fences, no explanation \
before or after the array."""


def build_geo_prompt(
    path: str,
    html: str,
    scores: dict,
    dimension_scores: dict[str, int],
    rule_results: list[dict],
    business_context: str | None = None,
    intent: str | None = None,
) -> str:
    """Build the GEO analysis prompt for an LLM advisor."""
    truncated = truncate_html(html) if html else "(no HTML available)"

    # Collect failing rules sorted by weight
    failing = [r for r in rule_results if not r.get("passed", True)]
    failing.sort(key=lambda r: r.get("weight", 0), reverse=True)

    failing_summary = "\n".join(
        f"  - {r.get('rule_id', '?')} (weight={r.get('weight', 0)}, "
        f"dimension={r.get('category', '?')}): {r.get('recommendation', 'N/A')}"
        for r in failing[:15]
    )

    # Dimension score breakdown
    dim_labels = {
        "extractability": "Extractability",
        "fact_density": "Fact Density",
        "authority": "Authority",
        "freshness": "Freshness",
        "metadata": "Structural Metadata",
    }
    dim_summary = "\n".join(
        f"  - {dim_labels.get(dim, dim)}: {score}/100"
        for dim, score in sorted(dimension_scores.items())
    )

    # Business context
    ctx_parts = [f"Site: {settings.site_name}"]
    if settings.site_description:
        ctx_parts.append(f"Description: {settings.site_description}")
    if business_context:
        ctx_parts.append(f"Additional context: {business_context}")
    business_section = "\n".join(ctx_parts)

    # Intent
    intent_section = (
        intent or "General GEO audit — improve this page's AI citation likelihood."
    )

    return f"""## Business Context
{business_section}

## Admin's Goal
{intent_section}

## Page: /{path}
Overall GEO Score: {scores.get('score', 'N/A')}/100

## Dimension Scores
{dim_summary or "  (no dimension scores available)"}

## Failing GEO Rules (highest impact first)
{failing_summary or "  (all rules passing)"}

## Page HTML (head + first 150 body lines)
```html
{truncated}
```

## Instructions
Analyze this page for Generative Engine Optimization. Focus on:
1. The weakest dimension scores above — prioritize suggestions that improve the lowest-scoring dimensions
2. Fixing the highest-weight failing GEO rules
3. Specific content rewrites that make sections more extractable by AI engines
4. Data and authority improvements (statistics, source citations, expert quotes)
5. Schema markup additions or improvements
6. IMPORTANT: Include 1-2 suggestions from your AI self-reflection — what would make YOU more likely to cite this page?

Provide 5-8 specific, actionable suggestions with concrete rewrite text."""


def parse_geo_suggestions(text: str) -> list[GEOSuggestion]:
    """Parse an LLM response into GEOSuggestion objects."""
    cleaned = text.strip()

    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    # Parse JSON
    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            try:
                items = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Could not parse GEO advisor response as JSON")
                return []
        else:
            return []

    if not isinstance(items, list):
        return []

    suggestions: list[GEOSuggestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            dimension = item.get("dimension", "extractability")
            if dimension not in VALID_DIMENSIONS:
                dimension = "extractability"
            suggestions.append(
                GEOSuggestion(
                    dimension=dimension,
                    priority=item.get("priority", "medium"),
                    title=item.get("title", "GEO Suggestion"),
                    description=item.get("description", ""),
                    current_value=item.get("current_value"),
                    suggested_value=item.get("suggested_value"),
                    rule_id=item.get("rule_id"),
                    ai_insight=bool(item.get("ai_insight", False)),
                )
            )
        except Exception:
            continue

    return suggestions
