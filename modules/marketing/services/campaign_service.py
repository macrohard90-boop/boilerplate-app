"""Campaign management — CRUD, sending via GDPR email infrastructure, stats."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Stats cache TTL in seconds (5 minutes)
_STATS_CACHE_TTL = 300


async def create_campaign(
    db: AsyncSession,
    name: str,
    subject: str,
    template_id: str,
    template_data: dict,
    created_by: str,
    scheduled_at: str | None = None,
) -> dict[str, Any]:
    """Create a draft campaign."""
    result = (
        await db.execute(
            text(
                "INSERT INTO marketing.campaigns "
                "(name, subject, template_id, template_data, created_by, scheduled_at) "
                "VALUES (:name, :subj, :tid, :tdata, :uid, :sched) "
                "RETURNING id, status, created_at"
            ),
            {
                "name": name,
                "subj": subject,
                "tid": template_id,
                "tdata": json.dumps(template_data),
                "uid": created_by,
                "sched": scheduled_at,
            },
        )
    ).mappings().first()

    await db.commit()
    logger.info("Campaign created: %s (%s)", result["id"], name)

    return {
        "id": str(result["id"]),
        "name": name,
        "subject": subject,
        "template_id": template_id,
        "status": result["status"],
        "scheduled_at": scheduled_at,
        "created_at": str(result["created_at"]),
    }


async def send_campaign(
    db: AsyncSession, campaign_id: str
) -> dict[str, Any]:
    """Send a campaign — render template, push to ESP, update status."""
    # Fetch campaign
    row = (
        await db.execute(
            text(
                "SELECT * FROM marketing.campaigns "
                "WHERE id = :cid AND status IN ('draft', 'scheduled')"
            ),
            {"cid": campaign_id},
        )
    ).mappings().first()

    if not row:
        raise ValueError("Campaign not found or already sent")

    # Render the template (DB first, then filesystem fallback)
    from modules.gdpr.services.template_service import render_template_hybrid

    template_data = row["template_data"] if isinstance(row["template_data"], dict) else {}
    html_content, _ = await render_template_hybrid(db, row["template_id"], template_data)

    # Get the email provider
    from modules.gdpr.adapters import get_email_provider

    provider = get_email_provider("marketing_email")

    # Create campaign in ESP
    result = await provider.create_campaign(
        name=row["name"],
        subject=row["subject"],
        html_content=html_content,
        scheduled_at=str(row["scheduled_at"]) if row["scheduled_at"] else None,
    )

    # Update campaign record
    await db.execute(
        text(
            "UPDATE marketing.campaigns "
            "SET status = :status, provider = :prov, "
            "provider_campaign_id = :pcid, sent_at = NOW() "
            "WHERE id = :cid"
        ),
        {
            "cid": campaign_id,
            "status": result.status,
            "prov": settings.email_provider,
            "pcid": result.provider_campaign_id,
        },
    )
    await db.commit()

    logger.info(
        "Campaign %s sent via %s (provider_id=%s)",
        campaign_id,
        settings.email_provider,
        result.provider_campaign_id,
    )

    return {
        "id": campaign_id,
        "status": result.status,
        "provider_campaign_id": result.provider_campaign_id,
    }


async def get_campaign_stats(
    db: AsyncSession, campaign_id: str
) -> dict[str, Any]:
    """Get campaign stats — pull from ESP if stale, otherwise return cached."""
    row = (
        await db.execute(
            text(
                "SELECT provider_campaign_id, stats_cache, stats_fetched_at "
                "FROM marketing.campaigns WHERE id = :cid"
            ),
            {"cid": campaign_id},
        )
    ).mappings().first()

    if not row:
        raise ValueError("Campaign not found")

    provider_campaign_id = row["provider_campaign_id"]

    # Check if cache is fresh
    if row["stats_fetched_at"]:
        fetched_at = row["stats_fetched_at"]
        if isinstance(fetched_at, datetime):
            age = (datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)).total_seconds()
            if age < _STATS_CACHE_TTL and row["stats_cache"]:
                return row["stats_cache"]

    # Pull fresh stats from ESP
    if not provider_campaign_id:
        return {"sent": 0, "delivered": 0, "opened": 0, "clicked": 0, "bounced": 0, "unsubscribed": 0}

    from modules.gdpr.adapters import get_email_provider

    provider = get_email_provider("marketing_email")

    try:
        stats = await provider.get_campaign_stats(provider_campaign_id)
        stats_dict = {
            "sent": stats.sent,
            "delivered": stats.delivered,
            "opened": stats.opened,
            "clicked": stats.clicked,
            "bounced": stats.bounced,
            "unsubscribed": stats.unsubscribed,
            "fetched_at": stats.fetched_at,
        }

        # Cache the stats
        await db.execute(
            text(
                "UPDATE marketing.campaigns "
                "SET stats_cache = :cache, stats_fetched_at = NOW() "
                "WHERE id = :cid"
            ),
            {"cid": campaign_id, "cache": json.dumps(stats_dict)},
        )
        await db.commit()

        return stats_dict
    except NotImplementedError:
        return {"sent": 0, "delivered": 0, "opened": 0, "clicked": 0, "bounced": 0, "unsubscribed": 0}


async def list_campaigns(
    db: AsyncSession,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List campaigns with optional status filter and pagination."""
    offset = (page - 1) * per_page
    params: dict[str, Any] = {"limit": per_page, "offset": offset}

    where = ""
    if status:
        where = "WHERE status = :status"
        params["status"] = status

    rows = (
        await db.execute(
            text(
                f"SELECT id, name, subject, template_id, status, "
                f"provider_campaign_id, recipient_count, "
                f"scheduled_at, sent_at, created_at "
                f"FROM marketing.campaigns {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).mappings().all()

    count_row = (
        await db.execute(
            text(f"SELECT COUNT(*) as total FROM marketing.campaigns {where}"),
            params,
        )
    ).mappings().first()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "subject": r["subject"],
                "template_id": r["template_id"],
                "status": r["status"],
                "provider_campaign_id": r["provider_campaign_id"],
                "recipient_count": r["recipient_count"],
                "scheduled_at": str(r["scheduled_at"]) if r["scheduled_at"] else None,
                "sent_at": str(r["sent_at"]) if r["sent_at"] else None,
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "total": count_row["total"],
        "page": page,
        "per_page": per_page,
    }


async def cancel_campaign(
    db: AsyncSession, campaign_id: str
) -> dict[str, Any]:
    """Cancel a draft or scheduled campaign."""
    result = await db.execute(
        text(
            "UPDATE marketing.campaigns SET status = 'cancelled' "
            "WHERE id = :cid AND status IN ('draft', 'scheduled') "
            "RETURNING id, status"
        ),
        {"cid": campaign_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError("Campaign not found or cannot be cancelled")

    await db.commit()
    logger.info("Campaign %s cancelled", campaign_id)

    return {"id": str(row["id"]), "status": "cancelled"}
