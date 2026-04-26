"""Phase 2: Admin Setup — bootstrap the app via API calls."""

import logging
import os
import time
from pathlib import Path

import httpx
import psycopg2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Product catalog for simulation
CATEGORIES = [
    {"name": "Electronics", "description": "Gadgets and devices"},
    {"name": "Clothing", "description": "Apparel and fashion"},
    {"name": "Accessories", "description": "Bags, watches, and more"},
    {"name": "Home", "description": "Home and kitchen essentials"},
]

PRODUCTS = [
    # One-time products
    {
        "name": "USB-C Hub",
        "description": "7-in-1 USB-C Hub with HDMI, USB 3.0, SD card reader",
        "base_price": 4999,
        "status": "active",
        "category": "Electronics",
        "variants": [
            {"name": "Silver", "stock_quantity": 50, "attributes": {"color": "silver"}},
            {"name": "Space Gray", "stock_quantity": 30, "attributes": {"color": "gray"}},
        ],
    },
    {
        "name": "Wireless Mouse",
        "description": "Ergonomic wireless mouse with Bluetooth 5.0",
        "base_price": 2999,
        "status": "active",
        "category": "Electronics",
        "variants": [
            {"name": "Black", "stock_quantity": 100, "attributes": {"color": "black"}},
            {"name": "White", "stock_quantity": 80, "attributes": {"color": "white"}},
        ],
    },
    {
        "name": "Classic T-Shirt",
        "description": "Premium cotton crew neck t-shirt",
        "base_price": 2499,
        "status": "active",
        "category": "Clothing",
        "variants": [
            {"name": "S / Black", "stock_quantity": 25, "attributes": {"size": "S", "color": "black"}},
            {"name": "M / Black", "stock_quantity": 40, "attributes": {"size": "M", "color": "black"}},
            {"name": "L / Navy", "stock_quantity": 35, "attributes": {"size": "L", "color": "navy"}},
        ],
    },
    {
        "name": "Leather Wallet",
        "description": "Genuine leather bifold wallet with RFID blocking",
        "base_price": 5999,
        "status": "active",
        "category": "Accessories",
        "variants": [
            {"name": "Brown", "stock_quantity": 20, "attributes": {"color": "brown"}},
            {"name": "Black", "stock_quantity": 15, "attributes": {"color": "black"}},
        ],
    },
    {
        "name": "Ceramic Mug Set",
        "description": "Set of 4 handcrafted ceramic mugs",
        "base_price": 3499,
        "status": "active",
        "category": "Home",
        "variants": [
            {"name": "Earth Tones", "stock_quantity": 40, "attributes": {"style": "earth"}},
            {"name": "Pastels", "stock_quantity": 30, "attributes": {"style": "pastel"}},
        ],
    },
    {
        "name": "Running Shoes",
        "description": "Lightweight running shoes with cushioned sole",
        "base_price": 12999,
        "status": "active",
        "category": "Clothing",
        "variants": [
            {"name": "Size 9 / Black", "stock_quantity": 15, "attributes": {"size": "9", "color": "black"}},
            {"name": "Size 10 / Blue", "stock_quantity": 12, "attributes": {"size": "10", "color": "blue"}},
            {"name": "Size 11 / White", "stock_quantity": 10, "attributes": {"size": "11", "color": "white"}},
        ],
    },
    # Out-of-stock product (for out_of_stock_viewed event)
    {
        "name": "Limited Edition Watch",
        "description": "Collector's edition automatic watch — SOLD OUT",
        "base_price": 19999,
        "status": "active",
        "category": "Accessories",
        "variants": [
            {"name": "Gold", "stock_quantity": 0, "attributes": {"color": "gold"}},
        ],
    },
    # Subscription products
    {
        "name": "Pro Monthly",
        "description": "Monthly subscription — unlimited access to all features",
        "base_price": 999,
        "status": "active",
        "category": "Electronics",
        "pricing_type": "recurring",
        "recurring_interval": "month",
        "recurring_interval_count": 1,
        "variants": [],
    },
]

