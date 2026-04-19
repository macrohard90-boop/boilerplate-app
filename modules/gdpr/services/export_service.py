"""Data export (Right of Access) — collect and package all user data."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)


async def request_export(db: AsyncSession, user_id: str) -> dict[str, Any]:
    """Create a data export request. Rate limited to 1 per 24 hours."""
    # Rate limit check
    recent = (
        (
            await db.execute(
                text(
                    "SELECT id FROM gdpr.data_export_requests "
                    "WHERE user_id = :uid AND requested_at > NOW() - INTERVAL '24 hours' "
                    "LIMIT 1"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if recent:
        raise ValueError("Export already requested in the last 24 hours")

    # Create pending request
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO gdpr.data_export_requests (user_id, status) "
                    "VALUES (:uid, 'pending') "
                    "RETURNING id, status, requested_at"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )
    await db.commit()

    export_id = str(row["id"])

    # Process immediately (async in-request for simplicity)
    await _process_export(db, user_id, export_id)

    # Return updated status
    return await get_export_status(db, user_id, export_id)


async def _process_export(db: AsyncSession, user_id: str, export_id: str) -> None:
    """Collect all user data and store as JSON."""
    # Update status to processing
    await db.execute(
        text(
            "UPDATE gdpr.data_export_requests SET status = 'processing' "
            "WHERE id = :eid"
        ),
        {"eid": export_id},
    )
    await db.commit()

    try:
        data: dict[str, Any] = {}

        # User profile
        user = (
            (
                await db.execute(
                    text(
                        "SELECT id, email, first_name, last_name, created_at, updated_at "
                        "FROM core.users WHERE id = :uid"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if user:
            data["profile"] = {k: str(v) if v else None for k, v in user.items()}

        # Orders
        orders = (
            (
                await db.execute(
                    text(
                        "SELECT id, order_number, status, total, currency, created_at "
                        "FROM ecommerce.orders WHERE user_id = :uid "
                        "ORDER BY created_at DESC"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        data["orders"] = [
            {k: str(v) if v else None for k, v in o.items()} for o in orders
        ]

        # Consent records
        consents = (
            (
                await db.execute(
                    text(
                        "SELECT consent_type, granted, version, created_at "
                        "FROM gdpr.consent_records WHERE user_id = :uid "
                        "ORDER BY created_at DESC"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        data["consent_records"] = [
            {k: str(v) if v else None for k, v in c.items()} for c in consents
        ]

        # Email preferences
        email_prefs = (
            (
                await db.execute(
                    text(
                        "SELECT marketing_email, transactional_email, suppressed_at, "
                        "suppression_reason, created_at "
                        "FROM gdpr.email_preferences WHERE user_id = :uid"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        data["email_preferences"] = (
            {k: str(v) if v else None for k, v in email_prefs.items()}
            if email_prefs
            else None
        )

        # Analytics sessions
        sessions = (
            (
                await db.execute(
                    text(
                        "SELECT session_id, started_at, ended_at, page_count "
                        "FROM analytics.analytics_sessions WHERE user_id = :uid "
                        "ORDER BY started_at DESC LIMIT 100"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        data["analytics_sessions"] = [
            {k: str(v) if v else None for k, v in s.items()} for s in sessions
        ]

        # Page views
        pageviews = (
            (
                await db.execute(
                    text(
                        "SELECT path, referrer, duration_ms, created_at "
                        "FROM analytics.page_views WHERE user_id = :uid "
                        "ORDER BY created_at DESC LIMIT 500"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        data["page_views"] = [
            {k: str(v) if v else None for k, v in p.items()} for p in pageviews
        ]

        # Events
        events = (
            (
                await db.execute(
                    text(
                        "SELECT event_type, event_data, created_at "
                        "FROM analytics.events WHERE user_id = :uid "
                        "ORDER BY created_at DESC LIMIT 500"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        data["events"] = [
            {
                "event_type": str(e["event_type"]),
                "event_data": (
                    e["event_data"]
                    if isinstance(e["event_data"], dict)
                    else str(e["event_data"])
                ),
                "created_at": str(e["created_at"]),
            }
            for e in events
        ]

        expiry_days = getattr(settings, "gdpr_export_expiry_days", 7)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

        # Store export data as JSON in file_url
        await db.execute(
            text(
                "UPDATE gdpr.data_export_requests "
                "SET status = 'completed', file_url = :data, "
                "completed_at = NOW(), expires_at = :exp "
                "WHERE id = :eid"
            ),
            {
                "eid": export_id,
                "data": json.dumps(data, default=str),
                "exp": expires_at,
            },
        )
        await db.commit()

    except Exception:
        logger.exception("Export processing failed for user %s", user_id)
        await db.rollback()
        await db.execute(
            text(
                "UPDATE gdpr.data_export_requests SET status = 'failed' "
                "WHERE id = :eid"
            ),
            {"eid": export_id},
        )
        await db.commit()
        raise


async def get_export_status(
    db: AsyncSession, user_id: str, export_id: str
) -> dict[str, Any]:
    """Get export request status and data if completed."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, status, requested_at, completed_at, expires_at, file_url "
                    "FROM gdpr.data_export_requests "
                    "WHERE id = :eid AND user_id = :uid"
                ),
                {"eid": export_id, "uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Export request not found")

    # Check expiry
    if row["status"] == "completed" and row["expires_at"]:
        if datetime.now(timezone.utc) > row["expires_at"]:
            await db.execute(
                text(
                    "UPDATE gdpr.data_export_requests SET status = 'expired', file_url = NULL "
                    "WHERE id = :eid"
                ),
                {"eid": export_id},
            )
            await db.commit()
            return {
                "id": str(row["id"]),
                "status": "expired",
                "requested_at": str(row["requested_at"]),
                "completed_at": (
                    str(row["completed_at"]) if row["completed_at"] else None
                ),
                "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
                "data": None,
            }

    data = None
    if row["status"] == "completed" and row["file_url"]:
        try:
            data = json.loads(row["file_url"])
        except (json.JSONDecodeError, TypeError):
            data = None

    return {
        "id": str(row["id"]),
        "status": row["status"],
        "requested_at": str(row["requested_at"]),
        "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
        "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
        "data": data,
    }
