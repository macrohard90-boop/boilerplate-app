# Phase 5: E-commerce Engine

**Estimate:** 5-6 hours
**Depends on:** Phase 2, Phase 3
**Category:** Core commerce

## Goal
Build the complete e-commerce backend: product CRUD with variants, categories, and images; shopping cart with guest and authenticated flows; order management; inventory tracking; wishlists; discount codes; and digital asset delivery. At the end of this phase, the full product catalog and shopping experience is functional via API.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 2.2 (E-commerce Schema), 2.9 (Money & Currency), 2.11 (Cart Status Lifecycle), 4 (Redis Key Architecture — cart keys), and 6 (Payment Lifecycle — Cart system) for the e-commerce specification.

## Deliverables

1. **Product CRUD** (modules/ecommerce/services/ + routes/):
   - `GET /api/products` — list products (paginated, filterable by category, status, price range, search)
   - `GET /api/products/{slug}` — product detail with variants, images, reviews, related items
   - `POST /api/products` — create product (admin/merchant only)
   - `PUT /api/products/{id}` — update product (admin/merchant only)
   - `DELETE /api/products/{id}` — soft-delete (set deleted_at)
   - Support for physical and digital product types
   - Slug generation from product name (unique, URL-safe)

2. **Product variants** (modules/ecommerce/services/):
   - CRUD for variants within a product
   - Attributes stored as JSONB (size, color, material, custom)
   - Price override: variant-specific price (INT cents), falls back to product base_price if null
   - Stock quantity per variant
   - SKU generation/validation (unique)

3. **Product images** (modules/ecommerce/services/):
   - CRUD for images per product or variant
   - Sort ordering, primary image flag
   - Alt text for accessibility/SEO
   - Image URL storage (actual file hosting deferred — store URLs only)

4. **Categories** (modules/ecommerce/services/ + routes/):
   - `GET /api/categories` — category tree (nested, 2+ levels)
   - `GET /api/categories/{slug}/products` — products in category (paginated)
   - `POST /api/categories` — create (admin only)
   - `PUT /api/categories/{id}` — update (admin only)
   - `DELETE /api/categories/{id}` — delete (admin only, check for child categories)
   - Self-referencing parent_id for hierarchy
   - Sort ordering within each level

5. **Shopping cart** (modules/ecommerce/services/ + routes/):
   - **Authenticated users**: PostgreSQL cart + cart_items tables
   - **Guest users**: Redis with session_id key, TTL 24h (`cart:guest:{session_id}`)
   - `GET /api/cart` — current cart contents with computed totals
   - `POST /api/cart/items` — add item (product_id, variant_id, quantity)
   - `PUT /api/cart/items/{item_id}` — update quantity
   - `DELETE /api/cart/items/{item_id}` — remove item
   - `POST /api/cart/discount` — apply discount code
   - Cart merge: when guest logs in, merge Redis cart into PostgreSQL cart
   - Price recorded at time of add (`unit_price_at_add`)
   - Cart status lifecycle: active → abandoned/converted/expired (per ARCHITECTURE.md §2.11)
   - Track last activity: `cart:last_active:{cart_id}` Redis key with CART_ABANDON_TIMEOUT TTL

6. **Order management** (modules/ecommerce/services/ + routes/):
   - `GET /api/orders` — list user's orders (paginated, filterable by status)
   - `GET /api/orders/{id}` — order detail with line items
   - `GET /api/admin/orders` — all orders (admin only, paginated, filterable)
   - `PUT /api/admin/orders/{id}/status` — update order status (admin only)
   - Order number generation (human-readable, sequential or prefixed)
   - Product snapshot in JSONB (preserves product state at purchase time)
   - Address storage as JSONB (shipping + billing)

7. **Inventory tracking** (modules/ecommerce/services/):
   - `inventory_records` append-only log: quantity_change, reason, reference_id
   - Stock check before cart operations (prevent adding out-of-stock items)
   - Inventory adjustment endpoint (admin only): restock, damage, correction
   - Real-time stock quantity derived from variant base stock + sum of inventory_records
   - Low stock alerts (configurable threshold — log-based for now)

8. **Wishlists** (modules/ecommerce/services/ + routes/):
   - `GET /api/wishlists` — user's wishlists
   - `POST /api/wishlists` — create wishlist (name, is_default)
   - `POST /api/wishlists/{id}/items` — add product/variant to wishlist
   - `DELETE /api/wishlists/{id}/items/{item_id}` — remove item
   - Default wishlist auto-created on first add

