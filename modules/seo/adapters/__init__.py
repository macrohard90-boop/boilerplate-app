"""SEO adapter factories."""

from backend.core.config import settings
from modules.seo.interfaces.analytics_provider import SEOAnalyticsProvider
from modules.seo.interfaces.keyword_provider import KeywordProvider
from modules.seo.interfaces.scoring_provider import ScoringProvider


def get_scoring_provider() -> ScoringProvider:
    """Return the configured scoring provider."""
    from modules.seo.adapters.rule_scoring_provider import RuleScoringProvider

    return RuleScoringProvider()


def get_keyword_provider() -> KeywordProvider:
    """Return the keyword research provider (Google Suggest)."""
    from modules.seo.adapters.google_suggest_provider import GoogleSuggestProvider

    return GoogleSuggestProvider()


def get_seo_advisor():
    """Return the configured SEO advisor provider.

    Selection controlled by SEO_ADVISOR_PROVIDER:
      - "claude_cli" (default): Uses Claude Agent SDK (CLI process, subscription-based)
      - "anthropic_api": Uses Anthropic Messages API (API key, pay per call)

    Both adapters handle graceful degradation when their dependencies
    are unavailable, returning an AdvisorResult with an error message.
    """
    provider = settings.seo_advisor_provider

    if provider == "anthropic_api":
        from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

        return AnthropicAPIAdvisor()

    # Default: claude_cli
    from modules.seo.adapters.claude_sdk_advisor import ClaudeSDKAdvisor

    return ClaudeSDKAdvisor()


def get_geo_advisor():
    """Return the configured GEO advisor provider.

    Selection controlled by GEO_ADVISOR_PROVIDER (falls back to
    SEO_ADVISOR_PROVIDER if not set):
      - "claude_cli" (default): Uses Claude CLI (subscription-based)
      - "anthropic_api": Uses Anthropic Messages API (API key, pay per call)

    Both adapters handle graceful degradation when their dependencies
    are unavailable, returning a GEOAdvisorResult with an error message.
    """
    provider = settings.geo_advisor_provider or settings.seo_advisor_provider

    if provider == "anthropic_api":
        from modules.seo.adapters.anthropic_api_geo_advisor import (
            AnthropicAPIGEOAdvisor,
        )

        return AnthropicAPIGEOAdvisor()

    # Default: claude_cli
    from modules.seo.adapters.claude_sdk_geo_advisor import ClaudeSDKGEOAdvisor

    return ClaudeSDKGEOAdvisor()


def get_seo_analytics_provider() -> SEOAnalyticsProvider:
    """Return the configured SEO analytics provider."""
    from modules.seo.adapters.internal_analytics_provider import (
        InternalAnalyticsProvider,
    )

    return InternalAnalyticsProvider()
