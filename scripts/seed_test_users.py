#!/usr/bin/env python3
"""
Seed 100 test users with realistic, varied data for campaign pipeline testing.

Creates users with Gmail + aliasing (adrian+test001@estmgroup.com .. adrian+test100@...)
so all emails route to one inbox. Each user gets a profile (champion, loyal, new, etc.)
that determines their order history, engagement score, cart status, and RFM segment.

Usage:
    python scripts/seed_test_users.py              # Seed 100 users
    python scripts/seed_test_users.py --reset       # Delete seed users and re-seed

Idempotent by default (ON CONFLICT DO NOTHING).
Does NOT call Stripe API — inserts fake cus_test_seed_XXX IDs directly.
"""

import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Constants ────────────────────────────────────────────────────────────────

BCRYPT_HASH = "$2b$12$x/zScld/uyRyTNdtUhgeqOpu0nRcIn/2Bk6VU/cciUL97xyx47kP."
CUSTOMER_ROLE_ID = "a0000000-0000-0000-0000-000000000003"
EMAIL_DOMAIN = "estmgroup.com"
EMAIL_PREFIX = "adrian"


# Deterministic UUIDs for idempotency: cc000000-0000-0000-0000-000000000{001..100}
def _user_uuid(i: int) -> str:
    return f"cc000000-0000-0000-0000-{i:012d}"


# ── Product catalog (from seeds/ecommerce.sql) ──────────────────────────────

PRODUCTS = [
    {
        "id": "d0000000-0000-0000-0000-000000000001",
        "name": "Wireless Headphones",
        "slug": "wireless-headphones",
        "base_price": 7999,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000001",
                "name": "Black",
                "sku": "WH-001-BLK",
                "price": 7999,
                "attrs": {"color": "black"},
                "image": "/images/products/headphones-black.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000002",
                "name": "White",
                "sku": "WH-001-WHT",
                "price": 7999,
                "attrs": {"color": "white"},
                "image": "/images/products/headphones-white.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000002",
        "name": "USB-C Hub",
        "slug": "usb-c-hub",
        "base_price": 4999,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000011",
                "name": "Default",
                "sku": "UC-001-DEF",
                "price": 4999,
                "attrs": {},
                "image": "/images/products/usb-hub.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000003",
        "name": "Classic T-Shirt",
        "slug": "classic-tshirt",
        "base_price": 2499,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000003",
                "name": "Navy - Small",
                "sku": "TS-001-NVY-S",
                "price": 2499,
                "attrs": {"size": "S", "color": "navy"},
                "image": "/images/products/tshirt-navy.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000004",
                "name": "Red - Medium",
                "sku": "TS-001-RED-M",
                "price": 2499,
                "attrs": {"size": "M", "color": "red"},
                "image": "/images/products/tshirt-red.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000005",
                "name": "Forest Green - Large",
                "sku": "TS-001-FGN-L",
                "price": 2499,
                "attrs": {"size": "L", "color": "forest"},
                "image": "/images/products/tshirt-forest.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000004",
        "name": "Running Shoes",
        "slug": "running-shoes",
        "base_price": 8999,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000006",
                "name": "Size 9",
                "sku": "RS-001-9",
                "price": 8999,
                "attrs": {"size": "9"},
                "image": "/images/products/shoes-main.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000007",
                "name": "Size 10",
                "sku": "RS-001-10",
                "price": 8999,
                "attrs": {"size": "10"},
                "image": "/images/products/shoes-main.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000008",
                "name": "Size 11",
                "sku": "RS-001-11",
                "price": 8999,
                "attrs": {"size": "11"},
                "image": "/images/products/shoes-main.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000005",
        "name": "Smart Watch",
        "slug": "smart-watch",
        "base_price": 19999,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000009",
                "name": "42mm Silver",
                "sku": "SW-001-42S",
                "price": 19999,
                "attrs": {"size": "42mm", "color": "silver"},
                "image": "/images/products/watch-silver.svg",
            },
            {
                "id": "e0000000-0000-0000-0000-000000000010",
                "name": "46mm Black",
                "sku": "SW-001-46B",
                "price": 22999,
                "attrs": {"size": "46mm", "color": "black"},
                "image": "/images/products/watch-black.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000006",
        "name": "Plant Pot Set",
        "slug": "plant-pot-set",
        "base_price": 3499,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000012",
                "name": "Default",
                "sku": "PP-001-DEF",
                "price": 3499,
                "attrs": {},
                "image": None,
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000007",
        "name": "E-Book: Web Dev Guide",
        "slug": "ebook-web-dev",
        "base_price": 1999,
        "type": "digital",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000013",
                "name": "PDF",
                "sku": "EB-001-PDF",
                "price": 1999,
                "attrs": {},
                "image": None,
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000008",
        "name": "Desk Lamp",
        "slug": "desk-lamp",
        "base_price": 4499,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000014",
                "name": "Default",
                "sku": "DL-001-DEF",
                "price": 4499,
                "attrs": {},
                "image": "/images/products/desk-lamp.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000009",
        "name": "Backpack",
        "slug": "backpack",
        "base_price": 5999,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000015",
                "name": "Default",
                "sku": "BP-001-DEF",
                "price": 5999,
                "attrs": {},
                "image": "/images/products/backpack.svg",
            },
        ],
    },
    {
        "id": "d0000000-0000-0000-0000-000000000010",
        "name": "Coffee Mug",
        "slug": "coffee-mug",
        "base_price": 1499,
        "type": "physical",
        "variants": [
            {
                "id": "e0000000-0000-0000-0000-000000000016",
                "name": "Default",
                "sku": "CM-001-DEF",
                "price": 1499,
                "attrs": {},
                "image": None,
            },
        ],
    },
]


