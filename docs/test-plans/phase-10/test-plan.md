# Phase 10: Stripe Integration & Payment Frontend — Test Plan

**Phase:** 10 — Stripe Integration & Payment Frontend
**Created:** 2026-02-18
**Last executed:** 2026-02-18
**Status:** Partially executed (6/69 core + 14/14 catalog/subs/coupons passed; full core suite requires Stripe keys + webhook forwarding)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Section A: CSRF Token Flow](#section-a-csrf-token-flow)
3. [Section B: Checkout — Happy Path](#section-b-checkout--happy-path)
4. [Section C: Checkout — Error Handling](#section-c-checkout--error-handling)
5. [Section D: Order Confirmation & Polling](#section-d-order-confirmation--polling)
6. [Section E: Payment Retry](#section-e-payment-retry)
7. [Section F: Stock Reservation & Reaper](#section-f-stock-reservation--reaper)
8. [Section G: Merchant Self-Signup](#section-g-merchant-self-signup)
9. [Section H: Webhook Handlers](#section-h-webhook-handlers)
10. [Section I: Provider Swapability](#section-i-provider-swapability)
11. [Section J: Stripe Test Cards](#section-j-stripe-test-cards)
12. [Section K: Frontend Integration](#section-k-frontend-integration)
13. [Section L: Admin Payment Method Toggles](#section-l-admin-payment-method-toggles)
14. [Section M: Product Catalog & Coupons UI](#section-m-product-catalog--coupons-ui)
15. [Section N: Subscriptions Lifecycle](#section-n-subscriptions-lifecycle)
16. [Section O: Stripe Coupon Sync](#section-o-stripe-coupon-sync)
17. [Test Summary](#test-summary)

---

## 1. Prerequisites

### Environment

- Docker Compose stack running: `docker compose up -d --build`
- All services healthy: postgres, redis, fastapi, nextjs, nginx
- Seed data loaded
- For Sections B, C, D, E, J: `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` set in `.env`
- For Section H: Stripe CLI installed and `STRIPE_WEBHOOK_SECRET` set

### Test Users (from seed data)

All passwords: `Test1234!`

| Email | Role | User ID |
|-------|------|---------|
| admin@example.com | admin | b0000000-0000-0000-0000-000000000001 |
| merchant@example.com | merchant | b0000000-0000-0000-0000-000000000002 |
| customer@example.com | customer | b0000000-0000-0000-0000-000000000003 |

---

## Section A: CSRF Token Flow

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| A1 | Login returns CSRF token | POST `/api/auth/login` with valid creds | Response contains `csrf_token` field | [ ] |
| A2 | Register returns CSRF token | POST `/api/auth/register` with new user | Response contains `csrf_token` field | [ ] |
| A3 | POST without CSRF token rejected | POST `/api/payments/checkout` without `X-CSRF-Token` header | 403 "Missing CSRF token" | [ ] |
| A4 | POST with valid CSRF token succeeds | POST with `X-CSRF-Token` header from login response | Request proceeds (may fail for other reasons, but not 403) | [ ] |

---

## Section B: Checkout — Happy Path

**Requires:** Stripe API keys configured

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| B1 | Checkout creates order + PaymentIntent | Login, add item to cart, POST `/api/payments/checkout` with shipping address | Returns `order_id`, `client_secret`, `total` | [ ] |
| B2 | Cart cleared after checkout | After B1, GET `/api/ecommerce/cart` | Cart is empty | [ ] |
| B3 | Order status is 'processing' | GET `/api/ecommerce/orders/{order_id}` | Status = "processing" | [ ] |
| B4 | Payment record created | Query DB: `SELECT * FROM ecommerce.payment_records WHERE order_id = :oid` | Row exists with status "pending" | [ ] |
| B5 | Stock decremented | Query DB: check variant stock_quantity | Decreased by order quantity | [ ] |
| B6 | Checkout with discount code | Apply valid discount code before checkout | `discount_amount > 0`, `total` reduced | [ ] |

---

## Section C: Checkout — Error Handling

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| C1 | Empty cart checkout | POST `/api/payments/checkout` with empty cart | 400 error | [ ] |
| C2 | Out-of-stock checkout | Set stock to 0, attempt checkout | 400 "insufficient stock" | [ ] |
| C3 | Invalid discount code | POST checkout with `discount_code: "INVALID"` | 400 "Invalid or expired discount code" | [ ] |
| C4 | Unauthenticated checkout | POST checkout without auth token | 401 | [ ] |
| C5 | Payment creation fails gracefully | Set invalid Stripe key, attempt checkout | 400, order marked "rejected", stock released | [ ] |

---

## Section D: Order Confirmation & Polling

**Requires:** Stripe API keys configured

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| D1 | Payment status endpoint returns data | GET `/api/payments/orders/{order_id}/payment` | Returns order_status, payment_status, amount | [ ] |
| D2 | Pending payment returns client_secret | Create checkout (don't confirm), GET payment status | `client_secret` present, status "pending" | [ ] |
| D3 | Succeeded payment no client_secret | After webhook marks payment succeeded | `payment_status: "succeeded"`, no client_secret needed | [ ] |
| D4 | Non-owner cannot view payment | Login as different user, GET payment status for other user's order | 404 | [ ] |

---

## Section E: Payment Retry

**Requires:** Stripe API keys configured

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| E1 | Failed payment shows client_secret | After payment fails, GET `/api/payments/orders/{id}/payment` | `client_secret` present for retry | [ ] |
| E2 | Retry page loads for failed payment | Navigate to `/orders/{id}/pay` | Stripe Elements render with existing client_secret | [ ] |
| E3 | Succeeded payment redirects from retry | Navigate to `/orders/{id}/pay` for completed order | Redirects to confirmation page | [ ] |
| E4 | Expired payment cannot retry | After reaper expires order, GET payment status | No client_secret, appropriate error | [ ] |

---

## Section F: Stock Reservation & Reaper

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| F1 | Reaper background task starts | Check FastAPI logs on startup | "Order reaper started" message present | [ ] |
| F2 | Stale order detected | Set `CHECKOUT_TIMEOUT=1` (1 min), create order, wait 2 min | Reaper finds and expires the order | [ ] |
| F3 | Stock released on expiry | After F2, check variant stock_quantity | Stock restored to pre-checkout level | [ ] |
| F4 | Payment record marked expired | After F2, check payment_records status | Status = "expired" | [ ] |
| F5 | PaymentIntent canceled | After F2, check Stripe dashboard or logs | PI canceled (or logged as cancel attempt) | [ ] |

---

## Section G: Merchant Self-Signup

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| G1 | Customer upgrades to merchant | Login as customer, POST `/api/auth/upgrade-to-merchant` | 200, "Account upgraded to merchant" | [ ] |
| G2 | Already-merchant rejected | Login as merchant, POST upgrade | 400 "already_merchant" | [ ] |
| G3 | Admin cannot upgrade | Login as admin, POST upgrade | 400 "invalid_role" | [ ] |
| G4 | Token refresh after upgrade | POST `/api/auth/refresh` after G1 | New JWT contains `role: "merchant"` | [ ] |
| G5 | Merchant onboard creates account | Login as merchant, POST `/api/payments/merchants/onboard` | Returns `account_id`, `onboarding_url` | [ ] |
| G6 | Merchant status returns data | After G5, GET `/api/payments/merchants/status` | Returns account status, charges_enabled, etc. | [ ] |

---

## Section H: Webhook Handlers

**Requires:** Stripe CLI with `stripe listen --forward-to localhost:80/api/payments/webhook`

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| H1 | payment_intent.succeeded | Complete a payment or `stripe trigger payment_intent.succeeded` | Order -> "completed", payment -> "succeeded" | [ ] |
| H2 | payment_intent.payment_failed | Use declined card or `stripe trigger payment_intent.payment_failed` | Order -> "rejected", stock released | [ ] |
| H3 | charge.succeeded | Complete payment (fires automatically after pi.succeeded) | `charge_id` stored in payment_records | [ ] |
| H4 | charge.refunded | Refund from Stripe dashboard or API | Refund record created, order -> "refunded" | [ ] |
| H5 | Duplicate event ignored | Send same event ID twice | Second returns "duplicate" | [ ] |
| H6 | Invalid signature rejected | POST to webhook with tampered payload | 400 "Invalid signature" | [ ] |

---

## Section I: Provider Swapability

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| I1 | Factory returns StripeProvider | Check `get_payment_provider()` with `payment_provider=stripe` | Returns `StripeProvider` instance | [ ] |
| I2 | Unknown provider raises error | Set `payment_provider=unknown` | `ValueError: Unknown payment provider: unknown` | [ ] |
| I3 | No stripe imports in services | `grep -r "import stripe" modules/ --include="*.py" \| grep -v stripe_provider.py` | No matches | [ ] |

---

## Section J: Stripe Test Cards

**Requires:** Full Stripe integration active (keys + webhook forwarding)

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| J1 | Successful payment (4242) | Complete checkout with `4242 4242 4242 4242` | Payment succeeds, order completed | [ ] |
| J2 | 3D Secure success | Use `4000 0025 0000 3155` | 3DS popup -> authenticate -> succeeds | [ ] |
| J3 | Generic decline | Use `4000 0000 0000 0002` | "Card declined" error | [ ] |
| J4 | Insufficient funds | Use `4000 0000 0000 9995` | "Insufficient funds" error | [ ] |
| J5 | 3DS auth fails | Use `4000 0082 6000 3178` | Authentication fails, payment fails | [ ] |
| J6 | Full refund | After J1, refund from API | Order -> "refunded", amount returned | [ ] |

---

## Section K: Frontend Integration

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| K1 | Checkout page renders 3 steps | Navigate to `/checkout` with items in cart | Shipping -> Review -> Payment steps shown | [ ] |
| K2 | Stripe Elements render | Reach payment step | PaymentElement loads with dark theme | [ ] |
| K3 | Confirmation shows success | After successful payment redirect | Green checkmark, "Payment successful!" | [ ] |
| K4 | Merchant register page shows for customers | Login as customer, navigate to `/merchant/register` | "Become a Merchant" upgrade page | [ ] |
| K5 | Merchant dashboard shows for merchants | Login as merchant, navigate to `/merchant/dashboard` | Account status, Stripe dashboard link | [ ] |

---

## Section L: Admin Payment Method Toggles

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| L1 | Migration 011 applies | Run `CREATE TABLE IF NOT EXISTS ecommerce.payment_settings` via async engine | Table created, no errors | [x] |
| L2 | API health after deploy | `curl http://localhost/api/health` after rebuilding fastapi with new code | `{"status":"ok","services":{"redis":"ok","db":"ok"}}` | [x] |
| L3 | Frontend builds with payments page | `npm run build` in frontend | Build succeeds, `/admin/payments` route included | [x] |
| L4 | Next.js container starts | `docker compose up -d nextjs` after rebuild | Container starts, `Ready in Xms` in logs | [x] |
| L5 | Payments nav link visible | Navigate to admin panel on lg+ viewport | "Payments" link appears in sidebar between GDPR and SEO | [x] |
| L6 | Payments page loads | Navigate to `/admin/payments` | Page renders with 7 payment method toggle cards | [x] |
| L7 | GET settings — no customization | `GET /api/payments/settings/payment-methods` with no DB rows | Returns all methods `true`, `customized: false` | [ ] |
| L8 | PUT settings — toggle methods | `PUT /api/payments/settings/payment-methods` with `{"methods": {"card": true, "klarna": false, ...}}` | Returns updated methods, `customized: true` | [ ] |
| L9 | GET settings — after customization | `GET /api/payments/settings/payment-methods` after L8 | Returns stored toggles, `customized: true` | [ ] |
| L10 | Non-admin rejected | `GET /api/payments/settings/payment-methods` as customer | 403 Forbidden | [ ] |
| L11 | Checkout uses automatic when no settings | Create checkout with no `payment_settings` row in DB | PaymentIntent created with `automatic_payment_methods: {enabled: true}` | [ ] |
| L12 | Checkout uses explicit methods | Set `payment_methods` setting to `{"card": true, "link": true, "klarna": false, ...}`, then checkout | PaymentIntent created with `payment_method_types: ["card", "link"]` | [ ] |
| L13 | All methods disabled falls back to automatic | Set all methods to `false` in DB, then checkout | Falls back to `automatic_payment_methods` (no empty list sent) | [ ] |
| L14 | Toggle UI saves and reflects | Toggle methods on/off in admin UI, click Save, refresh page | Saved state persists across page reload | [ ] |
| L15 | Reset to Auto | Click "Reset to Auto" button after customizing | All methods toggled on, dirty state shown | [ ] |

---

## Section M: Product Catalog & Coupons UI

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| M1 | Catalog layout renders sub-tabs | Navigate to `/admin/catalog` | Horizontal tabs: All Products, Coupons, Shipping Rates, Tax Rates | [x] |
| M2 | Products page with status filters | Navigate to `/admin/catalog/products` | Status filter pills (All/Active/Archived) visible, products listed | [x] |
| M3 | Coupons page loads | Navigate to `/admin/catalog/coupons` | Coupons table with status filters, create button | [x] |
| M4 | Shipping/Tax placeholders | Navigate to `/admin/catalog/shipping` and `/admin/catalog/tax` | "Coming soon" placeholder pages | [x] |
| M5 | Subscriptions sidebar link | View admin sidebar | "Subscriptions" link between Product Catalog and Orders | [x] |

---

## Section N: Subscriptions Lifecycle

**Requires:** Stripe API keys configured

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| N1 | Create recurring product | POST `/api/ecommerce/products` with `pricing_type: "recurring"`, `status: "active"` | Product created, Stripe product + recurring price synced | [x] |
| N2 | Create subscription | Login as customer, POST `/api/ecommerce/subscriptions` with product_id | 201, returns `stripe_subscription_id`, `client_secret`, status `incomplete` | [x] |
| N3 | List customer subscriptions | GET `/api/ecommerce/subscriptions` as customer | Returns list with product_name, status | [x] |
| N4 | Admin list subscriptions | GET `/api/ecommerce/admin/subscriptions` as admin | Returns paginated list with user_email, product_name, status | [x] |
| N5 | Admin filter by status | GET `/api/ecommerce/admin/subscriptions?status=incomplete` | Filtered results returned | [x] |
| N6 | Cancel subscription | POST `/api/ecommerce/subscriptions/{id}/cancel` as customer | `cancel_at_period_end: true`, `canceled_at` set | [x] |
| N7 | Non-recurring product rejected | POST subscription for a `pricing_type: "one_time"` product | 400 "Product is not a recurring subscription product" | [x] |

---

## Section O: Stripe Coupon Sync

**Requires:** Stripe API keys configured

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| O1 | Create coupon syncs to Stripe | POST `/api/ecommerce/admin/discounts` with percentage coupon | Stripe Coupon + Promotion Code created, IDs stored | [x] |
| O2 | Subscribe with coupon | POST subscription with `discount_code` | Subscription created with discount applied | [x] |
| O3 | One-time coupon rejected on subscription | Create coupon with `applies_to: "one_time"`, use on subscription | 400 "This coupon cannot be applied to recurring subscriptions" | [x] |
| O4 | Recurring coupon rejected on one-time checkout | Create coupon with `applies_to: "recurring"`, use on cart checkout | 400 "This coupon can only be used on recurring subscriptions" | [x] |

---

## Test Summary

| Section | Tests | Description |
|---------|-------|-------------|
| A | 4 | CSRF Token Flow |
| B | 6 | Checkout — Happy Path |
| C | 5 | Checkout — Error Handling |
| D | 4 | Order Confirmation & Polling |
| E | 4 | Payment Retry |
| F | 5 | Stock Reservation & Reaper |
| G | 6 | Merchant Self-Signup |
| H | 6 | Webhook Handlers |
| I | 3 | Provider Swapability |
| J | 6 | Stripe Test Cards |
| K | 5 | Frontend Integration |
| L | 15 | Admin Payment Method Toggles |
| M | 5 | Product Catalog & Coupons UI |
| N | 7 | Subscriptions Lifecycle |
| O | 4 | Stripe Coupon Sync |
| **Total** | **85** | |

### Tests by Stripe dependency:
- **Without Stripe keys (33 tests):** A1-A4, C1-C5, G1-G4, I1-I3, F1, L1-L10, L13, L15, M1-M5
- **With Stripe test keys (52 tests):** B1-B6, D1-D4, E1-E4, F2-F5, G5-G6, H1-H6, J1-J6, K1-K5, L11-L12, L14, N1-N7, O1-O4

### Executed tests:
- **2026-02-18:** L1-L6 passed (migration, API health, frontend build, container start, nav link visible, payments page loads)
- **2026-02-19:** M1-M5 passed (catalog layout, products with filters, coupons page, placeholders, subscriptions sidebar)
- **2026-02-19:** N1-N7 passed (recurring product creation, subscription create/list/admin list/filter/cancel, non-recurring rejection)
- **2026-02-19:** O1-O4 passed (coupon Stripe sync, subscribe with coupon, one-time coupon rejected on subscription, recurring coupon rejected on checkout)
