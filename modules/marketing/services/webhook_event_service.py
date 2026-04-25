"""Campaign webhook event service — records clicks, extracts zone positions.

Handles the campaign-specific side of webhook processing:
- Record email link clicks with zone position extraction (Layer 1 heatmap)
- Update campaign_recipients statuses for SMS/WhatsApp events
"""

import logging
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_email_click(
    db: AsyncSession,
    provider_message_id: str,
    url: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record an email click in campaign_link_clicks.

    Extracts zone position (_zp) from URL query params for heatmap tracking.
    Links back to campaign_recipients via provider_message_id.
    """
    # Look up the recipient by provider_message_id
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, campaign_id, user_id "
                    "FROM marketing.campaign_recipients "
                    "WHERE provider_message_id = :pmid"
                ),
                {"pmid": provider_message_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        logger.debug(
            "Click for unknown provider_message_id=%s (not a campaign message)",
            provider_message_id,
        )
        return

    recipient_id = str(row["id"])
    campaign_id = str(row["campaign_id"])
    user_id = str(row["user_id"]) if row["user_id"] else None

    # Extract zone position from URL params
    zone = _extract_zone(url)

    # Count click number for this recipient
    count_row = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) as cnt "
                    "FROM marketing.campaign_link_clicks "
                    "WHERE recipient_id = :rid"
                ),
                {"rid": recipient_id},
            )
        )
        .mappings()
        .first()
    )
    click_number = (count_row["cnt"] if count_row else 0) + 1

    # Insert click record
    await db.execute(
        text(
            "INSERT INTO marketing.campaign_link_clicks "
            "(recipient_id, campaign_id, user_id, url, zone, "
            " click_number, ip_address, user_agent, clicked_at) "
            "VALUES (:rid, :cid, :uid, :url, :zone, "
            " :click_num, :ip, :ua, NOW())"
        ),
        {
            "rid": recipient_id,
            "cid": campaign_id,
            "uid": user_id,
            "url": url,
            "zone": zone,
            "click_num": click_number,
            "ip": ip_address,
            "ua": user_agent,
        },
    )

    logger.info(
        "Recorded click: campaign=%s, recipient=%s, zone=%s, click#=%d",
        campaign_id,
        recipient_id,
        zone,
        click_number,
    )


async def update_sms_recipient_status(
    db: AsyncSession,
    provider_message_id: str,
    status: str,
) -> None:
    """Update campaign_recipients for SMS webhook events.

    Args:
        provider_message_id: Brevo SMS message ID (integer as string).
        status: Normalized status (delivered, bounced, failed).
    """
    status_map = {
        "delivered": ("delivered", "delivered_at"),
        "bounced": ("bounced", None),
        "failed": ("failed", None),
    }

    new_status, timestamp_col = status_map.get(status, (status, None))

    if timestamp_col:
        await db.execute(
            text(
                f"UPDATE marketing.campaign_recipients "
                f"SET status = :status, {timestamp_col} = COALESCE({timestamp_col}, NOW()) "
                f"WHERE provider_message_id = :pmid AND channel = 'sms'"
            ),
            {"pmid": provider_message_id, "status": new_status},
        )
    else:
        await db.execute(
            text(
                "UPDATE marketing.campaign_recipients "
                "SET status = :status "
                "WHERE provider_message_id = :pmid AND channel = 'sms'"
            ),
            {"pmid": provider_message_id, "status": new_status},
        )


async def update_whatsapp_recipient_status(
    db: AsyncSession,
    provider_message_id: str,
    status: str,
) -> None:
    """Update campaign_recipients for WhatsApp webhook events.

    Args:
        provider_message_id: Brevo WhatsApp message ID.
        status: Normalized status (delivered, read, failed).
    """
    status_map = {
        "delivered": ("delivered", "delivered_at"),
        "read": ("opened", "opened_at"),  # WA read = reliable open
        "failed": ("failed", None),
    }

    new_status, timestamp_col = status_map.get(status, (status, None))

    if timestamp_col:
        await db.execute(
            text(
                f"UPDATE marketing.campaign_recipients "
                f"SET status = :status, {timestamp_col} = COALESCE({timestamp_col}, NOW()) "
                f"WHERE provider_message_id = :pmid AND channel = 'whatsapp'"
            ),
            {"pmid": provider_message_id, "status": new_status},
        )
    else:
        await db.execute(
            text(
                "UPDATE marketing.campaign_recipients "
                "SET status = :status "
                "WHERE provider_message_id = :pmid AND channel = 'whatsapp'"
            ),
            {"pmid": provider_message_id, "status": new_status},
        )


def _extract_zone(url: str) -> str | None:
    """Extract heatmap zone position from URL query params.

    Looks for _zp (zone position) parameter added by link_rewriting_service.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        zp = params.get("_zp")
        if zp:
            return zp[0]
    except Exception:
        pass
    return None
