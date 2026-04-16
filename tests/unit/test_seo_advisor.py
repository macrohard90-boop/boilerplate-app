"""Tests for the SEO advisor adapters and shared utilities."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import from shared utils (canonical location)
from modules.seo.adapters.advisor_utils import (
    build_prompt,
    parse_suggestions,
    truncate_html,
)

# Also verify backward-compatible aliases still work
from modules.seo.adapters.claude_sdk_advisor import (
    _build_prompt,
    _parse_suggestions,
    _truncate_html,
)
from modules.seo.interfaces.seo_advisor import AdvisorResult, SEOSuggestion


# ── truncate_html tests ──────────────────────────────────────


def test_truncate_html_extracts_head_and_body():
    html = "<html><head><title>Test</title></head><body><p>Hello</p></body></html>"
    result = truncate_html(html)
    assert "<title>Test</title>" in result
    assert "<p>Hello</p>" in result


def test_truncate_html_limits_body_lines():
    body_lines = "\n".join(f"<p>Line {i}</p>" for i in range(200))
    html = (
        "<html>\n<head>\n<title>T</title>\n</head>\n"
        f"<body>\n{body_lines}\n</body>\n</html>"
    )
    result = truncate_html(html)
    assert "<!-- ... truncated ... -->" in result
    # Should not have all 200 lines
    assert "Line 199" not in result


def test_truncate_html_handles_empty():
    assert truncate_html("") == ""


def test_backward_compat_aliases():
    """Verify underscored aliases from claude_sdk_advisor still work."""
    assert _truncate_html is truncate_html
    assert _build_prompt is build_prompt
    assert _parse_suggestions is parse_suggestions


# ── build_prompt tests ──────────────────────────────────────


@patch("modules.seo.adapters.advisor_utils.settings")
def test_build_prompt_includes_business_context(mock_settings):
    mock_settings.site_name = "Shoe Store"
    mock_settings.site_description = "Handmade Italian leather shoes"

    prompt = build_prompt(
        path="products/test",
        html="<html><head></head><body>Hello</body></html>",
        scores={"score": 75, "provider": "rule_based"},
        rule_results=[],
        target_keywords=["leather shoes"],
        business_context="We target professionals aged 25-45",
        intent="Rank for 'Italian leather shoes'",
    )

    assert "Shoe Store" in prompt
    assert "Handmade Italian leather shoes" in prompt
    assert "We target professionals aged 25-45" in prompt
    assert "Rank for 'Italian leather shoes'" in prompt
    assert "leather shoes" in prompt
    assert "75" in prompt


@patch("modules.seo.adapters.advisor_utils.settings")
def test_build_prompt_works_without_optional_fields(mock_settings):
    mock_settings.site_name = "Test App"
    mock_settings.site_description = ""

    prompt = build_prompt(
        path="home",
        html="<html><head></head><body></body></html>",
        scores={"score": 50},
        rule_results=[],
        target_keywords=None,
    )

    assert "Test App" in prompt
    assert "General SEO audit" in prompt
    assert "(none assigned)" in prompt


@patch("modules.seo.adapters.advisor_utils.settings")
def test_build_prompt_includes_failing_rules(mock_settings):
    mock_settings.site_name = "App"
    mock_settings.site_description = ""

    rules = [
        {"rule_id": "title_present", "passed": False, "weight": 10,
         "category": "content", "recommendation": "Add a title"},
        {"rule_id": "desc_present", "passed": True, "weight": 10,
         "category": "content", "recommendation": None},
        {"rule_id": "h1_present", "passed": False, "weight": 5,
         "category": "content", "recommendation": "Add H1"},
    ]

    prompt = build_prompt(
        path="test",
        html="<html><head></head><body></body></html>",
        scores={"score": 60},
        rule_results=rules,
        target_keywords=None,
    )

    # Should include failing rules only
    assert "title_present" in prompt
    assert "h1_present" in prompt


@patch("modules.seo.adapters.advisor_utils.settings")
def test_build_prompt_search_instructions_when_keywords(mock_settings):
    mock_settings.site_name = "App"
    mock_settings.site_description = ""

    prompt = build_prompt(
        path="test",
        html="",
        scores={"score": 50},
        rule_results=[],
        target_keywords=["seo tools"],
    )

    assert "Search for the target keywords" in prompt


@patch("modules.seo.adapters.advisor_utils.settings")
def test_build_prompt_no_search_instructions_without_keywords(mock_settings):
    mock_settings.site_name = "App"
    mock_settings.site_description = ""

    prompt = build_prompt(
        path="test",
        html="",
        scores={"score": 50},
        rule_results=[],
        target_keywords=None,
    )

    assert "Search for the target keywords" not in prompt


# ── parse_suggestions tests ──────────────────────────────────


def test_parse_valid_json():
    data = json.dumps([
        {
            "category": "content",
            "priority": "high",
            "title": "Fix title",
            "description": "Your title needs improvement",
            "current_value": "Old Title",
            "suggested_value": "Better Title | Brand",
            "rule_id": "title_length",
        }
    ])
    result = parse_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Fix title"
    assert result[0].priority == "high"
    assert result[0].current_value == "Old Title"
    assert result[0].suggested_value == "Better Title | Brand"
    assert result[0].rule_id == "title_length"


def test_parse_json_with_markdown_fences():
    data = "```json\n" + json.dumps([
        {"category": "technical", "priority": "medium",
         "title": "Add viewport", "description": "Missing viewport tag"}
    ]) + "\n```"
    result = parse_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Add viewport"


def test_parse_json_embedded_in_text():
    data = 'Here are my suggestions:\n\n[{"category": "content", "priority": "low", "title": "Test", "description": "Desc"}]\n\nHope this helps!'
    result = parse_suggestions(data)
    assert len(result) == 1
    assert result[0].title == "Test"


def test_parse_garbage_input():
    result = parse_suggestions("This is not JSON at all")
    assert result == []


def test_parse_empty_string():
    result = parse_suggestions("")
    assert result == []


def test_parse_non_array_json():
    result = parse_suggestions('{"not": "an array"}')
    assert result == []


def test_parse_array_with_non_dict_items():
    data = json.dumps([
        {"category": "content", "priority": "high", "title": "Good", "description": "OK"},
        "not a dict",
        42,
        {"category": "technical", "priority": "low", "title": "Also Good", "description": "Fine"},
    ])
    result = parse_suggestions(data)
    assert len(result) == 2
    assert result[0].title == "Good"
    assert result[1].title == "Also Good"


def test_parse_defaults_missing_fields():
    data = json.dumps([{"description": "Only desc provided"}])
    result = parse_suggestions(data)
    assert len(result) == 1
    assert result[0].category == "general"
    assert result[0].priority == "medium"
    assert result[0].title == "SEO Suggestion"


# ── ClaudeSDKAdvisor tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_cli_advisor_returns_error_when_cli_unavailable():
    """When claude CLI is not on PATH, analyze returns an error result."""
    from modules.seo.adapters.claude_sdk_advisor import ClaudeSDKAdvisor

    with patch.object(ClaudeSDKAdvisor, "_sdk_available", return_value=False):
        advisor = ClaudeSDKAdvisor()
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 50},
            rule_results=[],
        )

    assert isinstance(result, AdvisorResult)
    assert result.provider == "claude_cli"
    assert result.error is not None
    assert "Claude CLI" in result.error
    assert len(result.suggestions) == 0


def test_factory_returns_claude_sdk_advisor():
    """When SEO_ADVISOR_PROVIDER=claude_cli, factory returns ClaudeSDKAdvisor."""
    from modules.seo.adapters.claude_sdk_advisor import ClaudeSDKAdvisor

    with patch("modules.seo.adapters.settings") as mock_settings:
        mock_settings.seo_advisor_provider = "claude_cli"
        from modules.seo.adapters import get_seo_advisor
        advisor = get_seo_advisor()
        assert isinstance(advisor, ClaudeSDKAdvisor)


# ── AnthropicAPIAdvisor tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_anthropic_advisor_returns_error_when_sdk_missing():
    """When anthropic package is not installed, analyze returns error."""
    from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

    with patch.object(AnthropicAPIAdvisor, "_sdk_available", return_value=False):
        advisor = AnthropicAPIAdvisor(api_key="test-key")
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 50},
            rule_results=[],
        )

    assert isinstance(result, AdvisorResult)
    assert result.provider == "anthropic_api"
    assert "not installed" in result.error


@pytest.mark.asyncio
async def test_anthropic_advisor_returns_error_when_no_api_key():
    """When ANTHROPIC_API_KEY is empty, analyze returns error."""
    from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

    with patch.object(AnthropicAPIAdvisor, "_sdk_available", return_value=True):
        advisor = AnthropicAPIAdvisor(api_key="")
        result = await advisor.analyze(
            path="test",
            html="<html></html>",
            scores={"score": 50},
            rule_results=[],
        )

    assert result.error is not None
    assert "ANTHROPIC_API_KEY" in result.error


@pytest.mark.asyncio
async def test_anthropic_advisor_parses_successful_response():
    """When API returns valid JSON suggestions, they are parsed correctly."""
    from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = json.dumps([
        {
            "category": "content",
            "priority": "high",
            "title": "Fix title tag",
            "description": "Add keyword to title",
        }
    ])

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]

    # Mock the anthropic module since it may not be installed on the host
    mock_anthropic = MagicMock()
    mock_anthropic.NOT_GIVEN = object()

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    import sys
    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        with patch.object(AnthropicAPIAdvisor, "_sdk_available", return_value=True):
            advisor = AnthropicAPIAdvisor(api_key="test-key")
            result = await advisor.analyze(
                path="test",
                html="<html></html>",
                scores={"score": 50},
                rule_results=[],
            )

    assert len(result.suggestions) == 1
    assert result.suggestions[0].title == "Fix title tag"
    assert result.provider == "anthropic_api"
    assert result.error is None


@pytest.mark.asyncio
async def test_anthropic_advisor_handles_web_search_blocks():
    """API response with web search blocks should only extract text blocks."""
    from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

    # Simulate mixed response: text + server_tool_use + web_search_result + text
    blocks = []
    for btype, text in [
        ("text", "I'll analyze this page."),
        ("server_tool_use", None),
        ("web_search_tool_result", None),
        ("text", json.dumps([
            {"category": "technical", "priority": "high",
             "title": "Add schema", "description": "Add structured data"}
        ])),
    ]:
        block = MagicMock()
        block.type = btype
        if text:
            block.text = text
        blocks.append(block)

    mock_response = MagicMock()
    mock_response.content = blocks

    # Mock the anthropic module
    mock_anthropic = MagicMock()
    mock_anthropic.NOT_GIVEN = object()

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    import sys
    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        with patch.object(AnthropicAPIAdvisor, "_sdk_available", return_value=True):
            advisor = AnthropicAPIAdvisor(api_key="test-key")
            result = await advisor.analyze(
                path="test",
                html="<html></html>",
                scores={"score": 50},
                rule_results=[],
            )

    assert len(result.suggestions) == 1
    assert result.suggestions[0].title == "Add schema"
    assert result.provider == "anthropic_api"


def test_factory_returns_anthropic_api_advisor():
    """When SEO_ADVISOR_PROVIDER=anthropic_api, factory returns AnthropicAPIAdvisor."""
    from modules.seo.adapters.anthropic_api_advisor import AnthropicAPIAdvisor

    with patch("modules.seo.adapters.settings") as mock_settings:
        mock_settings.seo_advisor_provider = "anthropic_api"
        from modules.seo.adapters import get_seo_advisor
        advisor = get_seo_advisor()
        assert isinstance(advisor, AnthropicAPIAdvisor)
