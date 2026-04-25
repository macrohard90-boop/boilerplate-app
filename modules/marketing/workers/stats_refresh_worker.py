"""Stats summary refresh worker — aggregates campaign_recipients into campaign_stats_summary.

Runs every 30 minutes for recently active campaigns. Computes aggregate counts
and rates per campaign (and per variant if A/B testing), then upserts into
campaign_stats_summary for fast dashboard reads.

This avoids expensive COUNT(*) queries on every dashboard load.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Shared SET clause for upserts
_UPDATE_SET = (
    " total_sent = EXCLUDED.total_sent, "
    " total_delivered = EXCLUDED.total_delivered, "
    " total_opened = EXCLUDED.total_opened, "
    " total_clicked = EXCLUDED.total_clicked, "
    " total_bounced = EXCLUDED.total_bounced, "
    " total_complained = EXCLUDED.total_complained, "
    " total_unsubscribed = EXCLUDED.total_unsubscribed, "
    " total_conversions = EXCLUDED.total_conversions, "
    " total_revenue = EXCLUDED.total_revenue, "
    " open_rate = EXCLUDED.open_rate, "
    " click_rate = EXCLUDED.click_rate, "
    " conversion_rate = EXCLUDED.conversion_rate, "
    " computed_at = NOW()"
)

_INSERT_COLS = (
    "INSERT INTO marketing.campaign_stats_summary "
    "(campaign_id, variant_id, total_sent, total_delivered, "
    " total_opened, total_clicked, total_bounced, total_complained, "
    " total_unsubscribed, total_conversions, total_revenue, "
    " open_rate, click_rate, conversion_rate, computed_at) "
)

_INSERT_VALS = (
    "VALUES (:cid, :vid, :sent, :delivered, "
    " :opened, :clicked, :bounced, :complained, "
    " :unsub, :conversions, :revenue, "
    " :open_rate, :click_rate, :conv_rate, NOW()) "
)


async def _upsert_stats_row(
    db: AsyncSession,
    campaign_id: str,
    variant_id: str | None,
    stats: dict,
    total_conversions: int,
    total_revenue: float,
) -> None:
    """Upsert a single stats summary row.

    Uses different ON CONFLICT clauses for NULL vs non-NULL variant_id
    because PostgreSQL partial unique indexes require WHERE conditions.
    """
    total_sent = stats.get("total_sent", 0) or 0
    total_delivered = stats.get("total_delivered", 0) or 0
    total_opened = stats.get("total_opened", 0) or 0
    total_clicked = stats.get("total_clicked", 0) or 0

    open_rate = round((total_opened / total_delivered) if total_delivered > 0 else 0, 4)
    click_rate = round(
        (total_clicked / total_delivered) if total_delivered > 0 else 0, 4
    )
    conv_rate = round((total_conversions / total_sent) if total_sent > 0 else 0, 4)

    params = {
        "cid": campaign_id,
        "vid": variant_id,
        "sent": total_sent,
        "delivered": total_delivered,
        "opened": total_opened,
        "clicked": total_clicked,
        "bounced": stats.get("total_bounced", 0) or 0,
        "complained": stats.get("total_complained", 0) or 0,
        "unsub": stats.get("total_unsubscribed", 0) or 0,
        "conversions": total_conversions,
        "revenue": total_revenue,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "conv_rate": conv_rate,
    }

    if variant_id is not None:
        # Non-NULL variant → use idx_css_campaign_variant partial index
        conflict = (
            "ON CONFLICT (campaign_id, variant_id) "
            "WHERE variant_id IS NOT NULL "
            "DO UPDATE SET" + _UPDATE_SET
        )
    else:
        # NULL variant (overall) → use idx_css_campaign_overall partial index
        conflict = (
            "ON CONFLICT (campaign_id) "
            "WHERE variant_id IS NULL "
            "DO UPDATE SET" + _UPDATE_SET
        )

    await db.execute(text(_INSERT_COLS + _INSERT_VALS + conflict), params)


async def refresh_campaign_stats(
    db: AsyncSession,
    campaign_id: str,
) -> dict:
    """Refresh stats summary for a single campaign.

    Aggregates campaign_recipients counts per variant (NULL variant = overall).
    Computes open_rate, click_rate, conversion_rate from totals.
    Upserts into campaign_stats_summary.
    """
    # Aggregate per variant
    rows = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  variant_id, "
                    "  COUNT(*) FILTER (WHERE status != 'failed') as total_sent, "
                    "  COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) as total_delivered, "
                    "  COUNT(*) FILTER (WHERE status IN ('opened','clicked')) as total_opened, "
                    "  COUNT(*) FILTER (WHERE status = 'clicked') as total_clicked, "
                    "  COUNT(*) FILTER (WHERE status = 'bounced') as total_bounced, "
                    "  COUNT(*) FILTER (WHERE status = 'complained') as total_complained, "
                    "  COUNT(*) FILTER (WHERE status = 'unsubscribed') as total_unsubscribed "
                    "FROM marketing.campaign_recipients "
                    "WHERE campaign_id = :cid "
                    "GROUP BY variant_id"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    if not rows:
        return {"status": "skipped", "reason": "no recipients"}

    # Get conversion + revenue from campaign_attributions
    attr_row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(*) as total_conversions, "
                    "  COALESCE(SUM(revenue), 0) as total_revenue "
                    "FROM marketing.campaign_attributions "
                    "WHERE campaign_id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    total_conversions = attr_row["total_conversions"] if attr_row else 0
    total_revenue = float(attr_row["total_revenue"]) if attr_row else 0.0

    upserted = 0
    has_variants = False

    for row in rows:
        variant_id = row.get("variant_id")
        if variant_id is not None:
            has_variants = True

        await _upsert_stats_row(
            db,
            campaign_id,
            str(variant_id) if variant_id else variant_id,
            dict(row),
            total_conversions,
            total_revenue,
        )
        upserted += 1

    # If we had per-variant rows, also compute overall (variant_id = NULL)
    if has_variants:
        overall = (
            (
                await db.execute(
                    text(
                        "SELECT "
                        "  COUNT(*) FILTER (WHERE status != 'failed') as total_sent, "
                        "  COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) as total_delivered, "
                        "  COUNT(*) FILTER (WHERE status IN ('opened','clicked')) as total_opened, "
                        "  COUNT(*) FILTER (WHERE status = 'clicked') as total_clicked, "
                        "  COUNT(*) FILTER (WHERE status = 'bounced') as total_bounced, "
                        "  COUNT(*) FILTER (WHERE status = 'complained') as total_complained, "
                        "  COUNT(*) FILTER (WHERE status = 'unsubscribed') as total_unsubscribed "
                        "FROM marketing.campaign_recipients "
                        "WHERE campaign_id = :cid"
                    ),
                    {"cid": campaign_id},
                )
            )
            .mappings()
            .first()
        )

        if overall:
            await _upsert_stats_row(
                db, campaign_id, None, dict(overall), total_conversions, total_revenue
            )
            upserted += 1

    await db.commit()

    return {
        "status": "refreshed",
        "campaign_id": campaign_id,
        "variants_upserted": upserted,
    }


async def refresh_recent_campaign_stats(db: AsyncSession) -> dict:
    """Refresh stats for all recently active campaigns.

    Called by the background worker every 30 minutes.
    Targets campaigns sent in the last 30 days that have not been
    refreshed in the last 30 minutes.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT c.id "
                    "FROM marketing.campaigns c "
                    "WHERE c.status = 'sent' "
                    "AND c.sent_at > NOW() - INTERVAL '30 days' "
                    "AND ( "
                    "  NOT EXISTS ( "
                    "    SELECT 1 FROM marketing.campaign_stats_summary css "
                    "    WHERE css.campaign_id = c.id "
                    "  ) "
                    "  OR EXISTS ( "
                    "    SELECT 1 FROM marketing.campaign_stats_summary css "
                    "    WHERE css.campaign_id = c.id "
                    "    AND css.computed_at < NOW() - INTERVAL '30 minutes' "
                    "  ) "
                    ") "
                    "ORDER BY c.sent_at DESC LIMIT 100"
                )
            )
        )
        .mappings()
        .all()
    )

    results = []
    for row in rows:
        result = await refresh_campaign_stats(db, str(row["id"]))
        results.append(result)

    refreshed = sum(1 for r in results if r.get("status") == "refreshed")
    skipped = sum(1 for r in results if r.get("status") == "skipped")

    logger.info(
        "Stats refresh run: %d campaigns checked, %d refreshed, %d skipped",
        len(results),
        refreshed,
        skipped,
    )

    return {
        "total": len(results),
        "refreshed": refreshed,
        "skipped": skipped,
    }
