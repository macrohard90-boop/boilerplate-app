"""Sunset policy worker — daily check for inactive users to suppress.

Finds users who haven't engaged (opened, clicked, visited, purchased)
within the sunset_inactivity_days window. Marks them as sunset in the
suppression list so they stop receiving marketing messages.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_sunset_policy(db: AsyncSession) -> dict:
    """Check for users who should be sunset due to inactivity.

    Users with zero engagement score AND no recent activity beyond
    the sunset threshold get added to the suppression list.
    Only applies to users who have received marketing messages.
    """
    # Get the sunset threshold (use the most conservative/longest across channels)
    config = (
        (
            await db.execute(
                text(
                    "SELECT MAX(sunset_inactivity_days) as max_days "
                    "FROM marketing.messaging_config "
                    "WHERE sunset_inactivity_days IS NOT NULL AND enabled = true"
                )
            )
        )
        .mappings()
        .first()
    )

    if not config or not config["max_days"]:
        return {"checked": 0, "sunset": 0}

    days = config["max_days"]

    # Find users who:
    # 1. Have received at least 3 marketing messages
    # 2. Have not opened/clicked/visited/purchased in the sunset window
    # 3. Are not already suppressed
    rows = (
        (
            await db.execute(
                text(
                    "SELECT DISTINCT mpl.user_id "
                    "FROM marketing.message_pressure_log mpl "
                    "WHERE mpl.message_type = 'marketing' "
                    "AND mpl.sent_at < NOW() - INTERVAL '1 day' * :days "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM analytics.engagement_scores es "
                    "  WHERE es.user_id = mpl.user_id "
                    "  AND (es.last_email_open > NOW() - INTERVAL '1 day' * :days "
                    "       OR es.last_email_click > NOW() - INTERVAL '1 day' * :days "
                    "       OR es.last_site_visit > NOW() - INTERVAL '1 day' * :days "
                    "       OR es.last_purchase > NOW() - INTERVAL '1 day' * :days)"
                    ") "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM gdpr.suppression_list sl "
                    "  WHERE sl.user_id = mpl.user_id"
                    ") "
                    "GROUP BY mpl.user_id "
                    "HAVING COUNT(*) >= 3 "
                    "LIMIT 100"
                ),
                {"days": days},
            )
        )
        .mappings()
        .all()
    )

    sunset_count = 0
    for row in rows:
        user_id = str(row["user_id"])
        try:
            await db.execute(
                text(
                    "INSERT INTO gdpr.suppression_list "
                    "(user_id, reason, suppressed_at) "
                    "VALUES (:uid, :reason, NOW()) "
                    "ON CONFLICT (user_id) DO NOTHING"
                ),
                {"uid": user_id, "reason": f"sunset_policy_{days}d_inactive"},
            )
            sunset_count += 1
        except Exception:
            logger.debug("Failed to sunset user=%s", user_id, exc_info=True)

    if sunset_count:
        await db.commit()

    logger.info(
        "Sunset check: %d users checked, %d sunset (threshold=%d days)",
        len(rows),
        sunset_count,
        days,
    )

    return {"checked": len(rows), "sunset": sunset_count}
