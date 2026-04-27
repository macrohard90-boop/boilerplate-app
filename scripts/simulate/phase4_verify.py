"""Phase 4: Verification — run checks against DB, generate report."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class Check:
    category: str
    name: str
    expected: str
    actual: str = ""
    passed: bool = False
    detail: str = ""


def _load_env() -> dict[str, str]:
    env = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _get_db_url() -> str:
    env = _load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    return url.replace("postgresql+asyncpg://", "postgresql://")


def run(
    user_count: int,
    db_url: str | None = None,
) -> list[Check]:
    """Run all verification checks against the database.

    Returns list of Check objects.
    """
    url = db_url or _get_db_url()
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    checks: list[Check] = []

    # ── Auth Checks ──

    # Total users
    cur.execute("SELECT COUNT(*) FROM core.users")
    user_total = cur.fetchone()[0]
    expected_users = user_count + 1  # +1 admin
    checks.append(
        Check(
            category="Auth",
            name="Total users in database",
            expected=f"{expected_users}",
            actual=str(user_total),
            passed=user_total == expected_users,
        )
    )

    # GDPR consent records
    cur.execute(
        "SELECT COUNT(DISTINCT user_id) FROM gdpr.consent_records WHERE granted = true"
    )
    consent_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Auth",
            name="Users with GDPR consent",
            expected=f">= {user_count}",
            actual=str(consent_count),
            passed=consent_count >= user_count,
        )
    )

    # Cookie preferences
    cur.execute("SELECT COUNT(*) FROM gdpr.cookie_preferences WHERE analytics = true")
    cookie_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Auth",
            name="Users with analytics cookie consent",
            expected=f">= {user_count}",
            actual=str(cookie_count),
            passed=cookie_count >= user_count,
        )
    )

    # ── Catalog Checks ──

    cur.execute("SELECT COUNT(*) FROM ecommerce.products WHERE status = 'active'")
    product_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Catalog",
            name="Active products",
            expected=">= 7",
            actual=str(product_count),
            passed=product_count >= 7,
        )
    )

    cur.execute(
        "SELECT COUNT(*) FROM ecommerce.products "
        "WHERE stripe_product_id IS NOT NULL AND status = 'active'"
    )
    synced = cur.fetchone()[0]
    checks.append(
        Check(
            category="Catalog",
            name="Products with Stripe sync",
            expected=str(product_count),
            actual=str(synced),
            passed=synced == product_count,
        )
    )

    cur.execute("SELECT COUNT(*) FROM ecommerce.categories")
    cat_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Catalog",
            name="Categories created",
            expected=">= 4",
            actual=str(cat_count),
            passed=cat_count >= 4,
        )
    )

    # ── Orders & Payments ──

    cur.execute("SELECT COUNT(*) FROM ecommerce.orders")
    order_count = cur.fetchone()[0]
    # Expected: ~35-50% of users create orders
    min_orders = round(user_count * 0.25)
    max_orders = round(user_count * 0.60)
    checks.append(
        Check(
            category="Orders",
            name="Total orders created",
            expected=f"{min_orders}-{max_orders}",
            actual=str(order_count),
            passed=min_orders <= order_count <= max_orders,
        )
    )

    cur.execute("SELECT COUNT(*) FROM ecommerce.orders WHERE status = 'completed'")
    completed_orders = cur.fetchone()[0]
    checks.append(
        Check(
            category="Orders",
            name="Completed orders",
            expected=f">= 1",
            actual=str(completed_orders),
            passed=completed_orders >= 1,
        )
    )

    cur.execute(
        "SELECT COUNT(*) FROM ecommerce.payment_records "
        "WHERE status = 'succeeded' AND provider_payment_id LIKE 'pi_%%'"
    )
    real_payments = cur.fetchone()[0]
    checks.append(
        Check(
            category="Orders",
            name="Real Stripe payments (not test seeds)",
            expected=f">= 1",
            actual=str(real_payments),
            passed=real_payments >= 1,
        )
    )

    # Orders with payment records
    cur.execute(
        "SELECT COUNT(*) FROM ecommerce.orders o "
        "WHERE o.status = 'completed' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM ecommerce.payment_records pr "
        "  WHERE pr.order_id = o.id AND pr.status = 'succeeded'"
        ")"
    )
    orphan_orders = cur.fetchone()[0]
    checks.append(
        Check(
            category="Orders",
            name="Completed orders without payment record",
            expected="0",
            actual=str(orphan_orders),
            passed=orphan_orders == 0,
            detail=(
                "These orders show 'completed' but have no successful payment"
                if orphan_orders
                else ""
            ),
        )
    )

    # ── Analytics Events ──

    cur.execute("SELECT COUNT(*) FROM analytics.events")
    event_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="Total events recorded",
            expected=f">= {user_count * 5}",
            actual=str(event_count),
            passed=event_count >= user_count * 5,
        )
    )

    cur.execute("SELECT COUNT(DISTINCT event_type) FROM analytics.events")
    distinct_types = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="Distinct event types fired",
            expected=">= 30",
            actual=str(distinct_types),
            passed=distinct_types >= 30,
        )
    )

    # login_completed = user_count
    cur.execute(
        "SELECT COUNT(*) FROM analytics.events WHERE event_type = 'login_completed'"
    )
    login_events = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="login_completed events",
            expected=str(user_count),
            actual=str(login_events),
            passed=login_events == user_count,
        )
    )

    # product_viewed count
    cur.execute(
        "SELECT COUNT(*) FROM analytics.events WHERE event_type = 'product_viewed'"
    )
    pv_events = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="product_viewed events",
            expected=f">= {user_count}",
            actual=str(pv_events),
            passed=pv_events >= user_count,
        )
    )

    # add_to_cart
    cur.execute(
        "SELECT COUNT(*) FROM analytics.events WHERE event_type = 'add_to_cart'"
    )
    atc_events = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="add_to_cart events",
            expected=">= 1",
            actual=str(atc_events),
            passed=atc_events >= 1,
        )
    )

    # purchase_completed should roughly match completed orders
    cur.execute(
        "SELECT COUNT(*) FROM analytics.events WHERE event_type = 'purchase_completed'"
    )
    pc_events = cur.fetchone()[0]
    checks.append(
        Check(
            category="Events",
            name="purchase_completed events vs completed orders",
            expected=f"~{completed_orders}",
            actual=str(pc_events),
            passed=abs(pc_events - completed_orders) <= 3,
            detail=(
                f"Events: {pc_events}, Orders: {completed_orders}"
                if abs(pc_events - completed_orders) > 3
                else ""
            ),
        )
    )

    # Event types that never fired
    cur.execute(
        "SELECT ed.name FROM analytics.event_definitions ed "
        "WHERE ed.is_enabled = true "
        "AND ed.name != 'oauth_started' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM analytics.events e WHERE e.event_type = ed.name"
        ") ORDER BY ed.name"
    )
    unfired = [row[0] for row in cur.fetchall()]
    checks.append(
        Check(
            category="Events",
            name="Enabled events that never fired",
            expected="<= 5",
            actual=f"{len(unfired)}: {', '.join(unfired[:10])}",
            passed=len(unfired) <= 5,
            detail=f"Unfired: {', '.join(unfired)}" if unfired else "",
        )
    )

    # ── Admin Events ──

    cur.execute(
        "SELECT event_type, count(*) FROM analytics.events "
        "WHERE event_type LIKE 'admin.%%' GROUP BY event_type ORDER BY event_type"
    )
    admin_events = {row[0]: row[1] for row in cur.fetchall()}
    total_admin_events = sum(admin_events.values())

    checks.append(
        Check(
            category="Admin Events",
            name="Total admin.* events",
            expected=">= 50",
            actual=str(total_admin_events),
            passed=total_admin_events >= 50,
            detail=", ".join(f"{k}={v}" for k, v in admin_events.items()),
        )
    )

    checks.append(
        Check(
            category="Admin Events",
            name="admin.product_created events",
            expected=">= 28",
            actual=str(admin_events.get("admin.product_created", 0)),
            passed=admin_events.get("admin.product_created", 0) >= 28,
        )
    )

    checks.append(
        Check(
            category="Admin Events",
            name="admin.category_created events",
            expected=">= 20",
            actual=str(admin_events.get("admin.category_created", 0)),
            passed=admin_events.get("admin.category_created", 0) >= 20,
        )
    )

    checks.append(
        Check(
            category="Admin Events",
            name="admin.coupon_created events",
            expected=">= 5",
            actual=str(admin_events.get("admin.coupon_created", 0)),
            passed=admin_events.get("admin.coupon_created", 0) >= 5,
        )
    )

    checks.append(
        Check(
            category="Admin Events",
            name="admin.product_deleted events",
            expected=">= 2",
            actual=str(admin_events.get("admin.product_deleted", 0)),
            passed=admin_events.get("admin.product_deleted", 0) >= 2,
        )
    )

    # Admin page views
    cur.execute(
        "SELECT COUNT(*) FROM analytics.page_views pv "
        "JOIN analytics.analytics_sessions s ON s.session_id = pv.session_id "
        "JOIN core.users u ON u.id = s.user_id "
        "JOIN core.roles r ON r.id = u.role_id "
        "WHERE r.name = 'admin'"
    )
    admin_pvs = cur.fetchone()[0]
    checks.append(
        Check(
            category="Admin Events",
            name="Admin page views",
            expected=">= 5",
            actual=str(admin_pvs),
            passed=admin_pvs >= 5,
        )
    )

    # Email templates survived reset
    cur.execute(
        "SELECT COUNT(*) FROM marketing.email_templates WHERE is_builtin = true"
    )
    templates = cur.fetchone()[0]
    checks.append(
        Check(
            category="Admin Events",
            name="Built-in email templates",
            expected="8",
            actual=str(templates),
            passed=templates == 8,
        )
    )

    # ── Sessions & Page Views ──

    cur.execute("SELECT COUNT(*) FROM analytics.analytics_sessions")
    session_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Sessions",
            name="Total analytics sessions",
            expected=f">= {user_count}",
            actual=str(session_count),
            passed=session_count >= user_count,
        )
    )

    cur.execute("SELECT COUNT(*) FROM analytics.page_views")
    pv_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Sessions",
            name="Total page views",
            expected=f">= {user_count * 2}",
            actual=str(pv_count),
            passed=pv_count >= user_count * 2,
        )
    )

    cur.execute(
        "SELECT COUNT(*) FROM analytics.page_views WHERE duration_ms IS NOT NULL"
    )
    pv_with_dur = cur.fetchone()[0]
    checks.append(
        Check(
            category="Sessions",
            name="Page views with duration",
            expected=f">= {pv_count // 2}",
            actual=str(pv_with_dur),
            passed=pv_with_dur >= pv_count // 2,
        )
    )

    cur.execute(
        "SELECT COUNT(*) FROM analytics.analytics_sessions WHERE user_id IS NULL"
    )
    anon_sessions = cur.fetchone()[0]
    checks.append(
        Check(
            category="Sessions",
            name="Anonymous sessions (user_id is NULL)",
            expected="0",
            actual=str(anon_sessions),
            passed=anon_sessions == 0,
        )
    )

    # ── Browser/Device Stats ──

    cur.execute("SELECT COUNT(*) FROM analytics.user_agents")
    ua_count = cur.fetchone()[0]
    checks.append(
        Check(
            category="Browser",
            name="User agent records",
            expected=f">= {session_count}",
            actual=str(ua_count),
            passed=ua_count >= max(1, session_count),
        )
    )

    cur.execute(
        "SELECT COUNT(*) FROM analytics.user_agents "
        "WHERE browser IN ('Chrome', 'Safari', 'Firefox', 'Edge', 'Opera')"
    )
    real_browsers = cur.fetchone()[0]
    checks.append(
        Check(
            category="Browser",
            name="Records with real browser names",
            expected=str(ua_count),
            actual=str(real_browsers),
            passed=real_browsers == ua_count if ua_count > 0 else True,
        )
    )

    cur.execute(
        "SELECT device_type, COUNT(*) FROM analytics.user_agents "
        "GROUP BY device_type ORDER BY COUNT(*) DESC"
    )
    device_dist = {row[0]: row[1] for row in cur.fetchall()}
    has_mobile = device_dist.get("mobile", 0) > 0
    has_desktop = device_dist.get("desktop", 0) > 0
    checks.append(
        Check(
            category="Browser",
            name="Device type distribution",
            expected="desktop + mobile",
            actual=", ".join(f"{k}: {v}" for k, v in device_dist.items()),
            passed=has_mobile and has_desktop,
        )
    )

    # ── Stripe ──

    cur.execute(
        "SELECT COUNT(*) FROM ecommerce.payment_records "
        "WHERE provider_payment_id LIKE 'pi_%%' AND status = 'failed'"
    )
    declined = cur.fetchone()[0]
    checks.append(
        Check(
            category="Stripe",
            name="Intentional payment declines recorded",
            expected=">= 1",
            actual=str(declined),
            passed=declined >= 1,
        )
    )

    cur.close()
    conn.close()

    return checks
