"""Engagement score refresh worker — recomputes scores for active users.

Runs every 30 minutes. Targets users who:
- Had any email opens/clicks/site visits in the last 90 days
- Haven't had their score computed in the last 30 minutes
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.services.engagement_scoring_service import (
    upsert_engagement_score,
)

logger = logging.getLogger(__name__)


async def refresh_engagement_scores(db: AsyncSession) -> dict:
    """Refresh engagement scores for recently active users.

    Finds users with activity in the last 90 days whose scores
    are stale (not computed in last 30 min), recomputes up to 200 at a time.
    """
    # Find users who need score refresh
    rows = (
        (
            await db.execute(
                text(
                    "SELECT DISTINCT u.id "
                    "FROM core.users u "
                    "WHERE u.is_verified = TRUE "
                    "AND ( "
                    "  EXISTS ( "
                    "    SELECT 1 FROM analytics.page_views pv "
                    "    WHERE pv.user_id = u.id "
                    "    AND pv.created_at > NOW() - INTERVAL '90 days' "
                    "  ) "
                    "  OR EXISTS ( "
                    "    SELECT 1 FROM marketing.campaign_recipients cr "
                    "    WHERE cr.user_id = u.id "
                    "    AND cr.created_at > NOW() - INTERVAL '90 days' "
                    "  ) "
                    "  OR EXISTS ( "
                    "    SELECT 1 FROM analytics.events ev "
                    "    WHERE ev.user_id = u.id "
                    "    AND ev.created_at > NOW() - INTERVAL '90 days' "
                    "  ) "
                    ") "
                    "AND ( "
                    "  NOT EXISTS ( "
                    "    SELECT 1 FROM analytics.engagement_scores es "
                    "    WHERE es.user_id = u.id "
                    "  ) "
                    "  OR EXISTS ( "
                    "    SELECT 1 FROM analytics.engagement_scores es "
                    "    WHERE es.user_id = u.id "
                    "    AND es.computed_at < NOW() - INTERVAL '30 minutes' "
                    "  ) "
                    ") "
                    "LIMIT 200"
                )
            )
        )
        .mappings()
        .all()
    )

    refreshed = 0
    errors = 0

    for row in rows:
        try:
            await upsert_engagement_score(db, str(row["id"]))
            refreshed += 1
        except Exception:
            logger.debug(
                "Failed to compute score for user=%s", row["id"], exc_info=True
            )
            errors += 1

    logger.info(
        "Engagement score refresh: %d users checked, %d refreshed, %d errors",
        len(rows),
        refreshed,
        errors,
    )

    return {
        "total": len(rows),
        "refreshed": refreshed,
        "errors": errors,
    }
