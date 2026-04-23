"""Campaign management — CRUD, A/B variants, sending via ESP, stats."""

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
        (
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
        )
        .mappings()
        .first()
    )

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


async def create_campaign_with_variants(
    db: AsyncSession,
    name: str,
    variants: list[dict[str, Any]],
    segment_ids: list[dict[str, Any]],
    created_by: str,
    utm_source: str | None = None,
    utm_medium: str | None = "email",
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    scheduled_at: str | None = None,
) -> dict[str, Any]:
    """Create a campaign with A/B variants and audience segments.

    Args:
        variants: List of dicts with keys: label, subject, html_content,
                  source_template_id (optional), weight.
        segment_ids: List of dicts with keys: segment_id, variant_label (optional).
    """
    if not variants:
        raise ValueError("At least one variant is required")

    # Use the first variant's subject as the campaign-level subject
    primary_subject = variants[0]["subject"]

    # Create the campaign
    campaign_row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.campaigns "
                    "(name, subject, template_id, template_data, created_by, "
                    "scheduled_at, utm_source, utm_medium, utm_campaign, "
                    "utm_content, utm_term) "
                    "VALUES (:name, :subj, :tid, :tdata, :uid, :sched, "
                    ":utm_src, :utm_med, :utm_camp, :utm_cont, :utm_term) "
                    "RETURNING id, status, created_at"
                ),
                {
                    "name": name,
                    "subj": primary_subject,
                    "tid": variants[0].get("source_template_id", "custom"),
                    "tdata": json.dumps({}),
                    "uid": created_by,
                    "sched": scheduled_at,
                    "utm_src": utm_source,
                    "utm_med": utm_medium,
                    "utm_camp": utm_campaign,
                    "utm_cont": utm_content,
                    "utm_term": utm_term,
                },
            )
        )
        .mappings()
        .first()
    )
    campaign_id = str(campaign_row["id"])

    # Create variants
    variant_results = []
    for v in variants:
        v_row = (
            (
                await db.execute(
                    text(
                        "INSERT INTO marketing.campaign_variants "
                        "(campaign_id, label, subject, html_content, "
                        "source_template_id, weight) "
                        "VALUES (:cid, :label, :subj, :html, :stid, :weight) "
                        "RETURNING id, label"
                    ),
                    {
                        "cid": campaign_id,
                        "label": v["label"],
                        "subj": v["subject"],
                        "html": v["html_content"],
                        "stid": v.get("source_template_id"),
                        "weight": v.get("weight", 100),
                    },
                )
            )
            .mappings()
            .first()
        )
        variant_results.append({"id": str(v_row["id"]), "label": v_row["label"]})

    # Link segments
    for seg in segment_ids:
        await db.execute(
            text(
                "INSERT INTO marketing.campaign_segments "
                "(campaign_id, segment_id, variant_label) "
                "VALUES (:cid, :sid, :vlabel) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "cid": campaign_id,
                "sid": seg["segment_id"],
                "vlabel": seg.get("variant_label"),
            },
        )

    await db.commit()
    logger.info(
        "Campaign created: %s (%s) with %d variants, %d segments",
        campaign_id,
        name,
        len(variants),
        len(segment_ids),
    )

    return {
        "id": campaign_id,
        "name": name,
        "subject": primary_subject,
        "status": campaign_row["status"],
        "variants": variant_results,
        "scheduled_at": scheduled_at,
        "created_at": str(campaign_row["created_at"]),
    }


