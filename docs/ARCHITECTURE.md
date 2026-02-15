# Boilerplate Application - Architecture Reference

> Read this file when building or modifying anything that touches shared infrastructure,
> database schemas, interface contracts, or cross-module dependencies.

---

## 1. Interface Contracts

### 1.1 PaymentProvider (modules/payments/interfaces/)
```python
class PaymentProvider(ABC):
    async def create_payment(order_id, amount, currency, customer_id) -> PaymentResult
    async def refund(payment_id, amount) -> RefundResult
    async def get_status(payment_id) -> PaymentStatus
    async def create_merchant(merchant_data) -> MerchantAccount
    async def list_transactions(filters) -> list[Transaction]
```
Default implementation: Stripe (Express + Connect accounts)
Swap by: implementing PaymentProvider ABC, updating PAYMENT_PROVIDER in .env

### 1.2 AuthProvider (modules/auth/interfaces/)
```python
class AuthProvider(ABC):
    async def authenticate(authorization_code, redirect_uri) -> TokenPair
    async def get_user_info(access_token) -> UserInfo
    async def refresh(refresh_token) -> TokenPair
    async def revoke(token) -> bool
```
Implementations: Google, Apple, Microsoft/Azure AD, GitHub, Generic OIDC
Flow: redirect → authorization code → exchange → get_user_info() → create or link account

### 1.3 GeoProvider (modules/tracking/interfaces/)
```python
class GeoProvider(ABC):
    async def lookup(ip_address) -> GeoResult  # country, city, region, lat/lng
```
Placeholder interface. Recommended: MaxMind GeoIP2.

### 1.4 RecommendationProvider (modules/recommendations/interfaces/)
```python
class RecommendationProvider(ABC):
    async def get_recommendations(product_id, limit, rule_type) -> list[ProductRecommendation]
    async def get_cart_recommendations(cart_item_ids, limit) -> list[ProductRecommendation]
    async def compute_associations(min_support, min_confidence) -> int  # returns rules created
```
Default implementation: association rule learning (batch-computed, served from `product_associations` table).
Swap by: implementing RecommendationProvider ABC, updating RECOMMENDATION_PROVIDER in .env

### 1.5 ReminderStrategy (modules/recommendations/interfaces/)
```python
class ReminderStrategy(ABC):
    async def get_cadence(user_id, cart_id) -> ReminderCadence  # timing + channel list
    async def should_send(user_id, cart_id, reminder_count) -> bool
    async def get_content(user_id, cart_id) -> ReminderContent  # subject, body, recommendations
```
Default implementation: uniform cadence (1hr, 24hr, 72hr). Swappable for RFM-segment-based strategy.

### 1.6 EmailProvider (modules/notifications/interfaces/)
```python
class EmailProvider(ABC):
    async def send(to, template_id, template_data, email_type) -> SendResult
    async def send_batch(recipients: list[BatchEmail]) -> list[SendResult]
    async def sync_suppression(suppressed_emails: list[str]) -> SyncResult
    async def process_webhook(payload, signature) -> WebhookEvent  # bounce/complaint/delivery
```
Default implementation: placeholder (logs to console). Swap in Mailgun, SendGrid, Postmark, etc.
Swap by: implementing EmailProvider ABC, updating EMAIL_PROVIDER in .env

Consent check flow:
1. Caller requests send with `email_type` (marketing_email | transactional_email)
2. Notifications service checks `email_preferences` for suppression + `consent_records` for opt-in
3. If consent valid and not suppressed → delegate to EmailProvider → log to `email_events`
4. If no consent or suppressed → skip send, log reason to `email_events`

Webhook flow (provider → app):
- POST /api/notifications/webhook — validates provider signature
- Bounce → auto-add to `email_preferences.suppressed_at`, reason = 'bounce'
- Complaint (spam report) → auto-add to `email_preferences.suppressed_at`, reason = 'complaint'
- Delivery confirmation → update `email_events.delivered_at`

### 1.7 ChatbotProvider (modules/chatbot/interfaces/)
```python
class ChatbotProvider(ABC):
    async def send_message(conversation_id, message) -> ChatResponse
    async def get_history(conversation_id) -> list[ChatMessage]
```
Placeholder interface. Implement per client with chosen AI provider.

