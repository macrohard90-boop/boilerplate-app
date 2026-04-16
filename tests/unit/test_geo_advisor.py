"""Tests for the GEO advisor adapters and shared utilities."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.seo.adapters.geo_advisor_utils import (
    GEO_SYSTEM_PROMPT,
    build_geo_prompt,
    parse_geo_suggestions,
)
from modules.seo.interfaces.geo_advisor import GEOAdvisorResult, GEOSuggestion


# ��─ GEO_SYSTEM_PROMPT tests ─────��──────────────────────────


def test_system_prompt_contains_meta_question():
    """The GEO system prompt must include the AI citation self-reflection."""
    assert "AI Citation Self-Reflection" in GEO_SYSTEM_PROMPT
    assert "ai_insight" in GEO_SYSTEM_PROMPT
    assert "reflect on your own" in GEO_SYSTEM_PROMPT


def test_system_prompt_mentions_five_dimensions():
    assert "Extractability" in GEO_SYSTEM_PROMPT
    assert "Fact Density" in GEO_SYSTEM_PROMPT
    assert "Authority" in GEO_SYSTEM_PROMPT
    assert "Freshness" in GEO_SYSTEM_PROMPT
    assert "Structural Metadata" in GEO_SYSTEM_PROMPT


# ─�� build_geo_prompt tests ──────────────────────────────────


@patch("modules.seo.adapters.geo_advisor_utils.settings")
def test_build_geo_prompt_includes_dimension_scores(mock_settings):
    mock_settings.site_name = "Test Store"
    mock_settings.site_description = "Italian leather goods"

    prompt = build_geo_prompt(
        path="products/test",
        html="<html><head></head><body>Hello</body></html>",
        scores={"score": 25, "provider": "geo_rule_based"},
        dimension_scores={
            "extractability": 33,
            "fact_density": 0,
            "authority": 10,
            "freshness": 21,
            "metadata": 0,
        },
        rule_results=[],
        business_context="We sell luxury shoes",
        intent="Get cited by ChatGPT",
    )

    assert "Test Store" in prompt
    assert "Italian leather goods" in prompt
    assert "We sell luxury shoes" in prompt
    assert "Get cited by ChatGPT" in prompt
    assert "25" in prompt
    assert "Extractability: 33/100" in prompt
    assert "Fact Density: 0/100" in prompt


@patch("modules.seo.adapters.geo_advisor_utils.settings")
def test_build_geo_prompt_works_without_optional_fields(mock_settings):
    mock_settings.site_name = "Test App"
    mock_settings.site_description = ""

    prompt = build_geo_prompt(
        path="home",
        html="<html><head></head><body></body></html>",
        scores={"score": 50},
        dimension_scores={},
        rule_results=[],
    )

    assert "Test App" in prompt
    assert "General GEO audit" in prompt


@patch("modules.seo.adapters.geo_advisor_utils.settings")
def test_build_geo_prompt_includes_failing_rules(mock_settings):
    mock_settings.site_name = "App"
    mock_settings.site_description = ""

    rules = [
        {"rule_id": "direct_answer_opening", "passed": False, "weight": 8,
         "category": "extractability", "recommendation": "Rewrite opening paragraph"},
        {"rule_id": "stat_density", "passed": True, "weight": 8,
         "category": "fact_density", "recommendation": None},
        {"rule_id": "faq_schema", "passed": False, "weight": 8,
         "category": "metadata", "recommendation": "Add FAQ schema"},
    ]

    prompt = build_geo_prompt(
        path="test",
        html="<html><head></head><body></body></html>",
        scores={"score": 30},
        dimension_scores={"extractability": 20, "metadata": 0},
        rule_results=rules,
    )

    # Should include failing rules only
    assert "direct_answer_opening" in prompt
    assert "faq_schema" in prompt
    # Passing rule should not be in the failing section
    # (stat_density is passing, but could appear in general prompt text)


@patch("modules.seo.adapters.geo_advisor_utils.settings")
def test_build_geo_prompt_ai_reflection_instruction(mock_settings):
    mock_settings.site_name = "App"
    mock_settings.site_description = ""

    prompt = build_geo_prompt(
        path="test",
        html="",
        scores={"score": 50},
        dimension_scores={},
        rule_results=[],
    )

    assert "AI self-reflection" in prompt
    assert "more likely to cite this page" in prompt


# ── parse_geo_suggestions tests ───���─────────────────────────


def test_parse_valid_json():
    data = json.dumps([
        {
            "dimension": "extractability",
            "priority": "high",
            "title": "Fix opening",
            "description": "Your opening needs a direct answer",
            "current_value": "Welcome to our store...",
            "suggested_value": "Italian leather shoes are handcrafted...",
            "rule_id": "direct_answer_opening",
            "ai_insight": False,
        }
    ])
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Fix opening"
    assert result[0].dimension == "extractability"
    assert result[0].priority == "high"
    assert result[0].rule_id == "direct_answer_opening"
    assert result[0].ai_insight is False


def test_parse_json_with_ai_insight():
    data = json.dumps([
        {
            "dimension": "authority",
            "priority": "high",
            "title": "AI citation preference",
            "description": "As an AI, I prioritize content with named sources",
            "ai_insight": True,
        }
    ])
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].ai_insight is True
    assert result[0].dimension == "authority"


def test_parse_json_with_markdown_fences():
    data = "```json\n" + json.dumps([
        {"dimension": "metadata", "priority": "medium",
         "title": "Add FAQ schema", "description": "Missing FAQ markup"}
    ]) + "\n```"
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Add FAQ schema"


def test_parse_json_embedded_in_text():
    data = 'Here are my suggestions:\n\n[{"dimension": "freshness", "priority": "low", "title": "Update date", "description": "Desc"}]\n\nHope this helps!'
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Update date"


def test_parse_garbage_input():
    result = parse_geo_suggestions("This is not JSON at all")
    assert result == []


def test_parse_empty_string():
    result = parse_geo_suggestions("")
    assert result == []


def test_parse_non_array_json():
    result = parse_geo_suggestions('{"not": "an array"}')
    assert result == []


def test_parse_array_with_non_dict_items():
    data = json.dumps([
        {"dimension": "fact_density", "priority": "high", "title": "Good", "description": "OK"},
        "not a dict",
        42,
        {"dimension": "authority", "priority": "low", "title": "Also Good", "description": "Fine"},
    ])
    result = parse_geo_suggestions(data)
    assert len(result) == 2
    assert result[0].title == "Good"
    assert result[1].title == "Also Good"


def test_parse_defaults_missing_fields():
    data = json.dumps([{"description": "Only desc provided"}])
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].dimension == "extractability"  # default
    assert result[0].priority == "medium"
    assert result[0].title == "GEO Suggestion"
    assert result[0].ai_insight is False


def test_parse_invalid_dimension_defaults_to_extractability():
    data = json.dumps([
        {"dimension": "not_a_real_dimension", "priority": "high",
         "title": "Test", "description": "Desc"}
    ])
    result = parse_geo_suggestions(data)
    assert len(result) == 1
    assert result[0].dimension == "extractability"


# ── ClaudeSDKGEOAdvisor tests ──────────────────────────────


@pytest.mark.asyncio
async def test_cli_geo_advisor_returns_error_when_cli_unavailable():
    """When claude CLI is not on PATH, analyze returns an error result."""
    from modules.seo.adapters.claude_sdk_geo_advisor import ClaudeSDKGEOAdvisor

    with patch.object(ClaudeSDKGEOAdvisor, "_sdk_available", return_value=False):
        advisor = ClaudeSDKGEOAdvisor()
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 25},
            dimension_scores={"extractability": 33},
            rule_results=[],
        )

    assert isinstance(result, GEOAdvisorResult)
    assert result.provider == "claude_cli"
    assert result.error is not None
    assert "Claude CLI" in result.error
    assert len(result.suggestions) == 0


# ── AnthropicAPIGEOAdvisor tests ────────────────────────────


@pytest.mark.asyncio
async def test_anthropic_geo_advisor_returns_error_when_sdk_missing():
    """When anthropic package is not installed, analyze returns error."""
    from modules.seo.adapters.anthropic_api_geo_advisor import AnthropicAPIGEOAdvisor

    with patch.object(AnthropicAPIGEOAdvisor, "_sdk_available", return_value=False):
        advisor = AnthropicAPIGEOAdvisor(api_key="test-key")
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 25},
            dimension_scores={},
            rule_results=[],
        )

    assert isinstance(result, GEOAdvisorResult)
    assert result.provider == "anthropic_api"
    assert "not installed" in result.error


@pytest.mark.asyncio
async def test_anthropic_geo_advisor_returns_error_when_no_api_key():
    """When ANTHROPIC_API_KEY is empty, analyze returns error."""
    from modules.seo.adapters.anthropic_api_geo_advisor import AnthropicAPIGEOAdvisor

    with patch.object(AnthropicAPIGEOAdvisor, "_sdk_available", return_value=True):
        advisor = AnthropicAPIGEOAdvisor(api_key="")
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 25},
            dimension_scores={},
            rule_results=[],
        )

    assert result.error is not None
    assert "ANTHROPIC_API_KEY" in result.error


@pytest.mark.asyncio
async def test_anthropic_geo_advisor_parses_successful_response():
    """When API returns valid GEO JSON suggestions, they are parsed correctly."""
    from modules.seo.adapters.anthropic_api_geo_advisor import AnthropicAPIGEOAdvisor

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = json.dumps([
        {
            "dimension": "extractability",
            "priority": "high",
            "title": "Rewrite opening paragraph",
            "description": "Your opening has filler text",
            "ai_insight": False,
        },
        {
            "dimension": "authority",
            "priority": "medium",
            "title": "AI citation preference",
            "description": "As an AI, I look for named expert sources",
            "ai_insight": True,
        },
    ])

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]

    mock_anthropic = MagicMock()
    mock_anthropic.NOT_GIVEN = object()

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    import sys
    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        with patch.object(AnthropicAPIGEOAdvisor, "_sdk_available", return_value=True):
            advisor = AnthropicAPIGEOAdvisor(api_key="test-key")
            result = await advisor.analyze(
                path="test",
                html="<html></html>",
                scores={"score": 25},
                dimension_scores={"extractability": 33},
                rule_results=[],
            )

    assert len(result.suggestions) == 2
    assert result.suggestions[0].title == "Rewrite opening paragraph"
    assert result.suggestions[0].ai_insight is False
    assert result.suggestions[1].ai_insight is True
    assert result.provider == "anthropic_api"
    assert result.error is None


# ── Factory tests ───────────────────────────────────────────


def test_factory_returns_claude_sdk_geo_advisor():
    """Default factory returns ClaudeSDKGEOAdvisor."""
    from modules.seo.adapters.claude_sdk_geo_advisor import ClaudeSDKGEOAdvisor

    with patch("modules.seo.adapters.settings") as mock_settings:
        mock_settings.geo_advisor_provider = ""
        mock_settings.seo_advisor_provider = "claude_cli"
        from modules.seo.adapters import get_geo_advisor
        advisor = get_geo_advisor()
        assert isinstance(advisor, ClaudeSDKGEOAdvisor)


def test_factory_returns_anthropic_api_geo_advisor():
    """When provider=anthropic_api, factory returns AnthropicAPIGEOAdvisor."""
    from modules.seo.adapters.anthropic_api_geo_advisor import AnthropicAPIGEOAdvisor

    with patch("modules.seo.adapters.settings") as mock_settings:
        mock_settings.geo_advisor_provider = "anthropic_api"
        mock_settings.seo_advisor_provider = "claude_cli"
        from modules.seo.adapters import get_geo_advisor
        advisor = get_geo_advisor()
        assert isinstance(advisor, AnthropicAPIGEOAdvisor)


def test_factory_falls_back_to_seo_advisor_provider():
    """When GEO_ADVISOR_PROVIDER is empty, falls back to SEO_ADVISOR_PROVIDER."""
    from modules.seo.adapters.anthropic_api_geo_advisor import AnthropicAPIGEOAdvisor

    with patch("modules.seo.adapters.settings") as mock_settings:
        mock_settings.geo_advisor_provider = ""
        mock_settings.seo_advisor_provider = "anthropic_api"
        from modules.seo.adapters import get_geo_advisor
        advisor = get_geo_advisor()
        assert isinstance(advisor, AnthropicAPIGEOAdvisor)