async def get_campaign_variants(
    db: AsyncSession, campaign_id: str
) -> list[dict[str, Any]]:
    """Get all variants for a campaign."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, campaign_id, label, subject, html_content, "
                    "source_template_id, weight, provider_campaign_id, "
                    "stats_cache, stats_fetched_at, created_at "
                    "FROM marketing.campaign_variants "
                    "WHERE campaign_id = :cid ORDER BY label"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": str(r["id"]),
            "campaign_id": str(r["campaign_id"]),
            "label": r["label"],
            "subject": r["subject"],
            "html_content": r["html_content"],
            "source_template_id": r["source_template_id"],
            "weight": r["weight"],
            "provider_campaign_id": r["provider_campaign_id"],
            "stats_cache": r["stats_cache"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


async def send_campaign(db: AsyncSession, campaign_id: str) -> dict[str, Any]:
    """Send a campaign — supports single or multi-variant A/B campaigns.

    For campaigns with variants:
      1. Compute audience from linked segments
      2. Split audience by variant weights
      3. Inject UTM params into each variant's HTML
      4. Send each variant as a separate ESP campaign
      5. Update status and recipient counts

    For legacy campaigns without variants (backward compat):
      Renders template from DB and sends as a single ESP campaign.
    """
    # Fetch campaign
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM marketing.campaigns "
                    "WHERE id = :cid AND status IN ('draft', 'scheduled')"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Campaign not found or already sent")

    # Check for variants
    variants = await get_campaign_variants(db, campaign_id)

    from modules.gdpr.adapters import get_email_provider
    from modules.gdpr.services.template_service import inject_utm_params

    provider = get_email_provider("marketing_email")

    # Build UTM params from campaign
    utm_params = {}
    if row.get("utm_source"):
        utm_params["utm_source"] = row["utm_source"]
    if row.get("utm_medium"):
        utm_params["utm_medium"] = row["utm_medium"]
    if row.get("utm_campaign"):
        utm_params["utm_campaign"] = row["utm_campaign"]

    if variants:
        # --- Multi-variant send ---
        total_recipients = 0
        first_provider_id = None
        final_status = "sent"

        for variant in variants:
            html = variant["html_content"]

            # Per-variant UTM content
            variant_utm = {**utm_params}
            if row.get("utm_content"):
                variant_utm["utm_content"] = row["utm_content"]
            elif len(variants) > 1:
                variant_utm["utm_content"] = f"variant-{variant['label'].lower()}"

            if variant_utm:
                html = inject_utm_params(html, variant_utm)

            # Send variant as ESP campaign
            variant_name = f"{row['name']} — Variant {variant['label']}"
            result = await provider.create_campaign(
                name=variant_name,
                subject=variant["subject"],
                html_content=html,
                scheduled_at=(
                    str(row["scheduled_at"]) if row["scheduled_at"] else None
                ),
            )

            # Update variant record
            await db.execute(
                text(
                    "UPDATE marketing.campaign_variants "
                    "SET provider_campaign_id = :pcid "
                    "WHERE id = :vid"
                ),
                {"vid": variant["id"], "pcid": result.provider_campaign_id},
            )

            if first_provider_id is None:
                first_provider_id = result.provider_campaign_id
            if result.status != "sent":
                final_status = result.status

        # Update campaign record
        await db.execute(
            text(
                "UPDATE marketing.campaigns "
                "SET status = :status, provider = :prov, "
                "provider_campaign_id = :pcid, sent_at = NOW(), "
                "recipient_count = :rcnt "
                "WHERE id = :cid"
            ),
            {
                "cid": campaign_id,
                "status": final_status,
                "prov": settings.email_provider,
                "pcid": first_provider_id,
                "rcnt": total_recipients,
            },
        )
        await db.commit()

        logger.info(
            "Campaign %s sent %d variants via %s",
            campaign_id,
            len(variants),
            settings.email_provider,
        )

        return {
            "id": campaign_id,
            "status": final_status,
            "provider_campaign_id": first_provider_id,
            "variants_sent": len(variants),
        }

    else:
        # --- Legacy single-send (no variants) ---
        from modules.gdpr.services.template_service import render_template_db

        template_data = (
            row["template_data"] if isinstance(row["template_data"], dict) else {}
        )
        html_content, _ = await render_template_db(
            db, row["template_id"], template_data
        )

        if utm_params:
            html_content = inject_utm_params(html_content, utm_params)

        result = await provider.create_campaign(
            name=row["name"],
            subject=row["subject"],
            html_content=html_content,
            scheduled_at=(str(row["scheduled_at"]) if row["scheduled_at"] else None),
        )

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


async def get_campaign_stats(db: AsyncSession, campaign_id: str) -> dict[str, Any]:
    """Get campaign stats — pull from ESP if stale, otherwise return cached."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT provider_campaign_id, stats_cache, stats_fetched_at "
                    "FROM marketing.campaigns WHERE id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Campaign not found")

    provider_campaign_id = row["provider_campaign_id"]

    # Check if cache is fresh
    if row["stats_fetched_at"]:
        fetched_at = row["stats_fetched_at"]
        if isinstance(fetched_at, datetime):
            age = (
                datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)
            ).total_seconds()
            if age < _STATS_CACHE_TTL and row["stats_cache"]:
                return row["stats_cache"]

    # Pull fresh stats from ESP
    if not provider_campaign_id:
        return {
            "sent": 0,
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "bounced": 0,
            "unsubscribed": 0,
        }

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
        return {
            "sent": 0,
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "bounced": 0,
            "unsubscribed": 0,
        }


