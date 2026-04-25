"""Conversion recording service — links purchases to campaigns via attribution.

When a user completes a purchase (order completed), this service:
1. Reads the user's attribution data from Redis
2. Checks if the attribution is within the campaign's attribution window
3. Inserts a row into marketing.campaign_attributions with the touch sequence
4. Clears the attribution data so the same conversion isn't double-counted
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Default attribution window if campaign doesn't specify
_DEFAULT_WINDOW_DAYS = 7


async def record_conversion(
    db: AsyncSession,
    user_id: str,
    conversion_event: str,
    conversion_value: float = 0,
    conversion_currency: str = "USD",
    order_id: str | None = None,
) -> dict | None:
    """Record a conversion attributed to a campaign.

    Looks up the user's attribution from Redis, verifies it's within
    the attribution window, and inserts into campaign_attributions.

    Returns the attribution record dict, or None if no attribution found.
    """
    if not settings.enable_marketing:
        return None

    from modules.marketing.services.attribution_service import (
        clear_attribution,
        get_attribution,
    )

    attr = await get_attribution(user_id)
    if not attr or not attr.get("campaign_id"):
        logger.debug("No attribution for user %s — conversion not attributed", user_id)
        return None

    campaign_id = attr["campaign_id"]
    recipient_id = attr.get("recipient_id")
    medium = attr.get("medium", "email")
    touches = attr.get("touches", [])

    # Check attribution window
    campaign_row = (
        (
            await db.execute(
                text(
                    "SELECT attribution_window_days "
                    "FROM marketing.campaigns WHERE id = :cid"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .first()
    )

    window_days = _DEFAULT_WINDOW_DAYS
    if campaign_row and campaign_row.get("attribution_window_days"):
        window_days = campaign_row["attribution_window_days"]

    # Check if first touch is within attribution window
    first_touch_at = attr.get("first_touch_at")
    if first_touch_at:
        try:
            first_touch = datetime.fromisoformat(first_touch_at)
            now = datetime.now(timezone.utc)
            days_since = (now - first_touch).days
            if days_since > window_days:
                logger.debug(
                    "Attribution expired: campaign=%s user=%s days_since=%d window=%d",
                    campaign_id,
                    user_id,
                    days_since,
                    window_days,
                )
                await clear_attribution(user_id)
                return None
        except (ValueError, TypeError):
            pass

    # Dedup check — don't attribute the same conversion event twice
    existing = (
        (
            await db.execute(
                text(
                    "SELECT id FROM marketing.campaign_attributions "
                    "WHERE campaign_id = :cid AND user_id = :uid "
                    "AND conversion_event = :evt "
                    "AND converted_at > NOW() - INTERVAL '1 hour'"
                ),
                {"cid": campaign_id, "uid": user_id, "evt": conversion_event},
            )
        )
        .mappings()
        .first()
    )

    if existing:
        logger.debug(
            "Duplicate conversion skipped: campaign=%s user=%s event=%s",
            campaign_id,
            user_id,
            conversion_event,
        )
        return None

    # Insert attribution record
    await db.execute(
        text(
            "INSERT INTO marketing.campaign_attributions "
            "(campaign_id, recipient_id, user_id, channel, "
            " conversion_event, conversion_value, conversion_currency, "
            " converted, converted_at, attribution_window_days, touch_sequence) "
            "VALUES (:cid, :rid, :uid, :channel, "
            " :evt, :val, :currency, "
            " true, NOW(), :window, CAST(:touches AS jsonb))"
        ),
        {
            "cid": campaign_id,
            "rid": recipient_id,
            "uid": user_id,
            "channel": medium,
            "evt": conversion_event,
            "val": int(conversion_value),
            "currency": conversion_currency,
            "window": window_days,
            "touches": json.dumps(touches),
        },
    )
    await db.commit()

    # Clear attribution so next purchase gets fresh attribution
    await clear_attribution(user_id)

    logger.info(
        "Conversion attributed: campaign=%s user=%s event=%s value=%s touches=%d",
        campaign_id,
        user_id,
        conversion_event,
        conversion_value,
        len(touches),
    )

    return {
        "campaign_id": campaign_id,
        "user_id": user_id,
        "conversion_event": conversion_event,
        "conversion_value": conversion_value,
        "touches": len(touches),
    }


async def record_conversion_fire_and_forget(
    user_id: str,
    conversion_event: str,
    conversion_value: float = 0,
    conversion_currency: str = "USD",
    order_id: str | None = None,
) -> None:
    """Non-blocking conversion recording with its own DB session."""

    async def _task() -> None:
        try:
            from backend.core.database import get_session_factory

            async with get_session_factory()() as db:
                await record_conversion(
                    db,
                    user_id=user_id,
                    conversion_event=conversion_event,
                    conversion_value=conversion_value,
                    conversion_currency=conversion_currency,
                    order_id=order_id,
                )
        except Exception:
            logger.debug("Conversion recording error (non-fatal)", exc_info=True)

    try:
        asyncio.create_task(_task())
    except Exception:
        pass
