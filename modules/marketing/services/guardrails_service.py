"""Guardrails service — frequency caps, quiet hours, sunset policy.

Enforced on every marketing send. Check order:
1. Consent check → SKIP if no consent
2. Suppression check → SKIP if suppressed
3. Frequency cap → SKIP if over cap
4. Quiet hours → DEFER to morning
5. Sunset policy → SKIP if inactive too long
"""

import logging
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GuardrailResult:
    """Result of a guardrails check."""

    def __init__(
        self,
        allowed: bool,
        reason: str | None = None,
        defer_until: datetime | None = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.defer_until = defer_until

    def __repr__(self) -> str:
        return f"GuardrailResult(allowed={self.allowed}, reason={self.reason})"


async def check_guardrails(
    db: AsyncSession,
    user_id: str,
    channel: str = "email",
    message_type: str = "marketing",
) -> GuardrailResult:
    """Run all guardrail checks for a single user/channel send.

    Returns GuardrailResult indicating whether the send is allowed.
    Transactional messages bypass frequency caps but not suppression.
    """
    # 1. Consent check
    consent = await _check_consent(db, user_id, channel)
    if not consent:
        return GuardrailResult(False, "no_consent")

    # 2. Suppression check
    suppressed = await _check_suppression(db, user_id)
    if suppressed:
        return GuardrailResult(False, "suppressed")

    # Transactional messages bypass remaining checks
    if message_type == "transactional":
        return GuardrailResult(True)

    # 3. Frequency cap check
    freq_result = await _check_frequency_cap(db, user_id, channel)
    if not freq_result:
        return GuardrailResult(False, "frequency_cap_exceeded")

    # 4. Quiet hours check
    quiet_result = await _check_quiet_hours(db, channel)
    if quiet_result is not None:
        return GuardrailResult(False, "quiet_hours", defer_until=quiet_result)

    # 5. Sunset policy check
    sunset = await _check_sunset(db, user_id, channel)
    if not sunset:
        return GuardrailResult(False, "sunset_inactive")

    return GuardrailResult(True)


async def get_guardrails_config(db: AsyncSession) -> list[dict[str, Any]]:
    """Get all channel guardrails configuration."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT channel, freq_cap_marketing_per_day, "
                    "  freq_cap_marketing_per_week, freq_cap_marketing_per_month, "
                    "  quiet_hours_start, quiet_hours_end, quiet_hours_timezone, "
                    "  sunset_inactivity_days, enabled "
                    "FROM marketing.messaging_config "
                    "ORDER BY channel"
                )
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "channel": r["channel"],
            "freq_cap_per_day": r["freq_cap_marketing_per_day"],
            "freq_cap_per_week": r["freq_cap_marketing_per_week"],
            "freq_cap_per_month": r["freq_cap_marketing_per_month"],
            "quiet_hours_start": (
                str(r["quiet_hours_start"]) if r["quiet_hours_start"] else None
            ),
            "quiet_hours_end": (
                str(r["quiet_hours_end"]) if r["quiet_hours_end"] else None
            ),
            "quiet_hours_timezone": r["quiet_hours_timezone"],
            "sunset_inactivity_days": r["sunset_inactivity_days"],
            "enabled": r["enabled"],
        }
        for r in rows
    ]


async def update_guardrails_config(
    db: AsyncSession,
    channel: str,
    **updates: Any,
) -> dict | None:
    """Update guardrails config for a channel."""
    allowed = {
        "freq_cap_marketing_per_day",
        "freq_cap_marketing_per_week",
        "freq_cap_marketing_per_month",
        "quiet_hours_start",
        "quiet_hours_end",
        "quiet_hours_timezone",
        "sunset_inactivity_days",
        "enabled",
    }

    set_parts = []
    params: dict[str, Any] = {"channel": channel}

    for key, value in updates.items():
        if key in allowed and value is not None:
            set_parts.append(f"{key} = :{key}")
            params[key] = value

    if not set_parts:
        return None

    await db.execute(
        text(
            f"UPDATE marketing.messaging_config "
            f"SET {', '.join(set_parts)} "
            f"WHERE channel = :channel"
        ),
        params,
    )
    await db.commit()

    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM marketing.messaging_config WHERE channel = :channel"
                ),
                {"channel": channel},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def log_message_pressure(
    db: AsyncSession,
    user_id: str,
    channel: str,
    message_type: str = "marketing",
    campaign_id: str | None = None,
) -> None:
    """Log a sent message for frequency cap tracking."""
    await db.execute(
        text(
            "INSERT INTO marketing.message_pressure_log "
            "(user_id, channel, message_type, campaign_id) "
            "VALUES (:uid, :channel, :mtype, :cid)"
        ),
        {
            "uid": user_id,
            "channel": channel,
            "mtype": message_type,
            "cid": campaign_id,
        },
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Internal checks
# ---------------------------------------------------------------------------


async def _check_consent(db: AsyncSession, user_id: str, channel: str) -> bool:
    """Check if user has marketing consent for the channel."""
    if channel == "email":
        # Check GDPR consent for marketing emails
        row = (
            (
                await db.execute(
                    text(
                        "SELECT 1 FROM gdpr.consent_records "
                        "WHERE user_id = :uid AND consent_type = 'marketing_email' "
                        "AND status = 'granted'"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        return row is not None

    # SMS/WhatsApp: check communication preferences
    row = (
        (
            await db.execute(
                text(
                    "SELECT 1 FROM marketing.user_communication_preferences ucp "
                    "JOIN marketing.communication_types ct ON ct.id = ucp.communication_type_id "
                    "WHERE ucp.user_id = :uid AND ct.name = :channel AND ucp.allowed = true"
                ),
                {"uid": user_id, "channel": channel},
            )
        )
        .mappings()
        .first()
    )
    return row is not None


async def _check_suppression(db: AsyncSession, user_id: str) -> bool:
    """Check if user is on the suppression list."""
    row = (
        (
            await db.execute(
                text("SELECT 1 FROM gdpr.suppression_list " "WHERE user_id = :uid"),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    return row is not None


async def _check_frequency_cap(db: AsyncSession, user_id: str, channel: str) -> bool:
    """Check if user is under frequency cap for the channel."""
    # Get config for this channel (fallback to global)
    config = (
        (
            await db.execute(
                text(
                    "SELECT freq_cap_marketing_per_day, "
                    "  freq_cap_marketing_per_week, "
                    "  freq_cap_marketing_per_month "
                    "FROM marketing.messaging_config "
                    "WHERE channel = :channel"
                ),
                {"channel": channel},
            )
        )
        .mappings()
        .first()
    )

    if not config:
        config = (
            (
                await db.execute(
                    text(
                        "SELECT freq_cap_marketing_per_day, "
                        "  freq_cap_marketing_per_week, "
                        "  freq_cap_marketing_per_month "
                        "FROM marketing.messaging_config "
                        "WHERE channel = 'global'"
                    )
                )
            )
            .mappings()
            .first()
        )

    if not config:
        return True  # No config = no cap

    # Count recent sends
    counts = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  COUNT(*) FILTER (WHERE sent_at > NOW() - INTERVAL '1 day') as day_count, "
                    "  COUNT(*) FILTER (WHERE sent_at > NOW() - INTERVAL '7 days') as week_count, "
                    "  COUNT(*) FILTER (WHERE sent_at > NOW() - INTERVAL '30 days') as month_count "
                    "FROM marketing.message_pressure_log "
                    "WHERE user_id = :uid AND channel = :channel "
                    "AND message_type = 'marketing'"
                ),
                {"uid": user_id, "channel": channel},
            )
        )
        .mappings()
        .first()
    )

    if not counts:
        return True

    cap_day = config["freq_cap_marketing_per_day"]
    cap_week = config["freq_cap_marketing_per_week"]
    cap_month = config["freq_cap_marketing_per_month"]

    if cap_day and counts["day_count"] >= cap_day:
        return False
    if cap_week and counts["week_count"] >= cap_week:
        return False
    if cap_month and counts["month_count"] >= cap_month:
        return False

    return True


async def _check_quiet_hours(db: AsyncSession, channel: str) -> datetime | None:
    """Check if current time is within quiet hours.

    Returns the datetime when quiet hours end (for deferral), or None if OK.
    """
    config = (
        (
            await db.execute(
                text(
                    "SELECT quiet_hours_start, quiet_hours_end, quiet_hours_timezone "
                    "FROM marketing.messaging_config "
                    "WHERE channel = :channel"
                ),
                {"channel": channel},
            )
        )
        .mappings()
        .first()
    )

    if not config or not config["quiet_hours_start"] or not config["quiet_hours_end"]:
        return None

    now_utc = datetime.now(timezone.utc)
    current_time = now_utc.time()

    start = config["quiet_hours_start"]
    end = config["quiet_hours_end"]

    # Handle cross-midnight quiet hours (e.g., 22:00 → 08:00)
    if start > end:
        # Quiet hours span midnight
        if current_time >= start or current_time < end:
            # In quiet hours — defer to end time tomorrow
            return now_utc.replace(
                hour=end.hour, minute=end.minute, second=0, microsecond=0
            )
    else:
        if start <= current_time < end:
            return now_utc.replace(
                hour=end.hour, minute=end.minute, second=0, microsecond=0
            )

    return None


async def _check_sunset(db: AsyncSession, user_id: str, channel: str) -> bool:
    """Check if user has been inactive beyond the sunset threshold.

    Returns True if user is still active (not sunset), False if should be sunset.
    """
    config = (
        (
            await db.execute(
                text(
                    "SELECT sunset_inactivity_days "
                    "FROM marketing.messaging_config "
                    "WHERE channel = :channel"
                ),
                {"channel": channel},
            )
        )
        .mappings()
        .first()
    )

    if not config or not config["sunset_inactivity_days"]:
        return True  # No sunset policy

    days = config["sunset_inactivity_days"]

    # Check if user has had any engagement in the sunset window
    engagement = (
        (
            await db.execute(
                text(
                    "SELECT 1 FROM analytics.engagement_scores "
                    "WHERE user_id = :uid AND score > 0 "
                    "AND (last_email_open > NOW() - INTERVAL '1 day' * :days "
                    "     OR last_email_click > NOW() - INTERVAL '1 day' * :days "
                    "     OR last_site_visit > NOW() - INTERVAL '1 day' * :days "
                    "     OR last_purchase > NOW() - INTERVAL '1 day' * :days)"
                ),
                {"uid": user_id, "days": days},
            )
        )
        .mappings()
        .first()
    )

    return engagement is not None
