"""Abstract interface for SEO analytics providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PageTraffic:
    """Traffic data for a single page."""

    path: str
    views: int = 0
    unique_sessions: int = 0
    avg_duration_ms: int | None = None
    trend: str = "stable"  # "rising", "stable", "declining"


class SEOAnalyticsProvider(ABC):
    """Abstract provider for SEO-related traffic analytics."""

    @abstractmethod
    async def get_page_traffic(
        self, db: object, path: str, days: int = 30
    ) -> PageTraffic:
        """Get traffic data for a specific page."""
        ...

    @abstractmethod
    async def get_top_pages(
        self, db: object, days: int = 30, limit: int = 20
    ) -> list[PageTraffic]:
        """Get the most-visited pages."""
        ...
