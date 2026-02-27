# Changelog

All notable changes to the boilerplate application after the initial 10-phase build are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Claude Code should read this file when returning to modify previously completed work.

---

## [Unreleased]
_Changes staged but not yet tagged._

## [2026-02-27] - Category Management, Product Images & Storefront Fixes

### Added
- **Admin category management** — full CRUD under Product Catalog > Categories tab with tree-indented table, create/edit/delete modals, product count display
- **Safe category deletion** — blocks delete if category has products or subcategories (409 Conflict), with descriptive error messages
- **Category picker in ProductForm** — pill-style toggle buttons grouped by parent/child; selecting a subcategory auto-selects its parent
- **Product images in list API** — `ProductResponse` now includes `images` (product-level) and `categories` via batch subqueries (no N+1)
- **Category filter on products browse page** — horizontal pill bar (All + root categories) filters products by `category_id`
- **Dynamic header navigation** — replaces hardcoded category links with live data from API (root categories, max 5)

### Changed
- **ProductCard category badge** — moved from image overlay (poor contrast on light images) to info section as uppercase purple text above product name
- **ProductForm** — removed `type` dropdown (Physical/Digital); field drove zero behavior, `pricing_type` handles all real logic. Backend defaults to `"physical"`
- **Status full-width** — Status dropdown now takes full row width since Type was removed

### Fixed
- **Search bar icon overlap** — `.input-glass` padding overrode Tailwind's `pl-10`; fixed with `!pl-10` important modifier
- **Products page search broken** — frontend sent `q` param but backend expects `search`; corrected to `params.set("search", search)`
- **Draft products visible on storefront** — category page (`/categories/[slug]`) missing `status=active` filter; product detail page now returns "not found" for non-active products
- **Category products missing images** — `get_category_products()` now calls `_attach_images_and_categories()` like the main product list

### Technical Details
- `ProductImageSummary` (url + is_primary) and `ProductCategorySummary` (id + name + slug) lightweight schemas for list endpoints
- `_attach_images_and_categories()` in product_service.py batch-fetches via `ANY(:pids)` — single query per data type for entire page
- Category delete checks both `product_categories` junction table and `categories` self-reference before allowing deletion
- `CategoryForm.tsx` prevents circular parent references via `getDescendantIds()` exclusion in parent dropdown

## [2026-02-26] - Variant-Level Images & Admin UX Improvements

### Added
- **Variant-level image support** — images can be assigned to specific variants via `variant_id` on the upload endpoint and admin ImageUploader
- **Cart item images** — `image_url` field on `CartItemResponse` with variant→product fallback via COALESCE subquery (works for both auth and guest carts)
- **Variant-aware storefront gallery** — selecting a variant with images swaps the gallery; falls back to product-level images
- **Checkout item images** — cart items in checkout sidebar show product/variant images instead of grey placeholders
- **Styled variant delete modal** — replaces native `window.confirm()` with themed Modal component matching product delete UX
- **Duplicate SKU validation** — product creation checks for existing SKU and returns user-friendly error ("SKU 'X' already exists")

### Changed
- **ImageUploader** — gains variant filter tabs (All / Product / per-variant), variant badges on thumbnails, and re-fetches images when variants change
- **Product edit page layout** — Variants section moved above Images for natural workflow (create variants first, then assign images)
- **VariantManager** — emits `onVariantsChange` callback so parent components stay in sync; accepts `refreshKey` for post-update sync status refresh
- **ProductForm** — `allowRecurring` prop hides recurring pricing option in catalog context; `Archived` status hidden on create (only Draft/Active)
- **Variant deletion** — now cascades to delete associated images from DB

### Fixed
- **Stale variant sync badges** — VariantManager now re-fetches after product update/sync via `refreshKey` prop
- **Orphan images after variant delete** — variant images are deleted from DB when variant is deleted
- **ImageUploader stale state** — re-fetches images when variants change (no orphan thumbnails after variant delete)

### Files Modified
- `modules/ecommerce/models/schemas.py` — image_url on CartItemResponse
- `modules/ecommerce/services/cart_service.py` — COALESCE image subqueries in auth + guest paths
- `modules/ecommerce/services/variant_service.py` — cascade delete variant images
- `modules/ecommerce/services/product_service.py` — duplicate SKU check
- `modules/ecommerce/routes/product_routes.py` — variant_id on upload, ValueError on create
- `frontend/components/admin/ImageUploader.tsx` — variant tabs, badges, re-fetch
- `frontend/components/admin/VariantManager.tsx` — onVariantsChange, refreshKey, delete modal
- `frontend/components/admin/ProductForm.tsx` — allowRecurring, hide Archived on create
- `frontend/app/admin/catalog/products/[id]/page.tsx` — wire variants + refreshKey
- `frontend/app/admin/catalog/products/page.tsx` — allowRecurring=false, error messages
- `frontend/app/products/[slug]/page.tsx` — variant-aware gallery
- `frontend/app/checkout/page.tsx` — render cart item images

## [2026-02-19] - Stripe Integration Improvements: Fee Tiers, Mixed Checkout, Zero-Cost Orders

### Added

**Subscription Plans Management Hub:**
- **Admin subscriptions layout** (`frontend/app/admin/subscriptions/layout.tsx`) — horizontal sub-tabs (Plans / Subscribers)
- **Subscription plans page** (`frontend/app/admin/subscriptions/plans/page.tsx`) — full CRUD for recurring products with subscriber count, status filters, create/edit/archive modals
- **Subscribers page** (`frontend/app/admin/subscriptions/subscribers/page.tsx`) — moved from parent page, admin cancel with confirmation modal
- **Admin cancel subscription endpoint** — `POST /admin/subscriptions/{id}/cancel`
- **`pricing_type` filter** on product list endpoint — `GET /products?pricing_type=recurring`
- **`subscriber_count`** field on ProductResponse

