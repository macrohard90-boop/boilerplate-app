"""Unit tests for the SEO keyword provider adapters."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.seo.interfaces.keyword_provider import KeywordProvider, KeywordSuggestion


# ---------------------------------------------------------------------------
# KeywordSuggestion dataclass
# ---------------------------------------------------------------------------


class TestKeywordSuggestion:
    def test_defaults(self):
        s = KeywordSuggestion(keyword="test")
        assert s.keyword == "test"
        assert s.search_volume is None
        assert s.competition is None
        assert s.trend is None
        assert s.source == "unknown"
        assert s.depth_level == 1
        assert s.related_keywords == []

    def test_full_init(self):
        s = KeywordSuggestion(
            keyword="seo tools",
            search_volume=5000,
            competition=0.7,
            trend="rising",
            source="google_suggest",
            depth_level=2,
            related_keywords=["seo software", "seo checker"],
        )
        assert s.search_volume == 5000
        assert s.competition == 0.7
        assert s.trend == "rising"
        assert s.depth_level == 2
        assert len(s.related_keywords) == 2


# ---------------------------------------------------------------------------
# KeywordProvider interface
# ---------------------------------------------------------------------------


class TestKeywordProviderInterface:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            KeywordProvider()  # type: ignore

    def test_expand_defaults_to_suggest(self):
        """expand_keywords should default to calling suggest_keywords."""

        class TestProvider(KeywordProvider):
            async def suggest_keywords(self, seed, limit=20):
                return [KeywordSuggestion(keyword=f"{seed}-suggestion")]

        provider = TestProvider()
        import asyncio

        results = asyncio.get_event_loop().run_until_complete(
            provider.expand_keywords("test", depth=2)
        )
        assert len(results) == 1
        assert results[0].keyword == "test-suggestion"


# ---------------------------------------------------------------------------
# GoogleSuggestProvider
# ---------------------------------------------------------------------------


class TestGoogleSuggestProvider:
    @pytest.fixture
    def provider(self):
        from modules.seo.adapters.google_suggest_provider import GoogleSuggestProvider

        return GoogleSuggestProvider()

    @pytest.mark.asyncio
    async def test_suggest_parses_xml(self, provider):
        """Test that valid Google Suggest XML is parsed correctly."""
        xml_response = (
            '<?xml version="1.0"?>'
            "<toplevel>"
            '<CompleteSuggestion><suggestion data="energy conference 2026"/></CompleteSuggestion>'
            '<CompleteSuggestion><suggestion data="energy conference Calgary"/></CompleteSuggestion>'
            '<CompleteSuggestion><suggestion data="energy events"/></CompleteSuggestion>'
            "</toplevel>"
        )

        mock_response = MagicMock()
        mock_response.text = xml_response
        mock_response.raise_for_status = MagicMock()

        with patch("modules.seo.adapters.google_suggest_provider.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            results = await provider.suggest_keywords("energy conference", limit=10)

        assert len(results) == 3
        assert results[0].keyword == "energy conference 2026"
        assert results[0].source == "google_suggest"
        assert results[0].depth_level == 1

    @pytest.mark.asyncio
    async def test_suggest_excludes_seed(self, provider):
        """Exact matches of seed keyword are excluded."""
        xml_response = (
            '<?xml version="1.0"?>'
            "<toplevel>"
            '<CompleteSuggestion><suggestion data="energy conference"/></CompleteSuggestion>'
            '<CompleteSuggestion><suggestion data="energy conference 2026"/></CompleteSuggestion>'
            "</toplevel>"
        )

        mock_response = MagicMock()
        mock_response.text = xml_response
        mock_response.raise_for_status = MagicMock()

        with patch("modules.seo.adapters.google_suggest_provider.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            results = await provider.suggest_keywords("energy conference", limit=10)

        assert len(results) == 1
        assert results[0].keyword == "energy conference 2026"

    @pytest.mark.asyncio
    async def test_suggest_respects_limit(self, provider):
        suggestions = "".join(
            f'<CompleteSuggestion><suggestion data="keyword {i}"/></CompleteSuggestion>'
            for i in range(20)
        )
        xml_response = f'<?xml version="1.0"?><toplevel>{suggestions}</toplevel>'

        mock_response = MagicMock()
        mock_response.text = xml_response
        mock_response.raise_for_status = MagicMock()

        with patch("modules.seo.adapters.google_suggest_provider.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            results = await provider.suggest_keywords("test", limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_suggest_handles_http_error(self, provider):
        """HTTP errors return empty list, not an exception."""
        import httpx

        with patch("modules.seo.adapters.google_suggest_provider.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            results = await provider.suggest_keywords("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_suggest_handles_invalid_xml(self, provider):
        mock_response = MagicMock()
        mock_response.text = "not xml at all"
        mock_response.raise_for_status = MagicMock()

        with patch("modules.seo.adapters.google_suggest_provider.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            results = await provider.suggest_keywords("test")

        assert results == []


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------


class TestAdapterFactory:
    def test_returns_google_suggest(self):
        from modules.seo.adapters import get_keyword_provider
        from modules.seo.adapters.google_suggest_provider import GoogleSuggestProvider

        provider = get_keyword_provider()
        assert isinstance(provider, GoogleSuggestProvider)
