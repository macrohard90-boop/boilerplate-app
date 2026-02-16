# Phase 5: E-commerce Engine — Test Plan

**Phase:** 5 — E-commerce Engine
**Created:** 2026-02-16
**Last executed:** 2026-02-16
**Status:** All automated tests passing

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Section A: Product Catalog — Public Read](#section-a-product-catalog--public-read)
3. [Section B: Product Catalog — Admin Write](#section-b-product-catalog--admin-write)
4. [Section C: Variant CRUD](#section-c-variant-crud)
5. [Section D: Image CRUD](#section-d-image-crud)
6. [Section E: Category Endpoints](#section-e-category-endpoints)
7. [Section F: Guest Cart (Redis)](#section-f-guest-cart-redis)
8. [Section G: Authenticated Cart (PostgreSQL)](#section-g-authenticated-cart-postgresql)
9. [Section H: Cart Merge](#section-h-cart-merge)
10. [Section I: Discount Codes](#section-i-discount-codes)
11. [Section J: Orders & Checkout](#section-j-orders--checkout)
12. [Section K: Admin — Orders, Inventory, Discounts](#section-k-admin--orders-inventory-discounts)
13. [Section L: Wishlists](#section-l-wishlists)
14. [Section M: Reviews & Moderation](#section-m-reviews--moderation)
15. [Section N: Seed Data Verification](#section-n-seed-data-verification)
16. [Section O: Re-run Checklist](#section-o-re-run-checklist)

---

## 1. Prerequisites

### Environment

- Docker Compose stack running: `docker compose up -d`
- All 5 services healthy: postgres, redis, fastapi, nextjs, nginx
- Verify with: `docker compose ps`
- Seed data loaded: `DATABASE_URL="postgresql://boilerplate:change-me@localhost:5432/boilerplate_db" python3 scripts/seed.py --reset`
- Ecommerce module loaded (check FastAPI logs for `Loaded module: ecommerce`)

### Connection Details

| Service | Host (from WSL) | Port | Credentials |
|---------|-----------------|------|-------------|
| PostgreSQL | localhost | 5432 | User: `boilerplate`, Password: `change-me`, DB: `boilerplate_db` |
| Redis | localhost | 6379 | No auth |
| API (via nginx) | localhost | 80 | — |

### Test Users (from seed data)

All passwords: `Test1234!`

| Email | Role | User ID |
|-------|------|---------|
| admin@example.com | admin | b0000000-0000-0000-0000-000000000001 |
| merchant@example.com | merchant | b0000000-0000-0000-0000-000000000002 |
| customer@example.com | customer | b0000000-0000-0000-0000-000000000003 |

### Test Product IDs (from seed data)

| Product | ID | Slug |
|---------|----|------|
| Wireless Headphones | d0000000-...-000000000001 | wireless-headphones |
| USB-C Hub | d0000000-...-000000000002 | usb-c-hub |
| Classic T-Shirt | d0000000-...-000000000003 | classic-tshirt |

### Python Dependencies

```bash
pip install requests
```

---

## Section A: Product Catalog — Public Read

**What it tests:** Product listing with pagination, filtering, search; product detail with variants/images/categories.

```python
import requests

BASE = "http://localhost/api/ecommerce"

# A1: List all products (paginated)
r = requests.get(f"{BASE}/products")
assert r.status_code == 200
data = r.json()
assert data["total"] == 10, f"Expected 10 products, got {data['total']}"
assert data["page"] == 1
assert data["page_size"] == 20
assert len(data["items"]) == 10
print("A1 PASS: Product list returns 10 products")

# A2: Pagination
r = requests.get(f"{BASE}/products?page=1&page_size=3")
assert r.status_code == 200
data = r.json()
assert len(data["items"]) == 3
assert data["total_pages"] == 4  # ceil(10/3)
print("A2 PASS: Pagination works (3 per page, 4 pages)")

# A3: Filter by status
r = requests.get(f"{BASE}/products?status=active")
assert r.status_code == 200
assert r.json()["total"] == 10
print("A3 PASS: Status filter works")

# A4: Search by name
r = requests.get(f"{BASE}/products?search=headphones")
assert r.status_code == 200
assert r.json()["total"] == 1
assert r.json()["items"][0]["slug"] == "wireless-headphones"
print("A4 PASS: Search by name works")

# A5: Search by description
r = requests.get(f"{BASE}/products?search=USB-C")
assert r.status_code == 200
assert r.json()["total"] >= 1
print("A5 PASS: Search by description works")

# A6: Filter by category
r = requests.get(f"{BASE}/products?category_id=c0000000-0000-0000-0000-000000000001")
assert r.status_code == 200
assert r.json()["total"] >= 3  # Electronics has headphones, USB hub, smart watch, ebook
print(f"A6 PASS: Category filter returns {r.json()['total']} products")

# A7: Product detail by slug (with variants, images, categories)
r = requests.get(f"{BASE}/products/wireless-headphones")
assert r.status_code == 200
data = r.json()
assert data["name"] == "Wireless Headphones"
assert data["base_price"] == 7999
assert data["currency"] == "USD"
assert len(data["variants"]) == 2, f"Expected 2 variants, got {len(data['variants'])}"
assert len(data["images"]) == 3, f"Expected 3 images, got {len(data['images'])}"
assert len(data["categories"]) >= 1
print("A7 PASS: Product detail includes variants, images, categories")

# A8: Variant effective price
variants = data["variants"]
for v in variants:
    assert "effective_price" in v
    assert v["effective_price"] == 7999  # No override, uses base_price
print("A8 PASS: Variant effective_price calculated correctly")

# A9: 404 for non-existent product
r = requests.get(f"{BASE}/products/non-existent-slug")
assert r.status_code == 404
print("A9 PASS: 404 for non-existent product")

print("\n=== Section A: All 9 tests passed ===")
```

---

## Section B: Product Catalog — Admin Write

**What it tests:** Product create, update, soft-delete with proper auth requirements.

```python
import requests

BASE = "http://localhost/api"

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
assert r.status_code == 200
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# B1: Create product (admin)
r = requests.post(f"{BASE}/ecommerce/products", json={
    "name": "Test Widget B1",
    "description": "A test product for section B",
    "base_price": 999,
    "status": "active",
    "type": "physical",
    "category_ids": ["c0000000-0000-0000-0000-000000000001"],
}, headers=headers)
assert r.status_code == 201
product = r.json()
assert product["slug"] == "test-widget-b1"
assert product["base_price"] == 999
pid = product["id"]
print("B1 PASS: Product created with auto-generated slug")

# B2: Update product
r = requests.put(f"{BASE}/ecommerce/products/{pid}", json={
    "name": "Updated Widget B2",
    "base_price": 1499,
}, headers=headers)
assert r.status_code == 200
assert r.json()["slug"] == "updated-widget-b2"
assert r.json()["base_price"] == 1499
print("B2 PASS: Product updated, slug regenerated")

# B3: Soft-delete product
r = requests.delete(f"{BASE}/ecommerce/products/{pid}", headers=headers)
assert r.status_code == 204
print("B3 PASS: Product soft-deleted")

# B4: Deleted product no longer in listing
r = requests.get(f"{BASE}/ecommerce/products?search=Updated+Widget+B2")
assert r.json()["total"] == 0
print("B4 PASS: Soft-deleted product excluded from listing")

# B5: Unauthenticated create rejected
r = requests.post(f"{BASE}/ecommerce/products", json={
    "name": "Unauthorized", "base_price": 100,
})
assert r.status_code == 401
print("B5 PASS: Unauthenticated create returns 401")

# B6: Customer role cannot create
r2 = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
cust_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = requests.post(f"{BASE}/ecommerce/products", json={
    "name": "Forbidden", "base_price": 100,
}, headers=cust_headers)
assert r.status_code == 403
print("B6 PASS: Customer cannot create products (403)")

print("\n=== Section B: All 6 tests passed ===")
```

---

## Section C: Variant CRUD

**What it tests:** Create, update, delete variants with JSONB attributes and effective price.

```python
import requests

BASE = "http://localhost/api"
PRODUCT_ID = "d0000000-0000-0000-0000-000000000001"

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# C1: List variants for headphones
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants")
assert r.status_code == 200
assert len(r.json()) == 2  # Black + White
print("C1 PASS: List variants returns 2")

# C2: Create variant
r = requests.post(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants", json={
    "name": "Gold",
    "sku": "WH-001-GLD-TEST",
    "stock_quantity": 15,
    "attributes": {"color": "gold"},
}, headers=headers)
assert r.status_code == 201
variant = r.json()
assert variant["name"] == "Gold"
assert variant["effective_price"] == 7999  # Falls back to base_price
vid = variant["id"]
print("C2 PASS: Variant created with JSONB attributes")

# C3: Update variant with price override
r = requests.put(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants/{vid}", json={
    "name": "Gold Edition",
    "price_override": 8999,
}, headers=headers)
assert r.status_code == 200
assert r.json()["name"] == "Gold Edition"
assert r.json()["effective_price"] == 8999  # Now uses override
print("C3 PASS: Variant updated, effective_price uses override")

# C4: Get single variant
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants/{vid}")
assert r.status_code == 200
assert r.json()["attributes"]["color"] == "gold"
print("C4 PASS: Get single variant with attributes")

# C5: Delete variant
r = requests.delete(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants/{vid}", headers=headers)
assert r.status_code == 204
print("C5 PASS: Variant deleted")

# C6: Verify deleted
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/variants/{vid}")
assert r.status_code == 404
print("C6 PASS: Deleted variant returns 404")

print("\n=== Section C: All 6 tests passed ===")
```

---

## Section D: Image CRUD

**What it tests:** Create, update, delete images with primary flag management.

```python
import requests

BASE = "http://localhost/api"
PRODUCT_ID = "d0000000-0000-0000-0000-000000000001"

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# D1: List images for headphones
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/images")
assert r.status_code == 200
images = r.json()
assert len(images) == 3  # main + side + white variant
primary_count = sum(1 for i in images if i["is_primary"])
assert primary_count == 1
print("D1 PASS: List images returns 3, one primary")

# D2: Create image
r = requests.post(f"{BASE}/ecommerce/products/{PRODUCT_ID}/images", json={
    "url": "/images/test-image.jpg",
    "alt_text": "Test image",
    "is_primary": False,
    "sort_order": 99,
}, headers=headers)
assert r.status_code == 201
img = r.json()
img_id = img["id"]
print("D2 PASS: Image created")

# D3: Update image to primary (clears others)
r = requests.put(f"{BASE}/ecommerce/products/{PRODUCT_ID}/images/{img_id}", json={
    "is_primary": True,
}, headers=headers)
assert r.status_code == 200
assert r.json()["is_primary"] is True
print("D3 PASS: Image updated to primary")

# D4: Delete image
r = requests.delete(f"{BASE}/ecommerce/products/{PRODUCT_ID}/images/{img_id}", headers=headers)
assert r.status_code == 204
print("D4 PASS: Image deleted")

print("\n=== Section D: All 4 tests passed ===")
```

---

## Section E: Category Endpoints

**What it tests:** Category tree, category products, admin CRUD.

```python
import requests

BASE = "http://localhost/api"

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# E1: List categories as tree
r = requests.get(f"{BASE}/ecommerce/categories")
assert r.status_code == 200
tree = r.json()
assert len(tree) == 3  # 3 root categories
electronics = next(c for c in tree if c["slug"] == "electronics")
assert len(electronics["children"]) == 1  # Smartphones subcategory
print("E1 PASS: Category tree with 3 roots, nested children")

# E2: Category products
r = requests.get(f"{BASE}/ecommerce/categories/electronics/products")
assert r.status_code == 200
data = r.json()
assert data["total"] >= 3
print(f"E2 PASS: Electronics has {data['total']} products")

# E3: Category products pagination
r = requests.get(f"{BASE}/ecommerce/categories/electronics/products?page_size=1")
assert r.status_code == 200
assert len(r.json()["items"]) == 1
print("E3 PASS: Category products pagination works")

# E4: Create category
r = requests.post(f"{BASE}/ecommerce/categories", json={
    "name": "Test Category E4",
    "sort_order": 99,
}, headers=headers)
assert r.status_code == 201
cat = r.json()
assert cat["slug"] == "test-category-e4"
cid = cat["id"]
print("E4 PASS: Category created with auto slug")

# E5: Update category
r = requests.put(f"{BASE}/ecommerce/categories/{cid}", json={
    "name": "Updated Category E5",
}, headers=headers)
assert r.status_code == 200
assert r.json()["slug"] == "updated-category-e5"
print("E5 PASS: Category updated, slug regenerated")

# E6: Delete category
r = requests.delete(f"{BASE}/ecommerce/categories/{cid}", headers=headers)
assert r.status_code == 204
print("E6 PASS: Category deleted")

# E7: 404 for non-existent category products
r = requests.get(f"{BASE}/ecommerce/categories/nonexistent/products")
assert r.status_code == 404
print("E7 PASS: 404 for non-existent category")

print("\n=== Section E: All 7 tests passed ===")
```

---

## Section F: Guest Cart (Redis)

**What it tests:** Guest cart operations via X-Session-ID header, stored in Redis with 24h TTL.

```python
import requests

BASE = "http://localhost/api/ecommerce"
SESSION_ID = "test-guest-session-F"
headers = {"X-Session-ID": SESSION_ID}

# F1: Empty guest cart
r = requests.get(f"{BASE}/cart", headers=headers)
assert r.status_code == 200
assert r.json()["item_count"] == 0
assert r.json()["total"] == 0
print("F1 PASS: Empty guest cart")

# F2: Add item to guest cart
r = requests.post(f"{BASE}/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000001",
    "variant_id": "e0000000-0000-0000-0000-000000000001",
    "quantity": 2,
}, headers=headers)
assert r.status_code == 200
cart = r.json()
assert cart["item_count"] == 2
assert cart["subtotal"] == 15998  # 7999 * 2
print("F2 PASS: Guest add item, subtotal correct")

# F3: Add second item
r = requests.post(f"{BASE}/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000002",
    "variant_id": "e0000000-0000-0000-0000-000000000011",
    "quantity": 1,
}, headers=headers)
assert r.status_code == 200
assert r.json()["item_count"] == 3  # 2 + 1
print("F3 PASS: Second item added")

# F4: Update quantity
r = requests.put(
    f"{BASE}/cart/items/d0000000-0000-0000-0000-000000000001_e0000000-0000-0000-0000-000000000001",
    json={"quantity": 1},
    headers=headers,
)
assert r.status_code == 200
assert r.json()["item_count"] == 2  # 1 + 1
print("F4 PASS: Guest item quantity updated")

# F5: Remove item
r = requests.delete(
    f"{BASE}/cart/items/d0000000-0000-0000-0000-000000000002_e0000000-0000-0000-0000-000000000011",
    headers=headers,
)
assert r.status_code == 200
assert r.json()["item_count"] == 1
print("F5 PASS: Guest item removed")

# F6: Error adding without session
r = requests.post(f"{BASE}/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000001",
    "variant_id": "e0000000-0000-0000-0000-000000000001",
    "quantity": 1,
})
assert r.status_code == 400
print("F6 PASS: No session or auth returns 400")

# F7: Error adding non-existent product
r = requests.post(f"{BASE}/cart/items", json={
    "product_id": "00000000-0000-0000-0000-000000000099",
    "variant_id": "00000000-0000-0000-0000-000000000099",
    "quantity": 1,
}, headers=headers)
assert r.status_code == 400
print("F7 PASS: Non-existent product returns 400")

print("\n=== Section F: All 7 tests passed ===")
```

---

## Section G: Authenticated Cart (PostgreSQL)

**What it tests:** Cart CRUD for logged-in user, stored in PostgreSQL.

```python
import requests

BASE = "http://localhost/api"

# Login as customer
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
assert r.status_code == 200
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# G1: Empty auth cart
r = requests.get(f"{BASE}/ecommerce/cart", headers=headers)
assert r.status_code == 200
assert r.json()["item_count"] == 0
print("G1 PASS: Empty auth cart")

# G2: Add item
r = requests.post(f"{BASE}/ecommerce/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000003",
    "variant_id": "e0000000-0000-0000-0000-000000000004",
    "quantity": 3,
}, headers=headers)
assert r.status_code == 200
assert r.json()["item_count"] == 3
assert r.json()["subtotal"] == 7497  # 2499 * 3
print("G2 PASS: Auth add item, subtotal correct")

# G3: Add same item again (should increment)
r = requests.post(f"{BASE}/ecommerce/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000003",
    "variant_id": "e0000000-0000-0000-0000-000000000004",
    "quantity": 2,
}, headers=headers)
assert r.status_code == 200
assert r.json()["item_count"] == 5  # 3 + 2
print("G3 PASS: Adding same item increments quantity")

# G4: Update quantity
r = requests.put(
    f"{BASE}/ecommerce/cart/items/d0000000-0000-0000-0000-000000000003_e0000000-0000-0000-0000-000000000004",
    json={"quantity": 1},
    headers=headers,
)
assert r.status_code == 200
assert r.json()["item_count"] == 1
print("G4 PASS: Auth item quantity updated")

# G5: Remove item
r = requests.delete(
    f"{BASE}/ecommerce/cart/items/d0000000-0000-0000-0000-000000000003_e0000000-0000-0000-0000-000000000004",
    headers=headers,
)
assert r.status_code == 200
assert r.json()["item_count"] == 0
print("G5 PASS: Auth item removed")

print("\n=== Section G: All 5 tests passed ===")
```

---

## Section H: Cart Merge

**What it tests:** Merging a guest Redis cart into an authenticated PostgreSQL cart on login.

```python
import requests

BASE = "http://localhost/api"
SESSION_ID = "test-merge-session-H"

# H1: Build a guest cart
gh = {"X-Session-ID": SESSION_ID}
r = requests.post(f"{BASE}/ecommerce/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000001",
    "variant_id": "e0000000-0000-0000-0000-000000000001",
    "quantity": 2,
}, headers=gh)
assert r.status_code == 200
print("H1 PASS: Guest cart created with 2 headphones")

# H2: Add a different item to auth cart
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
ah = {"Authorization": f"Bearer {token}"}

r = requests.post(f"{BASE}/ecommerce/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000010",
    "variant_id": "e0000000-0000-0000-0000-000000000016",
    "quantity": 1,
}, headers=ah)
assert r.status_code == 200
print("H2 PASS: Auth cart has 1 mug")

# H3: Merge guest into auth
r = requests.post(f"{BASE}/ecommerce/cart/merge", headers={**ah, "X-Session-ID": SESSION_ID})
assert r.status_code == 200
cart = r.json()
assert cart["item_count"] == 3  # 2 headphones + 1 mug
print(f"H3 PASS: Merge successful, {cart['item_count']} items")

# H4: Guest cart should be empty after merge
r = requests.get(f"{BASE}/ecommerce/cart", headers=gh)
assert r.json()["item_count"] == 0
print("H4 PASS: Guest cart empty after merge")

# H5: Merge requires auth
r = requests.post(f"{BASE}/ecommerce/cart/merge", headers={"X-Session-ID": SESSION_ID})
assert r.status_code == 401
print("H5 PASS: Merge requires authentication")

# Cleanup: remove items for subsequent tests
for item_key in [
    "d0000000-0000-0000-0000-000000000001_e0000000-0000-0000-0000-000000000001",
    "d0000000-0000-0000-0000-000000000010_e0000000-0000-0000-0000-000000000016",
]:
    requests.delete(f"{BASE}/ecommerce/cart/items/{item_key}", headers=ah)

print("\n=== Section H: All 5 tests passed ===")
```

---

## Section I: Discount Codes

**What it tests:** Discount application to cart, validation rules (type, min order, max uses).

```python
import requests

BASE = "http://localhost/api/ecommerce"
SESSION_ID = "test-discount-session-I"
headers = {"X-Session-ID": SESSION_ID}

# Build a guest cart with enough for discount
r = requests.post(f"{BASE}/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000001",
    "variant_id": "e0000000-0000-0000-0000-000000000001",
    "quantity": 2,
}, headers=headers)
assert r.status_code == 200
subtotal = r.json()["subtotal"]
print(f"Setup: Cart subtotal = {subtotal} cents")

# I1: Apply percentage discount
r = requests.post(f"{BASE}/cart/discount", json={"code": "WELCOME10"}, headers=headers)
assert r.status_code == 200
cart = r.json()
expected_discount = int(subtotal * 10 / 100)
assert cart["discount_amount"] == expected_discount
assert cart["discount_code"] == "WELCOME10"
assert cart["total"] == subtotal - expected_discount
print(f"I1 PASS: WELCOME10 applied, discount = {cart['discount_amount']} cents")

# I2: Remove discount
r = requests.delete(f"{BASE}/cart/discount", headers=headers)
assert r.status_code == 200
assert r.json()["discount_amount"] == 0
assert r.json()["discount_code"] is None
print("I2 PASS: Discount removed")

# I3: Apply fixed discount (SAVE5 = $5 off, min $25)
r = requests.post(f"{BASE}/cart/discount", json={"code": "SAVE5"}, headers=headers)
assert r.status_code == 200
assert r.json()["discount_amount"] == 500
print("I3 PASS: SAVE5 applied, $5 off")

# I4: Invalid discount code
r = requests.delete(f"{BASE}/cart/discount", headers=headers)
r = requests.post(f"{BASE}/cart/discount", json={"code": "INVALID"}, headers=headers)
assert r.status_code == 400
print("I4 PASS: Invalid code returns 400")

print("\n=== Section I: All 4 tests passed ===")
```

---

## Section J: Orders & Checkout

**What it tests:** Creating an order from cart (with stock reservation), listing orders, order detail.

```python
import requests

BASE = "http://localhost/api"

# Login as customer
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# Add item to cart for checkout
r = requests.post(f"{BASE}/ecommerce/cart/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000002",
    "variant_id": "e0000000-0000-0000-0000-000000000011",
    "quantity": 1,
}, headers=headers)
assert r.status_code == 200
print("Setup: Item added to cart")

# J1: Create order (checkout)
r = requests.post(f"{BASE}/ecommerce/orders", json={
    "shipping_address": {"street": "123 Test St", "city": "Test City", "zip": "12345"},
    "billing_address": {"street": "123 Test St", "city": "Test City", "zip": "12345"},
}, headers=headers)
assert r.status_code == 201
order = r.json()
assert order["status"] == "pending"
assert order["order_number"].startswith("ORD-")
assert order["total"] > 0
order_id = order["id"]
print(f"J1 PASS: Order created: {order['order_number']}, total = {order['total']} cents")

# J2: List orders (should include seeded order + new one)
r = requests.get(f"{BASE}/ecommerce/orders", headers=headers)
assert r.status_code == 200
assert r.json()["total"] >= 2  # Seeded + new
print(f"J2 PASS: Order list shows {r.json()['total']} orders")

# J3: Get order detail with items
r = requests.get(f"{BASE}/ecommerce/orders/{order_id}", headers=headers)
assert r.status_code == 200
detail = r.json()
assert len(detail["items"]) >= 1
assert "product_snapshot" in detail["items"][0]
print(f"J3 PASS: Order detail has {len(detail['items'])} items with product snapshots")

# J4: Cart should be empty after checkout (converted)
r = requests.get(f"{BASE}/ecommerce/cart", headers=headers)
assert r.json()["item_count"] == 0
print("J4 PASS: Cart empty after checkout (status = converted)")

# J5: Checkout with empty cart fails
r = requests.post(f"{BASE}/ecommerce/orders", json={}, headers=headers)
assert r.status_code == 400
print("J5 PASS: Checkout with empty cart returns 400")

# J6: Other user cannot see this order
r2 = requests.post(f"{BASE}/auth/login", json={"email": "merchant@example.com", "password": "Test1234!"})
other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = requests.get(f"{BASE}/ecommerce/orders/{order_id}", headers=other_headers)
assert r.status_code == 404
print("J6 PASS: Other user cannot access order (404)")

print("\n=== Section J: All 6 tests passed ===")
```

---

## Section K: Admin — Orders, Inventory, Discounts

**What it tests:** Admin-only endpoints for order management, inventory adjustments, and discount CRUD.

```python
import requests

BASE = "http://localhost/api"

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
csrf = r.json().get("csrf_token", "")
headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

# K1: Admin list all orders
r = requests.get(f"{BASE}/ecommerce/admin/orders", headers=headers)
assert r.status_code == 200
assert r.json()["total"] >= 1
order_id = r.json()["items"][0]["id"]
print(f"K1 PASS: Admin sees {r.json()['total']} orders")

# K2: Admin get order detail
r = requests.get(f"{BASE}/ecommerce/admin/orders/{order_id}", headers=headers)
assert r.status_code == 200
assert "items" in r.json()
print("K2 PASS: Admin order detail includes items")

# K3: Admin update order status
r = requests.put(f"{BASE}/ecommerce/admin/orders/{order_id}/status", json={"status": "processing"}, headers=headers)
assert r.status_code == 200
assert r.json()["status"] == "processing"
print("K3 PASS: Order status updated to processing")

# K4: Inventory adjustment
r = requests.post(f"{BASE}/ecommerce/admin/inventory/e0000000-0000-0000-0000-000000000001/adjust", json={
    "quantity_change": 20,
    "reason": "test restock",
}, headers=headers)
assert r.status_code == 200
record = r.json()
assert record["quantity_change"] == 20
assert record["reason"] == "test restock"
print("K4 PASS: Inventory adjusted +20")

# K5: Low stock report
r = requests.get(f"{BASE}/ecommerce/admin/inventory/low-stock?threshold=30", headers=headers)
assert r.status_code == 200
low_stock = r.json()
assert isinstance(low_stock, list)
print(f"K5 PASS: Low stock report returns {len(low_stock)} items below threshold 30")

# K6: Admin list discounts
r = requests.get(f"{BASE}/ecommerce/admin/discounts", headers=headers)
assert r.status_code == 200
assert r.json()["total"] >= 3  # 3 seeded
print(f"K6 PASS: {r.json()['total']} discounts listed")

# K7: Admin create discount
r = requests.post(f"{BASE}/ecommerce/admin/discounts", json={
    "code": "TESTK7",
    "type": "percentage",
    "value": 15,
    "min_order_amount": 1000,
}, headers=headers)
assert r.status_code == 201
assert r.json()["code"] == "TESTK7"
did = r.json()["id"]
print("K7 PASS: Discount TESTK7 created")

# K8: Admin update discount
r = requests.put(f"{BASE}/ecommerce/admin/discounts/{did}", json={"value": 20}, headers=headers)
assert r.status_code == 200
assert r.json()["value"] == 20
print("K8 PASS: Discount value updated to 20")

# K9: Admin deactivate discount
r = requests.delete(f"{BASE}/ecommerce/admin/discounts/{did}", headers=headers)
assert r.status_code == 204
print("K9 PASS: Discount deactivated")

# K10: Customer cannot access admin endpoints
r2 = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
cust_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = requests.get(f"{BASE}/ecommerce/admin/orders", headers=cust_headers)
assert r.status_code == 403
print("K10 PASS: Customer blocked from admin endpoints (403)")

print("\n=== Section K: All 10 tests passed ===")
```

---

## Section L: Wishlists

**What it tests:** Wishlist creation, adding/removing items, multiple wishlists, default wishlist.

```python
import requests

BASE = "http://localhost/api"

# Login as customer
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# L1: List wishlists (should have seeded default)
r = requests.get(f"{BASE}/ecommerce/wishlists", headers=headers)
assert r.status_code == 200
wishlists = r.json()
assert len(wishlists) >= 1
default_wl = next((w for w in wishlists if w["is_default"]), None)
assert default_wl is not None
print(f"L1 PASS: {len(wishlists)} wishlist(s), default exists")

# L2: Seeded wishlist has 2 items
assert len(default_wl["items"]) == 2
print("L2 PASS: Default wishlist has 2 seeded items")

# L3: Create new wishlist
r = requests.post(f"{BASE}/ecommerce/wishlists", json={"name": "Holiday Ideas"}, headers=headers)
assert r.status_code == 201
new_wl = r.json()
assert new_wl["name"] == "Holiday Ideas"
assert new_wl["is_default"] is False
wid = new_wl["id"]
print("L3 PASS: Non-default wishlist created")

# L4: Add item to wishlist
r = requests.post(f"{BASE}/ecommerce/wishlists/{wid}/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000005",
}, headers=headers)
assert r.status_code == 200
assert len(r.json()["items"]) == 1
print("L4 PASS: Item added to wishlist")

# L5: Add duplicate (should be idempotent via ON CONFLICT)
r = requests.post(f"{BASE}/ecommerce/wishlists/{wid}/items", json={
    "product_id": "d0000000-0000-0000-0000-000000000005",
}, headers=headers)
assert r.status_code == 200
assert len(r.json()["items"]) == 1  # Still 1, not 2
print("L5 PASS: Duplicate add is idempotent")

# L6: Remove item from wishlist
r = requests.delete(
    f"{BASE}/ecommerce/wishlists/{wid}/items/d0000000-0000-0000-0000-000000000005",
    headers=headers,
)
assert r.status_code == 204
print("L6 PASS: Item removed from wishlist")

# L7: Delete non-default wishlist
r = requests.delete(f"{BASE}/ecommerce/wishlists/{wid}", headers=headers)
assert r.status_code == 204
print("L7 PASS: Non-default wishlist deleted")

# L8: Cannot delete default wishlist
r = requests.delete(f"{BASE}/ecommerce/wishlists/{default_wl['id']}", headers=headers)
assert r.status_code == 400
print("L8 PASS: Cannot delete default wishlist (400)")

# L9: Unauthenticated access rejected
r = requests.get(f"{BASE}/ecommerce/wishlists")
assert r.status_code == 401
print("L9 PASS: Wishlists require auth (401)")

print("\n=== Section L: All 9 tests passed ===")
```

---

## Section M: Reviews & Moderation

**What it tests:** Review submission (one per user per product), public listing, admin moderation.

```python
import requests

BASE = "http://localhost/api"
PRODUCT_ID = "d0000000-0000-0000-0000-000000000006"  # Plant Pot Set (no existing reviews)

# Login as customer
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
cust_headers = {"Authorization": f"Bearer {token}"}

# Login as admin
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
admin_token = r.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}

# M1: List reviews for product (public, only approved)
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews")
assert r.status_code == 200
assert r.json()["total"] == 0  # No reviews yet for plant pots
print("M1 PASS: No reviews for plant pots")

# M2: List reviews for headphones (seeded, approved)
r = requests.get(f"{BASE}/ecommerce/products/d0000000-0000-0000-0000-000000000001/reviews")
assert r.status_code == 200
assert r.json()["total"] == 2
print("M2 PASS: Headphones have 2 approved reviews")

# M3: Submit review
r = requests.post(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews", json={
    "rating": 5,
    "title": "Beautiful pots",
    "body": "Perfect for my succulents!",
}, headers=cust_headers)
assert r.status_code == 201
review = r.json()
assert review["status"] == "pending"
assert review["rating"] == 5
review_id = review["id"]
print("M3 PASS: Review submitted with status=pending")

# M4: Duplicate review rejected
r = requests.post(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews", json={
    "rating": 4,
    "title": "Duplicate",
}, headers=cust_headers)
assert r.status_code == 409
print("M4 PASS: Duplicate review returns 409")

# M5: Pending review not visible in public listing
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews")
assert r.json()["total"] == 0  # Still 0 (pending, not approved)
print("M5 PASS: Pending review not in public listing")

# M6: Admin moderates review to approved
r = requests.put(f"{BASE}/ecommerce/admin/reviews/{review_id}/moderate", json={
    "status": "approved",
}, headers=admin_headers)
assert r.status_code == 200
assert r.json()["status"] == "approved"
print("M6 PASS: Admin approved review")

# M7: Approved review now visible
r = requests.get(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews")
assert r.json()["total"] == 1
print("M7 PASS: Approved review visible in public listing")

# M8: Unauthenticated review rejected
r = requests.post(f"{BASE}/ecommerce/products/{PRODUCT_ID}/reviews", json={
    "rating": 3, "title": "Anon",
})
assert r.status_code == 401
print("M8 PASS: Unauthenticated review returns 401")

print("\n=== Section M: All 8 tests passed ===")
```

---

## Section N: Seed Data Verification

**What it tests:** All enriched seed data loaded correctly after `--reset`.

```python
import requests

BASE = "http://localhost/api"

# Login as customer for auth endpoints
r = requests.post(f"{BASE}/auth/login", json={"email": "customer@example.com", "password": "Test1234!"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# N1: 10 products
r = requests.get(f"{BASE}/ecommerce/products")
assert r.json()["total"] == 10
print("N1 PASS: 10 products seeded")

# N2: 3 root categories with children
r = requests.get(f"{BASE}/ecommerce/categories")
tree = r.json()
assert len(tree) == 3
electronics = next(c for c in tree if c["slug"] == "electronics")
assert len(electronics["children"]) == 1
print("N2 PASS: 3 root categories, electronics has 1 child")

# N3: Headphones have 2 variants and 3 images
r = requests.get(f"{BASE}/ecommerce/products/wireless-headphones")
data = r.json()
assert len(data["variants"]) == 2
assert len(data["images"]) == 3
print("N3 PASS: Headphones: 2 variants, 3 images")

# N4: 2 approved reviews for headphones
r = requests.get(f"{BASE}/ecommerce/products/d0000000-0000-0000-0000-000000000001/reviews")
assert r.json()["total"] == 2
print("N4 PASS: 2 headphone reviews")

# N5: Customer has seeded order
r = requests.get(f"{BASE}/ecommerce/orders", headers=headers)
orders = r.json()
assert orders["total"] >= 1
seeded = next((o for o in orders["items"] if o["order_number"] == "ORD-20260101-SEED1"), None)
assert seeded is not None
assert seeded["status"] == "completed"
print("N5 PASS: Seeded order exists (completed)")

# N6: Customer has seeded wishlist with 2 items
r = requests.get(f"{BASE}/ecommerce/wishlists", headers=headers)
wishlists = r.json()
default = next((w for w in wishlists if w["is_default"]), None)
assert default is not None
assert len(default["items"]) == 2
print("N6 PASS: Seeded wishlist with 2 items")

# N7: 3 discount codes
r2 = requests.post(f"{BASE}/auth/login", json={"email": "admin@example.com", "password": "Test1234!"})
admin_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = requests.get(f"{BASE}/ecommerce/admin/discounts", headers=admin_headers)
assert r.json()["total"] >= 3
print(f"N7 PASS: {r.json()['total']} discount codes")

print("\n=== Section N: All 7 tests passed ===")
```

---

## Section O: Re-run Checklist

Before re-running tests after code changes:

1. **Reset seed data:**
   ```bash
   DATABASE_URL="postgresql://boilerplate:change-me@localhost:5432/boilerplate_db" python3 scripts/seed.py --reset
   ```

2. **Rebuild FastAPI:**
   ```bash
   docker compose up -d --build fastapi
   ```

3. **Wait for startup:**
   ```bash
   sleep 3 && docker compose logs fastapi --tail=5
   ```
   Verify: `Loaded modules: ['auth', 'ecommerce']` and `Application startup complete.`

4. **Clear Redis guest carts** (if cart tests fail on re-run):
   ```bash
   redis-cli -h localhost KEYS "cart:guest:*" | xargs redis-cli -h localhost DEL
   ```

5. **Run sections in order:** A through N. Some sections create data that later sections depend on (e.g., Section J creates orders that Section K manages).

### Expected results

| Section | Tests | Description |
|---------|-------|-------------|
| A | 9 | Product catalog public reads |
| B | 6 | Product admin writes |
| C | 6 | Variant CRUD |
| D | 4 | Image CRUD |
| E | 7 | Categories |
| F | 7 | Guest cart (Redis) |
| G | 5 | Auth cart (PostgreSQL) |
| H | 5 | Cart merge |
| I | 4 | Discount codes |
| J | 6 | Orders & checkout |
| K | 10 | Admin endpoints |
| L | 9 | Wishlists |
| M | 8 | Reviews & moderation |
| N | 7 | Seed data verification |
| **Total** | **93** | |