**Phase 1 — Auto-Sync Customers to Stripe at Signup:**
- New users are automatically synced to Stripe via `get_or_create_stripe_customer()` at registration
- Non-blocking: if Stripe call fails, user registration still succeeds (logged as warning)

**Phase 2 — Volume-Based Merchant Fee Tiers:**
- **Fee tiers migration** (`migrations/014_merchant_fee_tiers.sql`) — `ecommerce.fee_tiers` (global schedule) + `ecommerce.merchant_fee_overrides` (per-merchant) + `total_sales_volume` column on merchant_accounts
- **Fee tier service** (`modules/ecommerce/services/fee_tier_service.py`) — full CRUD for global tiers, per-merchant override management, `calculate_fee()` (looks up merchant volume, finds matching tier), `increment_merchant_volume()`
- **Fee tier schemas** — `FeeTierCreate`, `FeeTierUpdate`, `FeeTierResponse`, `MerchantFeeOverrideRequest`, `MerchantFeeOverrideResponse`
- **7 admin endpoints**: `GET/POST/PUT/DELETE /admin/fee-tiers`, `GET/PUT/DELETE /admin/merchants/{id}/fee-overrides`
- **Admin fee tiers page** (`frontend/app/admin/payments/fees/page.tsx`) — glass table with volume ranges, fee %, flat fee, create/edit modal, delete confirmation
- **Payments layout** (`frontend/app/admin/payments/layout.tsx`) — sub-tabs (Methods / Fee Tiers)
- **3 seed tiers**: Starter (15% + $0.30, up to $10K), Growth (12% + $0.25, $10K-$50K), Enterprise (10% + $0.20, $50K+)

**Phase 3 — Zero-Cost Order Support:**
- Orders with `total <= 0` (e.g. 100% discount) skip PaymentIntent creation, complete immediately
- Frontend redirects to confirmation page for free orders instead of showing Stripe payment form

**Phase 4 — Mixed Cart / Stripe Checkout Sessions:**
- **`create_checkout_session()`** on PaymentProvider interface + Stripe adapter — creates Stripe Checkout Sessions for subscription/mixed carts
- **Subscription checkout service** (`modules/payments/services/subscription_checkout_service.py`) — builds Checkout Session from cart items with `stripe_price_id`
- **`POST /checkout/session`** endpoint — returns `session_url` for redirect to Stripe-hosted checkout
- **`checkout.session.completed`** webhook handler — marks cart as converted
- Frontend detects subscription items and redirects to Stripe Checkout instead of embedded PaymentElement

**Phase 5 — Optional Shipping for Subscriptions:**
- `shipping_address` made optional in `CheckoutRequest`
- Checkout service only stores addresses when provided
- Frontend skips shipping step for subscription-only carts, shows "Digital subscription — no shipping required"
- Subscription items labeled with "(subscription)" badge in order review

**Phase 6 — Application Fee Guard:**
- `application_fee_amount` only sent to Stripe when `fee > 0` (prevents API error on very small orders)

### Changed
- **PaymentProvider interface** — `create_payment()` now accepts `fee_amount: int | None` parameter for pre-calculated fees; added `create_checkout_session()` method
- **StripeProvider** — uses `fee_amount` when provided, falls back to `platform_fee_percent` calculation
- **CartItem** — includes `pricing_type` field throughout backend (cart service queries, schemas) and frontend (CartItem interface, cart-context)
- **Checkout page** — cart type detection (`hasSubscription`, `hasOneTime`, `subscriptionOnly`) drives flow routing

### Schema Changes
- Migration `014_merchant_fee_tiers.sql`: creates `ecommerce.fee_tiers`, `ecommerce.merchant_fee_overrides`, adds `total_sales_volume BIGINT` to `ecommerce.merchant_accounts`

### Files Created
- `migrations/014_merchant_fee_tiers.sql`
- `modules/ecommerce/services/fee_tier_service.py`
- `modules/payments/services/subscription_checkout_service.py`
- `frontend/app/admin/payments/layout.tsx`
- `frontend/app/admin/payments/fees/page.tsx`
- `frontend/app/admin/subscriptions/layout.tsx`
- `frontend/app/admin/subscriptions/plans/page.tsx`
- `frontend/app/admin/subscriptions/subscribers/page.tsx`

### Files Modified
- `modules/auth/services/auth_service.py` — Stripe customer sync at signup
- `modules/ecommerce/models/schemas.py` — fee tier schemas, `pricing_type` on CartItemResponse, `subscriber_count` on ProductResponse
- `modules/ecommerce/routes/admin_routes.py` — fee tier + merchant override + cancel subscription endpoints
- `modules/ecommerce/routes/product_routes.py` — `pricing_type` query param
- `modules/ecommerce/services/cart_service.py` — `pricing_type` in cart item queries and serialization
- `modules/ecommerce/services/product_service.py` — `pricing_type` filter, subscriber count JOIN
- `modules/ecommerce/services/subscription_service.py` — `admin_cancel_subscription()`
- `modules/payments/adapters/stripe_provider.py` — `fee_amount` param, `create_checkout_session()`, fee guard
- `modules/payments/interfaces/payment_provider.py` — `fee_amount` param, `create_checkout_session()` method
- `modules/payments/models/schemas.py` — optional `shipping_address`/`client_secret`, checkout session schemas
- `modules/payments/routes/checkout_routes.py` — `/checkout/session` endpoint, optional shipping
- `modules/payments/services/checkout_service.py` — zero-cost guard, conditional address storage
- `modules/payments/services/webhook_service.py` — `checkout.session.completed` handler
- `frontend/app/admin/catalog/products/[id]/page.tsx` — subscription fields on Product interface
- `frontend/app/admin/subscriptions/page.tsx` — redirect to plans sub-tab
- `frontend/app/checkout/page.tsx` — cart type routing, subscription checkout, skip shipping, free orders
- `frontend/lib/cart-context.tsx` — `pricing_type` on CartItem
- `docs/ARCHITECTURE.md` — new tables, updated PaymentProvider interface

