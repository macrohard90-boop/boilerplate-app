#!/usr/bin/env python3
"""
Seed realistic analytics data for existing users.

Usage:
    python scripts/seed_analytics.py

Generates page_views, analytics_sessions, user_agents, referral_sources,
and events for all active users. Makes the marketing insights dashboard
show real data.
"""

import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "/",
    "/products",
    "/products/wireless-headphones",
    "/products/usb-c-hub",
    "/products/classic-t-shirt",
    "/products/running-shoes",
    "/products/smart-watch",
    "/about",
    "/contact",
    "/cart",
    "/checkout",
    "/dashboard",
    "/auth/login",
    "/categories/electronics",
    "/categories/clothing",
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
    ("google", "organic"),
    ("direct", "none"),
    ("facebook", "social"),
    ("instagram", "social"),
    ("email", "email"),
    ("twitter", "social"),
]

EVENT_TYPES = [
    "product_viewed",
    "add_to_cart",
    "remove_from_cart",
    "checkout_started",
    "checkout_abandoned",
    "search_performed",
    "wishlist_added",
    "coupon_applied",
]
EVENT_WEIGHTS = [40, 20, 5, 10, 5, 10, 5, 5]


def load_env() -> dict[str, str]:
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


def get_db_url() -> str:
    env = load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


def random_timestamp(days_back: int = 30) -> datetime:
    """Random timestamp within the last N days."""
    offset = random.uniform(0, days_back * 24 * 3600)
    return datetime.now(timezone.utc) - timedelta(seconds=offset)


def main():
    url = get_db_url()
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    # Get all active users
    cur.execute("SELECT id, email FROM core.users WHERE is_active = TRUE")
    users = cur.fetchall()
    if not users:
        print("No active users found.")
        conn.close()
        return

    print(f"Found {len(users)} active users. Seeding analytics data...")

    total_sessions = 0
    total_pageviews = 0
    total_events = 0

    for user_id, email in users:
        # Each user gets 3-10 sessions over the last 30 days
        num_sessions = random.randint(3, 10)

        for _ in range(num_sessions):
            session_id = str(uuid.uuid4())
            session_start = random_timestamp(30)

            # Pick device/browser for this session
            device = random.choices(DEVICES, weights=DEVICE_WEIGHTS, k=1)[0]
            browser = random.choice(BROWSERS)
            browser_version = random.choice(BROWSER_VERSIONS[browser])
            os_name = random.choice(OS_MAP[device])

            # Session duration: 1-20 minutes
            duration_minutes = random.randint(1, 20)
            session_end = session_start + timedelta(minutes=duration_minutes)

            # Pages viewed in session: 2-8
            num_pages = random.randint(2, 8)
            pages_viewed = random.choices(PAGES, k=num_pages)

            # Insert session
            cur.execute(
                "INSERT INTO analytics.analytics_sessions "
                "(user_id, session_id, started_at, ended_at, page_count) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (str(user_id), session_id, session_start, session_end, num_pages),
            )
            total_sessions += 1

            # Insert user_agent
            raw_ua = f"Mozilla/5.0 ({os_name}) {browser}/{browser_version}"
            cur.execute(
                "INSERT INTO analytics.user_agents "
                "(session_id, raw, browser, browser_version, os, device_type) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (session_id, raw_ua, browser, browser_version, os_name, device),
            )

            # Insert referral source (50% of sessions)
            if random.random() < 0.5:
                source, medium = random.choice(REFERRAL_SOURCES)
                cur.execute(
                    "INSERT INTO analytics.referral_sources "
                    "(session_id, source, medium) "
                    "VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (session_id, source, medium),
                )

            # Insert page views
            for i, page_path in enumerate(pages_viewed):
                pv_time = session_start + timedelta(
                    seconds=i * (duration_minutes * 60 / max(num_pages, 1))
                )
                duration_ms = random.randint(2000, 60000)
                trigger = (
                    "navigation"
                    if i == 0
                    else random.choice(["navigation", "click", "popstate"])
                )
                cur.execute(
                    "INSERT INTO analytics.page_views "
                    '(user_id, session_id, path, duration_ms, "trigger", created_at) '
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        str(user_id),
                        session_id,
                        page_path,
                        duration_ms,
                        trigger,
                        pv_time,
                    ),
                )
                total_pageviews += 1

            # Insert events (1-4 per session)
            num_events = random.randint(1, 4)
            event_types = random.choices(
                EVENT_TYPES, weights=EVENT_WEIGHTS, k=num_events
            )
            for j, event_type in enumerate(event_types):
                ev_time = session_start + timedelta(
                    seconds=random.randint(10, duration_minutes * 60)
                )
                event_data = {}
                if event_type == "product_viewed":
                    event_data = {"product": random.choice(PAGES[2:7])}
                elif event_type == "search_performed":
                    event_data = {
                        "query": random.choice(
                            ["shoes", "headphones", "shirt", "watch", "gift"]
                        )
                    }
                elif event_type == "add_to_cart":
                    event_data = {"product": random.choice(PAGES[2:7]), "quantity": 1}

                cur.execute(
                    "INSERT INTO analytics.events "
                    "(user_id, session_id, event_type, event_data, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        str(user_id),
                        session_id,
                        event_type,
                        str(event_data).replace("'", '"'),
                        ev_time,
                    ),
                )
                total_events += 1

        print(f"  {email}: {num_sessions} sessions")

    conn.commit()
    print(
        f"\nSeeded: {total_sessions} sessions, {total_pageviews} page views, {total_events} events"
    )

    conn.close()


if __name__ == "__main__":
    main()
