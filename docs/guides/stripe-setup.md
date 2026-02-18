# Stripe Integration Setup Guide

## Quick Start

### 1. Create a Stripe Account

1. Go to [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register) and create an account
2. Stay in **test mode** (toggle in the Stripe dashboard sidebar)

### 2. Get API Keys

1. Navigate to **Developers > API keys** in the Stripe dashboard
2. Copy the **Publishable key** (`pk_test_...`) and **Secret key** (`sk_test_...`)

### 3. Configure Environment

Add your keys to `.env`:

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

The `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is automatically set from `STRIPE_PUBLISHABLE_KEY` in `.env.template`.

### 4. Rebuild and Start

```bash
docker compose up -d --build
```

The frontend build inlines `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` at build time (Next.js requirement), so a rebuild is required whenever the publishable key changes.

---

## Webhook Setup

### Local Development (Stripe CLI)

1. **Install Stripe CLI:**
   ```bash
   # ARM64 Linux/WSL2:
   curl -L https://github.com/stripe/stripe-cli/releases/latest/download/stripe_linux_arm64.tar.gz | tar xz
   sudo mv stripe /usr/local/bin/

   # macOS:
   brew install stripe/stripe-cli/stripe
   ```

2. **Login:**
   ```bash
   stripe login
   ```

3. **Forward webhooks:**
   ```bash
   stripe listen --forward-to http://localhost:80/api/payments/webhook
   ```
   Copy the `whsec_...` secret shown and add it to `.env` as `STRIPE_WEBHOOK_SECRET`, then restart FastAPI.

4. **Test events:**
   ```bash
   stripe trigger payment_intent.succeeded
   stripe trigger payment_intent.payment_failed
   stripe trigger charge.refunded
   ```

### Production Webhooks

1. Go to **Developers > Webhooks** in the Stripe dashboard
2. Click **Add endpoint**
3. URL: `https://your-domain.com/api/payments/webhook`
4. Events to subscribe to:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.succeeded`
   - `charge.refunded`
   - `account.updated` (for Stripe Connect)
5. Copy the signing secret and set `STRIPE_WEBHOOK_SECRET` in production `.env`

---

## Stripe Connect (Merchants)

### Enable Connect

1. Go to **Connect > Get started** in the Stripe dashboard
2. Choose **Express** account type
3. Complete the platform profile

### Merchant Flow

1. Customer registers on the platform
2. Customer navigates to **Become a Merchant** (or `/merchant/register`)
3. Account is upgraded to `merchant` role via `POST /api/auth/upgrade-to-merchant`
4. Merchant starts Stripe Connect onboarding at `/merchant/onboard`
   - Calls `POST /api/payments/merchants/onboard` to create Express account
   - Redirected to Stripe-hosted KYC/onboarding
5. After onboarding, `account.updated` webhook fires and updates merchant status
6. Merchant views their dashboard at `/merchant/dashboard`
   - Shows Stripe account status, charges/payouts enabled
   - Links to Stripe Express dashboard

### Connect Return/Refresh URLs

The merchant onboarding endpoint sets:
- **Return URL:** Where Stripe redirects after completing onboarding
- **Refresh URL:** Where Stripe redirects if the link expires

These are configured in `modules/payments/services/merchant_service.py`.

---

## Test Cards

### Successful Payments
| Card Number | Description |
|---|---|
| `4242 4242 4242 4242` | Succeeds immediately |
| `4000 0025 0000 3155` | Requires 3D Secure authentication (succeeds) |

### Declined Payments
| Card Number | Description |
|---|---|
| `4000 0000 0000 0002` | Generic decline |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0000 0000 0069` | Expired card |
| `4000 0000 0000 0127` | Incorrect CVC |
| `4000 0000 0000 0119` | Processing error |

### 3D Secure
| Card Number | Description |
|---|---|
| `4000 0082 6000 3178` | 3DS required, authentication fails |

Use any future expiry date (e.g., `12/34`), any 3-digit CVC, and any 5-digit ZIP code.

---

## Payment Flow Architecture

```
Customer                    Frontend                    Backend                     Stripe
   |                           |                           |                          |
   |  Add to cart, checkout    |                           |                          |
   |-------------------------->|                           |                          |
   |                           | POST /payments/checkout   |                          |
   |                           |-------------------------->| create order + reserve   |
   |                           |                           | stock                    |
   |                           |                           |------------------------->|
   |                           |                           |  PaymentIntent created   |
   |                           |                           |<-------------------------|
   |                           |  { client_secret }        |                          |
   |                           |<--------------------------|                          |
   |                           |                           |                          |
   |  Enter card details       |                           |                          |
   |-------------------------->|                           |                          |
   |                           | stripe.confirmPayment()   |                          |
   |                           |-------------------------------------------------->---|
   |                           |                           |                          |
   |                           |  redirect to /confirmation|                          |
   |                           |<-----------------------------------------------------|
   |                           |                           |                          |
   |                           |                           |  webhook: pi.succeeded   |
   |                           |                           |<-------------------------|
   |                           |                           | update order + payment   |
   |                           |                           |                          |
   |                           |                           |  webhook: charge.succeeded|
   |                           |                           |<-------------------------|
   |                           |                           | store charge_id (audit)  |
```

