"""Campaign analytics service — funnel, variants, segments, time-series, revenue.

Provides the 5 dashboard views for individual campaign analytics:
1. Campaign-level funnel: Sent → Delivered → Opened → Clicked → Converted → Revenue
2. Variant comparison (A/B): side-by-side stats per variant
3. Segment breakdown: stats grouped by audience segment or custom grouping
4. Time-series: hourly/daily open/click/conversion rates
5. Revenue attribution: per-model attribution summaries
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_campaign_funnel(db: AsyncSession, campaign_id: str) -> dict[str, Any]:
    """Get the full conversion funnel for a campaign.

    Returns counts at each stage: sent, delivered, opened, clicked,
    bounced, complained, converted, and revenue.
    """
    # Try pre-computed stats first
    stats = (
        (
            await db.execute(
                text(
                    "SELECT total_sent, total_delivered, total_opened, "
                    "  total_clicked, total_bounced, total_complained, "
                    "  total_unsubscribed, total_conversions, total_revenue, "
                    "  open_rate, click_rate, conversion_rate, computed_at "
                    "FROM marketing.campaign_stats_summary "
                    "WHERE campaign_id = :cid AND variant_id IS NULL"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if stats:
        return {
            "campaign_id": campaign_id,
            "funnel": {
                "sent": stats["total_sent"],
                "delivered": stats["total_delivered"],
                "opened": stats["total_opened"],
                "clicked": stats["total_clicked"],
                "bounced": stats["total_bounced"],
                "complained": stats["total_complained"],
                "unsubscribed": stats["total_unsubscribed"],
                "converted": stats["total_conversions"],
                "revenue": float(stats["total_revenue"]),
            },
            "rates": {
                "open_rate": float(stats["open_rate"]),
                "click_rate": float(stats["click_rate"]),
                "conversion_rate": float(stats["conversion_rate"]),
                "bounce_rate": (
                    round(stats["total_bounced"] / stats["total_sent"], 4)
                    if stats["total_sent"]
                    else 0
                ),
            },
            "computed_at": (
                stats["computed_at"].isoformat() if stats["computed_at"] else None
            ),
        }

    # Fallback: compute live from campaign_recipients
    row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(*) FILTER (WHERE status != 'failed') as sent, "
                    "  COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) as delivered, "
                    "  COUNT(*) FILTER (WHERE status IN ('opened','clicked')) as opened, "
                    "  COUNT(*) FILTER (WHERE status = 'clicked') as clicked, "
                    "  COUNT(*) FILTER (WHERE status = 'bounced') as bounced, "
                    "  COUNT(*) FILTER (WHERE status = 'complained') as complained, "
                    "  COUNT(*) FILTER (WHERE status = 'unsubscribed') as unsubscribed "
                    "FROM marketing.campaign_recipients "
                    "WHERE campaign_id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    # Get conversions
    conv = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(conversion_value), 0) as revenue "
                    "FROM marketing.campaign_attributions "
                    "WHERE campaign_id = :cid AND converted = true"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    sent = row["sent"] if row else 0
    delivered = row["delivered"] if row else 0
    opened = row["opened"] if row else 0

    return {
        "campaign_id": campaign_id,
        "funnel": {
            "sent": sent,
            "delivered": delivered,
            "opened": opened,
            "clicked": row["clicked"] if row else 0,
            "bounced": row["bounced"] if row else 0,
            "complained": row["complained"] if row else 0,
            "unsubscribed": row["unsubscribed"] if row else 0,
            "converted": conv["cnt"] if conv else 0,
            "revenue": float(conv["revenue"]) if conv else 0,
        },
        "rates": {
            "open_rate": round(opened / delivered, 4) if delivered else 0,
            "click_rate": (
                round((row["clicked"] if row else 0) / delivered, 4) if delivered else 0
            ),
            "conversion_rate": (
                round((conv["cnt"] if conv else 0) / sent, 4) if sent else 0
            ),
            "bounce_rate": (
                round((row["bounced"] if row else 0) / sent, 4) if sent else 0
            ),
        },
        "computed_at": None,
    }


async def get_variant_comparison(
    db: AsyncSession, campaign_id: str
) -> list[dict[str, Any]]:
    """Get per-variant stats for A/B comparison.

    Returns a list of variant stats from campaign_stats_summary,
    falling back to live computation if not pre-computed.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT css.variant_id, cv.label as variant_label, "
                    "  css.total_sent, css.total_delivered, css.total_opened, "
                    "  css.total_clicked, css.total_bounced, "
                    "  css.open_rate, css.click_rate, css.conversion_rate "
                    "FROM marketing.campaign_stats_summary css "
                    "LEFT JOIN marketing.campaign_variants cv ON cv.id = css.variant_id "
                    "WHERE css.campaign_id = :cid AND css.variant_id IS NOT NULL "
                    "ORDER BY cv.label"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    if rows:
        return [
            {
                "variant_id": str(r["variant_id"]),
                "label": r["variant_label"] or "Unknown",
                "sent": r["total_sent"],
                "delivered": r["total_delivered"],
                "opened": r["total_opened"],
                "clicked": r["total_clicked"],
                "bounced": r["total_bounced"],
                "open_rate": float(r["open_rate"]),
                "click_rate": float(r["click_rate"]),
                "conversion_rate": float(r["conversion_rate"]),
            }
            for r in rows
        ]

    # Fallback: live computation grouped by variant_id
    live = (
        (
            await db.execute(
                text(
                    "SELECT cr.variant_id, cv.label, "
                    "  COUNT(*) FILTER (WHERE cr.status != 'failed') as sent, "
                    "  COUNT(*) FILTER (WHERE cr.status IN ('delivered','opened','clicked')) as delivered, "
                    "  COUNT(*) FILTER (WHERE cr.status IN ('opened','clicked')) as opened, "
                    "  COUNT(*) FILTER (WHERE cr.status = 'clicked') as clicked, "
                    "  COUNT(*) FILTER (WHERE cr.status = 'bounced') as bounced "
                    "FROM marketing.campaign_recipients cr "
                    "LEFT JOIN marketing.campaign_variants cv ON cv.id = cr.variant_id "
                    "WHERE cr.campaign_id = :cid AND cr.variant_id IS NOT NULL "
                    "GROUP BY cr.variant_id, cv.label "
                    "ORDER BY cv.label"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "variant_id": str(r["variant_id"]),
            "label": r["label"] or "Unknown",
            "sent": r["sent"],
            "delivered": r["delivered"],
            "opened": r["opened"],
            "clicked": r["clicked"],
            "bounced": r["bounced"],
            "open_rate": (
                round(r["opened"] / r["delivered"], 4) if r["delivered"] else 0
            ),
            "click_rate": (
                round(r["clicked"] / r["delivered"], 4) if r["delivered"] else 0
            ),
            "conversion_rate": 0,
        }
        for r in live
    ]


async def get_time_series(
    db: AsyncSession,
    campaign_id: str,
    interval: str = "hour",
) -> list[dict[str, Any]]:
    """Get time-series engagement data for a campaign.

    Groups campaign_recipients events by time bucket (hour or day).
    Returns list of {timestamp, delivered, opened, clicked} per bucket.
    """
    trunc = "hour" if interval == "hour" else "day"

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT "
                    f"  DATE_TRUNC('{trunc}', delivered_at) as ts, "
                    f"  COUNT(*) FILTER (WHERE delivered_at IS NOT NULL) as delivered, "
                    f"  COUNT(*) FILTER (WHERE opened_at IS NOT NULL) as opened, "
                    f"  COUNT(*) FILTER (WHERE clicked_at IS NOT NULL) as clicked "
                    f"FROM marketing.campaign_recipients "
                    f"WHERE campaign_id = :cid AND delivered_at IS NOT NULL "
                    f"GROUP BY 1 ORDER BY 1"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "timestamp": r["ts"].isoformat() if r["ts"] else None,
            "delivered": r["delivered"],
            "opened": r["opened"],
            "clicked": r["clicked"],
        }
        for r in rows
    ]


async def get_revenue_attribution(
    db: AsyncSession,
    campaign_id: str,
    model: str = "last_click",
) -> dict[str, Any]:
    """Get revenue attribution for a campaign under a specific model.

    Queries campaign_attributions, applies the model, and returns
    total conversions, total revenue, and attributed revenue.
    """
    from modules.marketing.services.attribution_engine import (
        get_campaign_attribution_report,
    )

    return await get_campaign_attribution_report(db, campaign_id, model)