---

## [2026-02-19] - Product Catalog Restructure, Subscriptions & Stripe Coupon Sync

### Added

**Phase A — Product Catalog Layout + Coupons UI:**
- **Admin catalog layout** (`frontend/app/admin/catalog/layout.tsx`) — horizontal sub-tab navigation (All Products, Coupons, Shipping Rates, Tax Rates) mirroring Stripe's dashboard structure
- **Coupons admin page** (`frontend/app/admin/catalog/coupons/page.tsx`) — full CRUD list with glass table, status filter pills (All/Active/Archived), create/edit modals, deactivate confirmation
- **CouponForm component** (`frontend/components/admin/CouponForm.tsx`) — reusable form with code, type (percentage/fixed/free_shipping), value, currency, min order, max uses, validity dates, applies_to, Stripe duration fields
- **Status filter pills** on products and coupons pages (All / Active / Archived)
- **Placeholder pages** for Shipping Rates and Tax Rates (Coming Soon)

**Phase B — Subscription/Recurring Products Backend:**
- **Subscriptions table** (`ecommerce.subscriptions`) — full lifecycle tracking: status, billing periods, trial dates, Stripe IDs, cancellation
- **Stripe customers table** (`ecommerce.stripe_customers`) — lazy user-to-Stripe-customer mapping
- **Subscription service** (`modules/ecommerce/services/subscription_service.py`) — create, cancel, list (user + admin), webhook updates
- **Subscription routes** (`modules/ecommerce/routes/subscription_routes.py`) — POST create, GET list, POST cancel (customer-facing)
- **Admin subscriptions page** (`frontend/app/admin/subscriptions/page.tsx`) — glass table with customer email, product name, status badges, billing period, status filter pills
- **Recurring product support** — products can be `pricing_type: recurring` with interval, interval count, trial days
- **Subscription webhook handlers** — `customer.subscription.created/updated/deleted`, `invoice.payment_failed`

**Phase C — Stripe Coupon Sync:**
- **Stripe coupon sync** — creating a discount code automatically creates a Stripe Coupon + Promotion Code; deactivating deletes from Stripe; value/type changes recreate (Stripe coupons are immutable)
- **Coupon applicability** — `applies_to` field (all/one_time/recurring) enforced at checkout and subscription creation
- **Stripe duration** — coupons support `once`, `repeating` (with month count), and `forever` durations for subscription discounts

### Fixed
- **Payment settings import error** — `settings_routes.py` imported `require_role` from wrong module path, causing entire settings router to fail to load ("Failed to load payment settings" error)
- **Payment toggle state initialization** — `methods` initialized as empty `{}` causing counter to show "0 of 7" while cards appeared enabled; fixed with `defaultMethods()` helper
- **Reset to Auto** — button only reset local state; added DELETE endpoint and async backend call
- **Stripe API 2025-03-31 breaking changes:**
  - `Invoice.payment_intent` → `Invoice.confirmation_secret` for subscription payment confirmation
  - `Subscription.current_period_start/end` → moved to subscription items level
  - `PromotionCode.create(coupon=...)` → `promotion={type: "coupon", coupon: ...}`
  - `Subscription.create(coupon=...)` → `discounts=[{coupon: ...}]`

### Changed
- **Admin sidebar** — "Products" renamed to "Product Catalog" (href `/admin/catalog`), added "Subscriptions" item
- **Products pages** moved from `/admin/products/` to `/admin/catalog/products/`
- **ProductForm** — added pricing_type (one-time/recurring), recurring interval, trial days fields
- **PaymentProvider interface** — added `create_customer()`, `create_subscription()`, `cancel_subscription()`, `get_subscription()` methods with `NotImplementedError` defaults
- **CatalogProvider interface** — `create_price()` now accepts optional `recurring_interval` and `recurring_interval_count`
- **StripeProvider** — implemented subscription, customer, coupon, and recurring price methods
- **Discount service** — `list_discounts()` supports `status` filter; create/update/deactivate trigger Stripe coupon sync
- **Checkout service** — rejects `applies_to='recurring'` coupons on one-time checkout

### Schema Changes
- Migration `012_subscriptions.sql`: adds recurring fields to products, creates `ecommerce.subscriptions` and `ecommerce.stripe_customers` tables
- Migration `013_coupon_stripe_sync.sql`: adds `stripe_coupon_id`, `stripe_promotion_code_id`, `applies_to`, `stripe_duration`, `stripe_duration_in_months` to `ecommerce.discount_codes`

