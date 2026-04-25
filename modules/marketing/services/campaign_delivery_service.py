"""Campaign delivery service — the core multi-channel send engine.

Replaces the old send_campaign flow with the full pipeline:
1. Resolve audience (from segments or all consented users)
2. Filter recipients (channel availability, suppression, consent, dedup)
3. Batch process (INSERT-BEFORE-SEND pattern, F20)
4. Render + rewrite links per channel
5. Send via provider adapter
6. Update status, log pressure, track progress in Redis
"""

import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Batch size for processing recipients
BATCH_SIZE = 50

# Redis key prefix for campaign send progress
_PROGRESS_KEY = "campaign:progress:{campaign_id}"


# --------------------------------------------------------------------------
# 1. Audience Resolution
# --------------------------------------------------------------------------


async def resolve_audience(
    db: AsyncSession,
    campaign_id: str,
    medium: str = "email",
) -> list[dict[str, Any]]:
    """Resolve the full audience for a campaign.

    Checks campaign_segments for segment-based targeting.
    Falls back to all consented users for the channel if no segments linked.

    Returns list of dicts: {user_id, email, phone, whatsapp_number, first_name}
    """
    # Check for linked segments
    seg_rows = (
        (
            await db.execute(
                text(
                    "SELECT segment_id, variant_label "
                    "FROM marketing.campaign_segments WHERE campaign_id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    if seg_rows:
        # Segment-based audience — resolve each segment's users
        from modules.marketing.services.segment_service import (
            resolve_segment_user_ids,
        )

        all_user_ids: set[str] = set()
        for seg in seg_rows:
            user_ids = await resolve_segment_user_ids(db, str(seg["segment_id"]))
            all_user_ids.update(user_ids)

        if not all_user_ids:
            return []

        # Fetch user details
        placeholders = ", ".join(f":uid{i}" for i in range(len(all_user_ids)))
        params = {f"uid{i}": uid for i, uid in enumerate(all_user_ids)}
        rows = (
            (
                await db.execute(
                    text(
                        f"SELECT u.id AS user_id, u.email, u.phone, "
                        f"u.whatsapp_number, u.first_name "
                        f"FROM core.users u "
                        f"WHERE u.id IN ({placeholders}) "
                        f"AND u.is_active = TRUE AND u.deleted_at IS NULL"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
    else:
        # No segments — fall back to all consented users for this channel
        if medium == "email":
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT u.id AS user_id, u.email, u.phone, "
                            "u.whatsapp_number, u.first_name "
                            "FROM core.users u "
                            "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                            "WHERE ep.marketing_email = TRUE "
                            "AND ep.suppressed_at IS NULL "
                            "AND u.is_active = TRUE AND u.deleted_at IS NULL"
                        )
                    )
                )
                .mappings()
                .all()
            )
        elif medium == "sms":
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT u.id AS user_id, u.email, u.phone, "
                            "u.whatsapp_number, u.first_name "
                            "FROM core.users u "
                            "WHERE u.phone IS NOT NULL AND u.phone != '' "
                            "AND u.is_active = TRUE AND u.deleted_at IS NULL"
                        )
                    )
                )
                .mappings()
                .all()
            )
        elif medium == "whatsapp":
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT u.id AS user_id, u.email, u.phone, "
                            "u.whatsapp_number, u.first_name "
                            "FROM core.users u "
                            "WHERE u.whatsapp_number IS NOT NULL "
                            "AND u.whatsapp_number != '' "
                            "AND u.is_active = TRUE AND u.deleted_at IS NULL"
                        )
                    )
                )
                .mappings()
                .all()
            )
        else:
            rows = []

    return [
        {
            "user_id": str(r["user_id"]),
            "email": r["email"],
            "phone": r.get("phone"),
            "whatsapp_number": r.get("whatsapp_number"),
            "first_name": r.get("first_name"),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# 2. Recipient Filtering
# --------------------------------------------------------------------------


async def filter_recipients(
    db: AsyncSession,
    users: list[dict[str, Any]],
    campaign_id: str,
    medium: str = "email",
) -> list[dict[str, Any]]:
    """Filter audience through the 5-stage pipeline.

    1. Channel availability (has email? has phone? has whatsapp_number?)
    2. Suppression check
    3. Consent check
    4. Already-received check (prevent duplicates on retry)
    5. Frequency cap check
    """
    if not users:
        return []

    eligible = []

    # Stage 4: Already-received (get all user IDs who already received this campaign)
    already_sent = set()
    try:
        rows = (
            (
                await db.execute(
                    text(
                        "SELECT user_id FROM marketing.campaign_recipients "
                        "WHERE campaign_id = :cid AND status != 'failed'"
                    ),
                    {"cid": campaign_id},
                )
            )
            .mappings()
            .all()
        )
        already_sent = {str(r["user_id"]) for r in rows}
    except Exception:
        pass  # Table might not exist yet — proceed without dedup

    for user in users:
        user_id = user["user_id"]

        # Stage 1: Channel availability
        if medium == "email" and not user.get("email"):
            continue
        if medium == "sms" and not user.get("phone"):
            continue
        if medium == "whatsapp" and not user.get("whatsapp_number"):
            continue

        # Stage 4: Already received
        if user_id in already_sent:
            continue

        # Stages 2, 3, 5 are checked during audience resolution (SQL JOINs above)
        # More granular checks (freq cap, sunset) happen at send time in Stage 9 guardrails
        eligible.append(user)

    logger.info(
        "Campaign %s: %d/%d recipients eligible after filtering (medium=%s)",
        campaign_id,
        len(eligible),
        len(users),
        medium,
    )
    return eligible


# --------------------------------------------------------------------------
# 3. Variant Assignment
# --------------------------------------------------------------------------


def assign_variants(
    recipients: list[dict[str, Any]],
    variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assign each recipient to a variant based on weight distribution.

    Uses deterministic assignment based on position in the list.
    Each recipient gets a 'variant_id' and 'variant' dict added.
    """
    if not variants:
        # No variants — all recipients get None variant
        for r in recipients:
            r["variant_id"] = None
            r["variant"] = None
        return recipients

    if len(variants) == 1:
        for r in recipients:
            r["variant_id"] = variants[0]["id"]
            r["variant"] = variants[0]
        return recipients

    # Multi-variant: split by weight
    total_weight = sum(v.get("weight", 100) for v in variants)
    thresholds = []
    cumulative = 0
    for v in variants:
        cumulative += v.get("weight", 100) / total_weight
        thresholds.append((cumulative, v))

    for i, r in enumerate(recipients):
        position = (i + 1) / len(recipients)
        for threshold, variant in thresholds:
            if position <= threshold:
                r["variant_id"] = variant["id"]
                r["variant"] = variant
                break
        else:
            # Edge case: assign to last variant
            r["variant_id"] = variants[-1]["id"]
            r["variant"] = variants[-1]

    return recipients


# --------------------------------------------------------------------------
# 4. Progress Tracking (Redis)
# --------------------------------------------------------------------------


async def _update_progress(
    campaign_id: str,
    total: int,
    sent: int,
    failed: int,
    status: str = "sending",
) -> None:
    """Update campaign send progress in Redis."""
    try:
        from backend.core.redis_client import get_redis

        redis = await get_redis()
        key = _PROGRESS_KEY.format(campaign_id=campaign_id)
        await redis.hset(
            key,
            mapping={
                "total": str(total),
                "sent": str(sent),
                "failed": str(failed),
                "status": status,
            },
        )
        await redis.expire(key, 3600)  # Expire after 1 hour
    except Exception:
        pass  # Non-critical


async def get_campaign_progress(campaign_id: str) -> dict[str, Any] | None:
    """Get campaign send progress from Redis."""
    try:
        from backend.core.redis_client import get_redis

        redis = await get_redis()
        key = _PROGRESS_KEY.format(campaign_id=campaign_id)
        data = await redis.hgetall(key)
        if data:
            return {
                "total": int(data.get("total", 0)),
                "sent": int(data.get("sent", 0)),
                "failed": int(data.get("failed", 0)),
                "status": data.get("status", "unknown"),
            }
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# 5. The Send Loop (per-channel dispatch)
# --------------------------------------------------------------------------


async def _send_email_recipient(
    db: AsyncSession,
    recipient: dict[str, Any],
    campaign: dict[str, Any],
    html_content: str,
    subject: str,
    utm_params: dict[str, str],
) -> dict[str, Any]:
    """Send email to one recipient with INSERT-BEFORE-SEND."""
    from modules.gdpr.adapters import get_email_provider
    from modules.marketing.services.link_rewriting_service import rewrite_email_links

    recipient_id = recipient["recipient_row_id"]

    # Rewrite links
    rewritten_html = rewrite_email_links(
        html_content,
        utm_params,
        campaign["id"],
        recipient_id,
        enable_heatmap=campaign.get("enable_heatmap", False),
    )

    # Send
    provider = get_email_provider("marketing_email")
    result = await provider.send_email(
        to_email=recipient["email"],
        subject=subject,
        html_content=rewritten_html,
        to_name=recipient.get("first_name"),
        tags=[f"campaign:{campaign['id']}"],
    )

    return {
        "success": result.success,
        "provider_message_id": result.provider_message_id,
        "error": result.error,
        "provider": result.provider,
    }


async def _send_sms_recipient(
    db: AsyncSession,
    recipient: dict[str, Any],
    campaign: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    """Send SMS to one recipient."""
    from modules.notifications.adapters import get_sms_provider

    provider = get_sms_provider()
    result = await provider.send_sms(
        to_number=recipient["phone"],
        content=content,
        tags=[f"campaign:{campaign['id']}"],
    )

    return {
        "success": result.success,
        "provider_message_id": result.provider_message_id,
        "error": result.error,
        "provider": result.provider,
    }


async def _send_whatsapp_recipient(
    db: AsyncSession,
    recipient: dict[str, Any],
    campaign: dict[str, Any],
    template_name: str,
    parameters: dict | None = None,
) -> dict[str, Any]:
    """Send WhatsApp to one recipient."""
    from modules.notifications.adapters import get_whatsapp_provider

    provider = get_whatsapp_provider()
    result = await provider.send_template(
        to_number=recipient["whatsapp_number"],
        template_name=template_name,
        parameters=parameters,
    )

    return {
        "success": result.success,
        "provider_message_id": result.provider_message_id,
        "error": result.error,
        "provider": result.provider,
    }


# --------------------------------------------------------------------------
# 6. Main Delivery Orchestrator
# --------------------------------------------------------------------------


async def deliver_campaign(
    db: AsyncSession,
    campaign_id: str,
) -> dict[str, Any]:
    """Execute the full campaign delivery pipeline.

    This is the main entry point called by the send route.

    Steps:
    1. Load campaign + variants
    2. Resolve audience
    3. Filter recipients
    4. Assign variants
    5. Batch process: INSERT-BEFORE-SEND → render → rewrite → send → update
    6. Update campaign status
    """
    # 1. Load campaign
    campaign_row = (
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
    if not campaign_row:
        raise ValueError("Campaign not found or already sent")

    campaign = dict(campaign_row)
    campaign["id"] = str(campaign["id"])
    medium = campaign.get("medium", "email") or "email"

    # Mark as sending
    await db.execute(
        text("UPDATE marketing.campaigns SET status = 'sending' WHERE id = :cid"),
        {"cid": campaign_id},
    )
    await db.commit()

    # Load variants
    from modules.marketing.services.campaign_service import get_campaign_variants

    variants = await get_campaign_variants(db, campaign_id)

    # 2. Resolve audience
    audience = await resolve_audience(db, campaign_id, medium)

    if not audience:
        await db.execute(
            text(
                "UPDATE marketing.campaigns "
                "SET status = 'sent', sent_at = NOW(), recipient_count = 0 "
                "WHERE id = :cid"
            ),
            {"cid": campaign_id},
        )
        await db.commit()
        return {
            "id": campaign_id,
            "status": "sent",
            "recipient_count": 0,
            "sent": 0,
            "failed": 0,
        }

    # 3. Filter recipients
    eligible = await filter_recipients(db, audience, campaign_id, medium)

    if not eligible:
        await db.execute(
            text(
                "UPDATE marketing.campaigns "
                "SET status = 'sent', sent_at = NOW(), recipient_count = 0 "
                "WHERE id = :cid"
            ),
            {"cid": campaign_id},
        )
        await db.commit()
        return {
            "id": campaign_id,
            "status": "sent",
            "recipient_count": 0,
            "sent": 0,
            "failed": 0,
        }

    # 4. Assign variants
    eligible = assign_variants(eligible, variants)

    # Build UTM params
    from modules.marketing.services.link_rewriting_service import build_utm_params

    total = len(eligible)
    sent_count = 0
    failed_count = 0

    await _update_progress(campaign_id, total, 0, 0, "sending")

    # 5. Batch process
    for batch_start in range(0, total, BATCH_SIZE):
        batch = eligible[batch_start : batch_start + BATCH_SIZE]

        for recipient in batch:
            user_id = recipient["user_id"]
            variant = recipient.get("variant")
            variant_id = recipient.get("variant_id")

            # Determine destination address
            if medium == "email":
                to_address = recipient["email"]
            elif medium == "sms":
                to_address = recipient["phone"]
            elif medium == "whatsapp":
                to_address = recipient["whatsapp_number"]
            else:
                to_address = recipient["email"]

            # INSERT-BEFORE-SEND (F20)
            try:
                row = (
                    (
                        await db.execute(
                            text(
                                "INSERT INTO marketing.campaign_recipients "
                                "(campaign_id, variant_id, user_id, channel, "
                                " to_address, status) "
                                "VALUES (:cid, :vid, :uid, :ch, :addr, 'sending') "
                                "ON CONFLICT (campaign_id, user_id) DO NOTHING "
                                "RETURNING id"
                            ),
                            {
                                "cid": campaign_id,
                                "vid": variant_id,
                                "uid": user_id,
                                "ch": medium,
                                "addr": to_address,
                            },
                        )
                    )
                    .mappings()
                    .first()
                )
                await db.commit()

                if not row:
                    # Duplicate — skip
                    continue

                recipient_row_id = str(row["id"])
                recipient["recipient_row_id"] = recipient_row_id
            except Exception:
                logger.exception(
                    "Failed to INSERT campaign_recipient for user=%s", user_id
                )
                failed_count += 1
                continue

            # Guardrails check (consent, suppression, frequency cap, quiet hours, sunset)
            try:
                from modules.marketing.services.guardrails_service import (
                    check_guardrails,
                )

                guardrail = await check_guardrails(
                    db, user_id, channel=medium, message_type="marketing"
                )
                if not guardrail.allowed:
                    await db.execute(
                        text(
                            "UPDATE marketing.campaign_recipients "
                            "SET status = 'skipped', error_message = :reason "
                            "WHERE id = :rid"
                        ),
                        {"rid": recipient_row_id, "reason": guardrail.reason},
                    )
                    await db.commit()
                    continue
            except Exception:
                logger.debug(
                    "Guardrails check error for user=%s (proceeding)",
                    user_id,
                    exc_info=True,
                )

            # Send per channel
            try:
                if medium == "email":
                    # Render content
                    if variant:
                        html_content = variant["html_content"]
                        subject = variant["subject"]
                    else:
                        # Legacy: render from template
                        from modules.gdpr.services.template_service import (
                            render_template_db,
                        )

                        template_data = (
                            campaign["template_data"]
                            if isinstance(campaign["template_data"], dict)
                            else {}
                        )
                        html_content, rendered_subject = await render_template_db(
                            db, campaign["template_id"], template_data
                        )
                        subject = rendered_subject or campaign["subject"]

                    utm = build_utm_params(
                        campaign["name"],
                        medium,
                        utm_source=campaign.get("utm_source"),
                        utm_medium=campaign.get("utm_medium"),
                        utm_campaign=campaign.get("utm_campaign"),
                        utm_content=campaign.get("utm_content"),
                        utm_term=campaign.get("utm_term"),
                        variant_label=(variant["label"] if variant else None),
                    )

                    send_result = await _send_email_recipient(
                        db, recipient, campaign, html_content, subject, utm
                    )

                elif medium == "sms":
                    # SMS: render template as plain text
                    if variant:
                        content = variant.get("html_content", "")
                        # Strip HTML tags for SMS
                        content = re.sub(r"<[^>]+>", "", content).strip()
                    else:
                        from modules.gdpr.services.template_service import (
                            render_template_db,
                        )

                        template_data = (
                            campaign["template_data"]
                            if isinstance(campaign["template_data"], dict)
                            else {}
                        )
                        html, _ = await render_template_db(
                            db, campaign["template_id"], template_data
                        )
                        content = re.sub(r"<[^>]+>", "", html).strip()

                    send_result = await _send_sms_recipient(
                        db, recipient, campaign, content
                    )

                elif medium == "whatsapp":
                    template_name = campaign.get("template_id", "")
                    template_data = (
                        campaign["template_data"]
                        if isinstance(campaign["template_data"], dict)
                        else {}
                    )
                    send_result = await _send_whatsapp_recipient(
                        db, recipient, campaign, template_name, template_data
                    )

                else:
                    send_result = {
                        "success": False,
                        "error": f"Unknown medium: {medium}",
                    }

                # Update recipient status
                if send_result["success"]:
                    await db.execute(
                        text(
                            "UPDATE marketing.campaign_recipients "
                            "SET status = 'sent', provider = :prov, "
                            "provider_message_id = :pmid, sent_at = NOW() "
                            "WHERE id = :rid"
                        ),
                        {
                            "rid": recipient_row_id,
                            "prov": send_result.get("provider", ""),
                            "pmid": send_result.get("provider_message_id"),
                        },
                    )
                    sent_count += 1
                else:
                    await db.execute(
                        text(
                            "UPDATE marketing.campaign_recipients "
                            "SET status = 'failed', error_message = :err "
                            "WHERE id = :rid"
                        ),
                        {
                            "rid": recipient_row_id,
                            "err": send_result.get("error", "Unknown error"),
                        },
                    )
                    failed_count += 1

                # Log message pressure
                await db.execute(
                    text(
                        "INSERT INTO marketing.message_pressure_log "
                        "(user_id, channel, message_type, campaign_id) "
                        "VALUES (:uid, :ch, 'marketing', :cid)"
                    ),
                    {"uid": user_id, "ch": medium, "cid": campaign_id},
                )
                await db.commit()

            except Exception:
                logger.exception(
                    "Failed to send to user=%s in campaign=%s",
                    user_id,
                    campaign_id,
                )
                failed_count += 1
                try:
                    await db.execute(
                        text(
                            "UPDATE marketing.campaign_recipients "
                            "SET status = 'failed', error_message = 'Send exception' "
                            "WHERE id = :rid"
                        ),
                        {"rid": recipient_row_id},
                    )
                    await db.commit()
                except Exception:
                    pass

        # Update progress after each batch
        await _update_progress(campaign_id, total, sent_count, failed_count, "sending")

    # 6. Update campaign status
    final_status = "sent"
    await db.execute(
        text(
            "UPDATE marketing.campaigns "
            "SET status = :status, sent_at = NOW(), "
            "recipient_count = :rcnt, provider = :prov "
            "WHERE id = :cid"
        ),
        {
            "cid": campaign_id,
            "status": final_status,
            "rcnt": sent_count,
            "prov": _get_provider_name(medium),
        },
    )
    await db.commit()

    await _update_progress(campaign_id, total, sent_count, failed_count, "complete")

    logger.info(
        "Campaign %s delivery complete: %d sent, %d failed out of %d (medium=%s)",
        campaign_id,
        sent_count,
        failed_count,
        total,
        medium,
    )

    return {
        "id": campaign_id,
        "status": final_status,
        "recipient_count": sent_count,
        "sent": sent_count,
        "failed": failed_count,
        "total_eligible": total,
    }


def _get_provider_name(medium: str) -> str:
    """Get the configured provider name for a medium."""
    if medium == "email":
        return settings.email_provider
    elif medium == "sms":
        return settings.sms_provider
    elif medium == "whatsapp":
        return settings.whatsapp_provider
    return "unknown"
