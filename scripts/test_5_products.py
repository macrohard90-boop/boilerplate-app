#!/usr/bin/env python3
"""
Create 5 test products via API, activate them (triggering Stripe sync),
and verify sync status.

Usage:
    python scripts/test_5_products.py [--base-url http://localhost:80]

Requires seeded admin user (admin@example.com / Test1234!).
"""

import argparse
import io
import json
import sys
import time
import requests


def login(base: str) -> str:
    """Login as admin and return access token."""
    r = requests.post(f"{base}/api/auth/login", json={
        "email": "admin@example.com",
        "password": "Test1234!",
    })
    r.raise_for_status()
    return r.json()["access_token"]


def api(base: str, token: str, method: str, path: str, **kwargs):
    """Make an authenticated API call."""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.request(method, f"{base}/api{path}", headers=headers, **kwargs)
    if r.status_code == 204:
        return None
    r.raise_for_status()
    return r.json()


def upload_placeholder_image(base: str, token: str, product_id: str, color: str = "blue"):
    """Upload a small placeholder PNG image for a product."""
    # Generate a tiny 1x1 PNG (valid PNG format)
    import struct
    import zlib

    # Map color names to RGB
    colors = {
        "blue": (66, 133, 244),
        "red": (234, 67, 53),
        "green": (52, 168, 83),
        "yellow": (251, 188, 4),
        "purple": (139, 92, 246),
    }
    rgb = colors.get(color, (66, 133, 244))

    # Build a minimal 4x4 PNG
    width, height = 4, 4
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00"  # filter byte
        for _ in range(width):
            raw_data += bytes(rgb)

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", zlib.compress(raw_data))
    png += png_chunk(b"IEND", b"")

    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (f"{color}_placeholder.png", io.BytesIO(png), "image/png")}
    r = requests.post(
        f"{base}/api/ecommerce/products/{product_id}/images/upload",
        headers=headers,
        files=files,
    )
    r.raise_for_status()
    return r.json()


PRODUCTS = [
    {
        "name": "Basic T-Shirt",
        "description": "A comfortable everyday cotton t-shirt available in multiple sizes.",
        "sku": "TSH-BASIC-001",
        "base_price": 2999,
        "currency": "USD",
        "type": "physical",
        "image_color": "blue",
        "variants": [
            {"name": "Small", "sku": "TSH-BASIC-S", "stock_quantity": 50},
            {"name": "Medium", "sku": "TSH-BASIC-M", "stock_quantity": 100},
            {"name": "Large", "sku": "TSH-BASIC-L", "stock_quantity": 75},
        ],
    },
    {
        "name": "Premium Hoodie",
        "description": "Premium heavyweight hoodie with kangaroo pocket.",
        "sku": "HOD-PREM-001",
        "base_price": 7999,
        "currency": "USD",
        "type": "physical",
        "image_color": "red",
        "variants": [
            {"name": "Black", "sku": "HOD-PREM-BLK", "stock_quantity": 30, "price_override": 7999},
            {"name": "White", "sku": "HOD-PREM-WHT", "stock_quantity": 25, "price_override": 8499},
        ],
    },
    {
        "name": "Digital Wallpaper Pack",
        "description": "High-resolution desktop and mobile wallpaper collection (20 designs).",
        "sku": "DIG-WALL-001",
        "base_price": 499,
        "currency": "USD",
        "type": "digital",
        "image_color": "green",
        "variants": [],
    },
    {
        "name": "Gift Card",
        "description": "Digital gift card redeemable on any product in our store.",
        "sku": "GFT-CARD-001",
        "base_price": 2500,
        "currency": "USD",
        "type": "digital",
        "image_color": "yellow",
        "variants": [
            {"name": "$25 Gift Card", "sku": "GFT-025", "stock_quantity": 999, "price_override": 2500},
            {"name": "$50 Gift Card", "sku": "GFT-050", "stock_quantity": 999, "price_override": 5000},
            {"name": "$75 Gift Card", "sku": "GFT-075", "stock_quantity": 999, "price_override": 7500},
            {"name": "$100 Gift Card", "sku": "GFT-100", "stock_quantity": 999, "price_override": 10000},
        ],
    },
    {
        "name": "Limited Edition Sneakers",
        "description": "Exclusive limited-run sneakers with premium leather upper.",
        "sku": "SNK-LTD-001",
        "base_price": 19999,
        "currency": "USD",
        "type": "physical",
        "image_color": "purple",
        "variants": [
            {"name": "US 9", "sku": "SNK-LTD-09", "stock_quantity": 5},
            {"name": "US 10", "sku": "SNK-LTD-10", "stock_quantity": 3},
        ],
    },
]


def main():
    parser = argparse.ArgumentParser(description="Create 5 test products with Stripe sync")
    parser.add_argument("--base-url", default="http://localhost:80", help="Base URL of the app")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"Connecting to {base}...")
    token = login(base)
    print("Logged in as admin@example.com")

    results = []

    for i, spec in enumerate(PRODUCTS, 1):
        print(f"\n--- Product {i}/5: {spec['name']} ---")

        # 1. Create as draft
        product = api(base, token, "POST", "/ecommerce/products", json={
            "name": spec["name"],
            "description": spec["description"],
            "sku": spec["sku"],
            "base_price": spec["base_price"],
            "currency": spec["currency"],
            "type": spec["type"],
            "status": "draft",
        })
        pid = product["id"]
        print(f"  Created (draft): {pid}")

        # 2. Upload image
        img = upload_placeholder_image(base, token, pid, spec["image_color"])
        print(f"  Image uploaded: {img['url']}")

        # 3. Create variants
        for v_spec in spec["variants"]:
            v = api(base, token, "POST", f"/ecommerce/products/{pid}/variants", json=v_spec)
            print(f"  Variant: {v['name']} (id={v['id']})")

        # 4. Activate (triggers Stripe sync)
        product = api(base, token, "PUT", f"/ecommerce/products/{pid}", json={
            "status": "active",
        })
        print(f"  Status: {product['status']}")
        print(f"  Sync: {product['stripe_sync_status']}")

        # 5. Brief pause for sync to complete, then re-fetch
        time.sleep(0.5)
        # Re-fetch via list to get latest sync status
        all_data = api(base, token, "GET", f"/ecommerce/products?page=1&page_size=100")
        fresh = next((p for p in all_data["items"] if p["id"] == pid), product)

        results.append({
            "name": spec["name"],
            "id": pid,
            "stripe_product_id": fresh.get("stripe_product_id"),
            "stripe_price_id": fresh.get("stripe_price_id"),
            "stripe_sync_status": fresh.get("stripe_sync_status"),
            "synced_provider": fresh.get("synced_provider"),
        })

        status_emoji = "OK" if fresh.get("stripe_sync_status") == "synced" else "FAIL"
        print(f"  [{status_emoji}] stripe_product_id: {fresh.get('stripe_product_id')}")
        print(f"  [{status_emoji}] synced_provider: {fresh.get('synced_provider')}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_synced = True
    for r in results:
        synced = r["stripe_sync_status"] == "synced"
        if not synced:
            all_synced = False
        mark = "OK" if synced else "FAIL"
        print(f"  [{mark}] {r['name']}")
        print(f"        Local ID:    {r['id']}")
        print(f"        Stripe ID:   {r['stripe_product_id']}")
        print(f"        Provider:    {r['synced_provider']}")
        print()

    if all_synced:
        print("All 5 products synced successfully!")
    else:
        print("WARNING: Some products failed to sync. Check API logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