---

## 2. Database Schemas

### 2.1 Core Schema (7 tables — always present)
```
users           id, email, password_hash, first_name, last_name, role_id, is_verified,
                is_active, created_at, updated_at, deleted_at
roles           id, name, description, created_at
permissions     id, role_id, resource, action, created_at
sessions        id, user_id, device, ip_address, user_agent, created_at, expires_at
api_keys        id, user_id, key_hash, name, scopes (JSONB), rate_limit, is_active,
                last_used_at, created_at
audit_log       id, user_id, api_key_id, action, resource, resource_id, ip_address,
                payload_hash, created_at
exchange_rates  id, base_currency CHAR(3), target_currency CHAR(3), rate NUMERIC(12,6),
                source VARCHAR(20), fetched_at TIMESTAMPTZ, created_at
                — UNIQUE(base_currency, target_currency). Display conversion only.
```
Note: All monetary amounts are INTEGER cents with a paired `currency CHAR(3)` column. See §2.9.

### 2.2 E-commerce Schema (21 tables — template choice)
```
products            id, name, slug, description, sku, base_price (INT cents), currency CHAR(3),
                    status, type (physical/digital), created_at, updated_at, deleted_at
categories          id, name, slug, parent_id (self-ref hierarchy), description, sort_order
product_categories  product_id, category_id (M2M junction)
product_variants    id, product_id, name, sku, price_override (INT cents, nullable),
                    stock_quantity, attributes (JSONB: size, color, material, custom)
product_images      id, product_id, variant_id (nullable), url, alt_text, sort_order, is_primary
product_reviews     id, product_id, user_id, rating (1-5), title, body,
                    status (pending/approved/rejected), created_at
related_items       id, product_id, related_product_id,
                    relation_type (cross-sell/upsell/project-link), sort_order
inventory_records   id, variant_id, quantity_change, reason, reference_id, created_at
wishlists           id, user_id, name, is_default, created_at
wishlist_items      wishlist_id, product_id, variant_id (nullable), added_at
discount_codes      id, code, type (percentage/fixed/free_shipping), value (INT cents for fixed),
                    currency CHAR(3), min_order_amount (INT cents), max_uses, uses_count,
                    valid_from, valid_until, active
digital_assets      id, product_id, file_url, file_name, file_size, download_limit, created_at
pricing_tiers       id, product_id, variant_id (nullable), min_quantity,
                    price_per_unit (INT cents), label
cart                id, user_id (nullable), session_id,
                    status VARCHAR(20) CHECK (active/abandoned/recovered/converted/expired),
                    discount_code_id, currency CHAR(3), created_at, updated_at
cart_items          cart_id, product_id, variant_id, quantity, unit_price_at_add (INT cents)
orders              id, user_id, order_number, status, currency CHAR(3),
                    subtotal (INT cents), discount_amount (INT cents), tax_amount (INT cents),
                    total (INT cents), shipping_address (JSONB), billing_address (JSONB), created_at
order_items         order_id, product_id, variant_id, quantity, unit_price (INT cents),
                    total_price (INT cents), product_snapshot (JSONB)
payment_records     id, order_id, provider, provider_payment_id, status,
                    amount (INT cents), currency CHAR(3), method, created_at
customer_metrics    user_id (FK unique), last_purchase_at, order_count,
                    total_spent (INT cents), default_currency CHAR(3),
                    rfm_segment VARCHAR(30) CHECK (champion/loyal/potential_loyalist/
                    at_risk/hibernating/lost/new),
                    last_calculated_at
abandoned_cart_events  id, cart_id (FK), user_id (FK), abandoned_at, reminder_count,
                    last_reminder_at, recovered_at,
                    status (abandoned/reminded/recovered/expired),
                    channel (JSONB: tracks which channels sent), created_at
product_associations   id, product_a_id (FK), product_b_id (FK),
                    rule_type (frequently_bought_together/category_affinity/sequential),
                    support, confidence, lift, sample_size, computed_at
```

