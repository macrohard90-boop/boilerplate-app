# Phase 4: Payment Processing

**Estimate:** 4-5 hours
**Depends on:** Phase 3, Phase 5
**Category:** Commerce & transactions

## Goal
Integrate Stripe as the default payment provider via the PaymentProvider adapter pattern, implement the cart-to-order conversion flow, webhook handling for payment events, and merchant onboarding via Stripe Connect. At the end of this phase, a user can complete a full checkout and payment lifecycle.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 1.1 (PaymentProvider interface), 6 (Payment Lifecycle), and 10 (Environment Variables — Stripe section) for the payment specification.

## Deliverables

1. **PaymentProvider interface** (modules/payments/interfaces/):
   - ABC with methods: `create_payment`, `refund`, `get_status`, `create_merchant`, `list_transactions`
   - `PaymentResult`, `RefundResult`, `PaymentStatus`, `MerchantAccount`, `Transaction` response models
   - Provider-agnostic — any payment gateway can implement this interface

2. **Stripe adapter** (modules/payments/adapters/):
   - Implements PaymentProvider ABC using Stripe SDK
   - Payment Intents API for creating and confirming payments
   - Refunds API (partial and full refunds)
   - Payment status retrieval
   - Stripe Connect Express for merchant accounts
   - Configurable platform fee (`PLATFORM_FEE_PERCENT`, default 10%)

3. **Cart-to-order conversion** (modules/payments/services/):
   - Validate cart contents (stock availability, price verification)
   - Reserve inventory (decrement stock, handle race conditions)
   - Create order record with line items, pricing snapshot, addresses
   - Price lock: use prices at conversion time, store in `product_snapshot` JSONB
   - Apply discount codes: validate code, calculate discount, update totals
   - Calculate tax amount (placeholder for tax service integration)
   - Create payment intent via PaymentProvider
   - On payment success: order status → completed, cart status → converted
   - On payment failure: release inventory reservation, order status → rejected

4. **Payment lifecycle management** (modules/payments/services/):
   - Status flow: `pending → processing → accepted → completed` or `→ rejected` or `→ refunded`
   - Create `payment_records` entry for each payment attempt
   - Idempotency: prevent duplicate payments for same order
   - Currency handling: pass through order currency to Stripe (INT cents)

5. **Webhook handling** (modules/payments/routes/):
   - `POST /api/payments/webhook` — receives Stripe webhook events
   - Signature validation using `STRIPE_WEBHOOK_SECRET`
   - Idempotency: store event_id, skip duplicate events
   - Key events handled:
     - `payment_intent.succeeded` → update order status, record payment
     - `payment_intent.payment_failed` → update order status, release inventory
     - `charge.refunded` → create refund record, update order status
     - `account.updated` → update merchant account status
   - Error handling: return 200 to Stripe even on processing errors (log and retry internally)

6. **Merchant onboarding** (modules/payments/services/):
   - `POST /api/payments/merchants/onboard` — generate Stripe Connect onboarding link
   - `GET /api/payments/merchants/status` — check onboarding completion
   - Stripe Express accounts: simplified onboarding, platform handles checkout
   - Platform fee deduction on each merchant transaction
   - Dashboard link generation for merchants to view payouts

7. **Checkout endpoints** (modules/payments/routes/):
   - `POST /api/checkout` — convert cart to order, create payment intent, return client_secret
   - `GET /api/orders/{id}` — order details with payment status
   - `GET /api/orders` — list user's orders (paginated)
   - `POST /api/orders/{id}/refund` — initiate refund (admin or order owner)
   - All endpoints require authentication

8. **Pydantic schemas** (modules/payments/models/):
   - `CheckoutRequest`: cart_id, shipping_address, billing_address, discount_code (optional)
   - `CheckoutResponse`: order_id, client_secret, total
   - `OrderResponse`: full order details with line items and payment status
   - `RefundRequest`: amount (optional for partial), reason
   - `WebhookEvent`: Stripe event payload model

## Acceptance Criteria
- [ ] PaymentProvider interface defined with all required methods
- [ ] Stripe adapter implements full interface
- [ ] Cart-to-order conversion creates order with correct totals (INT cents)
- [ ] Inventory is reserved on checkout, released on payment failure
- [ ] Discount codes apply correctly (percentage, fixed, free shipping)
- [ ] Payment intent created with correct amount and currency
- [ ] Webhook signature validation rejects invalid signatures
- [ ] `payment_intent.succeeded` webhook updates order to completed
- [ ] `charge.refunded` webhook creates refund record
- [ ] Duplicate webhook events are ignored (idempotency)
- [ ] Merchant onboarding generates valid Stripe Connect link
- [ ] Platform fee is applied to merchant transactions
- [ ] Refund flow works (partial and full)
- [ ] All monetary values stored as INT cents with currency CHAR(3)
- [ ] All checkout/order endpoints require authentication
- [ ] Product snapshots stored in JSONB (price at time of purchase preserved)

## Implementation Notes
- Stripe SDK: `stripe` Python package
- Payment amounts in cents (matches our INT cents convention and Stripe's API)
- Webhook endpoint must be excluded from CSRF protection (Stripe signs with its own scheme)
- Use database transactions for cart-to-order conversion (atomic operation)
- Inventory reservation: use `SELECT ... FOR UPDATE` to prevent race conditions
- Consider retry logic for failed webhook processing
- Test with Stripe test mode keys — never use live keys in development

## Files to Create
- `modules/payments/interfaces/payment_provider.py` — PaymentProvider ABC + response models
- `modules/payments/adapters/stripe_provider.py` — Stripe implementation
- `modules/payments/services/checkout_service.py` — Cart-to-order conversion, inventory, pricing
- `modules/payments/services/payment_service.py` — Payment lifecycle, refunds
- `modules/payments/services/merchant_service.py` — Stripe Connect onboarding
- `modules/payments/services/webhook_service.py` — Webhook processing and idempotency
- `modules/payments/models/schemas.py` — Pydantic request/response models
- `modules/payments/routes/checkout_routes.py` — Checkout and order endpoints
- `modules/payments/routes/webhook_routes.py` — Stripe webhook receiver
- `modules/payments/routes/merchant_routes.py` — Merchant onboarding endpoints
- `modules/payments/config.py` — Payment module configuration
- Modified: `backend/main.py` — Mount payment routes
- Modified: `backend/requirements.txt` — Add stripe
- Modified: `.env.template` — Add STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET
