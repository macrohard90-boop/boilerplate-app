"""Audience insights — aggregate stats for campaign wizard coaching."""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.services.segment_service import _build_segment_query

logger = logging.getLogger(__name__)


async def get_global_insights(db: AsyncSession) -> dict[str, Any]:
    """Overview stats for the entire marketing-eligible audience."""

    # Total eligible users (base query with no extra filters)
    total_sql, total_params = _build_segment_query({}, count_only=True)
    total_row = (await db.execute(text(total_sql), total_params)).mappings().first()
    total_eligible = total_row["cnt"] if total_row else 0

    # RFM segment breakdown
    rfm_rows = (
        (
            await db.execute(
                text(
                    "SELECT COALESCE(cm.rfm_segment, 'unknown') AS seg, "
                    "COUNT(*) AS cnt "
                    "FROM core.users u "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "LEFT JOIN ecommerce.customer_metrics cm ON cm.user_id = u.id "
                    "WHERE ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL "
                    "  AND u.is_active = TRUE AND u.deleted_at IS NULL "
                    "GROUP BY seg ORDER BY cnt DESC"
                )
            )
        )
        .mappings()
        .all()
    )
    by_rfm_segment = {r["seg"]: r["cnt"] for r in rfm_rows}

    # Average order value and orders per user
    aov_row = (
        (
            await db.execute(
                text(
                    "SELECT "
                    "  AVG(cm.total_spent) AS avg_total_spent, "
                    "  AVG(cm.order_count) AS avg_orders "
                    "FROM core.users u "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "JOIN ecommerce.customer_metrics cm ON cm.user_id = u.id "
                    "WHERE ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL "
                    "  AND u.is_active = TRUE AND u.deleted_at IS NULL "
                    "  AND cm.order_count > 0"
                )
            )
        )
        .mappings()
        .first()
    )
    avg_order_value = round(float(aov_row["avg_total_spent"] or 0) / 100, 2)
    avg_orders_per_user = round(float(aov_row["avg_orders"] or 0), 1)

    # Active in last 30 days (has page view)
    active_row = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(DISTINCT u.id) AS cnt "
                    "FROM core.users u "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "JOIN analytics.page_views pv ON pv.user_id = u.id "
                    "WHERE ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL "
                    "  AND u.is_active = TRUE AND u.deleted_at IS NULL "
                    "  AND pv.created_at >= NOW() - INTERVAL '30 days'"
                )
            )
        )
        .mappings()
        .first()
    )
    active_last_30_days = active_row["cnt"] if active_row else 0

    # Cart abandonment count
    cart_row = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(DISTINCT c.user_id) AS cnt "
                    "FROM ecommerce.carts c "
                    "JOIN core.users u ON u.id = c.user_id "
                    "JOIN gdpr.email_preferences ep ON ep.user_id = u.id "
                    "WHERE c.status = 'abandoned' "
                    "  AND ep.marketing_email = TRUE "
                    "  AND ep.suppressed_at IS NULL "
                    "  AND u.is_active = TRUE AND u.deleted_at IS NULL"
                )
            )
        )
        .mappings()
        .first()
    )
    cart_abandonment_count = cart_row["cnt"] if cart_row else 0

    # Top communication types by subscriber count
    ct_rows = (
        (
            await db.execute(
                text(
                    "SELECT ct.name, COUNT(ucp.user_id) AS subscriber_count "
                    "FROM marketing.communication_types ct "
                    "LEFT JOIN marketing.user_communication_preferences ucp "
                    "  ON ucp.communication_type_id = ct.id AND ucp.allowed = TRUE "
                    "WHERE ct.enabled = TRUE "
                    "GROUP BY ct.name ORDER BY subscriber_count DESC"
                )
            )
        )
        .mappings()
        .all()
    )
    top_communication_types = [
        {"name": r["name"], "subscriber_count": r["subscriber_count"]} for r in ct_rows
    ]

    return {
        "total_eligible": total_eligible,
        "by_rfm_segment": by_rfm_segment,
        "avg_order_value": avg_order_value,
        "avg_orders_per_user": avg_orders_per_user,
        "active_last_30_days": active_last_30_days,
        "cart_abandonment_count": cart_abandonment_count,
        "top_communication_types": top_communication_types,
    }


