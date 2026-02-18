# Phase 10: Stripe Integration & Payment Frontend

**Estimate:** 4-5 hours
**Depends on:** Phase 4, Phase 5, Phase 9
**Category:** Payment integration & frontend

## Goal
Connect the real Stripe payment integration end-to-end: replace the mock checkout frontend with Stripe Elements, add merchant self-signup flow, implement stock reservation timeout (stale order reaper), add payment retry, charge tracking, and ensure the payment provider is fully swappable via the adapter pattern. At the end of this phase, a user can complete a real purchase with a Stripe test card.

## Prerequisite Reading
Read `docs/phases/phase-4.md` for the payment backend spec and `docs/ARCHITECTURE.md` section 1.1 for the PaymentProvider interface.

## Deliverables

1. **CSRF token handling fix** (frontend/lib/):
   - [x] Store CSRF token from login/register/refresh responses
   - [x] Auto-attach `X-CSRF-Token` header on POST/PUT/DELETE/PATCH requests
   - [x] Clear token on logout

2. **Stripe.js setup** (frontend/lib/ + docker/):
   - [x] Install `@stripe/stripe-js` and `@stripe/react-stripe-js`
   - [x] Create `stripe.ts` singleton loader using `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
   - [x] Add `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` as Docker build arg
   - [x] Pass build arg in `docker-compose.yml`

3. **Checkout page rewrite** (frontend/app/checkout/):
   - [x] Replace mock checkout with real Stripe Elements (PaymentElement)
   - [x] 3-step flow: Shipping -> Review -> Payment
   - [x] Call `POST /api/payments/checkout` (not mock endpoint)
   - [x] Map frontend address fields to backend AddressSchema
   - [x] Clear cart after checkout API succeeds
   - [x] Dark theme Stripe Elements appearance

4. **Order confirmation rewrite** (frontend/app/orders/[id]/confirmation/):
   - [x] Read `redirect_status` from Stripe redirect URL params
   - [x] Three visual states: succeeded (green), processing (yellow), failed (red)
   - [x] Poll `GET /api/payments/orders/{id}/payment` every 3s
   - [x] Link to retry page on failure

5. **Stock reservation timeout + stale order reaper** (modules/payments/services/):
   - [x] Create `order_reaper.py` background task (runs every 5 minutes)
   - [x] Find orders in 'processing' older than `CHECKOUT_TIMEOUT` (default 60 min)
   - [x] Release inventory, expire order/payment, cancel payment via provider
   - [x] Register as startup background task in `main.py`
   - [x] Add `checkout_timeout` to Settings

6. **Payment retry page** (frontend/app/orders/[id]/pay/):
   - [x] Render Stripe Elements with existing `client_secret` for failed payments
   - [x] Add `client_secret` to `PaymentStatus` dataclass and `PaymentStatusResponse` schema
   - [x] Backend fetches fresh status + client_secret from provider for retryable payments

7. **Merchant self-signup flow** (modules/auth/ + frontend/app/merchant/):
   - [x] `POST /api/auth/upgrade-to-merchant` endpoint (customer -> merchant role)
   - [x] `frontend/app/merchant/register/page.tsx` — upgrade CTA page
   - [x] `frontend/app/merchant/onboard/page.tsx` — Stripe Connect onboarding form
   - [x] `frontend/app/merchant/dashboard/page.tsx` — merchant status + dashboard link
   - [x] Merchant/customer links in Header dropdown and Dashboard page

8. **Charge tracking** (modules/payments/):
   - [x] `charge.succeeded` webhook handler stores charge_id for audit trail
   - [x] Migration `008_payment_charge_id.sql`: add `charge_id` column, `expired` status

9. **Provider swapability** (modules/payments/adapters/ + interfaces/):
   - [x] Central `get_payment_provider()` factory reads `settings.payment_provider`
   - [x] All services use factory instead of direct `get_stripe_provider()` import
   - [x] `cancel_payment()` method on PaymentProvider interface
   - [x] `verify_webhook()` method on PaymentProvider interface
   - [x] `create_account_link()` and `create_login_link()` methods
   - [x] No `import stripe` outside of `stripe_provider.py`

10. **Documentation**:
    - [x] `docs/guides/stripe-setup.md` — comprehensive setup guide
    - [x] Test cards, webhook setup, going-live checklist, provider swapping guide

## Acceptance Criteria
- [x] CSRF tokens captured from auth responses and sent on state-changing requests
- [x] Stripe.js loads via `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` build arg
- [x] Checkout calls `POST /api/payments/checkout` and renders PaymentElement
- [x] Confirmation page reads Stripe redirect params and polls for status
- [x] Stale order reaper runs as background task, releases stock after timeout
- [x] Payment retry page renders Elements with existing client_secret
- [x] Customers can upgrade to merchant role via `/merchant/register`
- [x] Merchants can start Stripe Connect onboarding via `/merchant/onboard`
- [x] charge.succeeded webhook stores charge_id in payment_records
- [x] `import stripe` only appears in `stripe_provider.py` — all services use provider factory
- [x] TypeScript compiles clean, all Python files parse without error
- [x] Stripe setup guide covers: keys, webhooks, Connect, test cards, going live, provider swapping

## Files Created
- `frontend/lib/stripe.ts`
- `frontend/app/checkout/page.tsx` (rewritten)
- `frontend/app/orders/[id]/confirmation/page.tsx` (rewritten)
- `frontend/app/orders/[id]/pay/page.tsx`
- `frontend/app/merchant/register/page.tsx`
- `frontend/app/merchant/onboard/page.tsx`
- `frontend/app/merchant/dashboard/page.tsx`
- `modules/payments/adapters/__init__.py` (provider factory)
- `modules/payments/services/order_reaper.py`
- `migrations/008_payment_charge_id.sql`
- `docs/guides/stripe-setup.md`

## Files Modified
- `frontend/lib/api.ts` — CSRF token storage + auto-header
- `frontend/lib/auth-context.tsx` — capture csrf_token from responses
- `frontend/components/Header.tsx` — merchant/customer nav links
- `frontend/app/dashboard/page.tsx` — merchant CTA card
- `frontend/package.json` — Stripe JS dependencies
- `.env.template` — NEXT_PUBLIC key + CHECKOUT_TIMEOUT
- `docker/frontend.Dockerfile` — build arg for NEXT_PUBLIC key
- `docker-compose.yml` — pass build arg
- `backend/core/config.py` — checkout_timeout setting
- `backend/main.py` — register reaper background task
- `modules/auth/routes/auth_routes.py` — upgrade-to-merchant endpoint
- `modules/payments/interfaces/payment_provider.py` — cancel_payment, verify_webhook, create_account_link, create_login_link
- `modules/payments/adapters/stripe_provider.py` — implement new methods, return client_secret
- `modules/payments/models/schemas.py` — client_secret on PaymentStatusResponse
- `modules/payments/routes/checkout_routes.py` — use factory, expose client_secret
- `modules/payments/services/checkout_service.py` — use factory
- `modules/payments/services/webhook_service.py` — use factory for verify_webhook, add charge.succeeded
- `modules/payments/services/merchant_service.py` — use factory for all provider calls
- `modules/payments/services/order_reaper.py` — use factory for cancel_payment
