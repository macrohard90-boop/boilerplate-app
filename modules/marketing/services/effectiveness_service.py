"""Effectiveness service — cross-campaign ranking, trends, and fatigue detection.

View 4: All campaigns ranked by attributed revenue under different models.
View 5: Rolling engagement rates, conversion rates, list fatigue detection.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_campaign_rankings(
    db: AsyncSession,
    model: str = "last_click",
    limit: int = 20,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Rank campaigns by attributed revenue under a specific model.

    Returns campaigns sorted by attributed revenue (descending),
    with conversion counts, total revenue, and rates.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT c.id, c.name, c.medium, c.sent_at, "
                    "  css.total_sent, css.total_delivered, css.total_opened, "
                    "  css.total_clicked, css.open_rate, css.click_rate, "
                    "  css.total_conversions, css.total_revenue, css.conversion_rate "
                    "FROM marketing.campaigns c "
                    "LEFT JOIN marketing.campaign_stats_summary css "
                    "  ON css.campaign_id = c.id AND css.variant_id IS NULL "
                    "WHERE c.status = 'sent' "
                    "AND c.sent_at > NOW() - INTERVAL '1 day' * :days "
                    "ORDER BY COALESCE(css.total_revenue, 0) DESC "
                    "LIMIT :lim"
                ),
                {"days": days, "lim": limit},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "campaign_id": str(r["id"]),
            "name": r["name"],
            "medium": r["medium"],
            "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
            "sent": r["total_sent"] or 0,
            "delivered": r["total_delivered"] or 0,
            "opened": r["total_opened"] or 0,
            "clicked": r["total_clicked"] or 0,
            "open_rate": float(r["open_rate"]) if r["open_rate"] else 0,
            "click_rate": float(r["click_rate"]) if r["click_rate"] else 0,
            "conversions": r["total_conversions"] or 0,
            "revenue": float(r["total_revenue"]) if r["total_revenue"] else 0,
            "conversion_rate": (
                float(r["conversion_rate"]) if r["conversion_rate"] else 0
            ),
        }
        for r in rows
    ]


async def get_engagement_trends(
    db: AsyncSession,
    days: int = 30,
    interval: str = "day",
) -> list[dict[str, Any]]:
    """Get rolling engagement trends across all campaigns.

    Groups by day/week: average open rate, click rate, bounce rate,
    conversion rate across all campaigns sent in that period.
    """
    trunc = "day" if interval == "day" else "week"

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT "
                    f"  DATE_TRUNC('{trunc}', c.sent_at) as period, "
                    f"  COUNT(DISTINCT c.id) as campaigns, "
                    f"  AVG(css.open_rate) as avg_open_rate, "
                    f"  AVG(css.click_rate) as avg_click_rate, "
                    f"  AVG(css.conversion_rate) as avg_conversion_rate, "
                    f"  SUM(css.total_sent) as total_sent, "
                    f"  SUM(css.total_bounced) as total_bounced "
                    f"FROM marketing.campaigns c "
                    f"LEFT JOIN marketing.campaign_stats_summary css "
                    f"  ON css.campaign_id = c.id AND css.variant_id IS NULL "
                    f"WHERE c.status = 'sent' "
                    f"AND c.sent_at > NOW() - INTERVAL '1 day' * :days "
                    f"GROUP BY 1 ORDER BY 1"
                ),
                {"days": days},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "period": r["period"].isoformat() if r["period"] else None,
            "campaigns": r["campaigns"],
            "avg_open_rate": round(float(r["avg_open_rate"] or 0), 4),
            "avg_click_rate": round(float(r["avg_click_rate"] or 0), 4),
            "avg_conversion_rate": round(float(r["avg_conversion_rate"] or 0), 4),
            "total_sent": r["total_sent"] or 0,
            "bounce_rate": round((r["total_bounced"] or 0) / (r["total_sent"] or 1), 4),
        }
        for r in rows
    ]


async def get_fatigue_metrics(
    db: AsyncSession,
    days: int = 30,
) -> dict[str, Any]:
    """Detect list fatigue — declining engagement despite continued sending.

    Returns:
    - unsubscribe_trend: unsubscribes per period
    - engagement_decline: whether open rates are dropping
    - over_messaged_users: users who received 5+ campaigns in the period
    """
    # Unsubscribe trend
    unsub_rows = (
        (
            await db.execute(
                text(
                    "SELECT DATE_TRUNC('week', created_at) as week, "
                    "  COUNT(*) as unsubscribes "
                    "FROM marketing.campaign_recipients "
                    "WHERE status = 'unsubscribed' "
                    "AND created_at > NOW() - INTERVAL '1 day' * :days "
                    "GROUP BY 1 ORDER BY 1"
                ),
                {"days": days},
            )
        )
        .mappings()
        .all()
    )

    # Over-messaged users (received 5+ campaigns in period)
    over_msg = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) as cnt FROM ("
                    "  SELECT user_id, COUNT(DISTINCT campaign_id) as campaigns "
                    "  FROM marketing.campaign_recipients "
                    "  WHERE created_at > NOW() - INTERVAL '1 day' * :days "
                    "  AND user_id IS NOT NULL "
                    "  GROUP BY user_id "
                    "  HAVING COUNT(DISTINCT campaign_id) >= 5"
                    ") sub"
                ),
                {"days": days},
            )
        )
        .mappings()
        .first()
    )

    # Complaint rate
    complaint_row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(*) FILTER (WHERE status = 'complained') as complaints, "
                    "  COUNT(*) as total "
                    "FROM marketing.campaign_recipients "
                    "WHERE created_at > NOW() - INTERVAL '1 day' * :days"
                ),
                {"days": days},
            )
        )
        .mappings()
        .first()
    )

    return {
        "period_days": days,
        "unsubscribe_trend": [
            {
                "week": r["week"].isoformat() if r["week"] else None,
                "unsubscribes": r["unsubscribes"],
            }
            for r in unsub_rows
        ],
        "over_messaged_users": over_msg["cnt"] if over_msg else 0,
        "complaint_rate": (
            round(
                (complaint_row["complaints"] or 0)
                / max(complaint_row["total"] or 1, 1),
                4,
            )
            if complaint_row
            else 0
        ),
    }