### Files Created
- `frontend/app/admin/catalog/layout.tsx`
- `frontend/app/admin/catalog/page.tsx`
- `frontend/app/admin/catalog/products/page.tsx`
- `frontend/app/admin/catalog/products/[id]/page.tsx`
- `frontend/app/admin/catalog/coupons/page.tsx`
- `frontend/app/admin/catalog/shipping/page.tsx`
- `frontend/app/admin/catalog/tax/page.tsx`
- `frontend/app/admin/subscriptions/page.tsx`
- `frontend/components/admin/CouponForm.tsx`
- `migrations/012_subscriptions.sql`
- `migrations/013_coupon_stripe_sync.sql`
- `modules/ecommerce/services/subscription_service.py`
- `modules/ecommerce/routes/subscription_routes.py`

### Files Modified
- `frontend/app/admin/layout.tsx` — sidebar restructure
- `frontend/app/admin/payments/page.tsx` — bug fixes (state init, reset, import)
- `frontend/components/admin/ProductForm.tsx` — recurring product fields
- `modules/ecommerce/models/schemas.py` — subscription + discount schemas with new fields
- `modules/ecommerce/routes/__init__.py` — registered subscription routes
- `modules/ecommerce/routes/admin_routes.py` — admin subscriptions + discount status filter
- `modules/ecommerce/services/catalog_sync_service.py` — recurring price sync
- `modules/ecommerce/services/discount_service.py` — Stripe coupon sync
- `modules/ecommerce/services/product_service.py` — recurring fields in INSERT
- `modules/payments/adapters/stripe_provider.py` — subscription, coupon, Stripe API fixes
- `modules/payments/interfaces/catalog_provider.py` — recurring price params
- `modules/payments/interfaces/payment_provider.py` — subscription methods
- `modules/payments/routes/settings_routes.py` — import fix + DELETE endpoint
- `modules/payments/services/checkout_service.py` — coupon applicability check
- `modules/payments/services/payment_settings_service.py` — delete_setting()
- `modules/payments/services/webhook_service.py` — subscription event handlers

### Test Results
- Full subscription lifecycle verified: create product (recurring) -> Stripe sync -> create subscription -> list (customer + admin) -> cancel -> verify
- Coupon sync verified: create coupon -> Stripe Coupon + Promotion Code created -> apply to subscription -> applicability guards enforced
- Payment settings bug fixes verified: page loads, toggles work, counter accurate, reset calls backend

## [2026-02-18] - Admin Payment Method Toggles

### Added
- **Payment settings table** — `ecommerce.payment_settings` key-value store (JSONB) for admin-configurable payment settings
- **Payment settings service** (`modules/payments/services/payment_settings_service.py`) — `get_setting()`, `upsert_setting()`, `get_enabled_payment_methods()` for reading/writing payment method toggles
- **Settings API endpoints** (`modules/payments/routes/settings_routes.py`) — `GET /api/payments/settings/payment-methods` and `PUT /api/payments/settings/payment-methods` (admin-only)
- **Admin payments page** (`frontend/app/admin/payments/page.tsx`) — toggle cards for 7 payment methods (Card, Link, Apple Pay, Google Pay, Klarna, Afterpay, PayPal) with save/reset controls
- **Payments nav link** in admin sidebar

### Changed
- **PaymentProvider interface** — `create_payment()` now accepts optional `payment_method_types: list[str] | None` parameter
- **StripeProvider** — when `payment_method_types` is provided, uses explicit `payment_method_types` list on PaymentIntent instead of `automatic_payment_methods`
- **Checkout service** — fetches admin-configured payment methods from DB before creating PaymentIntent; falls back to automatic mode when no customization exists

### Schema Changes
- Migration `011_payment_settings.sql`: creates `ecommerce.payment_settings` table (key VARCHAR(100) PK, value JSONB, updated_at TIMESTAMPTZ)

### Files Created
- `migrations/011_payment_settings.sql`
- `modules/payments/services/payment_settings_service.py`
- `modules/payments/routes/settings_routes.py`
- `frontend/app/admin/payments/page.tsx`

### Files Modified
- `modules/payments/interfaces/payment_provider.py` — added `payment_method_types` param
- `modules/payments/adapters/stripe_provider.py` — conditional automatic vs explicit methods
- `modules/payments/services/checkout_service.py` — fetches enabled methods before payment creation
- `modules/payments/routes/__init__.py` — registered settings router
- `frontend/app/admin/layout.tsx` — added Payments nav item

## [2026-02-18] - Image Upload, Synced Provider, Catalog Webhooks & 5-Product Test

### Added
- **File upload infrastructure** — Docker `upload_data` volume shared between FastAPI (read/write) and Nginx (read-only static serving at `/uploads/`)
- **StorageProvider interface** (`modules/ecommerce/interfaces/storage_provider.py`) — abstract file storage with `upload()` and `delete()` methods
- **LocalStorageProvider** (`modules/ecommerce/adapters/local_storage.py`) — stores files on Docker volume with UUID-prefixed filenames
- **Image upload endpoint** — `POST /api/ecommerce/products/{id}/images/upload` accepts multipart file upload (JPEG, PNG, WebP, GIF, max 5 MB)
- **Image sync to Stripe** — product images are passed to Stripe Products API during catalog sync (requires `public_url` config for publicly accessible URLs)
- **`synced_provider` column** — tracks which payment provider a product is synced with (e.g. "stripe"), displayed in admin UI as "Synced to Stripe"
- **Product catalog webhooks** — handles `product.updated`, `product.deleted`, `price.updated`, `price.deleted` from Stripe so changes on Stripe side reflect locally (archiving, name changes, price removal)
- **ImageUploader component** (`frontend/components/admin/ImageUploader.tsx`) — drag-and-drop image upload with thumbnail grid and delete buttons
- **`apiUpload` helper** (`frontend/lib/api.ts`) — separate upload function for FormData (no Content-Type header, browser sets multipart boundary)
- **5-product test script** (`scripts/test_5_products.py`) — creates 5 diverse products with images and variants, activates them, verifies Stripe sync
- **`public_url` config** (`backend/core/config.py`) — configurable base URL for assets; when empty, images are omitted from Stripe API calls

