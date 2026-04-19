"""Shared utilities for SEO advisor adapters.

These functions are adapter-agnostic: they handle prompt construction,
HTML truncation, and response parsing regardless of which LLM provider
is used (Claude CLI, Anthropic API, OpenAI, etc.).
"""

import json
import logging

from backend.core.config import settings
from modules.seo.interfaces.seo_advisor import SEOSuggestion

logger = logging.getLogger(__name__)

MAX_BODY_LINES = 150

SYSTEM_PROMPT = """\
You are an expert SEO consultant with deep experience in technical SEO, \
content optimization, and search engine ranking strategies. You help \
businesses improve their web pages' search visibility.

Your approach:
1. Analyze the page's technical SEO (meta tags, structure, schema markup)
2. Evaluate content quality and keyword targeting
3. When target keywords are provided, use WebSearch to research what \
currently ranks for those keywords — note competitive patterns (title \
formats, content length, heading structure, schema types)
4. Provide specific, actionable suggestions with concrete rewrite text — \
never vague advice like "improve the title"

You always respond with a JSON array of suggestions. Each suggestion has:
- "category": one of "content", "technical", "social", "performance"
- "priority": "high", "medium", or "low"
- "title": short title (under 60 chars)
- "description": detailed explanation of why this matters and what to do
- "current_value": what the page currently has (null if not applicable)
- "suggested_value": specific text/code to use (null if not applicable)
- "rule_id": matching rule_id from the failing rules list (null if new)

Respond with ONLY the JSON array. No markdown fences, no explanation \
before or after the array."""


def truncate_html(html: str) -> str:
    """Extract <head> and first N lines of <body> for the prompt."""
    lines = html.split("\n")
    head_lines: list[str] = []
    body_lines: list[str] = []
    in_head = False
    in_body = False
    body_count = 0

    for line in lines:
        lower = line.lower().strip()
        if "<head" in lower:
            in_head = True
        if "</head" in lower:
            head_lines.append(line)
            in_head = False
            continue
        if "<body" in lower:
            in_body = True
        if in_head:
            head_lines.append(line)
        elif in_body:
            if body_count < MAX_BODY_LINES:
                body_lines.append(line)
                body_count += 1
            else:
                body_lines.append("<!-- ... truncated ... -->")
                break

    return "\n".join(head_lines + body_lines)


def build_prompt(
    path: str,
    html: str,
    scores: dict,
    rule_results: list[dict],
    target_keywords: list[str] | None,
    business_context: str | None = None,
    intent: str | None = None,
) -> str:
    """Build the analysis prompt for an LLM advisor."""
    truncated = truncate_html(html) if html else "(no HTML available)"

    # Collect failing rules
    failing = [r for r in rule_results if not r.get("passed", True)]
    failing.sort(key=lambda r: r.get("weight", 0), reverse=True)

    failing_summary = "\n".join(
        f"  - {r.get('rule_id', '?')} (weight={r.get('weight', 0)}, "
        f"category={r.get('category', '?')}): {r.get('recommendation', 'N/A')}"
        for r in failing[:15]
    )

    keywords_str = ", ".join(target_keywords) if target_keywords else "(none assigned)"

    # Business context section
    ctx_parts = [f"Site: {settings.site_name}"]
    if settings.site_description:
        ctx_parts.append(f"Description: {settings.site_description}")
    if business_context:
        ctx_parts.append(f"Additional context: {business_context}")
    business_section = "\n".join(ctx_parts)

    # Intent section
    intent_section = (
        intent or "General SEO audit — improve this page's search visibility."
    )

    keyword_instruction = (
        f"Search for the target keywords ({keywords_str}) to see what currently"
        " ranks. Note competitor patterns and incorporate insights into your"
        " suggestions.\n"
        if target_keywords
        else ""
    )

    return f"""## Business Context
{business_section}

## Admin's Goal
{intent_section}

## Page: /{path}
Score: {scores.get('score', 'N/A')}/100 | Target Keywords: {keywords_str}

## Failing Rules (highest impact first)
{failing_summary or "  (all rules passing)"}

## Page HTML (head + first {MAX_BODY_LINES} body lines)
```html
{truncated}
```

## Instructions
{keyword_instruction}Provide 5-8 specific, actionable suggestions. Focus on:
1. Fixing the highest-weight failing rules first
2. Content improvements informed by competitor analysis (if keywords searched)
3. Specific rewrite text (write actual better titles, descriptions, headings)
4. Technical SEO issues visible in the HTML"""


def parse_suggestions(text: str) -> list[SEOSuggestion]:
    """Parse an LLM response into SEOSuggestion objects."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            try:
                items = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Could not parse advisor response as JSON")
                return []
        else:
            return []

    if not isinstance(items, list):
        return []

    suggestions: list[SEOSuggestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            suggestions.append(
                SEOSuggestion(
                    category=item.get("category", "general"),
                    priority=item.get("priority", "medium"),
                    title=item.get("title", "SEO Suggestion"),
                    description=item.get("description", ""),
                    current_value=item.get("current_value"),
                    suggested_value=item.get("suggested_value"),
                    rule_id=item.get("rule_id"),
                )
            )
        except Exception:
            continue

    return suggestions
