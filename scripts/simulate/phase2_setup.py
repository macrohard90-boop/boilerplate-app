"""Phase 2: Admin Setup — bootstrap the app via API calls."""

import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Categories — top-level + subcategories
# ---------------------------------------------------------------------------
# Structure: {"name", "description", "children": [{"name", "description"}, ...]}
CATEGORY_TREE = [
    {
        "name": "Electronics",
        "description": "Gadgets, devices, and tech accessories",
        "children": [
            {"name": "Audio", "description": "Speakers, headphones, and earbuds"},
            {
                "name": "Cables & Chargers",
                "description": "Charging and connectivity accessories",
            },
            {
                "name": "Wearables",
                "description": "Smartwatch accessories and wearable tech",
            },
        ],
    },
    {
        "name": "Clothing",
        "description": "Apparel, shoes, and fashion",
        "children": [
            {"name": "Tops", "description": "T-shirts, shirts, and blouses"},
            {"name": "Outerwear", "description": "Jackets, coats, and hoodies"},
            {"name": "Shoes", "description": "Sneakers, boots, and casual footwear"},
            {"name": "Bottoms", "description": "Pants, shorts, and skirts"},
        ],
    },
    {
        "name": "Accessories",
        "description": "Bags, watches, wallets, and more",
        "children": [
            {"name": "Bags", "description": "Backpacks, totes, and messenger bags"},
            {"name": "Eyewear", "description": "Sunglasses and reading glasses"},
            {"name": "Watches & Jewelry", "description": "Timepieces and jewelry"},
            {
                "name": "Wallets",
                "description": "Wallets, cardholders, and money clips",
            },
        ],
    },
    {
        "name": "Home & Kitchen",
        "description": "Home essentials, decor, and kitchenware",
        "children": [
            {"name": "Kitchen", "description": "Cookware, utensils, and gadgets"},
            {"name": "Decor", "description": "Candles, art, and decorative items"},
        ],
    },
    {
        "name": "Sports & Outdoors",
        "description": "Fitness gear and outdoor equipment",
        "children": [
            {"name": "Fitness", "description": "Yoga, workout, and gym equipment"},
            {
                "name": "Hydration",
                "description": "Water bottles and hydration packs",
            },
        ],
    },
    {
        "name": "Books & Media",
        "description": "Physical books and digital content",
        "children": [
            {
                "name": "Technical Books",
                "description": "Programming, engineering, and science",
            },
            {
                "name": "Digital Downloads",
                "description": "Templates, icons, and digital assets",
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Products — 28 one-time + 2 draft + 4 subscriptions = 34 total
# Each product's "category" points to a SUBCATEGORY name from CATEGORY_TREE.
# ---------------------------------------------------------------------------
PRODUCTS = [
    # ── Audio (2 products) ──
    {
        "name": "Bluetooth Speaker",
        "description": "Waterproof portable speaker with 12-hour battery life",
        "base_price": 7999,
        "status": "active",
        "category": "Audio",
        "has_image": True,
        "variants": [
            {"name": "Black", "stock_quantity": 20, "attributes": {"color": "black"}},
            {"name": "Blue", "stock_quantity": 15, "attributes": {"color": "blue"}},
            {"name": "Red", "stock_quantity": 10, "attributes": {"color": "red"}},
        ],
    },
    {
        "name": "Noise-Canceling Headphones",
        "description": "Over-ear ANC headphones with 30-hour battery and Hi-Res audio",
        "base_price": 24999,
        "status": "active",
        "category": "Audio",
        "has_image": True,
        "variants": [
            {"name": "Black", "stock_quantity": 12, "attributes": {"color": "black"}},
            {
                "name": "Silver",
                "stock_quantity": 8,
                "attributes": {"color": "silver"},
            },
        ],
    },
    # ── Cables & Chargers (2 products) ──
    {
        "name": "USB-C Hub",
        "description": "7-in-1 USB-C Hub with HDMI, USB 3.0, SD card reader",
        "base_price": 4999,
        "status": "active",
        "category": "Cables & Chargers",
        "has_image": True,
        "variants": [
            {
                "name": "Silver",
                "stock_quantity": 50,
                "attributes": {"color": "silver"},
            },
            {
                "name": "Space Gray",
                "stock_quantity": 30,
                "attributes": {"color": "gray"},
            },
        ],
    },
    {
        "name": "Portable Charger",
        "description": "20000mAh power bank with USB-C PD and dual output",
        "base_price": 3999,
        "status": "active",
        "category": "Cables & Chargers",
        "has_image": True,
        "variants": [
            {
                "name": "Default",
                "stock_quantity": 60,
                "attributes": {"color": "black"},
            },
        ],
    },
    # ── Wearables (2 products) ──
    {
        "name": "Smart Watch Band",
        "description": "Silicone replacement band compatible with most smartwatches",
        "base_price": 1999,
        "status": "active",
        "category": "Wearables",
        "has_image": True,
        "variants": [
            {
                "name": "S / Black",
                "stock_quantity": 40,
                "attributes": {"size": "S", "color": "black"},
            },
            {
                "name": "M / Black",
                "stock_quantity": 35,
                "attributes": {"size": "M", "color": "black"},
            },
            {
                "name": "L / Black",
                "stock_quantity": 30,
                "attributes": {"size": "L", "color": "black"},
            },
            {
                "name": "L / Navy",
                "stock_quantity": 25,
                "attributes": {"size": "L", "color": "navy"},
            },
        ],
    },
    {
        "name": "Wireless Mouse",
        "description": "Ergonomic wireless mouse with Bluetooth 5.0 and silent clicks",
        "base_price": 2999,
        "status": "active",
        "category": "Wearables",
        "has_image": True,
        "variants": [
            {
                "name": "Black",
                "stock_quantity": 100,
                "attributes": {"color": "black"},
            },
            {
                "name": "White",
                "stock_quantity": 80,
                "attributes": {"color": "white"},
            },
        ],
    },
    # ── Tops (2 products) ──
    {
        "name": "Classic T-Shirt",
        "description": "Premium 100% organic cotton crew neck tee, pre-shrunk",
        "base_price": 2499,
        "status": "active",
        "category": "Tops",
        "has_image": True,
        "variants": [
            {
                "name": "S / Black",
                "stock_quantity": 25,
                "attributes": {"size": "S", "color": "black"},
            },
            {
                "name": "M / Black",
                "stock_quantity": 40,
                "attributes": {"size": "M", "color": "black"},
            },
            {
                "name": "L / Black",
                "stock_quantity": 35,
                "attributes": {"size": "L", "color": "black"},
            },
            {
                "name": "XL / Black",
                "stock_quantity": 20,
                "attributes": {"size": "XL", "color": "black"},
            },
            {
                "name": "M / Navy",
                "stock_quantity": 30,
                "attributes": {"size": "M", "color": "navy"},
            },
            {
                "name": "L / Navy",
                "stock_quantity": 28,
                "attributes": {"size": "L", "color": "navy"},
            },
        ],
    },
    {
        "name": "Henley Shirt",
        "description": "Slim-fit long-sleeve henley in soft waffle knit cotton",
        "base_price": 3499,
        "status": "active",
        "category": "Tops",
        "has_image": True,
        "variants": [
            {
                "name": "M / Charcoal",
                "stock_quantity": 20,
                "attributes": {"size": "M", "color": "charcoal"},
            },
            {
                "name": "L / Charcoal",
                "stock_quantity": 18,
                "attributes": {"size": "L", "color": "charcoal"},
            },
            {
                "name": "M / Olive",
                "stock_quantity": 15,
                "attributes": {"size": "M", "color": "olive"},
            },
        ],
    },
    # ── Outerwear (2 products) ──
    {
        "name": "Denim Jacket",
        "description": "Classic fit denim jacket with brass button hardware",
        "base_price": 8999,
        "status": "active",
        "category": "Outerwear",
        "has_image": True,
        "variants": [
            {"name": "Small", "stock_quantity": 10, "attributes": {"size": "S"}},
            {"name": "Medium", "stock_quantity": 15, "attributes": {"size": "M"}},
            {"name": "Large", "stock_quantity": 8, "attributes": {"size": "L"}},
        ],
    },
    {
        "name": "Wool Beanie",
        "description": "Merino wool knit beanie, double-layered for extra warmth",
        "base_price": 1499,
        "status": "active",
        "category": "Outerwear",
        "has_image": True,
        "variants": [
            {"name": "Gray", "stock_quantity": 50, "attributes": {"color": "gray"}},
            {
                "name": "Black",
                "stock_quantity": 45,
                "attributes": {"color": "black"},
            },
        ],
    },
    # ── Shoes (1 product + 1 draft) ──
    {
        "name": "Running Shoes",
        "description": "Lightweight running shoes with cushioned sole and breathable mesh",
        "base_price": 12999,
        "status": "active",
        "category": "Shoes",
        "has_image": True,
        "variants": [
            {
                "name": "Size 9 / Black",
                "stock_quantity": 15,
                "attributes": {"size": "9", "color": "black"},
            },
            {
                "name": "Size 10 / Blue",
                "stock_quantity": 12,
                "attributes": {"size": "10", "color": "blue"},
            },
            {
                "name": "Size 11 / White",
                "stock_quantity": 10,
                "attributes": {"size": "11", "color": "white"},
            },
        ],
    },
    # ── Bottoms (1 product) ──
    {
        "name": "Linen Shorts",
        "description": "Relaxed fit linen blend shorts with elastic waistband",
        "base_price": 3499,
        "status": "active",
        "category": "Bottoms",
        "has_image": True,
        "variants": [
            {
                "name": "S / Khaki",
                "stock_quantity": 20,
                "attributes": {"size": "S", "color": "khaki"},
            },
            {
                "name": "M / Khaki",
                "stock_quantity": 25,
                "attributes": {"size": "M", "color": "khaki"},
            },
            {
                "name": "L / Navy",
                "stock_quantity": 15,
                "attributes": {"size": "L", "color": "navy"},
            },
        ],
    },
    # ── Bags (1 product + 1 draft) ──
    {
        "name": "Canvas Backpack",
        "description": "Water-resistant waxed canvas backpack with laptop compartment",
        "base_price": 6999,
        "status": "active",
        "category": "Bags",
        "has_image": True,
        "variants": [
            {"name": "Olive", "stock_quantity": 18, "attributes": {"color": "olive"}},
            {
                "name": "Black",
                "stock_quantity": 22,
                "attributes": {"color": "black"},
            },
        ],
    },
    # ── Eyewear (1 product) ──
    {
        "name": "Aviator Sunglasses",
        "description": "Polarized UV400 aviator sunglasses with metal frame",
        "base_price": 4499,
        "status": "active",
        "category": "Eyewear",
        "has_image": True,
        "variants": [
            {
                "name": "Black",
                "stock_quantity": 30,
                "attributes": {"color": "black"},
            },
            {
                "name": "Tortoise",
                "stock_quantity": 25,
                "attributes": {"color": "tortoise"},
            },
            {
                "name": "Clear",
                "stock_quantity": 0,
                "attributes": {"color": "clear"},
            },  # OOS variant
        ],
    },
    # ── Watches & Jewelry (1 product — sold out) ──
    {
        "name": "Limited Edition Watch",
        "description": "Collector's edition automatic watch with sapphire crystal — SOLD OUT",
        "base_price": 19999,
        "status": "active",
        "category": "Watches & Jewelry",
        "has_image": False,  # No image — tests fallback
        "variants": [
            {"name": "Gold", "stock_quantity": 0, "attributes": {"color": "gold"}},
        ],
    },
    # ── Wallets (1 product) ──
    {
        "name": "Leather Wallet",
        "description": "Genuine leather bifold wallet with RFID blocking technology",
        "base_price": 5999,
        "status": "active",
        "category": "Wallets",
        "has_image": True,
        "variants": [
            {
                "name": "Brown",
                "stock_quantity": 20,
                "attributes": {"color": "brown"},
            },
            {
                "name": "Black",
                "stock_quantity": 15,
                "attributes": {"color": "black"},
            },
        ],
    },
    # ── Kitchen (3 products) ──
    {
        "name": "Ceramic Mug Set",
        "description": "Set of 4 handcrafted ceramic mugs, microwave and dishwasher safe",
        "base_price": 3499,
        "status": "active",
        "category": "Kitchen",
        "has_image": True,
        "variants": [
            {
                "name": "Earth Tones",
                "stock_quantity": 40,
                "attributes": {"style": "earth"},
            },
            {
                "name": "Pastels",
                "stock_quantity": 30,
                "attributes": {"style": "pastel"},
            },
        ],
    },
    {
        "name": "Bamboo Cutting Board",
        "description": "Extra-thick bamboo cutting board with juice groove, 18x12 inches",
        "base_price": 2999,
        "status": "active",
        "category": "Kitchen",
        "has_image": True,
        "variants": [],  # Single SKU — no variants
    },
    {
        "name": "Kitchen Timer",
        "description": "Magnetic digital kitchen timer with loud alarm and large display",
        "base_price": 1299,
        "status": "active",
        "category": "Kitchen",
        "has_image": False,  # No image — tests fallback
        "variants": [],  # Single SKU
    },
    # ── Decor (1 product) ──
    {
        "name": "Scented Candle Set",
        "description": "Hand-poured soy wax candles, 40-hour burn time each",
        "base_price": 2499,
        "status": "active",
        "category": "Decor",
        "has_image": True,
        "variants": [
            {
                "name": "Lavender",
                "stock_quantity": 50,
                "attributes": {"scent": "lavender"},
            },
            {
                "name": "Vanilla",
                "stock_quantity": 45,
                "attributes": {"scent": "vanilla"},
            },
            {
                "name": "Cedar",
                "stock_quantity": 40,
                "attributes": {"scent": "cedar"},
            },
        ],
    },
    # ── Fitness (2 products) ──
    {
        "name": "Yoga Mat",
        "description": "Non-slip TPE yoga mat, 6mm thick with carrying strap",
        "base_price": 4499,
        "status": "active",
        "category": "Fitness",
        "has_image": True,
        "variants": [
            {
                "name": "Purple",
                "stock_quantity": 25,
                "attributes": {"color": "purple"},
            },
            {"name": "Blue", "stock_quantity": 30, "attributes": {"color": "blue"}},
        ],
    },
    {
        "name": "Resistance Bands Set",
        "description": "5-piece resistance band set with door anchor and carry bag",
        "base_price": 2999,
        "status": "active",
        "category": "Fitness",
        "has_image": True,
        "variants": [],  # Single SKU
    },
    # ── Hydration (1 product) ──
    {
        "name": "Insulated Water Bottle",
        "description": "Double-wall vacuum insulated, keeps cold 24h / hot 12h",
        "base_price": 1999,
        "status": "active",
        "category": "Hydration",
        "has_image": True,
        "variants": [
            {
                "name": "500ml",
                "stock_quantity": 80,
                "attributes": {"size": "500ml"},
            },
            {
                "name": "750ml",
                "stock_quantity": 60,
                "attributes": {"size": "750ml"},
            },
            {"name": "1L", "stock_quantity": 40, "attributes": {"size": "1L"}},
        ],
    },
    # ── Technical Books (2 products) ──
    {
        "name": "Python Cookbook",
        "description": "Recipes for mastering Python 3, 500+ pages of practical examples",
        "base_price": 4999,
        "status": "active",
        "category": "Technical Books",
        "has_image": True,
        "variants": [],  # Single SKU
    },
    {
        "name": "Design Patterns Guide",
        "description": "Gang of Four patterns explained with modern language examples",
        "base_price": 3999,
        "status": "active",
        "category": "Technical Books",
        "has_image": False,  # No image — tests fallback
        "variants": [],  # Single SKU, low stock
        "_stock_override": 2,  # Will be set via SQL after creation
    },
    # ── Digital Downloads (2 products) ──
    {
        "name": "Premium Icon Pack",
        "description": "2000+ vector icons in SVG and PNG, lifetime updates",
        "base_price": 999,
        "status": "active",
        "category": "Digital Downloads",
        "has_image": True,
        "variants": [],  # Single SKU
    },
    {
        "name": "UI Template Kit",
        "description": "50 responsive website templates with source code",
        "base_price": 2499,
        "status": "active",
        "category": "Digital Downloads",
        "has_image": True,
        "variants": [],  # Single SKU
    },
    # ── Draft products (2 — should NOT appear in storefront) ──
    {
        "name": "Mystery Box",
        "description": "Surprise assortment of products — coming soon!",
        "base_price": 9999,
        "status": "draft",
        "category": "Bags",
        "has_image": False,  # No image for drafts
        "variants": [
            {
                "name": "Standard",
                "stock_quantity": 0,
                "attributes": {"tier": "standard"},
            },
        ],
    },
    {
        "name": "Limited Sneakers",
        "description": "Upcoming limited edition collaboration sneakers",
        "base_price": 14999,
        "status": "draft",
        "category": "Shoes",
        "has_image": True,
        "variants": [
            {"name": "Size 10", "stock_quantity": 0, "attributes": {"size": "10"}},
            {"name": "Size 11", "stock_quantity": 0, "attributes": {"size": "11"}},
        ],
    },
    # ── Subscriptions (4 plans) ──
    {
        "name": "Free Tier",
        "description": (
            "Basic access with limited features.\n\n"
            "- 5 projects\n- Community support\n- 1GB storage"
        ),
        "base_price": 0,
        "status": "active",
        "category": "Digital Downloads",
        "pricing_type": "recurring",
        "recurring_interval": "month",
        "recurring_interval_count": 1,
        "has_image": True,
        "variants": [],
    },
    {
        "name": "Starter Plan",
        "description": (
            "For individuals and small teams getting started.\n\n"
            "- 25 projects\n- Email support\n- 10GB storage\n- API access"
        ),
        "base_price": 999,
        "status": "active",
        "category": "Digital Downloads",
        "pricing_type": "recurring",
        "recurring_interval": "month",
        "recurring_interval_count": 1,
        "has_image": True,
        "variants": [],
    },
    {
        "name": "Pro Plan",
        "description": (
            "For growing teams that need more power.\n\n"
            "- Unlimited projects\n- Priority support\n- 100GB storage\n"
            "- API access\n- Custom integrations\n- Team collaboration"
        ),
        "base_price": 2999,
        "status": "active",
        "category": "Digital Downloads",
        "pricing_type": "recurring",
        "recurring_interval": "month",
        "recurring_interval_count": 1,
        "has_image": True,
        "variants": [],
    },
    {
        "name": "Enterprise Annual",
        "description": (
            "Best value for large organizations. Billed annually.\n\n"
            "- Everything in Pro\n- Dedicated account manager\n- 99.9% SLA\n"
            "- SSO & SAML\n- Unlimited storage\n- Custom contracts"
        ),
        "base_price": 29999,
        "status": "active",
        "category": "Digital Downloads",
        "pricing_type": "recurring",
        "recurring_interval": "year",
        "recurring_interval_count": 1,
        "has_image": True,
        "variants": [],
    },
]

# ---------------------------------------------------------------------------
# Coupons — 7 discount codes testing various restrictions
# ---------------------------------------------------------------------------
COUPONS = [
    {
        "code": "WELCOME10",
        "type": "percentage",
        "value": 10,
        "applies_to": "all",
        "stripe_duration": "once",
        "first_time_transaction_only": True,
        "description": "10% off first purchase",
    },
    {
        "code": "SAVE20",
        "type": "fixed",
        "value": 2000,  # $20.00 in cents
        "min_order_amount": 5000,  # Min $50 order
        "applies_to": "one_time",
        "stripe_duration": "once",
        "description": "$20 off orders over $50",
    },
    {
        "code": "HALFOFF",
        "type": "percentage",
        "value": 50,
        "applies_to": "one_time",
        "stripe_duration": "once",
        "restrict_to_product": "Bluetooth Speaker",  # Resolved to ID at runtime
        "description": "50% off Bluetooth Speaker only",
    },
    {
        "code": "FREESHIP",
        "type": "free_shipping",
        "value": 0,
        "applies_to": "all",
        "stripe_duration": "once",
        "description": "Free shipping on any order",
    },
    {
        "code": "SUBONLY20",
        "type": "percentage",
        "value": 20,
        "applies_to": "recurring",
        "stripe_duration": "repeating",
        "stripe_duration_in_months": 3,
        "description": "20% off subscriptions for 3 months",
    },
    {
        "code": "EXPIRED2025",
        "type": "percentage",
        "value": 15,
        "applies_to": "all",
        "stripe_duration": "once",
        "valid_until": "past",  # Special marker — set to yesterday
        "description": "Expired coupon (should fail validation)",
    },
    {
        "code": "MAXEDOUT",
        "type": "fixed",
        "value": 1000,  # $10.00
        "max_uses": 1,
        "applies_to": "all",
        "stripe_duration": "once",
        "exhaust_after_create": True,  # Special marker — set uses_count=1 via SQL
        "description": "$10 off (already fully redeemed)",
    },
]

# ---------------------------------------------------------------------------
# Image generation — color schemes per parent category, inherited by children
# ---------------------------------------------------------------------------
_PARENT_COLORS = {
    "Electronics": ("1a1a2e", "e94560"),
    "Clothing": ("533483", "e0aaff"),
    "Accessories": ("2d2d2d", "d4a574"),
    "Home & Kitchen": ("1b4332", "95d5b2"),
    "Sports & Outdoors": ("6b0f1a", "ef233c"),
    "Books & Media": ("3d2b1f", "c9a96e"),
}

# Build category → color map including subcategories (inherit parent color)
CATEGORY_COLORS: dict[str, tuple[str, str]] = {}
for _parent in CATEGORY_TREE:
    _color = _PARENT_COLORS.get(_parent["name"], ("333333", "ffffff"))
    CATEGORY_COLORS[_parent["name"]] = _color
    for _child in _parent.get("children", []):
        CATEGORY_COLORS[_child["name"]] = _color


def _placeholder_url(product_name: str, category: str, index: int = 0) -> str:
    """Generate a placeholder image URL with product name and category colors."""
    bg, fg = CATEGORY_COLORS.get(category, ("333333", "ffffff"))
    # Encode product name for URL (replace spaces with +)
    text = product_name.replace(" ", "+")
    suffix = f"+{index + 1}" if index > 0 else ""
    return f"https://placehold.co/600x400/{bg}/{fg}.png?text={text}{suffix}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run(api_url: str, admin_email: str, admin_password: str) -> dict:
    """Bootstrap the app: admin user, categories, products, coupons, Stripe sync.

    Returns dict with created resource IDs and status.
    """
    result = {
        "admin_user": None,
        "categories": [],
        "products": [],
        "coupons": [],
        "errors": [],
        "stripe_synced": False,
    }

    client = httpx.Client(timeout=30.0)

    # ── 1. Register admin user ──
    try:
        resp = client.post(
            f"{api_url}/auth/register",
            json={
                "email": admin_email,
                "password": admin_password,
                "first_name": "Sim",
                "last_name": "Admin",
            },
        )
        if resp.status_code == 201:
            data = resp.json()
            token = data["access_token"]
            csrf = data.get("csrf_token", "")
            result["admin_user"] = admin_email
            logger.info("Registered admin: %s", admin_email)
        else:
            result["errors"].append(f"Register failed: {resp.status_code} {resp.text}")
            return result
    except Exception as e:
        result["errors"].append(f"Register error: {e}")
        return result

    # ── 2. Promote to admin via direct SQL ──
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "UPDATE core.users SET role_id = "
            "(SELECT id FROM core.roles WHERE name = 'admin') "
            "WHERE email = %s",
            (admin_email,),
        )
        cur.close()
        conn.close()
        logger.info("Promoted %s to admin", admin_email)
    except Exception as e:
        result["errors"].append(f"Admin promotion failed: {e}")
        return result

    # ── 3. Re-login to get admin JWT ──
    try:
        resp = client.post(
            f"{api_url}/auth/login",
            json={"email": admin_email, "password": admin_password},
        )
        data = resp.json()
        token = data["access_token"]
        csrf = data.get("csrf_token", "")
        logger.info("Admin login successful")
    except Exception as e:
        result["errors"].append(f"Admin login failed: {e}")
        return result

    auth = {"Authorization": f"Bearer {token}", "X-Csrf-Token": csrf}

    # ── 3b. Grant analytics consent for admin (required for pageview tracking) ──
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        # Get admin user ID
        cur.execute("SELECT id FROM core.users WHERE email = %s", (admin_email,))
        admin_row = cur.fetchone()
        if admin_row:
            admin_uid = str(admin_row[0])
            # Get session ID from JWT claims
            import json
            import base64

            # Decode JWT payload (middle segment) to get session_id
            parts = token.split(".")
            if len(parts) == 3:
                # Add padding
                payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                admin_sid = payload.get("sid", "")
            else:
                admin_sid = ""

            cur.execute(
                "INSERT INTO gdpr.cookie_preferences "
                "(user_id, session_id, necessary, analytics, marketing, preferences) "
                "VALUES (%s, %s, true, true, true, true) "
                "ON CONFLICT DO NOTHING",
                (admin_uid, admin_sid),
            )
            cur.execute(
                "INSERT INTO gdpr.consent_records "
                "(user_id, consent_type, granted) "
                "VALUES (%s, 'analytics', true) "
                "ON CONFLICT DO NOTHING",
                (admin_uid,),
            )
            logger.info("Granted analytics consent for admin user")
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("Admin consent grant failed: %s", e)

    # ── Helper: simulate admin page navigation ──
    def _track_pageview(
        path: str, referrer: str | None = None, duration_ms: int = 8000
    ):
        """Record a pageview for the admin user to simulate navigation."""
        try:
            client.post(
                f"{api_url}/tracking/pageview",
                json={
                    "path": path,
                    "referrer": referrer,
                    "duration_ms": duration_ms,
                },
                headers=auth,
            )
        except Exception:
            pass  # Non-critical — don't fail setup over tracking

    # Simulate admin landing on dashboard after login
    _track_pageview("/admin", referrer="/auth/login", duration_ms=5000)

    # ── Rate-limit bypass: flush the rate-limit keys so setup isn't throttled ──
    def _flush_rate_keys():
        """Clear rate-limit keys in Redis so admin setup isn't throttled."""
        try:
            import redis as _redis

            env = _load_env()
            redis_url = os.environ.get(
                "REDIS_URL", env.get("REDIS_URL", "redis://redis:6379/0")
            )
            r = _redis.from_url(redis_url)
            keys = r.keys("rate:*")
            if keys:
                r.delete(*keys)
            r.close()
        except Exception:
            pass

    # ── 4. Create categories (parent + subcategories with parent_id) ──
    _flush_rate_keys()
    _track_pageview("/admin/catalog/categories", referrer="/admin", duration_ms=6000)
    category_map = {}  # name → id (includes both parents and children)

    for parent_data in CATEGORY_TREE:
        try:
            resp = client.post(
                f"{api_url}/ecommerce/categories",
                json={
                    "name": parent_data["name"],
                    "description": parent_data["description"],
                },
                headers=auth,
            )
            if resp.status_code in (200, 201):
                cat = resp.json()
                parent_id = cat["id"]
                category_map[parent_data["name"]] = parent_id
                result["categories"].append(
                    {"name": parent_data["name"], "id": parent_id, "parent": None}
                )
                logger.info("Created category: %s", parent_data["name"])

                # Create child categories under this parent
                for child_data in parent_data.get("children", []):
                    child_resp = client.post(
                        f"{api_url}/ecommerce/categories",
                        json={
                            "name": child_data["name"],
                            "description": child_data["description"],
                            "parent_id": parent_id,
                        },
                        headers=auth,
                    )
                    if child_resp.status_code in (200, 201):
                        child_cat = child_resp.json()
                        category_map[child_data["name"]] = child_cat["id"]
                        result["categories"].append(
                            {
                                "name": child_data["name"],
                                "id": child_cat["id"],
                                "parent": parent_data["name"],
                            }
                        )
                        logger.info(
                            "  Created subcategory: %s -> %s",
                            parent_data["name"],
                            child_data["name"],
                        )
                    else:
                        result["errors"].append(
                            f"Subcategory {child_data['name']}: "
                            f"{child_resp.status_code} {child_resp.text}"
                        )
            else:
                result["errors"].append(
                    f"Category {parent_data['name']}: "
                    f"{resp.status_code} {resp.text}"
                )
        except Exception as e:
            result["errors"].append(f"Category {parent_data['name']}: {e}")

    parent_count = len([c for c in result["categories"] if c["parent"] is None])
    child_count = len([c for c in result["categories"] if c["parent"] is not None])
    logger.info(
        "Categories done: %d parents, %d subcategories", parent_count, child_count
    )

    # ── 5. Create products with variants and images ──
    _flush_rate_keys()
    _track_pageview(
        "/admin/catalog/products",
        referrer="/admin/catalog/categories",
        duration_ms=12000,
    )
    product_name_to_id = {}  # For coupon product restrictions

    for idx, prod_data in enumerate(PRODUCTS):
        # Flush rate-limit keys every 5 products to avoid 429s
        if idx > 0 and idx % 5 == 0:
            _flush_rate_keys()
            time.sleep(0.5)

        try:
            product_payload = {
                "name": prod_data["name"],
                "description": prod_data["description"],
                "base_price": prod_data["base_price"],
                "status": prod_data["status"],
            }
            if prod_data.get("pricing_type"):
                product_payload["pricing_type"] = prod_data["pricing_type"]
                product_payload["recurring_interval"] = prod_data.get(
                    "recurring_interval"
                )
                product_payload["recurring_interval_count"] = prod_data.get(
                    "recurring_interval_count", 1
                )

            # Assign category (subcategory name → resolved ID)
            cat_name = prod_data.get("category", "")
            if cat_name and cat_name in category_map:
                product_payload["category_ids"] = [category_map[cat_name]]

            resp = client.post(
                f"{api_url}/ecommerce/products",
                json=product_payload,
                headers=auth,
            )
            if resp.status_code not in (200, 201):
                result["errors"].append(
                    f"Product {prod_data['name']}: {resp.status_code} {resp.text}"
                )
                continue

            product = resp.json()
            product_id = product["id"]
            product_name_to_id[prod_data["name"]] = product_id

            product_info = {
                "name": prod_data["name"],
                "id": product_id,
                "variants": [],
                "pricing_type": prod_data.get("pricing_type", "one_time"),
                "base_price": prod_data["base_price"],
                "status": prod_data["status"],
                "category": cat_name,
            }

            # Create variants
            for var_data in prod_data.get("variants", []):
                var_resp = client.post(
                    f"{api_url}/ecommerce/products/{product_id}/variants",
                    json=var_data,
                    headers=auth,
                )
                if var_resp.status_code in (200, 201):
                    var = var_resp.json()
                    product_info["variants"].append(
                        {
                            "name": var_data["name"],
                            "id": var["id"],
                            "stock": var_data["stock_quantity"],
                        }
                    )

            # Add placeholder images (85% of products)
            if prod_data.get("has_image", True):
                num_images = random.choice([1, 1, 1, 2])  # 75% get 1, 25% get 2
                for img_idx in range(num_images):
                    img_url = _placeholder_url(prod_data["name"], cat_name, img_idx)
                    client.post(
                        f"{api_url}/ecommerce/products/{product_id}/images",
                        json={
                            "url": img_url,
                            "alt_text": prod_data["name"],
                            "is_primary": img_idx == 0,
                        },
                        headers=auth,
                    )

            result["products"].append(product_info)
            logger.info(
                "Created product: %s (%d variants, %s, $%.2f, cat=%s)",
                prod_data["name"],
                len(product_info["variants"]),
                prod_data["status"],
                prod_data["base_price"] / 100,
                cat_name,
            )

        except Exception as e:
            result["errors"].append(f"Product {prod_data['name']}: {e}")

    # ── 6. Handle single-SKU products with stock overrides ──
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        for prod_data in PRODUCTS:
            if (
                "_stock_override" in prod_data
                and prod_data["name"] in product_name_to_id
            ):
                pid = product_name_to_id[prod_data["name"]]
                cur.execute(
                    "UPDATE ecommerce.product_variants SET stock_quantity = %s "
                    "WHERE product_id = %s::uuid",
                    (prod_data["_stock_override"], pid),
                )
                logger.info(
                    "Set stock override for %s: %d",
                    prod_data["name"],
                    prod_data["_stock_override"],
                )

        cur.close()
        conn.close()
    except Exception as e:
        result["errors"].append(f"Stock override failed: {e}")

    # ── 7. Create coupons ──
    _flush_rate_keys()
    _track_pageview(
        "/admin/catalog/coupons",
        referrer="/admin/catalog/products",
        duration_ms=8000,
    )
    for coupon_data in COUPONS:
        try:
            payload = {
                "code": coupon_data["code"],
                "type": coupon_data["type"],
                "value": coupon_data["value"],
                "applies_to": coupon_data.get("applies_to", "all"),
                "stripe_duration": coupon_data.get("stripe_duration", "once"),
            }

            if coupon_data.get("min_order_amount"):
                payload["min_order_amount"] = coupon_data["min_order_amount"]
            if coupon_data.get("max_uses"):
                payload["max_uses"] = coupon_data["max_uses"]
            if coupon_data.get("first_time_transaction_only"):
                payload["first_time_transaction_only"] = True
            if coupon_data.get("stripe_duration_in_months"):
                payload["stripe_duration_in_months"] = coupon_data[
                    "stripe_duration_in_months"
                ]
            if coupon_data.get("max_uses_per_customer"):
                payload["max_uses_per_customer"] = coupon_data["max_uses_per_customer"]

            # Product restriction
            restrict_product = coupon_data.get("restrict_to_product")
            if restrict_product and restrict_product in product_name_to_id:
                payload["product_ids"] = [product_name_to_id[restrict_product]]

            # Handle expired coupon
            if coupon_data.get("valid_until") == "past":
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
                payload["valid_until"] = yesterday

            resp = client.post(
                f"{api_url}/ecommerce/admin/discounts",
                json=payload,
                headers=auth,
            )

            if resp.status_code in (200, 201):
                coupon = resp.json()
                coupon_info = {
                    "code": coupon_data["code"],
                    "id": coupon.get("id", ""),
                    "type": coupon_data["type"],
                    "value": coupon_data["value"],
                    "description": coupon_data.get("description", ""),
                    "stripe_synced": coupon.get("stripe_sync_status") == "synced",
                }
                result["coupons"].append(coupon_info)
                logger.info(
                    "Created coupon: %s (%s)",
                    coupon_data["code"],
                    coupon_data.get("description", ""),
                )
            else:
                result["errors"].append(
                    f"Coupon {coupon_data['code']}: {resp.status_code} {resp.text}"
                )
        except Exception as e:
            result["errors"].append(f"Coupon {coupon_data['code']}: {e}")

    # ── 8. Exhaust MAXEDOUT coupon via SQL ──
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        for coupon_data in COUPONS:
            if coupon_data.get("exhaust_after_create"):
                cur.execute(
                    "UPDATE ecommerce.discount_codes SET uses_count = max_uses "
                    "WHERE UPPER(code) = %s AND max_uses IS NOT NULL",
                    (coupon_data["code"].upper(),),
                )
                logger.info("Exhausted coupon: %s", coupon_data["code"])

        cur.close()
        conn.close()
    except Exception as e:
        result["errors"].append(f"Coupon exhaustion failed: {e}")

    # Simulate admin viewing templates page
    _track_pageview(
        "/admin/marketing/templates",
        referrer="/admin/catalog/coupons",
        duration_ms=10000,
    )

    # ── 9. Archive a few products (generates admin.product_deleted events) ──
    _flush_rate_keys()
    PRODUCTS_TO_ARCHIVE = [
        "Mystery Box",       # Draft → archive (admin decided against launching)
        "Limited Sneakers",  # Draft → archive (collaboration fell through)
        "Kitchen Timer",      # Active → archive (discontinued)
    ]
    result["archived_products"] = []
    for pname in PRODUCTS_TO_ARCHIVE:
        pid = product_name_to_id.get(pname)
        if not pid:
            continue
        try:
            resp = client.delete(
                f"{api_url}/ecommerce/products/{pid}",
                headers=auth,
            )
            if resp.status_code == 204:
                result["archived_products"].append(pname)
                logger.info("Archived product: %s", pname)
            else:
                result["errors"].append(
                    f"Archive {pname}: {resp.status_code} {resp.text}"
                )
        except Exception as e:
            result["errors"].append(f"Archive {pname}: {e}")

    # ── 10. Wait for Stripe sync ──
    _flush_rate_keys()
    active_products = [p for p in result["products"] if p["status"] == "active"]
    if active_products:
        logger.info("Waiting for Stripe catalog sync...")
        for attempt in range(30):
            time.sleep(2)
            try:
                resp = client.get(f"{api_url}/ecommerce/products", headers=auth)
                products = resp.json().get("items", [])
                synced = all(
                    p.get("stripe_product_id")
                    for p in products
                    if p.get("status") == "active"
                )
                if synced and products:
                    result["stripe_synced"] = True
                    logger.info("Stripe sync complete after %ds", (attempt + 1) * 2)
                    break
            except Exception:
                pass
        else:
            result["errors"].append("Stripe sync timed out after 60s")

    # ── 11. Store auth tokens for later phases ──
    result["admin_token"] = token
    result["admin_csrf"] = csrf

    # Summary
    active_count = len([p for p in result["products"] if p["status"] == "active"])
    draft_count = len([p for p in result["products"] if p["status"] == "draft"])
    sub_count = len([p for p in result["products"] if p["pricing_type"] == "recurring"])
    archived_count = len(result.get("archived_products", []))
    logger.info(
        "Phase 2 complete: %d products (%d active, %d draft, %d subs, %d archived), "
        "%d categories (%d parents + %d subcategories), %d coupons",
        len(result["products"]),
        active_count,
        draft_count,
        sub_count,
        archived_count,
        len(result["categories"]),
        parent_count,
        child_count,
        len(result["coupons"]),
    )

    # ── Analytics summary ──
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            "SELECT event_type, count(*) FROM analytics.events "
            "WHERE event_type LIKE 'admin.%%' GROUP BY event_type ORDER BY event_type"
        )
        admin_events = dict(cur.fetchall())
        cur.execute("SELECT count(*) FROM analytics.page_views")
        page_view_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM analytics.analytics_sessions")
        session_count = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM marketing.email_templates WHERE is_builtin = true"
        )
        template_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        result["analytics_summary"] = {
            "admin_events": admin_events,
            "page_views": page_view_count,
            "sessions": session_count,
            "builtin_templates": template_count,
        }
        total_admin = sum(admin_events.values())
        logger.info(
            "Analytics: %d admin events (%s), %d page views, %d sessions, %d templates",
            total_admin,
            ", ".join(f"{k}={v}" for k, v in admin_events.items()),
            page_view_count,
            session_count,
            template_count,
        )
    except Exception as e:
        logger.warning("Analytics summary failed: %s", e)

    client.close()
    return result