def _product_snapshot(product: dict, variant: dict) -> str:
    """Build the JSONB product_snapshot for an order item."""
    return json.dumps(
        {
            "product_name": product["name"],
            "product_slug": product["slug"],
            "variant_name": variant["name"],
            "variant_sku": variant["sku"],
            "attributes": variant["attrs"],
            "product_type": product["type"],
            "image_url": variant.get("image"),
        }
    )


# ── User profiles ────────────────────────────────────────────────────────────

# Each profile defines data ranges for a target RFM segment.
# (name, count, order_range, recency_range_days, spend_range_cents,
#  engagement_score_range, velocity_range, cart_status)

PROFILES = [
    ("champion", 10, (8, 15), (1, 5), (50000, 200000), (70, 100), (2, 5), "converted"),
    ("loyal", 15, (5, 10), (5, 25), (20000, 80000), (50, 80), (1, 3), "converted"),
    (
        "potential_loyalist",
        15,
        (2, 4),
        (1, 7),
        (5000, 30000),
        (40, 70),
        (2, 5),
        "active",
    ),
    ("new", 15, (1, 2), (1, 7), (2000, 10000), (20, 50), (0, 3), "active"),
    (
        "at_risk",
        15,
        (5, 8),
        (100, 160),
        (20000, 60000),
        (20, 40),
        (-3, -1),
        "abandoned",
    ),
    (
        "hibernating",
        15,
        (1, 3),
        (100, 170),
        (3000, 15000),
        (5, 20),
        (-5, -2),
        "abandoned",
    ),
    ("lost", 15, (0, 1), (200, 365), (0, 5000), (0, 10), (-5, -1), "expired"),
]


# ── RFM scoring (same logic as startup_seeder.py) ───────────────────────────

RECENCY_THRESHOLDS = [7, 30, 90, 180]
FREQUENCY_THRESHOLDS = [1, 3, 5, 10]
MONETARY_THRESHOLDS = [2000, 5000, 15000, 50000]