async def get_segment_insights(
    db: AsyncSession, filters: dict[str, Any]
) -> dict[str, Any]:
    """Stats for a specific audience segment defined by filters."""

    # Get user IDs in this segment (use the filter engine)
    user_sql, user_params = _build_segment_query(filters)
    rows = (await db.execute(text(user_sql), user_params)).mappings().all()
    user_ids = [str(r["user_id"]) for r in rows]
    user_count = len(user_ids)

    if user_count == 0:
        return _empty_segment_insights()

    # Total eligible for percentage calculation
    total_sql, total_params = _build_segment_query({}, count_only=True)
    total_row = (await db.execute(text(total_sql), total_params)).mappings().first()
    total_eligible = total_row["cnt"] if total_row else 1
    pct_of_total = round((user_count / max(total_eligible, 1)) * 100, 1)

    # Build a CTE with segment user IDs for efficient joins
    # For small segments, use IN clause. For large segments, still use IN.
    # (A temp table would be better for 1000+ users, but IN is simpler and
    # sufficient for typical segment sizes.)
    id_placeholders = ", ".join(f":uid_{i}" for i in range(user_count))
    uid_params = {f"uid_{i}": uid for i, uid in enumerate(user_ids)}

    # Order stats for segment
    order_row = (
        (
            await db.execute(
                text(
                    f"SELECT "
                    f"  AVG(cm.total_spent) AS avg_spent, "
                    f"  AVG(cm.order_count) AS avg_orders, "
                    f"  SUM(cm.total_spent) AS total_revenue "
                    f"FROM ecommerce.customer_metrics cm "
                    f"WHERE cm.user_id IN ({id_placeholders}) "
                    f"  AND cm.order_count > 0"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    avg_order_value = round(float(order_row["avg_spent"] or 0) / 100, 2)
    avg_orders_per_user = round(float(order_row["avg_orders"] or 0), 1)
    total_revenue = int(order_row["total_revenue"] or 0)

    # RFM breakdown within segment
    rfm_rows = (
        (
            await db.execute(
                text(
                    f"SELECT COALESCE(cm.rfm_segment, 'unknown') AS seg, "
                    f"COUNT(*) AS cnt "
                    f"FROM ecommerce.customer_metrics cm "
                    f"WHERE cm.user_id IN ({id_placeholders}) "
                    f"GROUP BY seg ORDER BY cnt DESC"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    rfm_breakdown = {r["seg"]: r["cnt"] for r in rfm_rows}

    # Top 5 products purchased by this segment
    product_rows = (
        (
            await db.execute(
                text(
                    f"SELECT p.name, COUNT(*) AS purchase_count "
                    f"FROM ecommerce.order_items oi "
                    f"JOIN ecommerce.orders o ON o.id = oi.order_id "
                    f"JOIN ecommerce.products p ON p.id = oi.product_id "
                    f"WHERE o.user_id IN ({id_placeholders}) "
                    f"  AND o.status IN ('completed', 'accepted', 'processing') "
                    f"GROUP BY p.name ORDER BY purchase_count DESC LIMIT 5"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    top_products = [
        {"name": r["name"], "purchase_count": r["purchase_count"]} for r in product_rows
    ]

    # Recent email delivery stats (last 90 days)
    email_row = (
        (
            await db.execute(
                text(
                    f"SELECT "
                    f"  COUNT(*) FILTER (WHERE status = 'sent') AS sent, "
                    f"  COUNT(*) FILTER (WHERE status = 'delivered') AS delivered, "
                    f"  COUNT(*) FILTER (WHERE status = 'skipped') AS skipped, "
                    f"  COUNT(*) FILTER ("
                    f"WHERE status IN ('bounced', 'complained')"
                    f") AS bounced "
                    f"FROM gdpr.email_events "
                    f"WHERE user_id IN ({id_placeholders}) "
                    f"  AND created_at >= NOW() - INTERVAL '90 days'"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    recent_email_stats = {
        "sent": email_row["sent"] if email_row else 0,
        "delivered": email_row["delivered"] if email_row else 0,
        "skipped": email_row["skipped"] if email_row else 0,
        "bounced": email_row["bounced"] if email_row else 0,
    }

    return {
        "user_count": user_count,
        "pct_of_total": pct_of_total,
        "avg_order_value": avg_order_value,
        "avg_orders_per_user": avg_orders_per_user,
        "total_revenue": total_revenue,
        "rfm_breakdown": rfm_breakdown,
        "top_products": top_products,
        "recent_email_stats": recent_email_stats,
    }


async def get_send_time_suggestion(
    db: AsyncSession, filters: dict[str, Any]
) -> dict[str, Any]:
    """Suggest optimal send time based on audience page-view activity patterns.

    Looks at which hour-of-day and day-of-week the segment's users are most
    active (based on analytics.page_views created_at).
    """
    user_sql, user_params = _build_segment_query(filters)
    rows = (await db.execute(text(user_sql), user_params)).mappings().all()
    user_ids = [str(r["user_id"]) for r in rows]

    if not user_ids:
        return {
            "suggested_hour": 10,
            "suggested_day": "Tuesday",
            "confidence": "low",
            "note": "No users in segment — using industry default.",
        }

    id_placeholders = ", ".join(f":uid_{i}" for i in range(len(user_ids)))
    uid_params = {f"uid_{i}": uid for i, uid in enumerate(user_ids)}

    # Best hour of day
    hour_rows = (
        (
            await db.execute(
                text(
                    f"SELECT EXTRACT(HOUR FROM pv.created_at)::INT AS hr, "
                    f"COUNT(*) AS cnt "
                    f"FROM analytics.page_views pv "
                    f"WHERE pv.user_id IN ({id_placeholders}) "
                    f"  AND pv.created_at >= NOW() - INTERVAL '90 days' "
                    f"GROUP BY hr ORDER BY cnt DESC LIMIT 1"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    suggested_hour = hour_rows["hr"] if hour_rows else 10

    # Best day of week
    day_rows = (
        (
            await db.execute(
                text(
                    f"SELECT TO_CHAR(pv.created_at, 'Day') AS dow, "
                    f"COUNT(*) AS cnt "
                    f"FROM analytics.page_views pv "
                    f"WHERE pv.user_id IN ({id_placeholders}) "
                    f"  AND pv.created_at >= NOW() - INTERVAL '90 days' "
                    f"GROUP BY dow ORDER BY cnt DESC LIMIT 1"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    suggested_day = day_rows["dow"].strip() if day_rows else "Tuesday"

    # Confidence based on data volume
    total_views = sum(1 for _ in rows) if rows else 0
    confidence = (
        "high" if total_views >= 50 else "medium" if total_views >= 10 else "low"
    )

    return {
        "suggested_hour": suggested_hour,
        "suggested_day": suggested_day,
        "confidence": confidence,
    }


async def get_segment_behavior_insights(
    db: AsyncSession, filters: dict[str, Any]
) -> dict[str, Any]:
    """Device, browser, OS, page-view, and session breakdown for a segment.

    Returns aggregate analytics data for the users matching the given filters.
    """
    user_sql, user_params = _build_segment_query(filters)
    rows = (await db.execute(text(user_sql), user_params)).mappings().all()
    user_ids = [str(r["user_id"]) for r in rows]
    user_count = len(user_ids)

    if user_count == 0:
        return {
            "user_count": 0,
            "device_breakdown": {},
            "browser_breakdown": {},
            "os_breakdown": {},
            "top_pages": [],
            "avg_sessions_per_user": 0.0,
            "avg_page_views_per_user": 0.0,
        }

    id_placeholders = ", ".join(f":uid_{i}" for i in range(user_count))
    uid_params = {f"uid_{i}": uid for i, uid in enumerate(user_ids)}

    # Device type breakdown
    device_rows = (
        (
            await db.execute(
                text(
                    f"SELECT COALESCE(ua.device_type, 'unknown') AS dtype, "
                    f"COUNT(DISTINCT sess.user_id) AS cnt "
                    f"FROM analytics.analytics_sessions sess "
                    f"JOIN analytics.user_agents ua ON ua.session_id = sess.session_id "
                    f"WHERE sess.user_id IN ({id_placeholders}) "
                    f"GROUP BY dtype ORDER BY cnt DESC"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    device_breakdown = {r["dtype"]: r["cnt"] for r in device_rows}

    # Browser breakdown (top 10)
    browser_rows = (
        (
            await db.execute(
                text(
                    f"SELECT COALESCE(ua.browser, 'Unknown') AS bname, "
                    f"COUNT(DISTINCT sess.user_id) AS cnt "
                    f"FROM analytics.analytics_sessions sess "
                    f"JOIN analytics.user_agents ua ON ua.session_id = sess.session_id "
                    f"WHERE sess.user_id IN ({id_placeholders}) "
                    f"GROUP BY bname ORDER BY cnt DESC LIMIT 10"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    browser_breakdown = {r["bname"]: r["cnt"] for r in browser_rows}

    # OS breakdown (top 10)
    os_rows = (
        (
            await db.execute(
                text(
                    f"SELECT COALESCE(ua.os, 'Unknown') AS osname, "
                    f"COUNT(DISTINCT sess.user_id) AS cnt "
                    f"FROM analytics.analytics_sessions sess "
                    f"JOIN analytics.user_agents ua ON ua.session_id = sess.session_id "
                    f"WHERE sess.user_id IN ({id_placeholders}) "
                    f"GROUP BY osname ORDER BY cnt DESC LIMIT 10"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    os_breakdown = {r["osname"]: r["cnt"] for r in os_rows}

    # Top pages viewed (last 90 days)
    page_rows = (
        (
            await db.execute(
                text(
                    f"SELECT pv.path, COUNT(*) AS view_count "
                    f"FROM analytics.page_views pv "
                    f"WHERE pv.user_id IN ({id_placeholders}) "
                    f"  AND pv.created_at >= NOW() - INTERVAL '90 days' "
                    f"GROUP BY pv.path ORDER BY view_count DESC LIMIT 10"
                ),
                uid_params,
            )
        )
        .mappings()
        .all()
    )
    top_pages = [{"path": r["path"], "view_count": r["view_count"]} for r in page_rows]

    # Average sessions per user (last 90 days)
    sess_row = (
        (
            await db.execute(
                text(
                    f"SELECT AVG(sc) AS avg_sess FROM ("
                    f"  SELECT COUNT(*) AS sc "
                    f"  FROM analytics.analytics_sessions s "
                    f"  WHERE s.user_id IN ({id_placeholders}) "
                    f"    AND s.started_at >= NOW() - INTERVAL '90 days' "
                    f"  GROUP BY s.user_id"
                    f") sub"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    avg_sessions = round(float(sess_row["avg_sess"] or 0), 1) if sess_row else 0.0

    # Average page views per user (last 90 days)
    pv_row = (
        (
            await db.execute(
                text(
                    f"SELECT AVG(pc) AS avg_pv FROM ("
                    f"  SELECT COUNT(*) AS pc "
                    f"  FROM analytics.page_views pv "
                    f"  WHERE pv.user_id IN ({id_placeholders}) "
                    f"    AND pv.created_at >= NOW() - INTERVAL '90 days' "
                    f"  GROUP BY pv.user_id"
                    f") sub"
                ),
                uid_params,
            )
        )
        .mappings()
        .first()
    )
    avg_pv = round(float(pv_row["avg_pv"] or 0), 1) if pv_row else 0.0

    return {
        "user_count": user_count,
        "device_breakdown": device_breakdown,
        "browser_breakdown": browser_breakdown,
        "os_breakdown": os_breakdown,
        "top_pages": top_pages,
        "avg_sessions_per_user": avg_sessions,
        "avg_page_views_per_user": avg_pv,
    }


async def get_analytics_filter_options(db: AsyncSession) -> dict[str, Any]:
    """Return distinct device types, browsers, and OS values from analytics.

    Only returns values that actually exist in the system — no hardcoded lists.
    """
    device_rows = (
        (
            await db.execute(
                text(
                    "SELECT DISTINCT ua.device_type AS val "
                    "FROM analytics.user_agents ua "
                    "WHERE ua.device_type IS NOT NULL "
                    "ORDER BY val"
                )
            )
        )
        .mappings()
        .all()
    )

    browser_rows = (
        (
            await db.execute(
                text(
                    "SELECT ua.browser AS val, COUNT(*) AS cnt "
                    "FROM analytics.user_agents ua "
                    "WHERE ua.browser IS NOT NULL "
                    "GROUP BY ua.browser ORDER BY cnt DESC LIMIT 20"
                )
            )
        )
        .mappings()
        .all()
    )

    os_rows = (
        (
            await db.execute(
                text(
                    "SELECT ua.os AS val, COUNT(*) AS cnt "
                    "FROM analytics.user_agents ua "
                    "WHERE ua.os IS NOT NULL "
                    "GROUP BY ua.os ORDER BY cnt DESC LIMIT 20"
                )
            )
        )
        .mappings()
        .all()
    )

    top_pages = (
        (
            await db.execute(
                text(
                    "SELECT pv.path AS val, COUNT(*) AS cnt "
                    "FROM analytics.page_views pv "
                    "WHERE pv.created_at >= NOW() - INTERVAL '90 days' "
                    "GROUP BY pv.path ORDER BY cnt DESC LIMIT 30"
                )
            )
        )
        .mappings()
        .all()
    )

    referral_rows = (
        (
            await db.execute(
                text(
                    "SELECT rs.source AS val, COUNT(*) AS cnt "
                    "FROM analytics.referral_sources rs "
                    "WHERE rs.source IS NOT NULL "
                    "GROUP BY rs.source ORDER BY cnt DESC LIMIT 20"
                )
            )
        )
        .mappings()
        .all()
    )

    event_type_rows = (
        (
            await db.execute(
                text(
                    "SELECT event_type AS val, COUNT(*) AS cnt "
                    "FROM analytics.events "
                    "WHERE created_at >= NOW() - INTERVAL '90 days' "
                    "GROUP BY event_type ORDER BY cnt DESC LIMIT 50"
                )
            )
        )
        .mappings()
        .all()
    )

    return {
        "device_types": [r["val"] for r in device_rows],
        "browsers": [{"value": r["val"], "count": r["cnt"]} for r in browser_rows],
        "operating_systems": [{"value": r["val"], "count": r["cnt"]} for r in os_rows],
        "top_pages": [{"value": r["val"], "count": r["cnt"]} for r in top_pages],
        "referral_sources": [
            {"value": r["val"], "count": r["cnt"]} for r in referral_rows
        ],
        "event_types": [
            {"value": r["val"], "count": r["cnt"]} for r in event_type_rows
        ],
    }


def _empty_segment_insights() -> dict[str, Any]:
    """Return empty insights for a segment with zero users."""
    return {
        "user_count": 0,
        "pct_of_total": 0.0,
        "avg_order_value": 0.0,
        "avg_orders_per_user": 0.0,
        "total_revenue": 0,
        "rfm_breakdown": {},
        "top_products": [],
        "recent_email_stats": {
            "sent": 0,
            "delivered": 0,
            "skipped": 0,
            "bounced": 0,
        },
    }