9. **Discount codes** (modules/ecommerce/services/):
   - Types: percentage, fixed amount (INT cents), free shipping
   - Validation: active flag, date range (valid_from/valid_until), max uses, min order amount
   - Usage tracking: increment `uses_count` on successful application
   - CRUD for admin: create, update, deactivate discount codes

10. **Product reviews** (modules/ecommerce/services/ + routes/):
    - `GET /api/products/{id}/reviews` — reviews for product (paginated)
    - `POST /api/products/{id}/reviews` — submit review (authenticated, one per user per product)
    - Review moderation: status (pending/approved/rejected), admin approval endpoint
    - Rating: 1-5 scale, computed average stored or calculated on read

11. **Digital assets** (modules/ecommerce/services/):
    - Link digital files to products
    - Download limit enforcement
    - Secure download URL generation (time-limited)
    - Access granted after order completion

12. **Pricing tiers** (modules/ecommerce/services/):
    - Quantity-based pricing: different price_per_unit at different min_quantity thresholds
    - Applied automatically during cart total calculation
    - Per-product or per-variant

## Acceptance Criteria
- [ ] Product CRUD works with pagination, filtering, and search
- [ ] Product variants store JSONB attributes and optional price override
- [ ] Categories support nested hierarchy (parent_id self-reference)
- [ ] Authenticated cart persists in PostgreSQL
- [ ] Guest cart works via Redis with 24h TTL
- [ ] Cart merge works on guest login
- [ ] Cart status lifecycle tracked (active/abandoned/converted/expired)
- [ ] `cart:last_active:{cart_id}` Redis key set on cart interaction
- [ ] Discount codes validate correctly (date range, max uses, min order)
- [ ] Order records include JSONB product snapshots
- [ ] Inventory tracking prevents overselling
- [ ] Wishlists support multiple lists per user
- [ ] Product reviews enforce one review per user per product
- [ ] Digital asset download respects download limits
- [ ] Pricing tiers apply correctly to cart totals
- [ ] All prices stored as INT cents with currency CHAR(3)
- [ ] Soft-delete works on products (deleted_at)
- [ ] All write endpoints require appropriate auth (admin/merchant)
- [ ] Slug uniqueness enforced on products and categories

## Implementation Notes
- All monetary values as INT cents + currency CHAR(3) (see ARCHITECTURE.md §2.9)
- Cart abandonment detection is time-based via Redis key expiry; background job (Phase 6/7) handles events
- Guest cart → auth cart merge: combine quantities for same product/variant, keep higher quantity
- Product search: basic ILIKE on name/description for now; full-text search can be added later
- Inventory: optimistic locking or SELECT FOR UPDATE on variant stock during checkout
- Image hosting: store URLs only — actual upload/CDN integration deferred
- Pagination: cursor-based preferred for large catalogs, offset-based acceptable for MVP

## Files to Create
- `modules/ecommerce/services/product_service.py` — Product CRUD, search, filtering
- `modules/ecommerce/services/variant_service.py` — Variant management
- `modules/ecommerce/services/category_service.py` — Category tree, product listing
- `modules/ecommerce/services/cart_service.py` — Cart operations, guest/auth, merge, abandonment
- `modules/ecommerce/services/order_service.py` — Order creation, status management
- `modules/ecommerce/services/inventory_service.py` — Stock tracking, reservation
- `modules/ecommerce/services/wishlist_service.py` — Wishlist CRUD
- `modules/ecommerce/services/discount_service.py` — Discount code validation and application
- `modules/ecommerce/services/review_service.py` — Review submission and moderation
- `modules/ecommerce/services/digital_asset_service.py` — Download management
- `modules/ecommerce/services/pricing_service.py` — Tier pricing calculation
- `modules/ecommerce/models/schemas.py` — Pydantic request/response models
- `modules/ecommerce/routes/product_routes.py` — Product and variant endpoints
- `modules/ecommerce/routes/category_routes.py` — Category endpoints
- `modules/ecommerce/routes/cart_routes.py` — Cart endpoints
- `modules/ecommerce/routes/order_routes.py` — Order endpoints
- `modules/ecommerce/routes/wishlist_routes.py` — Wishlist endpoints
- `modules/ecommerce/routes/review_routes.py` — Review endpoints
- `modules/ecommerce/routes/admin_routes.py` — Admin-only endpoints (inventory, moderation)
- `modules/ecommerce/config.py` — E-commerce module configuration
- Modified: `backend/main.py` — Mount ecommerce routes