### 2.3 SaaS Schema (6 tables — alternative template)
```
plans           id, name, slug, description, price_monthly (INT cents), price_yearly (INT cents),
                currency CHAR(3), features (JSONB), is_active
plan_features   plan_id, feature_key, feature_value, limit
subscriptions   id, user_id, plan_id, status, currency CHAR(3),
                current_period_start, current_period_end, cancel_at_period_end
usage_records   id, subscription_id, feature_key, quantity, recorded_at
invoices        id, user_id, subscription_id, amount (INT cents), currency CHAR(3),
                status, due_date, paid_at
invoice_items   invoice_id, description, quantity, unit_price (INT cents), total (INT cents)
```

### 2.4 GDPR Schema (7 tables — always present)
```
consent_records       id, user_id, consent_type, granted, version, ip_address, created_at
                      consent_type values: marketing_email, transactional_email, third_party_sharing,
                      analytics, cookies_analytics, cookies_marketing
data_export_requests  id, user_id, status, file_url, requested_at, completed_at, expires_at
deletion_requests     id, user_id, status, requested_at, grace_period_ends, completed_at
cookie_preferences    id, user_id (nullable), session_id, necessary, analytics, marketing,
                      preferences, created_at, updated_at
consent_audit_log     id, user_id, action, consent_type, old_value, new_value, ip_address,
                      created_at
email_preferences     id, user_id (FK unique), marketing_email (bool), transactional_email (bool),
                      suppressed_at (nullable TIMESTAMPTZ), suppression_reason (nullable: bounce/
                      complaint/manual/deletion_request), updated_at
                      — App-side source of truth. Synced to email provider on change.
                      — Checked before every send. Suppressed users never receive any email.
email_events          id, user_id (FK), email_type (marketing_email/transactional_email),
                      template_id, provider, provider_message_id, consent_snapshot (JSONB:
                      consent state at send time), status (queued/sent/delivered/bounced/
                      complained/skipped), skip_reason (nullable: no_consent/suppressed),
                      sent_at, delivered_at, created_at
                      — Audit trail: proves what was sent, when, and that consent existed.
```

### 2.5 Analytics Schema (6 tables — optional module)
```
page_views       id, user_id (nullable), session_id, path, referrer, duration_ms, created_at
sessions         id, user_id (nullable), session_id, started_at, ended_at, page_count
events           id, user_id (nullable), session_id, event_type, event_data (JSONB), created_at
user_agents      id, session_id, raw, browser, browser_version, os, device_type
referral_sources id, session_id, source, medium, campaign
utm_tracking     id, session_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term
```

### 2.6 Indexing Strategy
- All foreign keys indexed
- All user_id columns indexed
- All created_at columns indexed (time-range queries)
- Frequently filtered columns: status, type, active, slug, email
- Composite indexes where queries combine user_id + status or product_id + variant_id

### 2.7 Migration System
- Numbered SQL files: 001_core_schema.sql, 002_ecommerce_schema.sql, etc.
- Each file has UP and DOWN sections for rollback
- Version tracking table: schema_migrations (version, applied_at)
- Migration runner script in /scripts/

### 2.8 Soft Delete
All user-facing tables include deleted_at column for GDPR compliance.
Queries default to WHERE deleted_at IS NULL.

### 2.9 Money & Currency Convention
- All monetary amounts stored as **INTEGER cents** (e.g., $19.99 = 1999). Matches Stripe, avoids floating point.
- Every amount column is paired with a `currency CHAR(3)` column (ISO 4217: USD, EUR, GBP, etc.)
- `DEFAULT_CURRENCY` in .env sets the deployment default; individual records can override.
- Display layer converts cents → formatted string using currency locale.
- Affected columns: `products.base_price`, `product_variants.price_override`, `pricing_tiers.price_per_unit`,
  `discount_codes.value` (for fixed type), `discount_codes.min_order_amount`, `cart_items.unit_price_at_add`,
  `orders.subtotal/discount_amount/tax_amount/total`, `order_items.unit_price/total_price`,
  `payment_records.amount`, `plans.price_monthly/price_yearly`, `invoices.amount`,
  `invoice_items.unit_price/total`, `customer_metrics.total_spent`
- **Exchange rates table** (core schema):
  ```
  exchange_rates    id, base_currency CHAR(3), target_currency CHAR(3), rate NUMERIC(12,6),
                    source (VARCHAR: manual/api), fetched_at TIMESTAMPTZ, created_at
  ```
  - Unique constraint on (base_currency, target_currency)
  - Updated manually or via external API (future integration)
  - Used for display conversion only; transactions always store the original currency

### 2.10 Enum Strategy
- All status/type columns use **VARCHAR + CHECK constraints** (not PostgreSQL ENUM types).
- Rationale: CHECK constraints can be altered inside transactions; PG ENUMs cannot (`ALTER TYPE ADD VALUE` is non-transactional).
- Pattern: `status VARCHAR(30) NOT NULL CHECK (status IN ('active', 'abandoned', 'converted', 'expired'))`
- When adding a new value: `ALTER TABLE ... DROP CONSTRAINT ...; ALTER TABLE ... ADD CONSTRAINT ... CHECK (status IN (...))`

### 2.11 Cart Status Lifecycle
```
active → abandoned (CART_ABANDON_TIMEOUT inactivity)
active → converted (checkout completed, order created)
active → expired (TTL exceeded, no recovery)
abandoned → recovered (user returns and interacts with cart) → active
abandoned → expired (max reminders sent, no recovery)
```
Valid `cart.status` values: `active`, `abandoned`, `recovered`, `converted`, `expired`

### 2.12 Migration Ordering
Migrations must run in dependency order due to cross-schema foreign keys:
```
000_extensions.sql      — uuid-ossp, schemas, updated_at trigger function
001_core_schema.sql     — users, roles, permissions, sessions, api_keys, audit_log, exchange_rates
002_ecommerce_schema.sql — all 21 ecommerce tables (references core.users) [template: ecommerce]
    OR
002_saas_schema.sql     — all 6 SaaS tables (references core.users) [template: saas]
003_gdpr_schema.sql     — all 7 GDPR tables (references core.users)
004_analytics_schema.sql — all 6 analytics tables [if ENABLE_TRACKING=true]
```
Core always runs first. Template migration (ecommerce XOR saas) second. GDPR third. Analytics last (optional).

---

## 3. Session & Auth Architecture

### 3.1 Human Auth Flow
```
Registration → bcrypt hash → email verification token → verify → active account
Login → validate credentials → create JWT access (15min) + refresh token (Redis 7-day TTL)
       → create Redis session → return tokens
Refresh → validate refresh token in Redis → rotate (new access + new refresh) → invalidate old
Logout → delete Redis session → invalidate refresh token
Password reset → generate token (Redis, 1hr TTL) → email link → validate → update password
```

### 3.2 Session Isolation Middleware Chain (6 steps)
Every authenticated request passes through:
1. Extract JWT from Authorization header or httpOnly cookie
2. Validate JWT signature and expiry
3. Look up active session in Redis using session_id from JWT claims
4. Verify session belongs to requesting user (user_id match)
5. Attach verified user context to request: {user_id, role, permissions, session_id}
6. All DB queries scoped by server-verified user_id (NEVER from client input)

### 3.3 Concurrent Session Management
- Configurable max sessions per user (default: 5)
- On new login: if at limit, evict oldest session from Redis
- Session registry per user: SET user_sessions:{user_id} in Redis

### 3.4 M2M (Machine-to-Machine) Auth
- API key generation: POST /api/auth/api-keys → hashed key stored, raw key shown once
- OAuth2 client credentials: POST /api/auth/m2m/token (client_id + client_secret)
- Scoped permissions: read:products, write:orders, read:analytics, admin:users, etc.
- Rate limiting per key: Redis sliding window (configurable requests/minute, requests/hour)
- Audit log: every M2M action recorded with key_id, endpoint, payload_hash, timestamp

### 3.5 RBAC
- Roles: admin, merchant, customer (extensible)
- Permissions: granular per-resource per-action (e.g., products:write, orders:read)
- Middleware checks role + specific permission before route handler

---