### Schema Changes
- Migration `010_synced_provider_and_images.sql`: adds `synced_provider VARCHAR(50)` to `ecommerce.products`; adds `storage_path VARCHAR(500)` to `ecommerce.product_images`

### Files Created
- `migrations/010_synced_provider_and_images.sql`
- `modules/ecommerce/interfaces/storage_provider.py`
- `modules/ecommerce/adapters/local_storage.py`
- `frontend/components/admin/ImageUploader.tsx`
- `scripts/test_5_products.py`

### Files Modified
- `docker-compose.yml` — added `upload_data` volume to fastapi and nginx
- `docker/nginx.conf` — added `/uploads/` location block with cache headers
- `docker/backend.Dockerfile` — added uploads directory creation
- `modules/ecommerce/adapters/__init__.py` — added storage provider factory
- `modules/ecommerce/services/image_service.py` — storage_path support + file cleanup on delete
- `modules/ecommerce/services/catalog_sync_service.py` — image URL fetching, synced_provider tracking
- `modules/ecommerce/routes/product_routes.py` — upload endpoint
- `modules/ecommerce/models/schemas.py` — synced_provider + storage_path fields
- `modules/payments/interfaces/catalog_provider.py` — images param on create/update
- `modules/payments/adapters/stripe_provider.py` — passes images to Stripe API
- `modules/payments/services/webhook_service.py` — 4 new catalog event handlers
- `backend/core/config.py` — public_url setting
- `frontend/lib/api.ts` — apiUpload helper
- `frontend/components/admin/SyncStatusBadge.tsx` — provider display
- `frontend/app/admin/products/page.tsx` — synced_provider passed to badge
- `frontend/app/admin/products/[id]/page.tsx` — ImageUploader + synced_provider

### Test Results
- 5/5 products created, images uploaded, and synced to Stripe successfully
- Products: Basic T-Shirt (3 variants), Premium Hoodie (2 variants w/ price overrides), Digital Wallpaper Pack (no variants), Gift Card (4 denomination variants), Limited Edition Sneakers (2 size variants)

---

## [2026-02-18] - Product Catalog Sync + Admin Product Management

### Added
- **CatalogProvider interface** (`modules/payments/interfaces/catalog_provider.py`) — new ABC for product/price catalog management, separate from PaymentProvider. Methods: `create_product`, `update_product`, `archive_product`, `create_price`, `archive_price`
- **StripeProvider catalog methods** — `StripeProvider` now implements both `PaymentProvider` and `CatalogProvider`. Uses `stripe.Product.*` and `stripe.Price.*` APIs
- **Catalog provider factory** — `get_catalog_provider()` in `modules/payments/adapters/__init__.py`, returns `None` for providers without catalog support (makes sync a no-op)
- **Catalog sync service** (`modules/ecommerce/services/catalog_sync_service.py`) — provider-agnostic orchestration: `sync_product_to_catalog`, `sync_variant_to_catalog`, `archive_product_in_catalog`, `retry_sync`
- **Product sync hooks** — `product_service.create_product/update_product/delete_product` and `variant_service.create_variant/update_variant` now trigger catalog sync automatically when products are active
- **Sync retry endpoint** — `POST /api/ecommerce/products/{id}/sync` (admin-only) for retrying failed syncs
- **Admin product management UI** — full CRUD: create modal, edit page with variant manager, delete confirmation, sync status badges, retry sync buttons
- **Product edit page** (`frontend/app/admin/products/[id]/page.tsx`) — dedicated edit page with product form + variant manager + sync status display
- **SyncStatusBadge component** — green (synced), gray (unsynced), red (error with retry button)
- **ProductForm component** — reusable create/edit form with price in dollars, status selector, Stripe sync notice
- **VariantManager component** — inline variant CRUD with effective price display and sync status

### Schema Changes
- Migration `009_stripe_catalog_sync.sql`: adds `stripe_product_id`, `stripe_price_id`, `stripe_sync_status`, `stripe_sync_error` to `ecommerce.products`; adds `stripe_price_id`, `stripe_sync_status`, `stripe_sync_error` to `ecommerce.product_variants`

### Design Decisions
- Sync triggers on "active" status only — draft products don't sync to Stripe
- Local-first: products always save locally; Stripe errors are tracked and retryable
- Stripe Prices are immutable — price changes archive old Price and create new one
- Providers without catalog support (e.g. PayPal) get `None` from factory, making all sync no-ops

### Files Created
- `migrations/009_stripe_catalog_sync.sql`
- `modules/payments/interfaces/catalog_provider.py`
- `modules/ecommerce/services/catalog_sync_service.py`
- `frontend/app/admin/products/[id]/page.tsx`
- `frontend/components/admin/ProductForm.tsx`
- `frontend/components/admin/VariantManager.tsx`
- `frontend/components/admin/SyncStatusBadge.tsx`

