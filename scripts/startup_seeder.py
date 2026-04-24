"""
Startup test-data seeder — runs on app boot when SEED_TEST_DATA=true.

Idempotent: uses ON CONFLICT / INSERT ... WHERE NOT EXISTS so repeated
restarts don't duplicate data.  Combines the logic from:
  - activate_test_users.sql   (verify + opt-in all active users)
  - compute_rfm.py            (RFM segment scoring)
  - seed_analytics.py         (page views, sessions, events)
"""

import json
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Analytics seed constants ────────────────────────────────────────────────

PAGES = [
    "/", "/products", "/products/wireless-headphones", "/products/usb-c-hub",
    "/products/classic-t-shirt", "/products/running-shoes", "/products/smart-watch",
    "/about", "/contact", "/cart", "/checkout", "/dashboard", "/auth/login",
    "/categories/electronics", "/categories/clothing",
]

BROWSERS = ["Chrome", "Safari", "Edge", "Firefox"]
BROWSER_VERSIONS = {
    "Chrome": ["120.0", "121.0", "122.0"],
    "Safari": ["17.2", "17.3", "17.4"],
    "Edge": ["120.0", "121.0"],
    "Firefox": ["121.0", "122.0"],
}
DEVICES = ["desktop", "mobile", "tablet"]
DEVICE_WEIGHTS = [60, 30, 10]
OS_MAP = {
    "desktop": ["Windows 10", "Windows 11", "macOS 14", "Linux"],
    "mobile": ["iOS 17", "Android 14", "Android 13"],
    "tablet": ["iPadOS 17", "Android 14"],
}
REFERRAL_SOURCES = [
    ("google", "organic"), ("direct", "none"), ("facebook", "social"),
    ("instagram", "social"), ("email", "email"), ("twitter", "social"),
]
EVENT_TYPES = [
    "product_viewed", "add_to_cart", "remove_from_cart",
    "checkout_started", "checkout_abandoned", "search_performed",
    "wishlist_added", "coupon_applied",
]
EVENT_WEIGHTS = [40, 20, 5, 10, 5, 10, 5, 5]

# ── RFM constants ───────────────────────────────────────────────────────────

RECENCY_THRESHOLDS = [7, 30, 90, 180]
FREQUENCY_THRESHOLDS = [1, 3, 5, 10]
MONETARY_THRESHOLDS = [2000, 5000, 15000, 50000]

SEGMENT_RULES: list[tuple] = [
    (lambda r, f, m: r >= 4 and f >= 4 and m >= 4, "champion"),
    (lambda r, f, m: f >= 3 and m >= 3 and r >= 3, "loyal"),
    (lambda r, f, m: r >= 4 and f >= 2, "potential_loyalist"),
    (lambda r, f, m: r >= 4 and f <= 2, "new"),
    (lambda r, f, m: r <= 2 and f >= 3, "at_risk"),
    (lambda r, f, m: r <= 2 and f >= 1, "hibernating"),
    (lambda r, f, m: r <= 1, "lost"),
]


def _score(value: int, thresholds: list[int], ascending: bool = True) -> int:
    """Score 1-5 against thresholds. ascending=True means lower value → higher score (recency)."""
    if ascending:
        for i, t in enumerate(thresholds):
            if value <= t:
                return 5 - i
    else:
        for i, t in enumerate(reversed(thresholds)):
            if value >= t:
                return 5 - i
    return 1


def _assign_segment(r: int, f: int, m: int) -> str:
    for fn, label in SEGMENT_RULES:
        if fn(r, f, m):
            return label
    return "lost"


def _random_ts(days_back: int = 30) -> datetime:
    offset = random.uniform(0, days_back * 24 * 3600)
    return datetime.now(timezone.utc) - timedelta(seconds=offset)


# ── Main entry point ────────────────────────────────────────────────────────

async def run_startup_seed(db: AsyncSession) -> None:
    """Run all seed steps. Idempotent — safe on every restart."""

    # Check if seeding was already done (marker row)
    result = await db.execute(
        text(
            "SELECT 1 FROM analytics.analytics_sessions LIMIT 1"
        )
    )
    if result.scalar() is not None:
        logger.info("Seed data already present — skipping startup seeder")
        return

    logger.info("SEED_TEST_DATA=true — running startup seeder...")

    await _activate_users(db)
    await _compute_rfm(db)
    await _seed_analytics(db)
    await db.commit()

    logger.info("Startup seeder complete")


async def _activate_users(db: AsyncSession) -> None:
    """Verify emails, opt into marketing for all active users."""

    # 1. Verify unverified users
    r = await db.execute(
        text("UPDATE core.users SET is_verified = TRUE WHERE is_verified = FALSE AND is_active = TRUE")
    )
    logger.info("Verified %d users", r.rowcount)

    # 2. Ensure email_preferences with marketing_email = TRUE
    await db.execute(text("""
        INSERT INTO gdpr.email_preferences (user_id, marketing_email, transactional_email)
        SELECT u.id, TRUE, TRUE
        FROM core.users u
        WHERE u.is_active = TRUE
          AND NOT EXISTS (
            SELECT 1 FROM gdpr.email_preferences ep WHERE ep.user_id = u.id
          )
    """))

    await db.execute(text("""
        UPDATE gdpr.email_preferences
        SET marketing_email = TRUE
        WHERE user_id IN (SELECT id FROM core.users WHERE is_active = TRUE)
    """))

    # 3. Opt into all enabled communication types
    await db.execute(text("""
        INSERT INTO marketing.user_communication_preferences (user_id, communication_type_id, allowed)
        SELECT u.id, ct.id, TRUE
        FROM core.users u
        CROSS JOIN marketing.communication_types ct
        WHERE u.is_active = TRUE AND ct.enabled = TRUE
        ON CONFLICT (user_id, communication_type_id) DO UPDATE SET allowed = TRUE
    """))

    logger.info("All active users opted into marketing")