# Placeholder image URLs
PLACEHOLDER_IMAGES = [
    "https://placehold.co/600x400/1a1a2e/e94560?text=Product",
    "https://placehold.co/600x400/16213e/0f3460?text=Product",
    "https://placehold.co/600x400/533483/e94560?text=Product",
]


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


def run(api_url: str, admin_email: str, admin_password: str) -> dict:
    """Bootstrap the app: admin user, products, categories, Stripe sync.

    Returns dict with created resource IDs and status.
    """
    result = {
        "admin_user": None,
        "categories": [],
        "products": [],
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

    # ── 4. Create categories ──
    category_map = {}  # name → id
    for cat_data in CATEGORIES:
        try:
            resp = client.post(f"{api_url}/categories", json=cat_data, headers=auth)
            if resp.status_code in (200, 201):
                cat = resp.json()
                category_map[cat_data["name"]] = cat["id"]
                result["categories"].append({"name": cat_data["name"], "id": cat["id"]})
                logger.info("Created category: %s", cat_data["name"])
            else:
                result["errors"].append(f"Category {cat_data['name']}: {resp.status_code} {resp.text}")
        except Exception as e:
            result["errors"].append(f"Category {cat_data['name']}: {e}")

    # ── 5. Create products with variants and images ──
    for prod_data in PRODUCTS:
        try:
            product_payload = {
                "name": prod_data["name"],
                "description": prod_data["description"],
                "base_price": prod_data["base_price"],
                "status": prod_data["status"],
            }
            if prod_data.get("pricing_type"):
                product_payload["pricing_type"] = prod_data["pricing_type"]
                product_payload["recurring_interval"] = prod_data.get("recurring_interval")
                product_payload["recurring_interval_count"] = prod_data.get("recurring_interval_count", 1)

            # Assign category
            cat_name = prod_data.get("category", "")
            if cat_name and cat_name in category_map:
                product_payload["category_ids"] = [category_map[cat_name]]

            resp = client.post(f"{api_url}/products", json=product_payload, headers=auth)
            if resp.status_code not in (200, 201):
                result["errors"].append(f"Product {prod_data['name']}: {resp.status_code} {resp.text}")
                continue

            product = resp.json()
            product_id = product["id"]
            product_info = {
                "name": prod_data["name"],
                "id": product_id,
                "variants": [],
                "pricing_type": prod_data.get("pricing_type", "one_time"),
            }

            # Create variants
            for var_data in prod_data.get("variants", []):
                var_resp = client.post(
                    f"{api_url}/products/{product_id}/variants",
                    json=var_data,
                    headers=auth,
                )
                if var_resp.status_code in (200, 201):
                    var = var_resp.json()
                    product_info["variants"].append({
                        "name": var_data["name"],
                        "id": var["id"],
                        "stock": var_data["stock_quantity"],
                    })

            # Add placeholder image
            img_url = PLACEHOLDER_IMAGES[len(result["products"]) % len(PLACEHOLDER_IMAGES)]
            client.post(
                f"{api_url}/products/{product_id}/images",
                json={"url": img_url, "alt_text": prod_data["name"], "is_primary": True},
                headers=auth,
            )

            result["products"].append(product_info)
            logger.info("Created product: %s (%d variants)", prod_data["name"], len(product_info["variants"]))

        except Exception as e:
            result["errors"].append(f"Product {prod_data['name']}: {e}")

    # ── 6. Wait for Stripe sync ──
    if result["products"]:
        logger.info("Waiting for Stripe catalog sync...")
        for attempt in range(30):
            time.sleep(2)
            try:
                resp = client.get(f"{api_url}/products", headers=auth)
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

    # ── 7. Store auth tokens for later phases ──
    result["admin_token"] = token
    result["admin_csrf"] = csrf

    client.close()
    return result
