"""Heatmap service — Layer 1 zone aggregation for email click tracking.

Aggregates campaign_link_clicks by zone position to show where users
clicked within the email template. Zones are assigned by
link_rewriting_service.py during campaign delivery.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_click_heatmap(
    db: AsyncSession,
    campaign_id: str,
    variant_id: str | None = None,
) -> dict[str, Any]:
    """Get click heatmap data for a campaign.

    Returns per-zone click counts and rates, sorted by zone position.
    Optionally filtered by variant_id for A/B comparison.
    """
    params: dict[str, Any] = {"cid": campaign_id}
    variant_filter = ""

    if variant_id:
        variant_filter = (
            "AND clc.recipient_id IN ("
            "  SELECT id FROM marketing.campaign_recipients "
            "  WHERE campaign_id = :cid AND variant_id = :vid"
            ") "
        )
        params["vid"] = variant_id

    # Get per-zone aggregates
    rows = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  clc.zone, "
                    "  COUNT(*) as total_clicks, "
                    "  COUNT(DISTINCT clc.recipient_id) as unique_clickers, "
                    "  COUNT(DISTINCT clc.url) as distinct_urls "
                    "FROM marketing.campaign_link_clicks clc "
                    f"WHERE clc.campaign_id = :cid {variant_filter}"
                    "GROUP BY clc.zone "
                    "ORDER BY clc.zone"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    # Get total recipients for rate calculation
    rate_params: dict[str, Any] = {"cid": campaign_id}
    rate_filter = ""
    if variant_id:
        rate_filter = "AND variant_id = :vid "
        rate_params["vid"] = variant_id

    total_row = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) as total "
                    "FROM marketing.campaign_recipients "
                    f"WHERE campaign_id = :cid {rate_filter}"
                    "AND status != 'failed'"
                ),
                rate_params,
            )
        )
        .mappings()
        .first()
    )
    total_recipients = total_row["total"] if total_row else 0

    zones = []
    for r in rows:
        zones.append(
            {
                "zone": r["zone"],
                "total_clicks": r["total_clicks"],
                "unique_clickers": r["unique_clickers"],
                "distinct_urls": r["distinct_urls"],
                "click_rate": (
                    round(r["unique_clickers"] / total_recipients, 4)
                    if total_recipients
                    else 0
                ),
            }
        )

    # Get top clicked URLs
    top_urls = (
        (
            await db.execute(
                text(
                    "SELECT url, zone, COUNT(*) as clicks, "
                    "  COUNT(DISTINCT recipient_id) as unique_clicks "
                    "FROM marketing.campaign_link_clicks "
                    "WHERE campaign_id = :cid "
                    "GROUP BY url, zone "
                    "ORDER BY clicks DESC LIMIT 20"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    return {
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "total_recipients": total_recipients,
        "zones": zones,
        "top_urls": [
            {
                "url": u["url"],
                "zone": u["zone"],
                "clicks": u["clicks"],
                "unique_clicks": u["unique_clicks"],
            }
            for u in top_urls
        ],
    }
