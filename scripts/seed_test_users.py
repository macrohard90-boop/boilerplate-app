#!/usr/bin/env python3
"""
Seed 100 test users with realistic, varied data for campaign pipeline testing.

Creates users with Gmail + aliasing (adrian+test001@estmgroup.com .. adrian+test100@...)
so all emails route to one inbox. Each user gets a profile (champion, loyal, new, etc.)
that determines their order history, engagement score, cart status, and RFM segment.

Also seeds comprehensive analytics (sessions, page views, events, user agents, referral
sources, UTM tracking), payment records, product reviews, cookie preferences, all 6
GDPR consent types, and communication preferences — so every audience preset and
segment filter returns non-zero matches, and the analytics UI shows rich data per user.

Usage:
    python scripts/seed_test_users.py              # Seed 100 users
    python scripts/seed_test_users.py --reset       # Delete seed users and re-seed

Idempotent by default (ON CONFLICT DO NOTHING / deterministic UUIDs).
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


def _det_uuid(*parts) -> str:
    """Deterministic UUID from parts — for idempotent inserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "-".join(str(p) for p in parts)))


# ── 100 Real Names ───────────────────────────────────────────────────────────

NAMES = [
    ("Olivia", "Chen"),
    ("Marcus", "Johnson"),
    ("Sofia", "Ramirez"),
    ("Ethan", "Nakamura"),
    ("Amara", "Okonkwo"),
    ("Liam", "O'Sullivan"),
    ("Priya", "Patel"),
    ("Noah", "Williams"),
    ("Mei", "Zhang"),
    ("Carlos", "Gutierrez"),
    ("Fatima", "Al-Rashid"),
    ("James", "Anderson"),
    ("Yuki", "Tanaka"),
    ("Isabella", "Moretti"),
    ("David", "Kim"),
    ("Aisha", "Mohammed"),
    ("Ryan", "Thompson"),
    ("Zara", "Singh"),
    ("Lucas", "Fernandez"),
    ("Chloe", "Dubois"),
    ("Ahmad", "Hassan"),
    ("Emma", "Larsson"),
    ("Daniel", "Cruz"),
    ("Nalini", "Sharma"),
    ("Tyler", "Brooks"),
    ("Sakura", "Watanabe"),
    ("Grace", "Mwangi"),
    ("Alexander", "Petrov"),
    ("Luna", "Reyes"),
    ("Benjamin", "Clarke"),
    ("Anya", "Volkov"),
    ("Michael", "Nguyen"),
    ("Iris", "Papadopoulos"),
    ("Omar", "Diallo"),
    ("Hannah", "Meyer"),
    ("Raj", "Krishnamurthy"),
    ("Elena", "Popescu"),
    ("Nathan", "Fischer"),
    ("Camila", "Santos"),
    ("Takeshi", "Yamamoto"),
    ("Leah", "Goldstein"),
    ("Victor", "Johansson"),
    ("Maya", "Reddy"),
    ("Sven", "Lindqvist"),
    ("Nadia", "Kozlov"),
    ("Patrick", "O'Brien"),
    ("Yara", "Mansouri"),
    ("Kenji", "Saito"),
    ("Aaliyah", "Jackson"),
    ("Erik", "Andersen"),
    ("Lucia", "Bianchi"),
    ("Samuel", "Otieno"),
    ("Freya", "Eriksen"),
    ("Hassan", "Yilmaz"),
    ("Mia", "Hoffmann"),
    ("Adrian", "Vasquez"),
    ("Ingrid", "Nilsson"),
    ("Kofi", "Asante"),
    ("Sophie", "Martin"),
    ("Arjun", "Mehta"),
    ("Clara", "Schmidt"),
    ("Diego", "Herrera"),
    ("Linnea", "Bergstrom"),
    ("Felix", "Wagner"),
    ("Aiko", "Suzuki"),
    ("Rachel", "Barnes"),
    ("Tariq", "Aziz"),
    ("Valentina", "Rossi"),
    ("Caleb", "Stewart"),
    ("Hana", "Park"),
    ("Leo", "Mueller"),
    ("Naomi", "Taylor"),
    ("Jin", "Liu"),
    ("Esther", "Osei"),
    ("Magnus", "Dahl"),
    ("Gabriella", "Torres"),
    ("Nikolai", "Sokolov"),
    ("Sienna", "Cooper"),
    ("Yousef", "Khoury"),
    ("Astrid", "Henriksen"),
    ("Dante", "Marchetti"),
    ("Mina", "Sato"),
    ("Christopher", "Evans"),
    ("Zuri", "Ndegwa"),
    ("Henrik", "Olsen"),
    ("Alina", "Ionescu"),
    ("Sebastian", "Rivera"),
    ("Ting", "Wu"),
    ("Nora", "Bakken"),
    ("Ivan", "Horvat"),
    ("Julia", "Kowalski"),
    ("Rafael", "Almeida"),
    ("Suki", "Acharya"),
    ("Dylan", "Murphy"),
    ("Lena", "Bauer"),
    ("Oscar", "Jimenez"),
    ("Kira", "Morozova"),
    ("Maxwell", "Reed"),
    ("Ananya", "Iyer"),
    ("Philip", "Lindberg"),
]


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
    ("new", 15, (0, 1), (1, 7), (2000, 10000), (20, 50), (0, 3), "active"),
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

