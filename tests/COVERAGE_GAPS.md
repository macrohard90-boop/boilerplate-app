# Phase 4: Coverage Gaps Report

## Summary

| Category | Files | Tests | Coverage |
|----------|-------|-------|----------|
| Tier 1 — Unit tests | 11 | ~150 | High |
| Tier 2 — Integration tests | 5 | ~25 | Medium-High |
| Tier 3 — E2E / API tests | 3 | ~15 | Medium |
| **Total** | **19** | **~190** | |

## What IS Tested

### Stripe Provider (38 unit tests)
- All 22 Stripe SDK calls mocked and verified
- Payment intents: create, get_status, cancel, refund
- Customers: create with metadata
- Subscriptions: create, cancel (immediate + at_period_end)
- Coupons: create, delete, promotion codes
- Catalog: products, prices, archive
- Checkout sessions: create with line_items, discounts
- Webhook signature verification

### Webhook Processing (30 unit tests + 5 integration)
- All 12 event handlers tested
- Signature verification (valid + invalid)
- Idempotency (duplicate event detection)
- Event recording in webhook_events table
- payment_intent.succeeded → payment record + order update
- payment_intent.payment_failed → inventory release + order rejection
- charge.succeeded → charge_id storage
- charge.refunded → refund record creation
- account.updated → merchant status transitions (active/restricted/disabled)
- product.updated/deleted → catalog sync
- price.updated/deleted → price ID cleanup
- customer.subscription.* → subscription status update
- invoice.payment_failed → past_due status
- checkout.session.completed → cart conversion

### Checkout Flow (9 unit + 5 integration + 3 e2e)
- Cart → order → payment intent pipeline
- Zero-cost order bypass (100% discount)
- Stripe failure → inventory release + order rejection
- Payment method toggles forwarded to Stripe
- Billing defaults to shipping address
- Discount code application with real cart subtotal (Bug B3 fix)
- API endpoint request/response cycle
- Refund endpoint with status validation

### Subscription Checkout (8 unit + 4 integration)
- Line item building from variant/product prices
- Stripe customer auto-creation
- Coupon forwarding to checkout session (Bug B4 fix)
- Empty cart / no cart error handling
- Unsynced product rejection
- Discount usage increment

### Discount/Coupon System (18 unit + 5 integration)
- validate_discount: all 7 validation checks
- calculate_discount: percentage, fixed, free_shipping, cap at subtotal
- Stripe coupon sync (create + promotion code)
- Stripe coupon deletion on deactivation
- Free shipping skips Stripe sync
- Error resilience (Stripe failures logged, not thrown)
- Admin CRUD: create, update, deactivate
- Value change → coupon recreation

### Catalog Sync (14 unit tests)
- Product sync (new + update)
- Variant sync with price rotation
- Archive product in catalog
- Retry sync
- Error marking (sync_status = 'error')
- Image URL building

### Payment Records (8 unit tests)
- CRUD: create, update status, get by order/provider ID
- Refund record with negative amount
- Method field storage

### Payment Settings (8 unit tests)
- Toggle enabled/disabled methods
- Filter unsupported methods
- CRUD: upsert, get, delete

### Merchant Onboarding (8 unit + 5 integration)
- New merchant → Stripe Connect Express
- Existing merchant → fresh onboarding link
- Status retrieval
- Dashboard login link generation
- account.updated webhook status transitions

### Order Reaper (3 unit tests)
- Stale order expiry
- Inventory release on expiry
- Cancel failure handling

---

## What is NOT Tested (Coverage Gaps)

### 1. Stripe SDK Error Handling (Medium Risk)
- **Gap**: Individual Stripe API error codes (card_declined, rate_limit, etc.) are not tested
- **Impact**: Users may see raw Stripe errors instead of friendly messages
- **Recommendation**: Add tests for `stripe.error.CardError`, `stripe.error.RateLimitError`, `stripe.error.InvalidRequestError` in StripeProvider methods

### 2. Webhook Retry Behavior (Low Risk)
- **Gap**: What happens when a webhook handler partially succeeds then fails mid-transaction
- **Impact**: Potential for inconsistent state (payment updated but order not)
- **Recommendation**: Test with DB transaction failures mid-handler