### Files Modified
- `modules/payments/adapters/stripe_provider.py` — added CatalogProvider methods
- `modules/payments/adapters/__init__.py` — added `get_catalog_provider()`
- `modules/ecommerce/services/product_service.py` — added sync hooks
- `modules/ecommerce/services/variant_service.py` — added sync hooks
- `modules/ecommerce/models/schemas.py` — added stripe fields to response models
- `modules/ecommerce/routes/product_routes.py` — added sync retry endpoint
- `frontend/app/admin/products/page.tsx` — rewritten with full CRUD

---

## [2026-02-18] - Phase 10: Stripe Integration & Payment Frontend

### Added
- **CSRF token handling** — frontend captures `csrf_token` from login/register/refresh responses and auto-attaches `X-CSRF-Token` header on state-changing requests
- **Stripe.js integration** — `@stripe/stripe-js` + `@stripe/react-stripe-js` installed, singleton loader at `frontend/lib/stripe.ts`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` as Docker build arg
- **Real checkout flow** — 3-step checkout (Shipping -> Review -> Payment) using Stripe PaymentElement, calls `POST /api/payments/checkout`
- **Order confirmation** — reads Stripe redirect params (`redirect_status`), shows success/processing/failed states, polls payment status every 3s
- **Payment retry** — `/orders/{id}/pay` re-renders Stripe Elements with existing `client_secret` for failed payments
- **Stale order reaper** — background task (5-min interval) expires orders in 'processing' beyond `CHECKOUT_TIMEOUT` (default 60 min), releases stock, cancels payment
- **Merchant self-signup** — `POST /api/auth/upgrade-to-merchant` endpoint, 3 frontend pages (register, onboard, dashboard), nav links in Header and Dashboard
- **charge.succeeded webhook** — stores `charge_id` in `ecommerce.payment_records` for audit trail
- **Provider factory** — `get_payment_provider()` reads `settings.payment_provider`, centralizes provider instantiation
- **Provider interface extensions** — `cancel_payment()`, `verify_webhook()`, `create_account_link()`, `create_login_link()` added to `PaymentProvider` ABC
- **Stripe setup guide** — `docs/guides/stripe-setup.md` with keys, webhooks, Connect, test cards, going-live checklist, provider swapping

### Changed
- All payment services now use `get_payment_provider()` factory instead of direct `get_stripe_provider()` imports
- `import stripe` only appears in `stripe_provider.py` — no Stripe SDK usage in services, routes, or reaper
- Webhook signature verification delegated to `PaymentProvider.verify_webhook()`
- Phase 10 (Integration & Deployment) renamed to Phase 11

### Schema Changes
- Migration `008_payment_charge_id.sql`: adds `charge_id VARCHAR(255)` column to `ecommerce.payment_records`, adds `expired` to status check constraint

### Files Created
- `frontend/lib/stripe.ts`, `frontend/app/checkout/page.tsx` (rewritten), `frontend/app/orders/[id]/confirmation/page.tsx` (rewritten)
- `frontend/app/orders/[id]/pay/page.tsx`, `frontend/app/merchant/register/page.tsx`, `frontend/app/merchant/onboard/page.tsx`, `frontend/app/merchant/dashboard/page.tsx`
- `modules/payments/adapters/__init__.py`, `modules/payments/services/order_reaper.py`
- `migrations/008_payment_charge_id.sql`, `docs/guides/stripe-setup.md`, `docs/phases/phase-10.md`, `docs/test-plans/phase-10/test-plan.md`

### Files Modified
- `frontend/lib/api.ts`, `frontend/lib/auth-context.tsx`, `frontend/components/Header.tsx`, `frontend/app/dashboard/page.tsx`
- `.env.template`, `docker/frontend.Dockerfile`, `docker-compose.yml`
- `backend/core/config.py`, `backend/main.py`
- `modules/auth/routes/auth_routes.py`
- `modules/payments/interfaces/payment_provider.py`, `modules/payments/adapters/stripe_provider.py`
- `modules/payments/models/schemas.py`, `modules/payments/routes/checkout_routes.py`
- `modules/payments/services/checkout_service.py`, `modules/payments/services/webhook_service.py`
- `modules/payments/services/merchant_service.py`, `modules/payments/services/order_reaper.py`

---

## [2026-02-17] - Admin user management, health checks, stack reference removal

### Added
- **Admin user management backend** (Phase 3) — 5 new endpoints under `/api/auth/admin/users`: list (paginated, searchable, filterable), detail (with `is_merchant` flag), role change, activate/deactivate, soft delete
- **Admin user management frontend** (Phase 9) — full user table with search, role/status filters, pagination, expandable detail rows with inline action buttons
- **Real health status card** — admin dashboard status card now calls `/api/health` and checks API, Database, and Cache services. Click to expand individual service statuses. Generic labels (no stack names exposed).

### Changed
- **Footer text** — "Built with Next.js & FastAPI" → "Powered by Boilerplate"
- **Footer description** — "A modern e-commerce platform built with Next.js and FastAPI." → "A modern e-commerce platform."
- **Meta description** — removed "built with Next.js and FastAPI" from layout metadata

### Security
- Merchant accounts cannot have role changed (checked via `ecommerce.merchant_accounts` table)
- Admin cannot change own role, deactivate self, or delete self (lockout prevention)
- All state changes (role, deactivation, delete) immediately revoke sessions via `invalidate_all_sessions()`
- Removed tech stack references from all user-visible frontend text to avoid exposing implementation details

### Files Modified
- `modules/auth/services/admin_user_service.py` — NEW: admin user management service
- `modules/auth/routes/admin_routes.py` — NEW: 5 admin user endpoints
- `modules/auth/models/schemas.py` — added admin user schemas
- `modules/auth/routes/__init__.py` — registered admin router
- `frontend/app/admin/users/page.tsx` — full rewrite with user management UI
- `frontend/app/admin/page.tsx` — real health status card
- `frontend/app/layout.tsx` — removed stack names from meta description
- `frontend/components/Footer.tsx` — removed stack names from footer text

### Schema Changes
- None (uses existing `core.users` columns: `role_id`, `is_active`, `deleted_at`)

---

## [2026-02-17] - Fix GDPR consent system, admin analytics & GDPR panels

### Added
- **ConsentModal component** (`frontend/components/ConsentModal.tsx`) — post-registration consent modal shown on first dashboard visit, grouped by category, syncs with backend consent records + cookie preferences
- **Shared consent type constants** (`frontend/lib/consent-types.ts`) — single source of truth for 6 consent types, categories, labels, and consent-to-cookie mapping
- **Device/browser analytics endpoint** (`GET /api/tracking/admin/analytics/devices`) — returns device type, browser, and OS breakdowns from `analytics.user_agents` table (Phase 6 backend)
- **Device/browser analytics schemas** (`DeviceStats`, `DeviceTypeStat`, `BrowserStat`, `OSStat`) in tracking module
- **Admin GDPR: Consent Statistics section** — opt-in rate per consent type with progress bars, grant/revoke counts
- **Admin GDPR: Consent Audit Log section** — paginated table of consent changes with filter by consent type, user ID, action badges, IP addresses
- **Admin Dashboard: Pending Deletions card** — shows count of active deletion requests (grace_period status), highlights pink when > 0
- **CookieBanner suppression** — authenticated users who completed consent modal don't see cookie banner

### Fixed
- **GDPR admin route prefix** (`modules/gdpr/routes/admin_routes.py`) — prefix was `/admin/gdpr` which combined with module loader's `/api/gdpr` created `/api/gdpr/admin/gdpr/...` (double `gdpr`). Changed to `/admin` so routes resolve to `/api/gdpr/admin/...`. This fix made consent-stats, audit log, exports, and deletions endpoints reachable from the frontend.
- **Privacy page API path** — was calling `/gdpr/consents` (plural) but backend route is `/gdpr/consent` (singular) → 404
- **Privacy page response parsing** — backend returns `{ consents: [...] }` wrapper but page expected bare array → consents always empty
- **Privacy page consent types** — was sending `functional`, `third_party`, `marketing`, `preferences` but backend only accepts the 6 registered types (`marketing_email`, `transactional_email`, etc.)
- **Admin Analytics API params** — frontend sent `?period=30d` / `?period=7d` but backend only accepts `date_from`/`date_to` query params → stats silently showed 0
- **Admin Analytics response mapping** — frontend expected `total`/`data[]` but backend returns `total_views`/`top_pages[]`, `total_sessions`, `sources[]`, `campaigns[]`
- **Admin GDPR export requests** — frontend used `created_at` but backend returns `requested_at`
- **Admin GDPR deletion requests** — frontend used `scheduled_at` but backend returns `grace_period_ends`

### Changed
- **Privacy page** redesigned with category-grouped toggles (Email, Data, Analytics, Cookies), `transactional_email` marked required/always-on, cookie sync on toggle
- **Admin Analytics page** — added unique visitors metric card, UTM campaigns table, device/browser/OS breakdown bars
- **Admin Dashboard** — stat cards now show 30d data (matching backend default), added GDPR summary card
- **Admin GDPR page** — complete rewrite with 4 sections: consent stats, audit log, exports, deletions
- **Dashboard layout** — integrates ConsentModal for first-visit consent collection

### Files Modified
- `modules/gdpr/routes/admin_routes.py` — route prefix fix
- `modules/tracking/routes/admin_routes.py` — new `/devices` endpoint
- `modules/tracking/models/schemas.py` — new device/browser/OS schemas
- `frontend/lib/consent-types.ts` — NEW: shared consent type constants
- `frontend/components/ConsentModal.tsx` — NEW: post-registration consent modal
- `frontend/components/CookieBanner.tsx` — suppression check for consent modal
- `frontend/app/dashboard/privacy/page.tsx` — 3 bug fixes + redesign
- `frontend/app/dashboard/layout.tsx` — ConsentModal integration
- `frontend/app/admin/page.tsx` — API param fix + GDPR summary card
- `frontend/app/admin/analytics/page.tsx` — API fix + device breakdown
- `frontend/app/admin/gdpr/page.tsx` — consent stats + audit log + field fixes

### Schema Changes
- None (no database migrations)

---

## [2026-02-17] - Fix cart quantity/remove buttons and add-to-cart

### Fixed
- Cart +/- quantity buttons and remove button were non-functional (silent failure, no errors)
- Add-to-cart from product detail page broken by stale closure after initial optimistic update attempt
- UI flicker on cart item rows during quantity changes (opacity-50 toggle during async call)

### Changed
- `CartProvider.updateQuantity()` — changed HTTP method from `PATCH` to `PUT`, URL from single `{itemId}` to composite `{product_id}_{variant_id}`, signature from `(itemId, qty)` to `(productId, variantId, qty)`
- `CartProvider.removeItem()` — URL changed to composite key format, signature from `(itemId)` to `(productId, variantId)`
- All cart mutation callbacks (`addItem`, `updateQuantity`, `removeItem`, `applyDiscount`, `removeDiscount`) now set cart state directly from API response instead of calling `refreshCart()` — eliminates loading spinner flash
- `updateQuantity` and `removeItem` use optimistic local state updates with `useRef` rollback on failure
- All `useCallback` dependencies changed to `[]` (stable references) — prevents stale closures and unnecessary re-renders
- `CartItem` interface updated to match actual API response (removed non-existent `id`/`slug` fields, added `currency`)
- Cart item React keys use `cartItemKey()` composite helper instead of `item.id`

### Files Modified
- `frontend/lib/cart-context.tsx` — API methods, interface, optimistic updates, stable callbacks
- `frontend/app/cart/page.tsx` — composite keys, removed flicker state, removed stale `item.id`/`item.slug` refs
- `frontend/app/checkout/page.tsx` — cart item React keys use `cartItemKey()`
- `docs/phases/phase-9.md` — added Post-Build Fixes section
- `docs/test-plans/phase-9/test-plan.md` — added 8 new tests (E9–E15, K16), updated totals to 170

---

## Template

<!--
Copy this block for each release/change:

## [YYYY-MM-DD] - Brief description

### Added
- New feature or module (reference: docs/features/feature-name.md if applicable)

### Changed
- Modified behavior or updated implementation
- Updated schema: table_name (added column_name, changed column_type)
- Updated interface: InterfaceName (added method_name)

### Fixed
- Bug fix description

### Removed
- Deprecated feature removed

### Schema Changes
- List any database migration needed (e.g., "Run: python scripts/migrate.py up")

### Files Modified
- List key files changed (helps Claude Code know what to re-read)

### Breaking Changes
- Any change that requires updating .env, re-running migrations, or modifying existing code
-->

---

## Initial Build

### Phase completion log
_Update as phases are completed:_

| Phase | Completed | Tag | Notes |
|-------|-----------|-----|-------|
| 1 | 2026-02-15 | phase-1-complete | Project skeleton, Docker Compose stack, module loader, Redis integration, CI/CD pipeline, setup script |
| 2 | 2026-02-15 | phase-2-complete | Database schemas (core 7, ecommerce 21, saas 6, gdpr 7, analytics 6), migration system, seed data, SQLAlchemy async engine, notifications + recommendations module scaffolds |
| 3 | 2026-02-16 | phase-3-complete | JWT auth, Redis sessions, bcrypt passwords, RBAC, rate limiting, M2M API keys, OAuth (Google/GitHub/Microsoft/Apple/OIDC), audit logging, lightweight frontend auth UI |
| 4 | 2026-02-16 | phase-4-complete | Payment processing: PaymentProvider ABC + Stripe adapter, checkout with cart-to-order conversion + PaymentIntent, webhook handler (signature verification + idempotency), refund flow, Stripe Connect Express merchant onboarding. ~7 endpoints, 4 services, 1 migration (merchant_accounts + webhook_events) |
| 5 | 2026-02-16 | phase-5-complete | E-commerce engine: product catalog (CRUD, variants, images, categories), shopping cart (guest Redis + auth PG + merge), orders with checkout + stock reservation, inventory management, discount codes, wishlists, reviews with moderation, digital assets with HMAC-signed downloads, pricing tiers. ~35 endpoints across 7 route files and 11 service files |
| 6 | 2026-02-16 | phase-6-complete | User tracking & analytics: GeoProvider + AgentParser interfaces, placeholder geo + regex UA parser adapters, GDPR consent checks, analytics sessions (Redis TTL), pageview/event collection (single + batch), UTM extraction, referral parsing, non-blocking tracking middleware (asyncio.create_task), 5 admin analytics endpoints (pageviews, sessions, events, sources, UTM). ~9 endpoints, 7 services, 1 middleware |
| 7 | 2026-02-16 | phase-7-complete | GDPR & cookie management: consent management (6 types with audit log), cookie preferences (auth + guest), data export (right of access, rate limited, JSON), data deletion (right to erasure, 30-day grace period, anonymization), email preferences with one-click unsubscribe (HMAC-signed, RFC 8058), 4 admin dashboard endpoints. ~14 endpoints, 5 services, 6 route files, ~20 Pydantic schemas |
| 8 | 2026-02-16 | phase-8-complete | SEO module: dynamic meta tags (auto-generated from products/categories + custom overrides), sitemap.xml (Redis-cached, products/categories/static pages, large catalog index support), robots.txt, Open Graph + Twitter Card tags, JSON-LD structured data (Product with price/availability/reviews, Organization, BreadcrumbList, WebSite with SearchAction), 6 admin endpoints, nginx root-level routing. ~8 endpoints + 2 root-level, 5 services, 1 migration |
| 9 | 2026-02-16 | phase-9-complete | Frontend (Next.js): Tailwind CSS v4 with neurons.html-inspired dark theme (particle canvas, gradient mesh, glass morphism), landing page with scroll reveal, auth pages (login, register, forgot/reset password with OAuth), product catalog (grid/list view, search, sort, pagination), product detail (variants, images, reviews, add-to-cart), categories, shopping cart with discount codes, mock checkout (3-step), order confirmation, user dashboard (overview, orders, order detail, profile, wishlists, privacy/GDPR), admin panel (dashboard, products, orders, users, analytics, GDPR, SEO), cookie consent banner, responsive design. ~21 pages, 15 components, 2 contexts, 1 utility lib |
| 10 | 2026-02-18 | phase-10-complete | Stripe integration: real checkout with Stripe Elements, merchant self-signup, stale order reaper, payment retry, charge tracking, provider factory abstraction, 54-test plan |
| 11 | — | — | — |