# Analytics config per profile
PROFILE_ANALYTICS = {
    "champion": {"sessions": (6, 10), "session_recency": (1, 30), "signup_days": (90, 365)},
    "loyal": {"sessions": (5, 8), "session_recency": (1, 60), "signup_days": (60, 300)},
    "potential_loyalist": {"sessions": (3, 5), "session_recency": (1, 14), "signup_days": (14, 60)},
    "new": {"sessions": (1, 3), "session_recency": (1, 7), "signup_days": (1, 14)},
    "at_risk": {"sessions": (2, 4), "session_recency": (100, 160), "signup_days": (90, 365)},
    "hibernating": {"sessions": (1, 2), "session_recency": (100, 170), "signup_days": (120, 365)},
    "lost": {"sessions": (1, 1), "session_recency": (200, 365), "signup_days": (200, 400)},
}

# ── Analytics seed constants ─────────────────────────────────────────────────

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

UTM_SOURCES = [
    ("google", "cpc"),
    ("facebook", "social"),
    ("instagram", "social"),
    ("newsletter", "email"),
    ("twitter", "social"),
]
UTM_CAMPAIGNS = [
    "spring_sale",
    "new_arrivals",
    "loyalty_program",
    "retargeting",
    "summer_clearance",
    "welcome_series",
]

PAYMENT_METHODS = ["card", "apple_pay", "google_pay"]

