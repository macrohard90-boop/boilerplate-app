"""Campaign management — CRUD, A/B variants, sending via ESP, stats."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


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
    """Get campaign stats aggregated from campaign_recipients table."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(*) FILTER (WHERE status NOT IN ('failed','sending')) AS sent, "
                    "  COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) AS delivered, "
                    "  COUNT(*) FILTER (WHERE status IN ('opened','clicked')) AS opened, "
                    "  COUNT(*) FILTER (WHERE status = 'clicked') AS clicked, "
                    "  COUNT(*) FILTER (WHERE status = 'bounced') AS bounced, "
                    "  COUNT(*) FILTER (WHERE status = 'unsubscribed') AS unsubscribed "
                    "FROM marketing.campaign_recipients WHERE campaign_id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        return _empty_stats()

    return {
        "sent": row["sent"] or 0,
        "delivered": row["delivered"] or 0,
        "opened": row["opened"] or 0,
        "clicked": row["clicked"] or 0,
        "bounced": row["bounced"] or 0,
        "unsubscribed": row["unsubscribed"] or 0,
    }


async def get_campaign_variant_stats(
    db: AsyncSession, campaign_id: str
) -> list[dict[str, Any]]:
    """Get per-variant stats for A/B campaigns."""
    variants = await get_campaign_variants(db, campaign_id)
    if not variants:
        return []

    rows = (
        (
            await db.execute(
                text(
                    "SELECT variant_id, "
                    "  COUNT(*) FILTER (WHERE status NOT IN ('failed','sending')) AS sent, "
                    "  COUNT(*) FILTER (WHERE status IN ('delivered','opened','clicked')) AS delivered, "
                    "  COUNT(*) FILTER (WHERE status IN ('opened','clicked')) AS opened, "
                    "  COUNT(*) FILTER (WHERE status = 'clicked') AS clicked, "
                    "  COUNT(*) FILTER (WHERE status = 'bounced') AS bounced, "
                    "  COUNT(*) FILTER (WHERE status = 'unsubscribed') AS unsubscribed "
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

    stats_by_variant = {str(r["variant_id"]): dict(r) for r in rows}

    results = []
    for v in variants:
        s = stats_by_variant.get(v["id"], {})
        results.append(
            {
                "label": v["label"],
                "subject": v["subject"],
                "weight": v["weight"],
                "stats": {
                    "sent": s.get("sent", 0) or 0,
                    "delivered": s.get("delivered", 0) or 0,
                    "opened": s.get("opened", 0) or 0,
                    "clicked": s.get("clicked", 0) or 0,
                    "bounced": s.get("bounced", 0) or 0,
                    "unsubscribed": s.get("unsubscribed", 0) or 0,
                },
            }
        )

    return results


async def get_campaign_detail(db: AsyncSession, campaign_id: str) -> dict[str, Any]:
    """Get full campaign detail with stats and variants."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT c.id, c.name, c.subject, c.template_id, c.status, "
                    "c.medium, c.recipient_count, c.sent_at, c.created_at, "
                    "c.scheduled_at, c.utm_source, c.utm_medium, c.utm_campaign, "
                    "t.display_name AS template_display_name "
                    "FROM marketing.campaigns c "
                    "LEFT JOIN marketing.email_templates t ON t.name = c.template_id "
                    "WHERE c.id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Campaign not found")

    stats = await get_campaign_stats(db, campaign_id)
    variants = await get_campaign_variants(db, campaign_id)
    variant_stats = await get_campaign_variant_stats(db, campaign_id)

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "subject": row["subject"],
        "template_id": row["template_id"],
        "template_display_name": row["template_display_name"],
        "status": row["status"],
        "medium": row["medium"] or "email",
        "recipient_count": row["recipient_count"] or 0,
        "sent_at": str(row["sent_at"]) if row["sent_at"] else None,
        "created_at": str(row["created_at"]),
        "scheduled_at": str(row["scheduled_at"]) if row["scheduled_at"] else None,
        "stats": stats,
        "variants": variants,
        "variant_stats": variant_stats,
    }


async def get_campaign_recipients(
    db: AsyncSession,
    campaign_id: str,
    status: str | None = None,
    variant_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """Get paginated recipient list for a campaign."""
    where = "WHERE cr.campaign_id = :cid"
    params: dict[str, Any] = {
        "cid": campaign_id,
        "lim": per_page,
        "off": (page - 1) * per_page,
    }

    if status:
        where += " AND cr.status = :status"
        params["status"] = status

    if variant_id:
        where += " AND cr.variant_id = :vid"
        params["vid"] = variant_id

    total = (
        await db.execute(
            text(f"SELECT COUNT(*) FROM marketing.campaign_recipients cr {where}"),
            params,
        )
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT cr.id, cr.to_address, cr.variant_id, cr.status, "
                    f"cr.provider, cr.provider_message_id, cr.error_message, "
                    f"cr.sent_at, cr.delivered_at, cr.opened_at, cr.clicked_at, "
                    f"cr.created_at, u.first_name, u.last_name, "
                    f"cv.label AS variant_label "
                    f"FROM marketing.campaign_recipients cr "
                    f"LEFT JOIN core.users u ON u.id = cr.user_id "
                    f"LEFT JOIN marketing.campaign_variants cv ON cv.id = cr.variant_id "
                    f"{where} "
                    f"ORDER BY cr.created_at ASC "
                    f"LIMIT :lim OFFSET :off"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [
            {
                "id": str(r["id"]),
                "to_address": r["to_address"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "variant_id": str(r["variant_id"]) if r["variant_id"] else None,
                "variant_label": r["variant_label"],
                "status": r["status"],
                "error_message": r["error_message"],
                "sent_at": str(r["sent_at"]) if r["sent_at"] else None,
                "delivered_at": str(r["delivered_at"]) if r["delivered_at"] else None,
                "opened_at": str(r["opened_at"]) if r["opened_at"] else None,
                "clicked_at": str(r["clicked_at"]) if r["clicked_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


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
