"""Google Suggest keyword provider — free autocomplete suggestions."""

import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx

from modules.seo.interfaces.keyword_provider import KeywordProvider, KeywordSuggestion

logger = logging.getLogger(__name__)

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
REQUEST_DELAY = 0.5  # seconds between requests (rate limiting)


class GoogleSuggestProvider(KeywordProvider):
    """Uses Google's autocomplete API (free, no API key) to discover keywords."""

    async def suggest_keywords(
        self, seed: str, limit: int = 20
    ) -> list[KeywordSuggestion]:
        """Fetch autocomplete suggestions for a seed term."""
        suggestions: list[KeywordSuggestion] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    SUGGEST_URL,
                    params={"output": "toolbar", "q": seed},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                logger.warning("Google Suggest request failed for seed: %s", seed)
                return suggestions

        try:
            root = ET.fromstring(resp.text)
            for suggestion in root.findall(".//suggestion"):
                data = suggestion.get("data", "").strip()
                if data and data.lower() != seed.lower():
                    suggestions.append(
                        KeywordSuggestion(
                            keyword=data,
                            source="google_suggest",
                            depth_level=1,
                        )
                    )
                if len(suggestions) >= limit:
                    break
        except ET.ParseError:
            logger.warning("Failed to parse Google Suggest XML for seed: %s", seed)

        return suggestions

    async def expand_keywords(
        self, seed: str, depth: int = 2, limit: int = 50
    ) -> list[KeywordSuggestion]:
        """Multi-degree expansion using recursive autocomplete queries.

        Depth 1: direct suggestions for seed.
        Depth 2: also query top suggestions from depth 1.
        Depth 3: also query top suggestions from depth 2.
        """
        seen: set[str] = {seed.lower()}
        all_suggestions: list[KeywordSuggestion] = []

        # Depth 1
        first_level = await self.suggest_keywords(seed, limit=10)
        for s in first_level:
            key = s.keyword.lower()
            if key not in seen:
                seen.add(key)
                s.depth_level = 1
                all_suggestions.append(s)

        if depth < 2 or len(all_suggestions) >= limit:
            return all_suggestions[:limit]

        # Depth 2: expand top results from depth 1
        seeds_2 = [s.keyword for s in all_suggestions[:5]]
        for sub_seed in seeds_2:
            await asyncio.sleep(REQUEST_DELAY)
            second_level = await self.suggest_keywords(sub_seed, limit=5)
            for s in second_level:
                key = s.keyword.lower()
                if key not in seen:
                    seen.add(key)
                    s.depth_level = 2
                    all_suggestions.append(s)
            if len(all_suggestions) >= limit:
                return all_suggestions[:limit]

        if depth < 3:
            return all_suggestions[:limit]

        # Depth 3: expand top results from depth 2
        depth2_kws = [s for s in all_suggestions if s.depth_level == 2][:3]
        for kw in depth2_kws:
            await asyncio.sleep(REQUEST_DELAY)
            third_level = await self.suggest_keywords(kw.keyword, limit=5)
            for s in third_level:
                key = s.keyword.lower()
                if key not in seen:
                    seen.add(key)
                    s.depth_level = 3
                    all_suggestions.append(s)
            if len(all_suggestions) >= limit:
                break

        return all_suggestions[:limit]