REVIEW_TITLES_POSITIVE = [
    "Great product!",
    "Exceeded expectations",
    "Amazing purchase",
    "Works perfectly",
    "Solid build quality",
    "Love it!",
    "Highly recommend",
    "Fantastic!",
    "Would buy again",
    "Best purchase this year",
]
REVIEW_TITLES_NEGATIVE = [
    "Could be better",
    "Not what I expected",
    "Just okay",
    "Disappointing quality",
    "Wouldn't recommend",
]
REVIEW_BODIES_POSITIVE = [
    "Really happy with this purchase. Exactly what I was looking for.",
    "The quality is outstanding. Would definitely recommend to friends.",
    "Works as described. No complaints so far.",
    "Absolutely love it! Great value for money.",
    "Solid product. Good build quality and fast delivery.",
    "Exceeded my expectations in every way.",
]
REVIEW_BODIES_NEGATIVE = [
    "Not the best I've seen but does the job.",
    "It's okay for the price. Nothing spectacular.",
    "Disappointed with the quality. Expected better for the price.",
    "Had some issues initially but customer support helped.",
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


def _event_data_for(event_type: str) -> dict:
    """Generate realistic event_data JSONB for an event type."""
    if event_type == "product_viewed":
        p = random.choice(PRODUCTS)
        return {"product": f"/products/{p['slug']}", "product_id": p["id"]}
    elif event_type == "add_to_cart":
        p, v = _pick_product_variant()
        return {"product": f"/products/{p['slug']}", "product_id": p["id"], "quantity": 1}
    elif event_type == "remove_from_cart":
        p = random.choice(PRODUCTS)
        return {"product_id": p["id"]}
    elif event_type == "checkout_started":
        return {"cart_total": random.randint(2000, 50000)}
    elif event_type == "checkout_abandoned":
        return {"cart_total": random.randint(2000, 50000), "item_count": random.randint(1, 5)}
    elif event_type == "search_performed":
        return {"query": random.choice(["shoes", "headphones", "shirt", "watch", "gift", "laptop", "phone"])}
    elif event_type == "wishlist_added":
        p = random.choice(PRODUCTS)
        return {"product_id": p["id"], "product_name": p["name"]}
    elif event_type == "coupon_applied":
        return {"code": random.choice(["SAVE10", "WELCOME20", "SUMMER15", "VIP25"])}
    return {}


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
    payments_created = 0
    sessions_created = 0
    pageviews_created = 0
    events_created = 0
    reviews_created = 0

    # Get communication type IDs for comm preferences
    comm_types = {}
    try:
        cur.execute("SELECT id, name FROM marketing.communication_types WHERE enabled = TRUE")
        comm_types = {name: str(ct_id) for ct_id, name in cur.fetchall()}
    except Exception:
        conn.rollback()

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
        analytics_cfg = PROFILE_ANALYTICS[profile_name]

        for _ in range(count):
            user_idx += 1
            user_id = _user_uuid(user_idx)
            email = f"{EMAIL_PREFIX}+test{user_idx:03d}@{EMAIL_DOMAIN}"
            first_name, last_name = NAMES[user_idx - 1]
            phone = f"+1555001{user_idx:04d}"
            whatsapp = f"+1555002{user_idx:04d}"
            stripe_cus = f"cus_test_seed_{user_idx:03d}"

            # Marketing opt-in: 80% opted in, 20% opted out (users 81-100)
            marketing_opted_in = user_idx <= 80

            # Email verified: users 91-100 are unverified (for testing verification flow)
            is_verified = user_idx <= 90

            # Signup date varies by profile
            signup_date = _random_past(*analytics_cfg["signup_days"])

            # ── 1. core.users ────────────────────────────────────────────
            cur.execute(
                """
                INSERT INTO core.users
                    (id, email, password_hash, first_name, last_name,
                     role_id, phone, whatsapp_number, is_verified, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (email) DO UPDATE SET
                    phone = EXCLUDED.phone,
                    whatsapp_number = EXCLUDED.whatsapp_number,
                    is_verified = EXCLUDED.is_verified,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name
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
                    signup_date,
                ),
            )
            users_created += cur.rowcount

            # ── 2. gdpr.email_preferences ────────────────────────────────
            cur.execute(
                """
                INSERT INTO gdpr.email_preferences
                    (user_id, marketing_email, transactional_email)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET
                    marketing_email = EXCLUDED.marketing_email
                """,
                (user_id, marketing_opted_in),
            )

            # ── 3. gdpr.consent_records (all 6 types) ───────────────────
            consent_map = [
                ("marketing_email", user_idx <= 80),
                ("transactional_email", user_idx <= 95),
                ("analytics", user_idx <= 70),
                ("third_party_sharing", user_idx <= 50),
                ("cookies_analytics", user_idx <= 70),
                ("cookies_marketing", user_idx <= 60),
            ]
            for consent_type, granted in consent_map:
                consent_id = _det_uuid("seed-consent", user_idx, consent_type)
                cur.execute(
                    """
                    INSERT INTO gdpr.consent_records
                        (id, user_id, consent_type, granted, version, ip_address)
                    VALUES (%s, %s, %s, %s, '1.0', '127.0.0.1')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (consent_id, user_id, consent_type, granted),
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

            # ── 5. Orders + Payment Records ──────────────────────────────
            num_orders = random.randint(*order_range)
            total_spent = 0
            last_purchase_at = None
            ordered_products = []  # Track for reviews

            for order_idx in range(num_orders):
                order_id = str(
                    uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-order-{user_idx}-{order_idx}")
                )
                order_number = f"ORD-SEED-{user_idx:03d}-{order_idx:02d}"

                # Spread orders across the recency window
                if num_orders > 1:
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
                seen_pv = set()
                items = []
                order_subtotal = 0

                for _ in range(num_items):
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
                    ordered_products.append(product)

                # Payment record for this order
                payment_status_map = {
                    "completed": "succeeded",
                    "pending": "pending",
                    "refunded": "refunded",
                }
                payment_id = _det_uuid("seed-pay", user_idx, order_idx)
                cur.execute(
                    """
                    INSERT INTO ecommerce.payment_records
                        (id, order_id, provider, provider_payment_id, status,
                         amount, currency, method, created_at)
                    VALUES (%s, %s, 'stripe', %s, %s, %s, 'USD', %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        payment_id,
                        order_id,
                        f"pi_test_seed_{user_idx:03d}_{order_idx:02d}",
                        payment_status_map.get(status, "pending"),
                        order_subtotal,
                        random.choice(PAYMENT_METHODS),
                        order_date,
                    ),
                )
                payments_created += 1

                # Track totals for customer_metrics (only count completed orders)
                if status == "completed":
                    total_spent += order_subtotal
                    if last_purchase_at is None or order_date > last_purchase_at:
                        last_purchase_at = order_date

                orders_created += 1

            # ── 6. ecommerce.customer_metrics ────────────────────────────
            # Always create a row — even for 0-order users.
            # _compute_rfm skips order_count=0 rows, so the profile segment persists
            # for "new" and "lost" users who have no orders.
            if num_orders > 0:
                completed_count = num_orders
                days_since = (now - last_purchase_at).days if last_purchase_at else 999
                r = _score(days_since, RECENCY_THRESHOLDS, ascending=True)
                f = _score(completed_count, FREQUENCY_THRESHOLDS, ascending=False)
                m = _score(total_spent, MONETARY_THRESHOLDS, ascending=False)
                rfm = _assign_segment(r, f, m)
            else:
                completed_count = 0
                rfm = profile_name

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

            # ── 10. Analytics: sessions, page views, user agents, referrals, events ──
            num_sessions = random.randint(*analytics_cfg["sessions"])

            for sess_idx in range(num_sessions):
                session_id = f"seed-sess-{user_idx:03d}-{sess_idx:02d}"
                sess_recency = analytics_cfg["session_recency"]
                # Spread sessions across the recency window
                if num_sessions > 1:
                    day_offset = sess_recency[0] + (
                        (sess_recency[1] - sess_recency[0])
                        * sess_idx / max(num_sessions - 1, 1)
                    )
                else:
                    day_offset = random.uniform(*sess_recency)
                session_start = now - timedelta(days=day_offset)
                duration_minutes = random.randint(1, 20)
                session_end = session_start + timedelta(minutes=duration_minutes)
                num_pages = random.randint(2, 8)
                pages_viewed = random.choices(PAGES, k=num_pages)

                # Session
                sess_db_id = _det_uuid("seed-session", user_idx, sess_idx)
                cur.execute(
                    """
                    INSERT INTO analytics.analytics_sessions
                        (id, user_id, session_id, started_at, ended_at, page_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (sess_db_id, user_id, session_id, session_start, session_end, num_pages),
                )
                sessions_created += 1

                # User agent
                device = random.choices(DEVICES, weights=DEVICE_WEIGHTS, k=1)[0]
                browser = random.choice(BROWSERS)
                browser_version = random.choice(BROWSER_VERSIONS[browser])
                os_name = random.choice(OS_MAP[device])
                raw_ua = f"Mozilla/5.0 ({os_name}) {browser}/{browser_version}"
                ua_id = _det_uuid("seed-ua", user_idx, sess_idx)
                cur.execute(
                    """
                    INSERT INTO analytics.user_agents
                        (id, session_id, raw, browser, browser_version, os, device_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (ua_id, session_id, raw_ua, browser, browser_version, os_name, device),
                )

                # Referral source (50% of sessions)
                if random.random() < 0.5:
                    source, medium = random.choice(REFERRAL_SOURCES)
                    ref_id = _det_uuid("seed-ref", user_idx, sess_idx)
                    cur.execute(
                        """
                        INSERT INTO analytics.referral_sources
                            (id, session_id, source, medium)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (ref_id, session_id, source, medium),
                    )

                # UTM tracking (30% of sessions)
                if random.random() < 0.3:
                    utm_source, utm_medium = random.choice(UTM_SOURCES)
                    utm_campaign = random.choice(UTM_CAMPAIGNS)
                    utm_id = _det_uuid("seed-utm", user_idx, sess_idx)
                    cur.execute(
                        """
                        INSERT INTO analytics.utm_tracking
                            (id, session_id, utm_source, utm_medium, utm_campaign)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (utm_id, session_id, utm_source, utm_medium, utm_campaign),
                    )

                # Page views
                for pv_idx, page_path in enumerate(pages_viewed):
                    pv_time = session_start + timedelta(
                        seconds=pv_idx * (duration_minutes * 60 / max(num_pages, 1))
                    )
                    duration_ms = random.randint(2000, 60000)
                    trigger = (
                        "navigation"
                        if pv_idx == 0
                        else random.choice(["navigation", "click", "popstate"])
                    )
                    pv_id = _det_uuid("seed-pv", user_idx, sess_idx, pv_idx)
                    cur.execute(
                        """
                        INSERT INTO analytics.page_views
                            (id, user_id, session_id, path, duration_ms, "trigger", created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (pv_id, user_id, session_id, page_path, duration_ms, trigger, pv_time),
                    )
                    pageviews_created += 1

                # Events (1-4 random events per session)
                num_events = random.randint(1, 4)
                event_types = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=num_events)
                for ev_idx, event_type in enumerate(event_types):
                    ev_time = session_start + timedelta(
                        seconds=random.randint(10, max(duration_minutes * 60, 11))
                    )
                    event_data = _event_data_for(event_type)
                    ev_id = _det_uuid("seed-ev", user_idx, sess_idx, ev_idx)
                    cur.execute(
                        """
                        INSERT INTO analytics.events
                            (id, user_id, session_id, event_type, event_data, created_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (ev_id, user_id, session_id, event_type, json.dumps(event_data), ev_time),
                    )
                    events_created += 1

            # ── 11. Targeted events for preset coverage ──────────────────
            # Use the user's most recent session for targeted events
            first_session_id = f"seed-sess-{user_idx:03d}-00"

            if profile_name == "new":
                # Ensure add_to_cart events exist (for `added_to_cart` preset)
                for tev_idx in range(2):
                    tev_id = _det_uuid("seed-target-ev", user_idx, "add_to_cart", tev_idx)
                    ev_time = _random_past(1, 7)
                    cur.execute(
                        """
                        INSERT INTO analytics.events
                            (id, user_id, session_id, event_type, event_data, created_at)
                        VALUES (%s, %s, %s, 'add_to_cart', %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (tev_id, user_id, first_session_id,
                         json.dumps(_event_data_for("add_to_cart")), ev_time),
                    )
                    events_created += 1

            elif profile_name == "at_risk":
                # Ensure checkout_abandoned events (for `checkout_dropoff` preset)
                for tev_idx in range(2):
                    tev_id = _det_uuid("seed-target-ev", user_idx, "checkout_abandoned", tev_idx)
                    ev_time = _random_past(1, 90)
                    cur.execute(
                        """
                        INSERT INTO analytics.events
                            (id, user_id, session_id, event_type, event_data, created_at)
                        VALUES (%s, %s, %s, 'checkout_abandoned', %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (tev_id, user_id, first_session_id,
                         json.dumps(_event_data_for("checkout_abandoned")), ev_time),
                    )
                    events_created += 1

            elif profile_name == "potential_loyalist":
                # 6 product_viewed events in last 5 days (for `high_intent` preset: >=5 in 7d)
                for tev_idx in range(6):
                    tev_id = _det_uuid("seed-target-ev", user_idx, "product_viewed", tev_idx)
                    ev_time = _random_past(0.1, 5)
                    cur.execute(
                        """
                        INSERT INTO analytics.events
                            (id, user_id, session_id, event_type, event_data, created_at)
                        VALUES (%s, %s, %s, 'product_viewed', %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (tev_id, user_id, first_session_id,
                         json.dumps(_event_data_for("product_viewed")), ev_time),
                    )
                    events_created += 1

            elif profile_name == "loyal":
                # 4 search_performed events in last 20 days (for `repeat_searchers` preset: >=3 in 30d)
                for tev_idx in range(4):
                    tev_id = _det_uuid("seed-target-ev", user_idx, "search_performed", tev_idx)
                    ev_time = _random_past(1, 20)
                    cur.execute(
                        """
                        INSERT INTO analytics.events
                            (id, user_id, session_id, event_type, event_data, created_at)
                        VALUES (%s, %s, %s, 'search_performed', %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (tev_id, user_id, first_session_id,
                         json.dumps(_event_data_for("search_performed")), ev_time),
                    )
                    events_created += 1

            # ── 12. Product reviews ──────────────────────────────────────
            if ordered_products and profile_name in ("champion", "loyal", "at_risk"):
                if profile_name == "champion":
                    num_reviews = random.randint(2, 4)
                    rating_range = (4, 5)
                elif profile_name == "loyal":
                    num_reviews = random.randint(1, 2)
                    rating_range = (3, 5)
                else:  # at_risk
                    num_reviews = 1
                    rating_range = (1, 3)

                # Pick unique products to review
                reviewed = set()
                for rev_idx in range(min(num_reviews, len(ordered_products))):
                    product = ordered_products[rev_idx % len(ordered_products)]
                    if product["id"] in reviewed:
                        continue
                    reviewed.add(product["id"])

                    rating = random.randint(*rating_range)
                    if rating >= 4:
                        title = random.choice(REVIEW_TITLES_POSITIVE)
                        body = random.choice(REVIEW_BODIES_POSITIVE)
                    else:
                        title = random.choice(REVIEW_TITLES_NEGATIVE)
                        body = random.choice(REVIEW_BODIES_NEGATIVE)

                    review_id = _det_uuid("seed-review", user_idx, product["id"])
                    review_date = _random_past(*recency_range)
                    cur.execute(
                        """
                        INSERT INTO ecommerce.product_reviews
                            (id, product_id, user_id, rating, title, body, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'approved', %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (review_id, product["id"], user_id, rating, title, body, review_date),
                    )
                    reviews_created += 1

            # ── 13. gdpr.cookie_preferences ──────────────────────────────
            cookie_id = _det_uuid("seed-cookie", user_idx)
            cur.execute(
                """
                INSERT INTO gdpr.cookie_preferences
                    (id, user_id, necessary, analytics, marketing, preferences)
                VALUES (%s, %s, TRUE, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    cookie_id,
                    user_id,
                    user_idx <= 70,   # analytics: 70%
                    user_idx <= 60,   # marketing: 60%
                    user_idx <= 80,   # preferences: 80%
                ),
            )

            # ── 14. marketing.user_communication_preferences ─────────────
            if comm_types and marketing_opted_in:
                for ct_name, ct_id in comm_types.items():
                    if ct_name == "newsletters":
                        allowed = True
                    elif ct_name == "promotions":
                        allowed = user_idx <= 60
                    elif ct_name == "product_updates":
                        allowed = user_idx <= 70
                    else:
                        allowed = True

                    cur.execute(
                        """
                        INSERT INTO marketing.user_communication_preferences
                            (user_id, communication_type_id, allowed)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, communication_type_id) DO UPDATE SET
                            allowed = EXCLUDED.allowed
                        """,
                        (user_id, ct_id, allowed),
                    )

    conn.commit()

    summary = {
        "users": users_created,
        "orders": orders_created,
        "payments": payments_created,
        "carts": carts_created,
        "wishlists": wishlists_created,
        "sessions": sessions_created,
        "pageviews": pageviews_created,
        "events": events_created,
        "reviews": reviews_created,
    }
    return summary


def reset_seed_users(conn):
    """Remove all seed test users and their cascade data."""
    cur = conn.cursor()
    user_pattern = f"{EMAIL_PREFIX}+test%@{EMAIL_DOMAIN}"
    print("  Deleting seed test users...")

    uid_sub = "(SELECT id FROM core.users WHERE email LIKE %s)"

    # ── New table deletions (analytics, payments, reviews, etc.) ─────
    # UTM tracking, referral sources, user agents (by session_id pattern)
    cur.execute(
        "DELETE FROM analytics.utm_tracking WHERE session_id LIKE 'seed-sess-%'"
    )
    cur.execute(
        "DELETE FROM analytics.referral_sources WHERE session_id LIKE 'seed-sess-%'"
    )
    cur.execute(
        "DELETE FROM analytics.user_agents WHERE session_id LIKE 'seed-sess-%'"
    )

    # Page views and events (by user_id)
    cur.execute(
        f"DELETE FROM analytics.page_views WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )
    cur.execute(
        f"DELETE FROM analytics.events WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Analytics sessions (by session_id pattern)
    cur.execute(
        "DELETE FROM analytics.analytics_sessions WHERE session_id LIKE 'seed-sess-%'"
    )

    # Payment records (by order pattern)
    cur.execute(
        "DELETE FROM ecommerce.payment_records WHERE order_id IN "
        "(SELECT id FROM ecommerce.orders WHERE order_number LIKE 'ORD-SEED-%')"
    )

    # Product reviews
    cur.execute(
        f"DELETE FROM ecommerce.product_reviews WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Cookie preferences
    cur.execute(
        f"DELETE FROM gdpr.cookie_preferences WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Communication preferences
    cur.execute(
        f"DELETE FROM marketing.user_communication_preferences WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # ── Existing deletions ───────────────────────────────────────────
    # Delete engagement scores
    cur.execute(
        f"DELETE FROM analytics.engagement_scores WHERE user_id IN {uid_sub}",
        (user_pattern,),
    )

    # Delete cart items then carts
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
        print(f"    Users:      {summary['users']}")
        print(f"    Orders:     {summary['orders']}")
        print(f"    Payments:   {summary['payments']}")
        print(f"    Carts:      {summary['carts']}")
        print(f"    Wishlists:  {summary['wishlists']}")
        print(f"    Sessions:   {summary['sessions']}")
        print(f"    Page Views: {summary['pageviews']}")
        print(f"    Events:     {summary['events']}")
        print(f"    Reviews:    {summary['reviews']}")
        print(
            f"\n  All users: {EMAIL_PREFIX}+test001@{EMAIL_DOMAIN} .. {EMAIL_PREFIX}+test100@{EMAIL_DOMAIN}"
        )
        print(f"  Password:  Test1234!")
        print()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