SEGMENT_RULES = [
    (lambda r, f, m: r >= 4 and f >= 4 and m >= 4, "champion"),
    (lambda r, f, m: f >= 3 and m >= 3 and r >= 3, "loyal"),
    (lambda r, f, m: r >= 4 and f >= 2, "potential_loyalist"),
    (lambda r, f, m: r >= 4 and f <= 2, "new"),
    (lambda r, f, m: r <= 2 and f >= 3, "at_risk"),
    (lambda r, f, m: r <= 2 and f >= 1, "hibernating"),
    (lambda r, f, m: r <= 1, "lost"),
]


def _score(value: int, thresholds: list[int], ascending: bool = True) -> int:
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


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _random_past(min_days: int, max_days: int) -> datetime:
    days = random.uniform(min_days, max_days)
    return _now() - timedelta(days=days)


def _pick_product_variant() -> tuple[dict, dict]:
    """Pick a random product and one of its variants."""
    product = random.choice(PRODUCTS)
    variant = random.choice(product["variants"])
    return product, variant


# ── DB helpers ───────────────────────────────────────────────────────────────


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
        # Build URL from individual env vars
        user = os.environ.get("POSTGRES_USER", env.get("POSTGRES_USER", "boilerplate"))
        pw = os.environ.get(
            "POSTGRES_PASSWORD", env.get("POSTGRES_PASSWORD", "change-me")
        )
        host = os.environ.get("POSTGRES_HOST", env.get("POSTGRES_HOST", "localhost"))
        port = os.environ.get("POSTGRES_PORT", env.get("POSTGRES_PORT", "5432"))
        db = os.environ.get("POSTGRES_DB", env.get("POSTGRES_DB", "boilerplate_db"))
        return f"postgresql://{user}:{pw}@{host}:{port}/{db}"

    # Resolve ${VAR} references from env
    import re

    def _resolve(match):
        var = match.group(1)
        return os.environ.get(var, env.get(var, match.group(0)))

    url = re.sub(r"\$\{(\w+)\}", _resolve, url)
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    # When running outside Docker, swap internal hostname for localhost
    if not os.path.exists("/.dockerenv"):
        url = url.replace("@postgres:", "@localhost:")
    return url


# ── Main seed logic ─────────────────────────────────────────────────────────