## 4. Redis Key Architecture
```
session:{session_id}              → {user_id, role, device, ip, created_at}        TTL: 7 days
user_sessions:{user_id}           → SET of session_ids                             TTL: 7 days
refresh:{token}                   → {user_id, session_id}                          TTL: 7 days
rate:user:{user_id}:{window}      → counter                                        TTL: 60s
rate:key:{api_key_id}:{window}    → counter                                        TTL: 60s
cart:guest:{session_id}           → {items: [...], discount_code_id}               TTL: 24h
csrf:{token}                      → {session_id}                                   TTL: 1h
cache:products:{hash}             → {data}                                         TTL: configurable
cache:categories:{hash}           → {data}                                         TTL: configurable
reset:{token}                     → {user_id}                                      TTL: 1h
cart:last_active:{cart_id}        → timestamp                                      TTL: CART_ABANDON_TIMEOUT
recommend:{product_id}            → [{product_id, score, rule_type}, ...]          TTL: configurable
```

---

## 5. Full Middleware Chain (Request Pipeline)
```
Request → CORS → Rate Limit → JWT Extract → Session Verify → RBAC Check
       → Scope Check (M2M) → GDPR Consent → Tracking → Audit Log → Route Handler → Response
```

---

## 6. Payment Lifecycle
```
cart → pending → processing → accepted → completed
                            → rejected
                            → refunded (partial or full)
```

Cart system:
- Guest users: Redis with session_id key, TTL 24h
- Authenticated users: PostgreSQL cart + cart_items tables
- Cart-to-order: inventory reservation, price lock at conversion time

Abandoned cart recovery:
- Time-based: cart marked abandoned after CART_ABANDON_TIMEOUT minutes of inactivity (configurable, default 60)
- Background job scans for inactive carts, creates `abandoned_cart_events` record
- Reminders via email + webhook (external channels). Default cadence: 1hr, 24hr, 72hr
- `ReminderStrategy` interface determines cadence — swappable for RFM-segment-based logic
- Recovery: if user completes checkout after abandonment, status → recovered, recovered_at set
- Recommendations: abandoned cart reminders include similar/associated products from `product_associations`

Product association rules:
- Batch job computes association rules from completed order history (Apriori / FP-Growth)
- Stored in `product_associations` with support, confidence, lift metrics
- `RecommendationProvider` interface serves pre-computed results, swappable for real-time ML
- Used in: cart page ("frequently bought together"), abandoned cart emails, product detail page

RFM (Recency, Frequency, Monetary) analysis:
- `customer_metrics` table updated on each completed order (last_purchase_at, order_count, total_spent)
- Batch job computes rfm_segment based on configurable thresholds
- Segments: champion, loyal, potential_loyalist, at_risk, hibernating, lost, new (extensible)
- Used by `ReminderStrategy` to vary abandoned cart reminder cadence per segment

Webhook handling:
- POST /api/payments/webhook with Stripe-Signature header validation
- Idempotency keys: event_id stored, duplicate events ignored
- Key events: payment_intent.succeeded, charge.refunded, account.updated

Merchant onboarding:
- Stripe Connect Express accounts
- Configurable platform fee (default 10%)
- Onboarding link generation via API

---

## 7. Docker Compose Services