### 3. Currency Handling (Medium Risk)
- **Gap**: All tests use USD. No tests for zero-decimal currencies (JPY) or multi-currency
- **Impact**: JPY amounts would be 100x wrong (2999 yen ≠ $29.99)
- **Recommendation**: Add tests with `currency="JPY"` to verify amount handling

### 4. Subscription Trial Periods (Low Risk)
- **Gap**: Trial period logic (trial_start/trial_end timestamps) is set but never asserted
- **Impact**: Trial end dates could be wrong without detection
- **Recommendation**: Add test that verifies trial_end = now + trial_period_days

### 5. Pagination Edge Cases (Low Risk)
- **Gap**: `list_all_subscriptions` and `list_discounts` pagination not tested (page_size=0, page > total_pages)
- **Impact**: Division by zero on page_size=0 (math.ceil(total / 0))
- **Recommendation**: Add edge case test; consider guarding against page_size=0

### 6. Admin Subscription Cancel (Low Risk)
- **Gap**: `admin_cancel_subscription` (no user_id check) has no tests
- **Impact**: Admin cancellation bypass path untested
- **Recommendation**: Mirror the user cancel tests for admin variant

### 7. Order Service (create_order_from_cart) (Medium Risk)
- **Gap**: The `order_service.create_order_from_cart` function is always mocked in checkout tests
- **Impact**: Cart-to-order conversion logic (stock reservation, pricing snapshots, order numbering) is untested
- **Recommendation**: Add dedicated integration tests for order_service

### 8. Concurrent Webhook Processing (Medium Risk)
- **Gap**: Two webhooks for the same payment_intent arriving simultaneously
- **Impact**: Could create duplicate payment records or double-update order status
- **Recommendation**: Test with `asyncio.gather` on two `verify_and_process_webhook` calls with same event

### 9. Stripe Connect Fee Tiers (Low Risk)
- **Gap**: Application fee calculation for merchant payments not tested
- **Impact**: Fee amounts could be wrong
- **Recommendation**: Add tests for fee tier calculation in checkout with merchant context

### 10. Frontend Stripe.js Integration (High Risk)
- **Gap**: Playwright tests are skipped (require running app + real Stripe keys)
- **Impact**: Card input, payment confirmation, error display untested in browser
- **Recommendation**: Set up CI pipeline with Stripe test keys; run Playwright headed for manual verification

### 11. Race Condition: Double Checkout (High Risk)
- **Gap**: No row-level locking on cart during checkout
- **Impact**: Two simultaneous requests can create two orders from one cart
- **Recommendation**: Add `SELECT ... FOR UPDATE` on cart row in `create_order_from_cart`; the test in `test_race_condition.py` demonstrates this vulnerability

### 12. Discount Code Timing (Low Risk)
- **Gap**: `valid_from` in the future is tested but `valid_from` exactly at boundary (now) is not
- **Impact**: Off-by-one on timezone boundaries
- **Recommendation**: Test with valid_from = now (should succeed)

---

## Monitoring Recommendations

### Metrics to Track in Production
1. **Payment success rate**: `succeeded / (succeeded + failed)` — alert if below 95%
2. **Webhook processing time**: P99 latency — alert if > 5s
3. **Duplicate webhook rate**: `duplicate / total` — informational, high rate may indicate Stripe retries
4. **Failed catalog syncs**: Count of `stripe_sync_status = 'error'` — alert if growing
5. **Stale orders**: Orders in `processing` for > 30 minutes — reaper should catch these
6. **Refund rate**: `refunded / completed` — alert if above 10% (may indicate product issues)

### Alerts to Configure
- Webhook signature failures (potential attack)
- Payment creation failures (Stripe outage)
- Subscription status flapping (active → past_due → active in < 1 hour)
- Cart conversion rate drop (may indicate checkout bugs)

---

## Bugs Fixed in This Audit

### Bug B3: min_order_amount Validation Bypass (FIXED)
- **File**: `modules/payments/services/checkout_service.py`
- **Issue**: `_apply_discount_to_cart` passed `subtotal=0` to `validate_discount`, causing any coupon with `min_order_amount > 0` to always be rejected
- **Fix**: Added SQL query to calculate real cart subtotal before validation
- **Test**: `test_checkout_service.py::TestApplyDiscountToCart::test_valid_discount_applied`

