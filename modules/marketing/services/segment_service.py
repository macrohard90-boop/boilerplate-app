"""Audience segment management — CRUD, filter-to-SQL engine, count refresh."""

import json
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filter-to-SQL engine
# ---------------------------------------------------------------------------


def _build_segment_query(
    filters: dict[str, Any],
    *,
    count_only: bool = False,
    limit: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Translate a segment filters dict into a SQL query + params.

    Always applies base eligibility:
      - marketing email consent (gdpr.email_preferences.marketing_email = true)
      - not suppressed (suppressed_at IS NULL)
      - account active + not soft-deleted

    Returns (sql_string, params_dict).
    """
    select = "COUNT(*) AS cnt" if count_only else "u.id AS user_id, u.email"
    joins: list[str] = [
        "JOIN gdpr.email_preferences ep ON ep.user_id = u.id",
    ]
    wheres: list[str] = [
        "ep.marketing_email = TRUE",
        "ep.suppressed_at IS NULL",
        "u.is_active = TRUE",
        "u.deleted_at IS NULL",
        "u.is_verified = TRUE",
    ]
    params: dict[str, Any] = {}

    # --- Ecommerce customer metrics filters ---
    needs_cm = any(
        k in filters
        for k in (
            "rfm_segment",
            "order_count_min",
            "order_count_max",
            "total_spent_min",
            "total_spent_max",
            "last_purchase_days_max",
            "has_orders",
        )
    )
    if needs_cm:
        joins.append("LEFT JOIN ecommerce.customer_metrics cm ON cm.user_id = u.id")

    if "rfm_segment" in filters and filters["rfm_segment"]:
        segments = filters["rfm_segment"]
        if isinstance(segments, str):
            segments = [segments]
        placeholders = ", ".join(f":rfm_{i}" for i in range(len(segments)))
        wheres.append(f"cm.rfm_segment IN ({placeholders})")
        for i, seg in enumerate(segments):
            params[f"rfm_{i}"] = seg

    if "order_count_min" in filters and filters["order_count_min"] is not None:
        wheres.append("COALESCE(cm.order_count, 0) >= :oc_min")
        params["oc_min"] = int(filters["order_count_min"])

    if "order_count_max" in filters and filters["order_count_max"] is not None:
        wheres.append("COALESCE(cm.order_count, 0) <= :oc_max")
        params["oc_max"] = int(filters["order_count_max"])

    if "total_spent_min" in filters and filters["total_spent_min"] is not None:
        wheres.append("COALESCE(cm.total_spent, 0) >= :ts_min")
        params["ts_min"] = int(filters["total_spent_min"])

    if "total_spent_max" in filters and filters["total_spent_max"] is not None:
        wheres.append("COALESCE(cm.total_spent, 0) <= :ts_max")
        params["ts_max"] = int(filters["total_spent_max"])

    if (
        "last_purchase_days_max" in filters
        and filters["last_purchase_days_max"] is not None
    ):
        wheres.append("cm.last_purchase_at >= NOW() - INTERVAL '1 day' * :lp_days")
        params["lp_days"] = int(filters["last_purchase_days_max"])

    if filters.get("has_orders"):
        wheres.append("COALESCE(cm.order_count, 0) > 0")

    # --- Signup age filters ---
    if "signup_days_min" in filters and filters["signup_days_min"] is not None:
        wheres.append("u.created_at <= NOW() - INTERVAL '1 day' * :su_min")
        params["su_min"] = int(filters["signup_days_min"])

    if "signup_days_max" in filters and filters["signup_days_max"] is not None:
        wheres.append("u.created_at >= NOW() - INTERVAL '1 day' * :su_max")
        params["su_max"] = int(filters["signup_days_max"])

    # --- Cart status filter ---
    if "cart_status" in filters and filters["cart_status"]:
        joins.append("JOIN ecommerce.cart cart ON cart.user_id = u.id")
        wheres.append("cart.status = :cart_st")
        params["cart_st"] = filters["cart_status"]

    # --- Wishlist filter ---
    if filters.get("has_wishlist"):
        joins.append("JOIN ecommerce.wishlists wl ON wl.user_id = u.id")

    # --- Communication type filter ---
    if "communication_type" in filters and filters["communication_type"]:
        joins.append(
            "JOIN marketing.communication_types ct "
            "ON ct.name = :ct_name AND ct.enabled = TRUE"
        )
        joins.append(
            "JOIN marketing.user_communication_preferences ucp "
            "ON ucp.user_id = u.id AND ucp.communication_type_id = ct.id "
            "AND ucp.allowed = TRUE"
        )
        params["ct_name"] = filters["communication_type"]

    # --- Email verification filter (overrides the default is_verified=TRUE) ---
    if "is_verified" in filters and filters["is_verified"] is not None:
        if not filters["is_verified"]:
            # Remove the default verified filter to include unverified users
            wheres = [w for w in wheres if w != "u.is_verified = TRUE"]
        # If is_verified=True, the default already handles it

    # --- User role filter ---
    if "user_role" in filters and filters["user_role"]:
        roles = filters["user_role"]
        if isinstance(roles, str):
            roles = [roles]
        role_placeholders = ", ".join(f":role_{i}" for i in range(len(roles)))
        joins.append("JOIN core.roles _r ON _r.id = u.role_id")
        wheres.append(f"_r.name IN ({role_placeholders})")
        for i, role in enumerate(roles):
            params[f"role_{i}"] = role

    # --- Device type filter (mobile/desktop/tablet) ---
    if "device_type" in filters and filters["device_type"]:
        device_types = filters["device_type"]
        if isinstance(device_types, str):
            device_types = [device_types]
        dt_placeholders = ", ".join(f":dt_{i}" for i in range(len(device_types)))
        wheres.append(
            f"EXISTS (SELECT 1 FROM analytics.analytics_sessions _ds "
            f"JOIN analytics.user_agents _ua ON _ua.session_id = _ds.session_id "
            f"WHERE _ds.user_id = u.id AND _ua.device_type IN ({dt_placeholders}))"
        )
        for i, dt in enumerate(device_types):
            params[f"dt_{i}"] = dt

    # --- Browser filter ---
    if "browser" in filters and filters["browser"]:
        browsers = filters["browser"]
        if isinstance(browsers, str):
            browsers = [browsers]
        br_placeholders = ", ".join(f":br_{i}" for i in range(len(browsers)))
        wheres.append(
            f"EXISTS (SELECT 1 FROM analytics.analytics_sessions _bs "
            f"JOIN analytics.user_agents _bua ON _bua.session_id = _bs.session_id "
            f"WHERE _bs.user_id = u.id AND _bua.browser IN ({br_placeholders}))"
        )
        for i, br in enumerate(browsers):
            params[f"br_{i}"] = br

    # --- OS filter ---
    if "os" in filters and filters["os"]:
        os_list = filters["os"]
        if isinstance(os_list, str):
            os_list = [os_list]
        os_placeholders = ", ".join(f":os_{i}" for i in range(len(os_list)))
        wheres.append(
            f"EXISTS (SELECT 1 FROM analytics.analytics_sessions _os "
            f"JOIN analytics.user_agents _oua ON _oua.session_id = _os.session_id "
            f"WHERE _os.user_id = u.id AND _oua.os IN ({os_placeholders}))"
        )
        for i, os_val in enumerate(os_list):
            params[f"os_{i}"] = os_val

    # --- Viewed pages filter (users who visited specific paths) ---
    if "viewed_pages" in filters and filters["viewed_pages"]:
        pages = filters["viewed_pages"]
        if isinstance(pages, str):
            pages = [pages]
        vp_placeholders = ", ".join(f":vp_{i}" for i in range(len(pages)))
        wheres.append(
            f"EXISTS (SELECT 1 FROM analytics.page_views _vp "
            f"WHERE _vp.user_id = u.id AND _vp.path IN ({vp_placeholders}))"
        )
        for i, pg in enumerate(pages):
            params[f"vp_{i}"] = pg

    # --- Min page views (last 90 days) ---
    if "min_page_views" in filters and filters["min_page_views"] is not None:
        wheres.append(
            "EXISTS (SELECT 1 FROM analytics.page_views _mpv "
            "WHERE _mpv.user_id = u.id "
            "AND _mpv.created_at >= NOW() - INTERVAL '90 days' "
            "GROUP BY _mpv.user_id HAVING COUNT(*) >= :min_pv)"
        )
        params["min_pv"] = int(filters["min_page_views"])

    # --- Min sessions (last 90 days) ---
    if "min_sessions" in filters and filters["min_sessions"] is not None:
        wheres.append(
            "EXISTS (SELECT 1 FROM analytics.analytics_sessions _ms "
            "WHERE _ms.user_id = u.id "
            "AND _ms.started_at >= NOW() - INTERVAL '90 days' "
            "GROUP BY _ms.user_id HAVING COUNT(*) >= :min_sess)"
        )
        params["min_sess"] = int(filters["min_sessions"])

    # --- Engagement score filters ---
    needs_es = any(
        k in filters
        for k in ("score_above", "score_below", "velocity_min", "velocity_max")
    )
    if needs_es:
        joins.append("LEFT JOIN analytics.engagement_scores es ON es.user_id = u.id")

    if "score_above" in filters and filters["score_above"] is not None:
        wheres.append("COALESCE(es.score, 0) >= :score_above")
        params["score_above"] = float(filters["score_above"])

    if "score_below" in filters and filters["score_below"] is not None:
        wheres.append("COALESCE(es.score, 0) <= :score_below")
        params["score_below"] = float(filters["score_below"])

    if "velocity_min" in filters and filters["velocity_min"] is not None:
        wheres.append("COALESCE(es.velocity, 0) >= :vel_min")
        params["vel_min"] = float(filters["velocity_min"])

    if "velocity_max" in filters and filters["velocity_max"] is not None:
        wheres.append("COALESCE(es.velocity, 0) <= :vel_max")
        params["vel_max"] = float(filters["velocity_max"])

    # --- Referral source filter ---
    if "referral_source" in filters and filters["referral_source"]:
        wheres.append(
            "EXISTS (SELECT 1 FROM analytics.analytics_sessions _rs "
            "JOIN analytics.referral_sources _ref "
            "ON _ref.session_id = _rs.session_id "
            "WHERE _rs.user_id = u.id AND _ref.source = :ref_src)"
        )
        params["ref_src"] = filters["referral_source"]

    # --- Event-based filters (event_type, event_min_count, event_days_lookback) ---
    if "event_type" in filters and filters["event_type"]:
        event_types = filters["event_type"]
        if isinstance(event_types, str):
            event_types = [event_types]
        ev_placeholders = ", ".join(f":ev_{i}" for i in range(len(event_types)))
        for i, et in enumerate(event_types):
            params[f"ev_{i}"] = et

        ev_where = f"_ev.user_id = u.id AND _ev.event_type IN ({ev_placeholders})"
        if (
            "event_days_lookback" in filters
            and filters["event_days_lookback"] is not None
        ):
            ev_where += " AND _ev.created_at >= NOW() - INTERVAL '1 day' * :ev_days"
            params["ev_days"] = int(filters["event_days_lookback"])

        if "event_min_count" in filters and filters["event_min_count"] is not None:
            wheres.append(
                f"EXISTS (SELECT 1 FROM analytics.events _ev "
                f"WHERE {ev_where} "
                f"GROUP BY _ev.user_id "
                f"HAVING COUNT(*) >= :ev_min)"
            )
            params["ev_min"] = int(filters["event_min_count"])
        else:
            wheres.append(
                f"EXISTS (SELECT 1 FROM analytics.events _ev WHERE {ev_where})"
            )

    # --- NOT-event filter (exclude users who have specific event types) ---
    if "not_event_type" in filters and filters["not_event_type"]:
        not_event_types = filters["not_event_type"]
        if isinstance(not_event_types, str):
            not_event_types = [not_event_types]
        nev_placeholders = ", ".join(f":nev_{i}" for i in range(len(not_event_types)))
        for i, net in enumerate(not_event_types):
            params[f"nev_{i}"] = net

        nev_where = f"_nev.user_id = u.id AND _nev.event_type IN ({nev_placeholders})"
        if (
            "not_event_days_lookback" in filters
            and filters["not_event_days_lookback"] is not None
        ):
            nev_where += " AND _nev.created_at >= NOW() - INTERVAL '1 day' * :nev_days"
            params["nev_days"] = int(filters["not_event_days_lookback"])

        wheres.append(
            f"NOT EXISTS (SELECT 1 FROM analytics.events _nev WHERE {nev_where})"
        )

    # --- Subscription status filter ---
    if "subscription_status" in filters and filters["subscription_status"]:
        statuses = filters["subscription_status"]
        if isinstance(statuses, str):
            statuses = [statuses]
        sub_placeholders = ", ".join(f":sub_st_{i}" for i in range(len(statuses)))
        wheres.append(
            f"EXISTS (SELECT 1 FROM ecommerce.subscriptions _sub "
            f"WHERE _sub.user_id = u.id AND _sub.status IN ({sub_placeholders}))"
        )
        for i, st in enumerate(statuses):
            params[f"sub_st_{i}"] = st

    # --- No subscription filter ---
    if filters.get("no_subscription"):
        wheres.append(
            "NOT EXISTS (SELECT 1 FROM ecommerce.subscriptions _nosub "
            "WHERE _nosub.user_id = u.id)"
        )

    # --- Subscription cancelled within N days ---
    if (
        "subscription_cancelled_days" in filters
        and filters["subscription_cancelled_days"] is not None
    ):
        wheres.append(
            "EXISTS (SELECT 1 FROM ecommerce.subscriptions _csub "
            "WHERE _csub.user_id = u.id AND _csub.status = 'canceled' "
            "AND _csub.updated_at >= NOW() - INTERVAL '1 day' * :csub_days)"
        )
        params["csub_days"] = int(filters["subscription_cancelled_days"])

    # --- Cart abandoned within N days ---
    if "cart_abandoned_days" in filters and filters["cart_abandoned_days"] is not None:
        wheres.append(
            "EXISTS (SELECT 1 FROM ecommerce.cart _ac "
            "WHERE _ac.user_id = u.id AND _ac.status = 'abandoned' "
            "AND _ac.updated_at >= NOW() - INTERVAL '1 day' * :cart_aband_days)"
        )
        params["cart_aband_days"] = int(filters["cart_abandoned_days"])

    # --- Min abandoned cart value (cents) ---
    if "min_cart_value" in filters and filters["min_cart_value"] is not None:
        wheres.append(
            "EXISTS (SELECT 1 FROM ecommerce.cart _hvc "
            "JOIN ecommerce.cart_items _hvci ON _hvci.cart_id = _hvc.id "
            "WHERE _hvc.user_id = u.id AND _hvc.status = 'abandoned' "
            "GROUP BY _hvc.id "
            "HAVING SUM(_hvci.unit_price_at_add * _hvci.quantity) >= :min_cart_val)"
        )
        params["min_cart_val"] = int(filters["min_cart_value"])

    # --- Inactive for N days (no page views) ---
    if "inactive_days" in filters and filters["inactive_days"] is not None:
        wheres.append(
            "NOT EXISTS (SELECT 1 FROM analytics.page_views _ipv "
            "WHERE _ipv.user_id = u.id "
            "AND _ipv.created_at >= NOW() - INTERVAL '1 day' * :inactive_days)"
        )
        params["inactive_days"] = int(filters["inactive_days"])

    # --- Active within N days (has page views) ---
    if "active_days" in filters and filters["active_days"] is not None:
        wheres.append(
            "EXISTS (SELECT 1 FROM analytics.page_views _apv "
            "WHERE _apv.user_id = u.id "
            "AND _apv.created_at >= NOW() - INTERVAL '1 day' * :active_days)"
        )
        params["active_days"] = int(filters["active_days"])

    # --- Purchased specific product ---
    if "purchased_product_id" in filters and filters["purchased_product_id"]:
        pp_where = (
            "_pp.user_id = u.id "
            "AND _pp.status IN ('completed','processing','accepted') "
            "AND _ppi.product_id = :pp_product_id"
        )
        params["pp_product_id"] = filters["purchased_product_id"]
        if (
            "purchase_days_lookback" in filters
            and filters["purchase_days_lookback"] is not None
        ):
            pp_where += (
                " AND _pp.created_at >= NOW() - INTERVAL '1 day' * :purchase_lookback"
            )
            params["purchase_lookback"] = int(filters["purchase_days_lookback"])
        wheres.append(
            f"EXISTS (SELECT 1 FROM ecommerce.orders _pp "
            f"JOIN ecommerce.order_items _ppi ON _ppi.order_id = _pp.id "
            f"WHERE {pp_where})"
        )

    # --- Purchased from specific category ---
    if "purchased_category_id" in filters and filters["purchased_category_id"]:
        pc_where = (
            "_pc.user_id = u.id "
            "AND _pc.status IN ('completed','processing','accepted') "
            "AND _pccat.category_id = :pc_category_id"
        )
        params["pc_category_id"] = filters["purchased_category_id"]
        if (
            "purchase_days_lookback" in filters
            and filters["purchase_days_lookback"] is not None
            and "purchase_lookback" not in params
        ):
            pc_where += (
                " AND _pc.created_at >= NOW() - INTERVAL '1 day' * :purchase_lookback"
            )
            params["purchase_lookback"] = int(filters["purchase_days_lookback"])
        wheres.append(
            f"EXISTS (SELECT 1 FROM ecommerce.orders _pc "
            f"JOIN ecommerce.order_items _pci ON _pci.order_id = _pc.id "
            f"JOIN ecommerce.product_categories _pccat ON _pccat.product_id = _pci.product_id "
            f"WHERE {pc_where})"
        )

    # --- NOT purchased specific product ---
    if "not_purchased_product_id" in filters and filters["not_purchased_product_id"]:
        wheres.append(
            "NOT EXISTS (SELECT 1 FROM ecommerce.orders _np "
            "JOIN ecommerce.order_items _npi ON _npi.order_id = _np.id "
            "WHERE _np.user_id = u.id "
            "AND _np.status IN ('completed','processing','accepted') "
            "AND _npi.product_id = :np_product_id)"
        )
        params["np_product_id"] = filters["not_purchased_product_id"]

    # --- Used specific coupon code ---
    if "used_coupon_code" in filters and filters["used_coupon_code"]:
        wheres.append(
            "EXISTS (SELECT 1 FROM ecommerce.orders _co "
            "JOIN ecommerce.discount_codes _dc ON _dc.id = _co.discount_code_id "
            "WHERE _co.user_id = u.id "
            "AND _co.status IN ('completed','processing','accepted') "
            "AND _dc.code = :coupon_code)"
        )
        params["coupon_code"] = filters["used_coupon_code"]

    # --- Has any coupon order ---
    if filters.get("has_coupon"):
        wheres.append(
            "EXISTS (SELECT 1 FROM ecommerce.orders _hco "
            "WHERE _hco.user_id = u.id "
            "AND _hco.status IN ('completed','processing','accepted') "
            "AND _hco.discount_code_id IS NOT NULL)"
        )

    # --- Viewed product but not purchased ---
    if (
        "viewed_product_not_purchased" in filters
        and filters["viewed_product_not_purchased"]
    ):
        vpnp_id = filters["viewed_product_not_purchased"]
        wheres.append(
            "EXISTS (SELECT 1 FROM analytics.events _vpnp "
            "WHERE _vpnp.user_id = u.id AND _vpnp.event_type = 'product_viewed' "
            "AND _vpnp.event_data->>'product_id' = :vpnp_product_id)"
        )
        wheres.append(
            "NOT EXISTS (SELECT 1 FROM ecommerce.orders _vpno "
            "JOIN ecommerce.order_items _vpnoi ON _vpnoi.order_id = _vpno.id "
            "WHERE _vpno.user_id = u.id "
            "AND _vpno.status IN ('completed','processing','accepted') "
            "AND _vpnoi.product_id = :vpnp_product_uuid)"
        )
        params["vpnp_product_id"] = str(vpnp_id)
        params["vpnp_product_uuid"] = vpnp_id

    join_clause = "\n".join(joins)
    where_clause = " AND ".join(wheres)
    limit_clause = f" LIMIT {int(limit)}" if limit else ""

    sql = (
        f"SELECT {select} FROM core.users u\n"
        f"{join_clause}\n"
        f"WHERE {where_clause}"
        f"{limit_clause}"
    )
    return sql, params


# ---------------------------------------------------------------------------
# Segment user queries
# ---------------------------------------------------------------------------


async def compute_segment_users(
    db: AsyncSession,
    filters: dict[str, Any],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return matching users for the given filter criteria."""
    sql, params = _build_segment_query(filters, limit=limit)
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [{"user_id": str(r["user_id"]), "email": r["email"]} for r in rows]


async def compute_segment_count(db: AsyncSession, filters: dict[str, Any]) -> int:
    """Fast COUNT(*) for the given filter criteria."""
    sql, params = _build_segment_query(filters, count_only=True)
    row = (await db.execute(text(sql), params)).mappings().first()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Metric-backed segment helpers
# ---------------------------------------------------------------------------


async def _get_metric_sql(db: AsyncSession, metric_id: str) -> str:
    """Fetch and validate the SQL query for an audience metric."""
    from modules.tracking.services.sql_safety_service import validate_query

    row = (
        await db.execute(
            text(
                "SELECT sql_query FROM analytics.saved_metrics "
                "WHERE id = :mid AND is_audience = TRUE"
            ),
            {"mid": metric_id},
        )
    ).fetchone()
    if not row:
        raise ValueError(f"Audience metric {metric_id} not found")
    return validate_query(row.sql_query)


async def compute_metric_segment_count(db: AsyncSession, metric_id: str) -> int:
    """Execute a metric's SQL query and count the resulting user_ids."""
    safe_sql = await _get_metric_sql(db, metric_id)
    # Strip the auto-appended LIMIT so COUNT reflects the full audience
    unlimit_sql = re.sub(r"\s+LIMIT\s+\d+\s*$", "", safe_sql, flags=re.IGNORECASE)
    count_sql = f"SELECT COUNT(*) AS cnt FROM ({unlimit_sql}) AS aq"
    await db.execute(text("SET LOCAL statement_timeout = '10s'"))
    result = (await db.execute(text(count_sql))).fetchone()
    return result.cnt if result else 0


async def compute_metric_segment_users(
    db: AsyncSession, metric_id: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Execute a metric's SQL query and return the user_id list."""
    safe_sql = await _get_metric_sql(db, metric_id)
    unlimit_sql = re.sub(r"\s+LIMIT\s+\d+\s*$", "", safe_sql, flags=re.IGNORECASE)
    user_sql = f"SELECT DISTINCT user_id FROM ({unlimit_sql}) AS aq"
    if limit:
        user_sql += f" LIMIT {int(limit)}"
    await db.execute(text("SET LOCAL statement_timeout = '10s'"))
    rows = (await db.execute(text(user_sql))).mappings().all()
    return [{"user_id": str(r["user_id"]), "email": ""} for r in rows]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_segments(
    db: AsyncSession, include_system: bool = True
) -> list[dict[str, Any]]:
    """List audience segments."""
    where = "" if include_system else "WHERE is_system = FALSE"
    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, name, description, filters, is_system, "
                    f"user_count, last_computed_at, created_at, metric_id "
                    f"FROM marketing.audience_segments {where} "
                    f"ORDER BY is_system DESC, name"
                )
            )
        )
        .mappings()
        .all()
    )
    return [_row_to_dict(r) for r in rows]


async def get_segment(db: AsyncSession, segment_id: str) -> dict[str, Any]:
    """Get a single segment by ID."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, name, description, filters, is_system, "
                    "user_count, last_computed_at, created_at, metric_id "
                    "FROM marketing.audience_segments WHERE id = :sid"
                ),
                {"sid": segment_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Segment not found")
    return _row_to_dict(row)


async def create_segment(
    db: AsyncSession,
    name: str,
    description: str | None,
    filters: dict[str, Any],
    created_by: str,
    metric_id: str | None = None,
) -> dict[str, Any]:
    """Create a custom audience segment, optionally backed by a metric SQL query.

    When no metric_id is provided and filters are non-empty, a linked
    analytics.saved_metrics row is auto-created so the audience appears
    in the Custom Metrics page and can be reused across campaigns.
    """
    if metric_id:
        user_count = await compute_metric_segment_count(db, metric_id)
    else:
        user_count = await compute_segment_count(db, filters)

    # Auto-create a saved metric when this is a filter-based audience
    # without an existing metric link — keeps both systems in sync.
    if not metric_id and filters:
        try:
            from modules.tracking.services.audience_seed_service import (
                _filters_to_sql,
            )

            sql_query = _filters_to_sql(filters)
            metric_row = (
                await db.execute(
                    text(
                        "INSERT INTO analytics.saved_metrics "
                        "(name, description, sql_query, visualization_type, "
                        "created_by, is_audience, audience_filters) "
                        "VALUES (:name, :desc, :sql, 'table', :uid, TRUE, :af) "
                        "RETURNING id"
                    ),
                    {
                        "name": name,
                        "desc": description or "",
                        "sql": sql_query,
                        "uid": created_by,
                        "af": json.dumps(filters),
                    },
                )
            ).fetchone()
            metric_id = str(metric_row.id)
            logger.info(
                "Auto-created saved_metric %s for segment '%s'",
                metric_id,
                name,
            )
        except Exception as e:
            logger.warning(
                "Failed to auto-create saved_metric for segment '%s': %s",
                name,
                e,
            )

    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.audience_segments "
                    "(name, description, filters, is_system, user_count, "
                    "last_computed_at, created_by, metric_id) "
                    "VALUES (:name, :desc, :filters, FALSE, :cnt, NOW(), :uid, :mid) "
                    "RETURNING id, name, description, filters, is_system, "
                    "user_count, last_computed_at, created_at, metric_id"
                ),
                {
                    "name": name,
                    "desc": description,
                    "filters": json.dumps(filters),
                    "cnt": user_count,
                    "uid": created_by,
                    "mid": metric_id,
                },
            )
        )
        .mappings()
        .first()
    )
    await db.commit()
    logger.info("Segment created: %s (%s) — %d users", row["id"], name, user_count)
    return _row_to_dict(row)


async def update_segment(
    db: AsyncSession,
    segment_id: str,
    name: str | None = None,
    description: str | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update a custom audience segment. Cannot update system segments."""
    existing = await get_segment(db, segment_id)
    if existing["is_system"]:
        raise ValueError("Cannot update system segments")

    sets: list[str] = []
    params: dict[str, Any] = {"sid": segment_id}

    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = description
    if filters is not None:
        sets.append("filters = :filters")
        params["filters"] = json.dumps(filters)
        user_count = await compute_segment_count(db, filters)
        sets.append("user_count = :cnt")
        sets.append("last_computed_at = NOW()")
        params["cnt"] = user_count

    if not sets:
        raise ValueError("No fields to update")

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE marketing.audience_segments SET {', '.join(sets)} "
                    f"WHERE id = :sid "
                    f"RETURNING id, name, description, filters, is_system, "
                    f"user_count, last_computed_at, created_at, metric_id"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("Segment not found")

    await db.commit()
    return _row_to_dict(row)


