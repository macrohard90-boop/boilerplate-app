"""SEO advisor powered by the Anthropic Messages API.

Uses the `anthropic` Python SDK to call Claude via the REST API.
Authentication requires ANTHROPIC_API_KEY in the environment.
Web search is enabled via the server-side web_search tool so the
advisor can research SERPs and competitor patterns.

Stateless per request — no persistent process or connection.
"""

import asyncio
import logging

from backend.core.config import settings
from modules.seo.adapters.advisor_utils import (
    SYSTEM_PROMPT,
    build_prompt,
    parse_suggestions,
)
from modules.seo.interfaces.seo_advisor import (
    AdvisorResult,
    SEOAdvisorProvider,
)

logger = logging.getLogger(__name__)

_ADVISOR_TIMEOUT = 120  # seconds — higher than CLI because web search adds latency


class AnthropicAPIAdvisor(SEOAdvisorProvider):
    """SEO advisor using the Anthropic Messages API.

    Requires:
        - ``anthropic`` package installed (pip install anthropic)
        - ``ANTHROPIC_API_KEY`` set in environment / .env

    Configuration via settings:
        - seo_advisor_model: model ID (default: claude-sonnet-4-20250514)
        - seo_advisor_max_searches: web search max_uses per request (default: 5)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_searches: int | None = None,
    ):
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.seo_advisor_model
        self._max_searches = (
            max_searches
            if max_searches is not None
            else settings.seo_advisor_max_searches
        )

    @staticmethod
    def _sdk_available() -> bool:
        """Check if the anthropic package is installed."""
        try:
            import anthropic  # noqa: F401

            return True
        except ImportError:
            return False

    def _get_client(self):
        """Create an AsyncAnthropic client (lightweight, stateless)."""
        import anthropic

        return anthropic.AsyncAnthropic(api_key=self._api_key)

    async def _run_analysis(self, prompt: str) -> AdvisorResult:
        """Send the prompt to Claude API and parse the response."""
        import anthropic

        client = self._get_client()

        tools = []
        if self._max_searches > 0:
            tools.append(
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": self._max_searches,
                }
            )

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                tools=tools if tools else anthropic.NOT_GIVEN,
            )
        except anthropic.AuthenticationError:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error="Invalid ANTHROPIC_API_KEY. Check your API key in .env.",
            )
        except anthropic.RateLimitError:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error="Anthropic API rate limit exceeded. Try again later.",
            )
        except anthropic.APIConnectionError as e:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=f"Cannot connect to Anthropic API: {e}",
            )
        except anthropic.APIStatusError as e:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=f"Anthropic API error ({e.status_code}): {e.message}",
            )

        # Extract text from response content blocks
        # (skip server_tool_use and web_search_tool_result blocks)
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        full_text = "\n".join(text_parts)
        suggestions = parse_suggestions(full_text)

        if not suggestions:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error="Could not parse suggestions from API response.",
            )

        return AdvisorResult(
            suggestions=suggestions,
            provider="anthropic_api",
        )

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
        if not self._sdk_available():
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=(
                    "anthropic package not installed. " "Run: pip install anthropic"
                ),
            )

        if not self._api_key:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=(
                    "ANTHROPIC_API_KEY not configured. "
                    "Set it in .env to use the Anthropic API advisor."
                ),
            )

        prompt = build_prompt(
            path,
            html,
            scores,
            rule_results,
            target_keywords,
            business_context,
            intent,
        )

        try:
            result = await asyncio.wait_for(
                self._run_analysis(prompt),
                timeout=_ADVISOR_TIMEOUT,
            )
            return result

        except asyncio.TimeoutError:
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=(
                    f"Analysis timed out after {_ADVISOR_TIMEOUT} seconds. "
                    "Try again or simplify your request."
                ),
            )

        except Exception as e:
            error_type = type(e).__name__
            logger.error("Anthropic API advisor error: %s: %s", error_type, e)
            return AdvisorResult(
                suggestions=[],
                provider="anthropic_api",
                error=f"Anthropic API error: {error_type}: {e}",
            )
