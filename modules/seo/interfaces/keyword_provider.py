"""Abstract interface for keyword research providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class KeywordSuggestion:
    """A single keyword suggestion from a provider."""

    keyword: str
    search_volume: int | None = None
    competition: float | None = None  # 0.0-1.0
    trend: str | None = None  # "rising", "stable", "declining"
    source: str = "unknown"
    depth_level: int = 1  # 1st/2nd/3rd degree expansion
    related_keywords: list[str] = field(default_factory=list)


class KeywordProvider(ABC):
    """Abstract keyword provider. Implement to add new keyword research backends."""

    @abstractmethod
    async def suggest_keywords(
        self, seed: str, limit: int = 20
    ) -> list[KeywordSuggestion]:
        """Suggest keywords based on a seed term."""
        ...

    async def expand_keywords(
        self, seed: str, depth: int = 2, limit: int = 50
    ) -> list[KeywordSuggestion]:
        """Multi-degree keyword expansion. Default: single-degree via suggest."""
        return await self.suggest_keywords(seed, limit=limit)