async def delete_segment(db: AsyncSession, segment_id: str) -> None:
    """Delete a custom segment. System segments cannot be deleted."""
    existing = await get_segment(db, segment_id)
    if existing["is_system"]:
        raise ValueError("Cannot delete system segments")

    await db.execute(
        text("DELETE FROM marketing.audience_segments WHERE id = :sid"),
        {"sid": segment_id},
    )
    await db.commit()
    logger.info("Segment deleted: %s", segment_id)


async def refresh_segment_counts(db: AsyncSession) -> int:
    """Recompute user_count for all segments. Returns number updated."""
    segments = await list_segments(db)
    updated = 0
    for seg in segments:
        try:
            if seg.get("metric_id"):
                count = await compute_metric_segment_count(db, seg["metric_id"])
            else:
                filters = seg["filters"] if isinstance(seg["filters"], dict) else {}
                count = await compute_segment_count(db, filters)
        except Exception as e:
            logger.warning("Failed to refresh segment %s: %s", seg["id"], e)
            continue
        await db.execute(
            text(
                "UPDATE marketing.audience_segments "
                "SET user_count = :cnt, last_computed_at = NOW() "
                "WHERE id = :sid"
            ),
            {"cnt": count, "sid": seg["id"]},
        )
        updated += 1
    await db.commit()
    return updated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def resolve_segment_user_ids(db: AsyncSession, segment_id: str) -> list[str]:
    """Resolve a segment ID to a list of user IDs.

    Loads the segment's filters and runs the query to find matching users.
    For metric-backed segments, uses the metric's SQL query instead.
    """
    segment = await get_segment(db, segment_id)

    # Check if metric-backed
    metric_id = segment.get("metric_id")
    if metric_id:
        users = await compute_metric_segment_users(db, metric_id)
    else:
        users = await compute_segment_users(db, segment["filters"])

    return [u["user_id"] for u in users]


def _row_to_dict(r: Any) -> dict[str, Any]:
    """Convert a DB row mapping to a segment dict."""
    filters = r["filters"]
    if isinstance(filters, str):
        filters = json.loads(filters)
    result = {
        "id": str(r["id"]),
        "name": r["name"],
        "description": r["description"],
        "filters": filters or {},
        "is_system": r["is_system"],
        "user_count": r["user_count"] or 0,
        "last_computed_at": (
            str(r["last_computed_at"]) if r["last_computed_at"] else None
        ),
        "created_at": str(r["created_at"]),
    }
    if "metric_id" in r.keys():
        result["metric_id"] = str(r["metric_id"]) if r["metric_id"] else None
    return result
