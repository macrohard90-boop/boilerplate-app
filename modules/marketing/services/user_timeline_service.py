"""User timeline service — UNION ALL across tables for a single user's event stream.

Combines campaign interactions, site events, page views, and purchases
into a single chronological timeline for admin user profiles.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_timeline(
    db: AsyncSession,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Get a unified timeline of events for a user.

    UNION ALL across:
    - campaign_recipients (email/sms/wa sends, opens, clicks)
    - analytics.events (product_viewed, add_to_cart, etc.)
    - analytics.page_views (site visits)
    - ecommerce.orders (purchases)
    - campaign_attributions (conversions attributed)
    """
    rows = (
        (
            await db.execute(
                text(
                    "("
                    "  SELECT 'campaign_sent' as event_type, "
                    "    cr.created_at as ts, "
                    "    json_build_object("
                    "      'campaign_id', cr.campaign_id, "
                    "      'channel', cr.channel, "
                    "      'status', cr.status, "
                    "      'campaign_name', c.name"
                    "    )::text as details "
                    "  FROM marketing.campaign_recipients cr "
                    "  JOIN marketing.campaigns c ON c.id = cr.campaign_id "
                    "  WHERE cr.user_id = :uid "
                    ") UNION ALL ("
                    "  SELECT 'email_opened' as event_type, "
                    "    cr.opened_at as ts, "
                    "    json_build_object("
                    "      'campaign_id', cr.campaign_id, "
                    "      'campaign_name', c.name"
                    "    )::text as details "
                    "  FROM marketing.campaign_recipients cr "
                    "  JOIN marketing.campaigns c ON c.id = cr.campaign_id "
                    "  WHERE cr.user_id = :uid AND cr.opened_at IS NOT NULL "
                    ") UNION ALL ("
                    "  SELECT 'email_clicked' as event_type, "
                    "    cr.clicked_at as ts, "
                    "    json_build_object("
                    "      'campaign_id', cr.campaign_id, "
                    "      'campaign_name', c.name"
                    "    )::text as details "
                    "  FROM marketing.campaign_recipients cr "
                    "  JOIN marketing.campaigns c ON c.id = cr.campaign_id "
                    "  WHERE cr.user_id = :uid AND cr.clicked_at IS NOT NULL "
                    ") UNION ALL ("
                    "  SELECT event_type, "
                    "    created_at as ts, "
                    "    event_data::text as details "
                    "  FROM analytics.events "
                    "  WHERE user_id = :uid "
                    ") UNION ALL ("
                    "  SELECT 'page_view' as event_type, "
                    "    created_at as ts, "
                    "    json_build_object('path', path, 'referrer', referrer)::text as details "
                    "  FROM analytics.page_views "
                    "  WHERE user_id = :uid "
                    ") UNION ALL ("
                    "  SELECT 'purchase' as event_type, "
                    "    created_at as ts, "
                    "    json_build_object("
                    "      'order_id', id, "
                    "      'order_number', order_number, "
                    "      'total', total, "
                    "      'currency', currency, "
                    "      'status', status"
                    "    )::text as details "
                    "  FROM ecommerce.orders "
                    "  WHERE user_id = :uid "
                    ") UNION ALL ("
                    "  SELECT 'conversion_attributed' as event_type, "
                    "    converted_at as ts, "
                    "    json_build_object("
                    "      'campaign_id', ca.campaign_id, "
                    "      'campaign_name', c.name, "
                    "      'conversion_event', ca.conversion_event, "
                    "      'conversion_value', ca.conversion_value"
                    "    )::text as details "
                    "  FROM marketing.campaign_attributions ca "
                    "  JOIN marketing.campaigns c ON c.id = ca.campaign_id "
                    "  WHERE ca.user_id = :uid "
                    ") "
                    "ORDER BY ts DESC NULLS LAST "
                    "LIMIT :lim OFFSET :off"
                ),
                {"uid": user_id, "lim": limit, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    import json

    events = []
    for r in rows:
        details = r["details"]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, TypeError):
                pass

        events.append(
            {
                "event_type": r["event_type"],
                "timestamp": r["ts"].isoformat() if r["ts"] else None,
                "details": details,
            }
        )

    # Get engagement score
    score_row = (
        (
            await db.execute(
                text(
                    "SELECT score, velocity, computed_at "
                    "FROM analytics.engagement_scores "
                    "WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    return {
        "user_id": user_id,
        "events": events,
        "total_returned": len(events),
        "engagement": (
            {
                "score": float(score_row["score"]) if score_row else 0,
                "velocity": float(score_row["velocity"]) if score_row else 0,
                "computed_at": (
                    score_row["computed_at"].isoformat()
                    if score_row and score_row["computed_at"]
                    else None
                ),
            }
            if score_row
            else None
        ),
    }
