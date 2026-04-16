"""Internal analytics provider — uses the tracking module's page_views table."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.seo.interfaces.analytics_provider import PageTraffic, SEOAnalyticsProvider

logger = logging.getLogger(__name__)


class InternalAnalyticsProvider(SEOAnalyticsProvider):
    """Queries analytics.page_views for SEO traffic correlation."""

    async def get_page_traffic(
        self, db: AsyncSession, path: str, days: int = 30
    ) -> PageTraffic:
        """Get traffic data for a specific page over the given time window."""
        try:
            row = (
                await db.execute(
                    text(
                        "SELECT "
                        "  COUNT(*) AS views, "
                        "  COUNT(DISTINCT session_id) AS unique_sessions, "
                        "  AVG(duration_ms) AS avg_duration "
                        "FROM analytics.page_views "
                        "WHERE path = :path "
                        "  AND created_at >= NOW() - INTERVAL '1 day' * :days"
                    ),
                    {"path": path, "days": days},
                )
            ).mappings().first()

            if not row or row["views"] == 0:
                return PageTraffic(path=path)

            # Compute trend: compare last half vs first half of the window
            trend = await self._compute_trend(db, path, days)

            return PageTraffic(
                path=path,
                views=row["views"],
                unique_sessions=row["unique_sessions"],
                avg_duration_ms=int(row["avg_duration"]) if row["avg_duration"] else None,
                trend=trend,
            )
        except Exception:
            logger.exception("Failed to get page traffic for: %s", path)
            return PageTraffic(path=path)

    async def get_top_pages(
        self, db: AsyncSession, days: int = 30, limit: int = 20
    ) -> list[PageTraffic]:
        """Get the most-visited pages, excluding API and static asset paths."""
        try:
            rows = (
                await db.execute(
                    text(
                        "SELECT "
                        "  path, "
                        "  COUNT(*) AS views, "
                        "  COUNT(DISTINCT session_id) AS unique_sessions, "
                        "  AVG(duration_ms) AS avg_duration "
                        "FROM analytics.page_views "
                        "WHERE created_at >= NOW() - INTERVAL '1 day' * :days "
                        "  AND path NOT LIKE '/api/%' "
                        "  AND path NOT LIKE '/_next/%' "
                        "GROUP BY path "
                        "ORDER BY views DESC "
                        "LIMIT :lim"
                    ),
                    {"days": days, "lim": limit},
                )
            ).mappings().all()

            return [
                PageTraffic(
                    path=r["path"],
                    views=r["views"],
                    unique_sessions=r["unique_sessions"],
                    avg_duration_ms=int(r["avg_duration"]) if r["avg_duration"] else None,
                )
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to get top pages")
            return []

    async def _compute_trend(
        self, db: AsyncSession, path: str, days: int
    ) -> str:
        """Compare recent half vs older half of the window to determine trend."""
        half = days // 2
        try:
            row = (
                await db.execute(
                    text(
                        "SELECT "
                        "  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day' * :half) AS recent, "
                        "  COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '1 day' * :half "
                        "    AND created_at >= NOW() - INTERVAL '1 day' * :days) AS older "
                        "FROM analytics.page_views "
                        "WHERE path = :path "
                        "  AND created_at >= NOW() - INTERVAL '1 day' * :days"
                    ),
                    {"path": path, "half": half, "days": days},
                )
            ).mappings().first()

            if not row or (row["recent"] == 0 and row["older"] == 0):
                return "stable"

            recent = row["recent"]
            older = max(row["older"], 1)  # avoid division by zero
            ratio = recent / older

            if ratio > 1.2:
                return "rising"
            elif ratio < 0.8:
                return "declining"
            return "stable"
        except Exception:
            return "stable"