---

## Stock Reservation & Stale Order Reaper

Stock is reserved (decremented) when the order is created at checkout, **before** payment completes. This ensures accurate stock counts but requires cleanup for abandoned checkouts.

### Stale Order Reaper

A background task runs every 5 minutes and finds orders in `processing` status older than `CHECKOUT_TIMEOUT` minutes (default: 60). For each stale order:

1. Releases reserved inventory (adds stock back)
2. Updates order status to `expired`
3. Updates payment record status to `expired`
4. Cancels the Stripe PaymentIntent (best-effort)

Configuration: Set `CHECKOUT_TIMEOUT` in `.env` (in minutes).

### Payment Failure

When a payment fails (webhook `payment_intent.payment_failed`), inventory is released immediately and the order is marked `rejected`. The customer can retry from `/orders/{id}/pay`.

---

## Going Live Checklist

1. Switch Stripe to **live mode** in the dashboard
2. Copy **live** API keys (`pk_live_...`, `sk_live_...`) to `.env`
3. Create a **live** webhook endpoint in Stripe dashboard (same events as test)
4. Update `STRIPE_WEBHOOK_SECRET` with the live signing secret
5. Rebuild frontend: `docker compose up -d --build` (to inline live publishable key)
6. Test with a real card (small amount like $1), verify it appears in Stripe dashboard
7. Verify refund works: refund the test charge from the Stripe dashboard or via API

---

## File Reference

### Backend
| File | Purpose |
|---|---|
| `backend/core/config.py` | `stripe_secret_key`, `stripe_publishable_key`, `stripe_webhook_secret` settings |
| `modules/payments/adapters/stripe_provider.py` | Stripe API implementation (PaymentIntents, Connect, refunds) |
| `modules/payments/interfaces/payment_provider.py` | `PaymentProvider` ABC — implement this to swap providers |
| `modules/payments/routes/checkout_routes.py` | Checkout, payment status, refund endpoints |
| `modules/payments/routes/webhook_routes.py` | Webhook receiver with signature verification |
| `modules/payments/routes/merchant_routes.py` | Merchant onboarding, status, dashboard link |
| `modules/payments/services/checkout_service.py` | Cart-to-order conversion + PaymentIntent creation |
| `modules/payments/services/webhook_service.py` | Webhook event handlers (payment, charge, account) |
| `modules/payments/services/order_reaper.py` | Background task to expire abandoned orders |
| `modules/payments/services/merchant_service.py` | Stripe Connect Express account management |

### Frontend
| File | Purpose |
|---|---|
| `frontend/lib/stripe.ts` | Stripe.js loader singleton |
| `frontend/app/checkout/page.tsx` | Checkout flow with Stripe Elements |
| `frontend/app/orders/[id]/confirmation/page.tsx` | Payment result + polling |
| `frontend/app/orders/[id]/pay/page.tsx` | Payment retry for failed payments |
| `frontend/app/merchant/register/page.tsx` | Customer-to-merchant upgrade |
| `frontend/app/merchant/onboard/page.tsx` | Stripe Connect onboarding |
| `frontend/app/merchant/dashboard/page.tsx` | Merchant status + dashboard link |

### Environment Variables
| Variable | Where Used | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | Backend | Stripe secret API key |
| `STRIPE_PUBLISHABLE_KEY` | `.env` only | Source for the frontend key |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Frontend (build-time) | Stripe publishable key inlined into client bundle |
| `STRIPE_WEBHOOK_SECRET` | Backend | Webhook signing secret |
| `CHECKOUT_TIMEOUT` | Backend | Minutes before abandoned orders expire (default: 60) |
| `PLATFORM_FEE_PERCENT` | Backend | Platform fee on merchant payments (default: 10%) |

---

## Provider Swapping

To replace Stripe with another provider:

1. Create a new adapter in `modules/payments/adapters/` implementing the `PaymentProvider` ABC from `modules/payments/interfaces/payment_provider.py`
2. The ABC requires: `create_payment_intent()`, `confirm_payment()`, `get_status()`, `refund()`, `create_connect_account()`, `create_account_link()`, `get_account_status()`, `create_login_link()`
3. Update `modules/payments/adapters/stripe_provider.py:get_stripe_provider()` or create a factory function that reads `settings.payment_provider` and returns the appropriate adapter
4. Update webhook handling in `modules/payments/routes/webhook_routes.py` for the new provider's webhook format
