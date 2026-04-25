"""Reconciliation service — pull provider stats to backfill missed webhooks.

Runs every 6 hours for sent campaigns. Compares our campaign_recipients
counts against provider-reported totals. Records any delta for audit.

This catches:
- Webhooks lost in transit
- Events that arrived during downtime
- Provider-side delays in delivery reporting
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def reconcile_campaign(
    db: AsyncSession,
    campaign_id: str,
) -> dict:
    """Reconcile a single campaign's stats against provider data.

    Compares our campaign_recipients aggregate counts with provider-reported
    stats (via get_campaign_stats). Records delta if mismatch found.
    """
    # Get campaign info
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, provider_campaign_id, medium, provider "
                    "FROM marketing.campaigns WHERE id = :cid AND status = 'sent'"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if not row or not row["provider_campaign_id"]:
        return {"status": "skipped", "reason": "no provider campaign ID"}

    medium = row.get("medium", "email") or "email"

    # Only email campaigns have provider-side stats to reconcile
    if medium != "email":
        return {"status": "skipped", "reason": f"medium={medium} (no provider stats)"}

    # Get our local counts
    local_row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE status != 'failed') as total_sent, "
                    "COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) as total_delivered, "
                    "COUNT(*) FILTER (WHERE status IN ('opened','clicked')) as total_opened, "
                    "COUNT(*) FILTER (WHERE status = 'clicked') as total_clicked, "
                    "COUNT(*) FILTER (WHERE status = 'bounced') as total_bounced "
                    "FROM marketing.campaign_recipients WHERE campaign_id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    local_stats = {
        "sent": local_row["total_sent"] if local_row else 0,
        "delivered": local_row["total_delivered"] if local_row else 0,
        "opened": local_row["total_opened"] if local_row else 0,
        "clicked": local_row["total_clicked"] if local_row else 0,
        "bounced": local_row["total_bounced"] if local_row else 0,
    }

    # Get provider stats
    try:
        from modules.gdpr.adapters import get_email_provider

        provider = get_email_provider("marketing_email")
        provider_stats = await provider.get_campaign_stats(row["provider_campaign_id"])
        provider_dict = {
            "sent": provider_stats.sent,
            "delivered": provider_stats.delivered,
            "opened": provider_stats.opened,
            "clicked": provider_stats.clicked,
            "bounced": provider_stats.bounced,
        }
    except (NotImplementedError, Exception) as e:
        logger.debug("Cannot get provider stats for campaign %s: %s", campaign_id, e)
        return {"status": "skipped", "reason": "provider stats unavailable"}

    # Compute delta
    delta = {}
    for key in ["sent", "delivered", "opened", "clicked", "bounced"]:
        diff = provider_dict.get(key, 0) - local_stats.get(key, 0)
        if diff != 0:
            delta[key] = diff

    # Record reconciliation result
    await db.execute(
        text(
            "UPDATE marketing.campaigns "
            "SET last_reconciled_at = NOW(), reconciliation_delta = :delta "
            "WHERE id = :cid"
        ),
        {"cid": campaign_id, "delta": json.dumps(delta) if delta else None},
    )
    await db.commit()

    if delta:
        logger.info("Campaign %s reconciliation delta: %s", campaign_id, delta)
    else:
        logger.debug("Campaign %s reconciled — no delta", campaign_id)

    return {
        "status": "reconciled",
        "campaign_id": campaign_id,
        "delta": delta,
        "local": local_stats,
        "provider": provider_dict,
    }


async def reconcile_recent_campaigns(db: AsyncSession) -> dict:
    """Reconcile all campaigns sent in the last 7 days.

    Called by the background worker every 6 hours.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id FROM marketing.campaigns "
                    "WHERE status = 'sent' "
                    "AND sent_at > NOW() - INTERVAL '7 days' "
                    "AND (last_reconciled_at IS NULL "
                    "     OR last_reconciled_at < NOW() - INTERVAL '6 hours') "
                    "ORDER BY sent_at DESC LIMIT 50"
                )
            )
        )
        .mappings()
        .all()
    )

    results = []
    for row in rows:
        result = await reconcile_campaign(db, str(row["id"]))
        results.append(result)

    reconciled = sum(1 for r in results if r.get("status") == "reconciled")
    skipped = sum(1 for r in results if r.get("status") == "skipped")

    logger.info(
        "Reconciliation run: %d campaigns checked, %d reconciled, %d skipped",
        len(results),
        reconciled,
        skipped,
    )

    return {
        "total": len(results),
        "reconciled": reconciled,
        "skipped": skipped,
    }