async def _compute_rfm(db: AsyncSession) -> None:
    """Compute RFM segments for customers with orders."""
    result = await db.execute(text(
        "SELECT user_id, order_count, total_spent, last_purchase_at "
        "FROM ecommerce.customer_metrics "
        "WHERE order_count > 0 AND last_purchase_at IS NOT NULL"
    ))
    rows = result.fetchall()
    if not rows:
        logger.info("No customers with orders — skipping RFM")
        return

    now = datetime.now(timezone.utc)
    count = 0
    for user_id, order_count, total_spent, last_purchase_at in rows:
        days_since = (now - last_purchase_at).days
        r = _score(days_since, RECENCY_THRESHOLDS, ascending=True)
        f = _score(order_count, FREQUENCY_THRESHOLDS, ascending=False)
        m = _score(total_spent, MONETARY_THRESHOLDS, ascending=False)
        segment = _assign_segment(r, f, m)
        await db.execute(
            text(
                "UPDATE ecommerce.customer_metrics "
                "SET rfm_segment = :seg, last_calculated_at = NOW() "
                "WHERE user_id = :uid"
            ),
            {"seg": segment, "uid": user_id},
        )
        count += 1

    logger.info("Computed RFM for %d customers", count)


async def _seed_analytics(db: AsyncSession) -> None:
    """Generate realistic analytics data for all active users."""
    result = await db.execute(
        text("SELECT id, email FROM core.users WHERE is_active = TRUE")
    )
    users = result.fetchall()
    if not users:
        logger.info("No active users — skipping analytics seed")
        return

    total_sessions = 0
    total_pageviews = 0
    total_events = 0

    for user_id, email in users:
        num_sessions = random.randint(3, 10)

        for _ in range(num_sessions):
            session_id = str(uuid.uuid4())
            session_start = _random_ts(30)
            device = random.choices(DEVICES, weights=DEVICE_WEIGHTS, k=1)[0]
            browser = random.choice(BROWSERS)
            browser_version = random.choice(BROWSER_VERSIONS[browser])
            os_name = random.choice(OS_MAP[device])
            duration_minutes = random.randint(1, 20)
            session_end = session_start + timedelta(minutes=duration_minutes)
            num_pages = random.randint(2, 8)
            pages_viewed = random.choices(PAGES, k=num_pages)

            # Session
            await db.execute(
                text(
                    "INSERT INTO analytics.analytics_sessions "
                    "(user_id, session_id, started_at, ended_at, page_count) "
                    "VALUES (:uid, :sid, :start, :end, :pc) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"uid": str(user_id), "sid": session_id, "start": session_start, "end": session_end, "pc": num_pages},
            )
            total_sessions += 1

            # User agent
            raw_ua = f"Mozilla/5.0 ({os_name}) {browser}/{browser_version}"
            await db.execute(
                text(
                    "INSERT INTO analytics.user_agents "
                    "(session_id, raw, browser, browser_version, os, device_type) "
                    "VALUES (:sid, :raw, :br, :bv, :os, :dt) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"sid": session_id, "raw": raw_ua, "br": browser, "bv": browser_version, "os": os_name, "dt": device},
            )

            # Referral source (50% of sessions)
            if random.random() < 0.5:
                source, medium = random.choice(REFERRAL_SOURCES)
                await db.execute(
                    text(
                        "INSERT INTO analytics.referral_sources "
                        "(session_id, source, medium) "
                        "VALUES (:sid, :src, :med) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"sid": session_id, "src": source, "med": medium},
                )

            # Page views
            for i, page_path in enumerate(pages_viewed):
                pv_time = session_start + timedelta(
                    seconds=i * (duration_minutes * 60 / max(num_pages, 1))
                )
                duration_ms = random.randint(2000, 60000)
                trigger = "navigation" if i == 0 else random.choice(["navigation", "click", "popstate"])
                await db.execute(
                    text(
                        'INSERT INTO analytics.page_views '
                        '(user_id, session_id, path, duration_ms, "trigger", created_at) '
                        "VALUES (:uid, :sid, :path, :dur, :trig, :ts)"
                    ),
                    {"uid": str(user_id), "sid": session_id, "path": page_path, "dur": duration_ms, "trig": trigger, "ts": pv_time},
                )
                total_pageviews += 1

            # Events (1-4 per session)
            num_events = random.randint(1, 4)
            event_types = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=num_events)
            for event_type in event_types:
                ev_time = session_start + timedelta(
                    seconds=random.randint(10, duration_minutes * 60)
                )
                event_data: dict = {}
                if event_type == "product_viewed":
                    event_data = {"product": random.choice(PAGES[2:7])}
                elif event_type == "search_performed":
                    event_data = {"query": random.choice(["shoes", "headphones", "shirt", "watch", "gift"])}
                elif event_type == "add_to_cart":
                    event_data = {"product": random.choice(PAGES[2:7]), "quantity": 1}

                await db.execute(
                    text(
                        "INSERT INTO analytics.events "
                        "(user_id, session_id, event_type, event_data, created_at) "
                        "VALUES (:uid, :sid, :etype, :edata, :ts)"
                    ),
                    {"uid": str(user_id), "sid": session_id, "etype": event_type, "edata": json.dumps(event_data), "ts": ev_time},
                )
                total_events += 1

    logger.info("Seeded: %d sessions, %d page views, %d events", total_sessions, total_pageviews, total_events)