def seed_test_users(conn) -> dict:
    """Create 100 test users with varied data. Returns summary dict."""
    random.seed(42)  # Deterministic for reproducible data
    cur = conn.cursor()

    now = _now()
    users_created = 0
    orders_created = 0
    carts_created = 0
    wishlists_created = 0

    user_idx = 0  # Running index across all profiles

    for (
        profile_name,
        count,
        order_range,
        recency_range,
        spend_range,
        eng_score_range,
        velocity_range,
        cart_status,
    ) in PROFILES:

        for _ in range(count):
            user_idx += 1
            user_id = _user_uuid(user_idx)
            email = f"{EMAIL_PREFIX}+test{user_idx:03d}@{EMAIL_DOMAIN}"
            first_name = "Test"
            last_name = f"User {user_idx:03d}"
            phone = f"+1555001{user_idx:04d}"
            whatsapp = f"+1555002{user_idx:04d}"
            stripe_cus = f"cus_test_seed_{user_idx:03d}"

            # Marketing opt-in: 80% opted in, 20% opted out (users 81-100)
            marketing_opted_in = user_idx <= 80

            # Email verified: users 91-100 are unverified (for testing verification flow)
            is_verified = user_idx <= 90

            # ── 1. core.users ────────────────────────────────────────────
            cur.execute(
                """
                INSERT INTO core.users
                    (id, email, password_hash, first_name, last_name,
                     role_id, phone, whatsapp_number, is_verified, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO NOTHING
                """,
                (
                    user_id,
                    email,
                    BCRYPT_HASH,
                    first_name,
                    last_name,
                    CUSTOMER_ROLE_ID,
                    phone,
                    whatsapp,
                    is_verified,
                ),
            )
            users_created += cur.rowcount

            # ── 2. gdpr.email_preferences ────────────────────────────────
            cur.execute(
                """
                INSERT INTO gdpr.email_preferences
                    (user_id, marketing_email, transactional_email)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, marketing_opted_in),
            )

            # ── 3. gdpr.consent_records ──────────────────────────────────
            if marketing_opted_in:
                for consent_type in ("marketing_email", "analytics"):
                    cur.execute(
                        """
                        INSERT INTO gdpr.consent_records
                            (user_id, consent_type, granted, version, ip_address)
                        VALUES (%s, %s, TRUE, '1.0', '127.0.0.1')
                        """,
                        (user_id, consent_type),
                    )

            # ── 4. ecommerce.stripe_customers ────────────────────────────
            cur.execute(
                """
                INSERT INTO ecommerce.stripe_customers
                    (user_id, stripe_customer_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, stripe_cus),
            )

            # ── 5. Orders ────────────────────────────────────────────────
            num_orders = random.randint(*order_range)
            total_spent = 0
            last_purchase_at = None

            for order_idx in range(num_orders):
                order_id = str(
                    uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-order-{user_idx}-{order_idx}")
                )
                order_number = f"ORD-SEED-{user_idx:03d}-{order_idx:02d}"

                # Spread orders across the recency window
                if num_orders > 1:
                    # Most recent order within recency range, older ones further back
                    order_recency = recency_range[0] + (
                        (recency_range[1] - recency_range[0])
                        * order_idx
                        / max(num_orders - 1, 1)
                    )
                else:
                    order_recency = random.uniform(*recency_range)
                order_date = now - timedelta(days=order_recency)

                # Pick 1-3 items per order
                num_items = random.randint(1, 3)
                # Track (product_id, variant_id) to avoid PK conflicts within one order
                seen_pv = set()
                items = []
                order_subtotal = 0

                for _ in range(num_items):
                    # Keep trying until we get a unique product+variant combo
                    for _attempt in range(20):
                        product, variant = _pick_product_variant()
                        pv_key = (product["id"], variant["id"])
                        if pv_key not in seen_pv:
                            seen_pv.add(pv_key)
                            break
                    else:
                        continue

                    qty = random.randint(1, 3)
                    unit_price = variant["price"]
                    item_total = unit_price * qty
                    order_subtotal += item_total
                    items.append((product, variant, qty, unit_price, item_total))

                if not items:
                    continue

                # Status: mostly completed, some variety
                status_roll = random.random()
                if status_roll < 0.80:
                    status = "completed"
                elif status_roll < 0.90:
                    status = "pending"
                else:
                    status = "refunded"

                cur.execute(
                    """
                    INSERT INTO ecommerce.orders
                        (id, user_id, order_number, status, currency,
                         subtotal, discount_amount, tax_amount, total, created_at)
                    VALUES (%s, %s, %s, %s, 'USD', %s, 0, 0, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        order_id,
                        user_id,
                        order_number,
                        status,
                        order_subtotal,
                        order_subtotal,
                        order_date,
                    ),
                )

                for product, variant, qty, unit_price, item_total in items:
                    cur.execute(
                        """
                        INSERT INTO ecommerce.order_items
                            (order_id, product_id, variant_id, quantity,
                             unit_price, total_price, product_snapshot)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            order_id,
                            product["id"],
                            variant["id"],
                            qty,
                            unit_price,
                            item_total,
                            _product_snapshot(product, variant),
                        ),
                    )

                # Track totals for customer_metrics (only count completed orders)
                if status == "completed":
                    total_spent += order_subtotal
                    if last_purchase_at is None or order_date > last_purchase_at:
                        last_purchase_at = order_date

                orders_created += 1

            # ── 6. ecommerce.customer_metrics ────────────────────────────
            if num_orders > 0:
                completed_count = (
                    num_orders  # approximate; some may be pending/refunded
                )
                days_since = (now - last_purchase_at).days if last_purchase_at else 999
                r = _score(days_since, RECENCY_THRESHOLDS, ascending=True)
                f = _score(completed_count, FREQUENCY_THRESHOLDS, ascending=False)
                m = _score(total_spent, MONETARY_THRESHOLDS, ascending=False)
                rfm = _assign_segment(r, f, m)

                cur.execute(
                    """
                    INSERT INTO ecommerce.customer_metrics
                        (user_id, order_count, total_spent, default_currency,
                         last_purchase_at, rfm_segment, last_calculated_at)
                    VALUES (%s, %s, %s, 'USD', %s, %s, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        order_count = EXCLUDED.order_count,
                        total_spent = EXCLUDED.total_spent,
                        last_purchase_at = EXCLUDED.last_purchase_at,
                        rfm_segment = EXCLUDED.rfm_segment,
                        last_calculated_at = NOW()
                    """,
                    (user_id, completed_count, total_spent, last_purchase_at, rfm),
                )

            # ── 7. Cart ──────────────────────────────────────────────────
            if cart_status != "expired" or random.random() < 0.3:
                cart_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-cart-{user_idx}"))
                cart_date = (
                    _random_past(1, 30)
                    if cart_status in ("active", "converted")
                    else _random_past(30, 120)
                )

                cur.execute(
                    """
                    INSERT INTO ecommerce.cart
                        (id, user_id, status, currency, created_at, updated_at)
                    VALUES (%s, %s, %s, 'USD', %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (cart_id, user_id, cart_status, cart_date, cart_date),
                )

                # Add 1-3 items to cart
                num_cart_items = random.randint(1, 3)
                seen_cart_pv = set()
                for _ in range(num_cart_items):
                    for _attempt in range(20):
                        product, variant = _pick_product_variant()
                        pv_key = (product["id"], variant["id"])
                        if pv_key not in seen_cart_pv:
                            seen_cart_pv.add(pv_key)
                            break
                    else:
                        continue

                    cur.execute(
                        """
                        INSERT INTO ecommerce.cart_items
                            (cart_id, product_id, variant_id, quantity, unit_price_at_add)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            cart_id,
                            product["id"],
                            variant["id"],
                            random.randint(1, 2),
                            variant["price"],
                        ),
                    )
                carts_created += 1

            # ── 8. Wishlist (40% of users) ───────────────────────────────
            if random.random() < 0.4:
                wl_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-wishlist-{user_idx}"))
                cur.execute(
                    """
                    INSERT INTO ecommerce.wishlists
                        (id, user_id, name, is_default)
                    VALUES (%s, %s, 'My Wishlist', TRUE)
                    ON CONFLICT DO NOTHING
                    """,
                    (wl_id, user_id),
                )

                # 1-4 items
                num_wl_items = random.randint(1, 4)
                seen_wl = set()
                for _ in range(num_wl_items):
                    product, variant = _pick_product_variant()
                    if product["id"] not in seen_wl:
                        seen_wl.add(product["id"])
                        cur.execute(
                            """
                            INSERT INTO ecommerce.wishlist_items
                                (wishlist_id, product_id, variant_id)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (wl_id, product["id"], variant["id"]),
                        )
                wishlists_created += 1

            # ── 9. analytics.engagement_scores ───────────────────────────
            eng_score = round(random.uniform(*eng_score_range), 2)
            velocity = round(random.uniform(*velocity_range), 2)

            # Engagement timestamps based on profile
            last_site = _random_past(*recency_range) if num_orders > 0 else None
            last_purchase_ts = last_purchase_at
            last_email_open = (
                _random_past(1, 30)
                if marketing_opted_in and random.random() < 0.6
                else None
            )
            last_email_click = (
                _random_past(1, 60)
                if last_email_open and random.random() < 0.4
                else None
            )

            cur.execute(
                """
                INSERT INTO analytics.engagement_scores
                    (user_id, score, velocity, last_email_open, last_email_click,
                     last_site_visit, last_purchase, computed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    velocity = EXCLUDED.velocity,
                    last_email_open = EXCLUDED.last_email_open,
                    last_email_click = EXCLUDED.last_email_click,
                    last_site_visit = EXCLUDED.last_site_visit,
                    last_purchase = EXCLUDED.last_purchase,
                    computed_at = NOW()
                """,
                (
                    user_id,
                    eng_score,
                    velocity,
                    last_email_open,
                    last_email_click,
                    last_site,
                    last_purchase_ts,
                ),
            )

    conn.commit()

    summary = {
        "users": users_created,
        "orders": orders_created,
        "carts": carts_created,
        "wishlists": wishlists_created,
    }
    return summary


def reset_seed_users(conn):
    """Remove all seed test users and their cascade data."""
    cur = conn.cursor()
    user_pattern = f"{EMAIL_PREFIX}+test%@{EMAIL_DOMAIN}"
    print("  Deleting seed test users...")

    # Use a subquery pattern for all deletions (avoids UUID cast issues)
    uid_sub = "(SELECT id FROM core.users WHERE email LIKE %s)"

    # Delete engagement scores
    cur.execute(
        f"DELETE FROM analytics.engagement_scores WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Delete cart items then carts (ON DELETE SET NULL on user_id, so no cascade)
    cur.execute(
        f"DELETE FROM ecommerce.cart_items WHERE cart_id IN "
        f"(SELECT id FROM ecommerce.cart WHERE user_id IN {uid_sub})",
        (user_pattern,),
    )
    cur.execute(
        f"DELETE FROM ecommerce.cart WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )
    # Also clean up orphaned carts with NULL user_id from previous resets
    cur.execute(
        "DELETE FROM ecommerce.cart_items WHERE cart_id IN "
        "(SELECT id FROM ecommerce.cart WHERE user_id IS NULL)"
    )
    cur.execute("DELETE FROM ecommerce.cart WHERE user_id IS NULL")

    # Delete orders (RESTRICT on user_id, need to delete items first)
    cur.execute(
        "DELETE FROM ecommerce.order_items WHERE order_id IN "
        "(SELECT id FROM ecommerce.orders WHERE order_number LIKE 'ORD-SEED-%')"
    )
    cur.execute("DELETE FROM ecommerce.orders WHERE order_number LIKE 'ORD-SEED-%'")

    # Delete wishlists (CASCADE handles wishlist_items)
    cur.execute(
        f"DELETE FROM ecommerce.wishlists WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Delete customer_metrics
    cur.execute(
        f"DELETE FROM ecommerce.customer_metrics WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Delete stripe_customers
    cur.execute(
        f"DELETE FROM ecommerce.stripe_customers WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Delete GDPR data
    cur.execute(
        f"DELETE FROM gdpr.consent_records WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )
    cur.execute(
        f"DELETE FROM gdpr.email_preferences WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Count before deleting
    cur.execute("SELECT count(*) FROM core.users WHERE email LIKE %s", (user_pattern,))
    count = cur.fetchone()[0]

    # Finally delete the users
    cur.execute("DELETE FROM core.users WHERE email LIKE %s", (user_pattern,))

    conn.commit()
    print(f"  Deleted {count} seed test users and all related data.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed 100 test users")
    parser.add_argument("--reset", action="store_true", help="Delete seed users first")
    args = parser.parse_args()

    conn = psycopg2.connect(get_db_url())
    try:
        if args.reset:
            reset_seed_users(conn)

        print("\nSeeding 100 test users...")
        summary = seed_test_users(conn)
        print(f"\n  Done! Created:")
        print(f"    Users:     {summary['users']}")
        print(f"    Orders:    {summary['orders']}")
        print(f"    Carts:     {summary['carts']}")
        print(f"    Wishlists: {summary['wishlists']}")
        print(
            f"\n  All users: {EMAIL_PREFIX}+test001@{EMAIL_DOMAIN} .. {EMAIL_PREFIX}+test100@{EMAIL_DOMAIN}"
        )
        print(f"  Password:  Test1234!")
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