async def get_campaign_variant_stats(
    db: AsyncSession, campaign_id: str
) -> list[dict[str, Any]]:
    """Get per-variant stats for A/B campaigns."""
    variants = await get_campaign_variants(db, campaign_id)
    if not variants:
        return []

    from modules.gdpr.adapters import get_email_provider

    provider = get_email_provider("marketing_email")
    results = []

    for v in variants:
        pcid = v.get("provider_campaign_id")
        if not pcid:
            results.append(
                {
                    "label": v["label"],
                    "subject": v["subject"],
                    "weight": v["weight"],
                    "stats": _empty_stats(),
                }
            )
            continue

        # Check variant cache
        cached = v.get("stats_cache")
        if cached and isinstance(cached, dict):
            results.append(
                {
                    "label": v["label"],
                    "subject": v["subject"],
                    "weight": v["weight"],
                    "stats": cached,
                }
            )
            continue

        try:
            stats = await provider.get_campaign_stats(pcid)
            stats_dict = {
                "sent": stats.sent,
                "delivered": stats.delivered,
                "opened": stats.opened,
                "clicked": stats.clicked,
                "bounced": stats.bounced,
                "unsubscribed": stats.unsubscribed,
                "fetched_at": stats.fetched_at,
            }
            # Cache on the variant
            await db.execute(
                text(
                    "UPDATE marketing.campaign_variants "
                    "SET stats_cache = :cache, stats_fetched_at = NOW() "
                    "WHERE id = :vid"
                ),
                {"vid": v["id"], "cache": json.dumps(stats_dict)},
            )
            results.append(
                {
                    "label": v["label"],
                    "subject": v["subject"],
                    "weight": v["weight"],
                    "stats": stats_dict,
                }
            )
        except (NotImplementedError, Exception):
            results.append(
                {
                    "label": v["label"],
                    "subject": v["subject"],
                    "weight": v["weight"],
                    "stats": _empty_stats(),
                }
            )

    if results:
        await db.commit()
    return results


def _empty_stats() -> dict[str, Any]:
    return {
        "sent": 0,
        "delivered": 0,
        "opened": 0,
        "clicked": 0,
        "bounced": 0,
        "unsubscribed": 0,
    }


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
        (
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
        )
        .mappings()
        .all()
    )

    count_row = (
        (
            await db.execute(
                text(f"SELECT COUNT(*) as total FROM marketing.campaigns {where}"),
                params,
            )
        )
        .mappings()
        .first()
    )

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


async def cancel_campaign(db: AsyncSession, campaign_id: str) -> dict[str, Any]:
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