### Bug B4: Missing Coupon in Subscription Checkout (FIXED)
- **File**: `modules/payments/services/subscription_checkout_service.py`
- **Issue**: `stripe_coupon_id` was fetched but never forwarded to `create_checkout_session`
- **Fix**: Added `discounts` parameter to session creation; updated provider interface
- **Test**: `test_subscription_checkout.py::test_discount_passes_coupon_to_session`

### Variant-Level Images & Admin UX — Manual Test Results (2026-02-26)

**All 180 automated tests passing** (3 skipped, 10 xfailed — all pre-existing).

Manual verification performed:

| Test Case | Result |
|-----------|--------|
| Admin: Upload product-level image (no variant tab) → no variant badge | Pass |
| Admin: Select variant tab, upload → variant badge shown | Pass |
| Admin: Variant images show under correct tab, product images under "Product" | Pass |
| Admin: Only "Default" variant → no variant tabs shown | Pass |
| Admin: Add new variants → tabs appear immediately (onVariantsChange callback) | Pass |
| Admin: Delete variant → variant images removed from grid without refresh | Pass |
| Admin: Delete variant → styled confirmation modal (not window.confirm) | Pass |
| Admin: Product update → variant sync status badges refresh immediately | Pass |
| Admin: Create product → no "Recurring" pricing option | Pass |
| Admin: Create product → no "Archived" status option | Pass |
| Admin: Create product with duplicate SKU → toast shows "SKU 'X' already exists" | Pass |
| Storefront: Select variant with images → gallery swaps to variant images | Pass |
| Storefront: Select variant without images → falls back to product-level images | Pass |
| Cart API: `GET /ecommerce/cart` returns `image_url` per item (variant preferred, product fallback) | Pass |
| Checkout page: Images appear next to line items instead of grey squares | Pass |
| Guest cart: `image_url` included in Redis-stored cart items | Pass |

---

## Test File Index

```
tests/
  conftest.py                              # DB fixtures, Stripe mocks, seed helpers
  factories.py                             # make_* factories for all domain objects
  pytest.ini                               # asyncio_mode=auto, markers

  unit/
    test_stripe_provider.py                # 38 tests — all Stripe SDK calls
    test_webhook_service.py                # 30 tests — all 12 event handlers
    test_payment_service.py                # 8 tests  — payment record CRUD
    test_payment_settings.py               # 8 tests  — payment method toggles
    test_checkout_service.py               # 9 tests  — checkout flow + discounts
    test_subscription_checkout.py          # 8 tests  — subscription checkout session
    test_subscription_service.py           # 14 tests — subscription lifecycle
    test_discount_service.py               # 18 tests — validation, sync, CRUD
    test_catalog_sync.py                   # 14 tests — product/variant sync
    test_order_reaper.py                   # 3 tests  — stale order cleanup
    test_merchant_service.py               # 8 tests  — Connect Express onboarding

  integration/
    test_checkout_flow.py                  # 5 tests  — full checkout pipeline
    test_subscription_flow.py              # 5 tests  — subscription lifecycle
    test_webhook_flow.py                   # 5 tests  — webhook verify→process→DB
    test_coupon_flow.py                    # 5 tests  — coupon CRUD + Stripe sync
    test_merchant_flow.py                  # 5 tests  — merchant onboarding

  e2e/
    test_checkout_api.py                   # 8 tests  — HTTP endpoint tests
    test_race_condition.py                 # 2 tests  — concurrent checkout vulnerability
    test_playwright_checkout.py            # 3 tests  — browser tests (skipped until app running)
```

## Running the Tests

```bash
# All unit tests (fast, no external deps)
pytest tests/unit -m unit -v

# All integration tests (needs PostgreSQL running)
pytest tests/integration -m integration -v

# All e2e tests (needs PostgreSQL; Playwright tests need full stack)
pytest tests/e2e -m e2e -v

# Everything except slow tests
pytest tests/ -m "not slow" -v

# Just the race condition test
pytest tests/e2e/test_race_condition.py -v

# With coverage report
pytest tests/ --cov=modules/payments --cov=modules/ecommerce --cov-report=term-missing
```