| Service   | Image              | Port        | Purpose                                    |
|-----------|--------------------|-------------|--------------------------------------------|
| nginx     | nginx:alpine       | 80, 443     | Reverse proxy, SSL, routes /api/* and /*   |
| fastapi   | python:3.11-slim   | 8000 (int)  | Backend API, Uvicorn, 2 workers default    |
| nextjs    | node:20-alpine     | 3000 (int)  | Frontend SSR/SSG                           |
| redis     | redis:7-alpine     | 6379 (int)  | Sessions, cache, rate limits, AOF persist  |
| postgres  | postgres:16-alpine | 5432 (int)  | Database, persistent volume                |
| pgbouncer | pgbouncer          | 6432 (int)  | Connection pooler (optional, Growth+ tier) |

Scaling profile (docker-compose.scale.yml):
- Multiple FastAPI replicas (2-4)
- Multiple Next.js replicas (2-3)
- Nginx upstream load balancing (round-robin or least-connections)
- Health checks on all services

---

## 8. Scaling Tiers

| Tier    | Concurrent Users | Containers                    | Redis           | Cost       |
|---------|-----------------|-------------------------------|-----------------|------------|
| Starter | 10-20           | 1 FastAPI + 1 Next.js         | Shared on VPS   | $5-12/mo   |
| Growth  | 50-100          | 2-3 FastAPI + 2 Next.js       | Dedicated       | $30-60/mo  |
| Scale   | 100-500+        | 4+ FastAPI + 3+ Next.js       | Redis Cluster   | $80-200/mo |

When to scale:
- Starter → Growth: sustained >15 concurrent users, response times >500ms, CPU >70%
- Growth → Scale: sustained >80 concurrent users, response times >300ms, geographic distribution needed

Additional costs: Stripe (2.9% + $0.30/txn), domain (~$12/yr), Supabase Pro if needed ($25/mo)

---

## 9. Connection Pooling
- FastAPI: SQLAlchemy async pool (pool_size=5, max_overflow=10, pool_timeout=30 — all configurable via .env)
- PgBouncer: transaction pooling mode (required at Growth tier, optional at Starter)
- Redis: connection pool per Uvicorn worker (pool_size=10, configurable)
- Rule of thumb: pool_size = expected_concurrent_users / number_of_app_instances

---

## 10. Environment Variables (.env.template)

### Module Toggles
ENABLE_PAYMENTS=true | ENABLE_TRACKING=true | ENABLE_CHATBOT=false | ENABLE_MARKETING=true | ENABLE_RECOMMENDATIONS=true

### Abandoned Cart & Recommendations
CART_ABANDON_TIMEOUT=60 | RECOMMENDATION_PROVIDER=default | RFM_COMPUTE_SCHEDULE=daily

### Currency
DEFAULT_CURRENCY=USD

### Database
DATABASE_URL | POOL_SIZE=5 | MAX_OVERFLOW=10 | POOL_TIMEOUT=30

### Redis
REDIS_URL | REDIS_POOL_SIZE=10 | SESSION_TTL=604800 | CART_TTL=86400 | RATE_LIMIT_WINDOW=60

### Auth
JWT_SECRET | JWT_EXPIRY=900 | REFRESH_TOKEN_TTL=604800 | MAX_SESSIONS_PER_USER=5

### OAuth (per provider)
GOOGLE_CLIENT_ID | GOOGLE_CLIENT_SECRET
APPLE_CLIENT_ID | APPLE_CLIENT_SECRET
MICROSOFT_CLIENT_ID | MICROSOFT_CLIENT_SECRET
GITHUB_CLIENT_ID | GITHUB_CLIENT_SECRET
OIDC_ISSUER | OIDC_CLIENT_ID | OIDC_CLIENT_SECRET

### Stripe
STRIPE_SECRET_KEY | STRIPE_PUBLISHABLE_KEY | STRIPE_WEBHOOK_SECRET | PLATFORM_FEE_PERCENT=10

### Email / Notifications
EMAIL_PROVIDER=placeholder | FROM_EMAIL | FROM_NAME
SMTP_HOST | SMTP_PORT | SMTP_USER | SMTP_PASSWORD (fallback if provider uses SMTP relay)

### Domain
DOMAIN | FRONTEND_URL | BACKEND_URL

### Scaling
UVICORN_WORKERS=2 | NEXTJS_WORKERS=1

### SEO
SITE_NAME | DEFAULT_OG_IMAGE | SOCIAL_HANDLES

---

## 11. 24-Hour Deployment Workflow
1. Clone GitHub Template into new private repo
2. Run setup script: set name, brand, domain, select template (ecommerce or saas)
3. Configure .env: database, Stripe keys, OAuth credentials, SMTP, scaling params
4. Toggle modules as needed
5. Run migrations + seed data
6. Customize products/plans, categories, content
7. Provision VPS, install Docker, clone repo, configure Nginx
8. Deploy containers: docker compose up -d
9. DNS + SSL (Certbot / Let's Encrypt)
10. Smoke tests: auth, products, cart, checkout, payment
11. SEO: submit sitemap to Search Console, verify OG tags
12. Hand off or begin custom development

---

## 12. Security Measures
- Passwords: bcrypt, cost factor 12
- Secrets: environment variables only, never in code
- Transport: HTTPS enforced via Nginx + Let's Encrypt
- CORS: configured per environment (strict in production)
- Rate limiting: all public endpoints, sliding window in Redis
- SQL injection: parameterized queries via SQLAlchemy
- XSS: React built-in escaping
- CSRF: server-side tokens in Redis with short TTL
- Session fixation: token rotation on refresh
- Audit log: all sensitive operations recorded
