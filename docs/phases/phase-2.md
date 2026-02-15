# Phase 2: Database Schema & Migration System

**Estimate:** 4-5 hours
**Depends on:** Phase 1
**Category:** Data layer

## Goal
Create all database schemas (core, e-commerce, SaaS, GDPR, analytics), the migration system, SQLAlchemy async engine with connection pooling, indexing strategy, and seed data. At the end of this phase, the database is fully structured and populated with sample data for the chosen template.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 2 (Database Schemas) and 9 (Connection Pooling) for the complete schema definitions and pool configuration.

## Deliverables

1. **Core schema** (always present):
   - users, roles, permissions, sessions, api_keys, audit_log, **exchange_rates**
   - `exchange_rates`: base_currency, target_currency, rate, source, fetched_at — UNIQUE(base, target), display conversion only
   - See ARCHITECTURE.md §2.1 for full column definitions

2. **E-commerce schema** (21 tables, template choice):
   - products, categories, product_categories, product_variants, product_images,
     product_reviews, related_items, inventory_records, wishlists, wishlist_items,
     discount_codes, digital_assets, pricing_tiers, cart, cart_items, orders,
     order_items, payment_records, **customer_metrics**, **abandoned_cart_events**,
     **product_associations**
   - `customer_metrics`: user_id (FK unique), last_purchase_at, order_count, total_spent, rfm_segment, last_calculated_at — updated on each completed order, RFM segment computed by batch job
   - `abandoned_cart_events`: id, cart_id (FK), user_id (FK), abandoned_at, reminder_count, last_reminder_at, recovered_at, status (abandoned/reminded/recovered/expired), channel (JSONB — tracks which channels sent: email, webhook), created_at
   - `product_associations`: id, product_a_id (FK), product_b_id (FK), rule_type (frequently_bought_together/category_affinity/sequential), support, confidence, lift, sample_size, computed_at — stores pre-computed association rules
   - See ARCHITECTURE.md §2.2 for full column definitions

3. **SaaS schema** (6 tables, alternative template):
   - plans, plan_features, subscriptions, usage_records, invoices, invoice_items
   - See ARCHITECTURE.md §2.3 for full column definitions

4. **GDPR schema** (7 tables, always present):
   - consent_records, data_export_requests, deletion_requests, cookie_preferences, consent_audit_log, **email_preferences**, **email_events**
   - `consent_records.consent_type` taxonomy: `marketing_email`, `transactional_email`, `third_party_sharing`, `analytics`, `cookies_analytics`, `cookies_marketing`
   - `email_preferences`: per-user suppression list + per-type opt-in booleans. App-side source of truth synced to email provider.
   - `email_events`: audit trail of every email sent/skipped, with consent snapshot at send time and provider message ID
   - See ARCHITECTURE.md §2.4 for full column definitions

5. **Analytics schema** (6 tables, optional module):
   - page_views, analytics_sessions, events, user_agents, referral_sources, utm_tracking
   - **Note:** Table renamed from `sessions` to `analytics_sessions` to avoid collision with core `sessions` table
   - See ARCHITECTURE.md §2.5 for full column definitions

6. **PostgreSQL schemas (namespacing):**
   - Use actual PG schemas instead of flat table names: `core`, `ecommerce`, `saas`, `gdpr`, `analytics`
   - Each migration creates its schema with `CREATE SCHEMA IF NOT EXISTS`
   - Provides cleaner namespacing, per-schema permissions, and resolves any table name collisions
   - SQLAlchemy models set `__table_args__ = {"schema": "<schema_name>"}`

7. **SQLAlchemy async engine** (backend/core/database.py):
   - Async engine using asyncpg
   - Connection pool: pool_size, max_overflow, pool_timeout from .env
   - Session factory: async_sessionmaker
   - Dependency injection: get_db() for FastAPI routes
   - Engine disposal on shutdown
   - PgBouncer-compatible: disable prepared statement caching (`statement_cache_size=0` on asyncpg connect args), avoid session-level `SET` commands

8. **Indexing strategy:**
   - All foreign keys
   - All user_id columns
   - All created_at columns
   - Frequently filtered: status, type, active, slug, email
   - Composite: user_id + status, product_id + variant_id where relevant

9. **Migration system** (scripts/migrate.py + /migrations/):
   - Numbered SQL files: 000_extensions.sql, 001_core_schema.sql, 002_ecommerce_schema.sql, etc.
   - Each file has `-- UP` and `-- DOWN` sections
   - **Migration 000**: `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` and `CREATE SCHEMA` statements
   - Version tracking table: schema_migrations (version, applied_at)
   - Commands: `migrate up`, `migrate down`, `migrate down --to <version>`, `migrate status`
   - **Transactional**: each migration wrapped in `BEGIN/COMMIT` with `ROLLBACK` on error
   - Template-aware: only runs e-commerce OR SaaS migrations based on config

10. **`updated_at` trigger:**
    - Create a reusable PostgreSQL function: `core.update_timestamp()` that sets `updated_at = NOW()`
    - Apply as a `BEFORE UPDATE` trigger on all tables that have an `updated_at` column
    - Defined in migration 000 or 001 so it's available to all subsequent migrations

12. **Abandoned cart & recommendations schema support:**
    - `CART_ABANDON_TIMEOUT=60` env var (minutes of inactivity before cart is marked abandoned)
    - `abandoned_cart_events` indexed on: user_id, status, abandoned_at (for batch reminder queries)
    - `product_associations` indexed on: product_a_id, rule_type, confidence DESC (for fast recommendation lookups)
    - `customer_metrics` indexed on: rfm_segment, last_purchase_at (for segment-based queries)

13. **Seed data** (scripts/seed.py + /seeds/):
    - E-commerce seeds: 10 products with variants and images, 5 categories (2 levels deep), 3 test users (admin, merchant, customer), sample discount codes, sample reviews
    - SaaS seeds: 3 plans (free, pro, enterprise) with features, 3 test users, sample subscriptions
    - Common seeds: roles (admin, merchant, customer), default permissions
    - **`seed --reset` flag**: truncates seeded tables (CASCADE) before re-inserting, safe for re-runs
    - **Idempotent by default**: uses `INSERT ... ON CONFLICT DO NOTHING` for roles/permissions

## Acceptance Criteria
- [ ] `python scripts/migrate.py up` creates all tables without errors
- [ ] `python scripts/migrate.py down` drops all tables cleanly
- [ ] `python scripts/migrate.py down --to 001` rolls back to a specific version
- [ ] `python scripts/migrate.py status` shows applied migrations
- [ ] `python scripts/seed.py` populates database with template-appropriate sample data
- [ ] `python scripts/seed.py --reset` truncates and re-seeds cleanly
- [ ] SQLAlchemy async session works from a FastAPI route (test endpoint)
- [ ] All indexes created (verify with `\di` in psql)
- [ ] PG schemas created: `core`, `ecommerce`/`saas`, `gdpr`, `analytics` (verify with `\dn` in psql)
- [ ] Soft-delete columns (deleted_at) present on all user-facing tables
- [ ] `updated_at` trigger fires correctly (verify with manual UPDATE + SELECT)
- [ ] Schema matches ARCHITECTURE.md exactly (with documented deviations noted below)
- [ ] `customer_metrics`, `abandoned_cart_events`, `product_associations` tables created with correct indexes
- [ ] `email_preferences`, `email_events` tables created in GDPR schema
- [ ] `consent_records` consent_type values documented and consistent with email_preferences booleans
- [ ] All monetary columns are INTEGER (cents) with paired `currency CHAR(3)` column
- [ ] All status/type columns use VARCHAR + CHECK constraints (no PG ENUMs)
- [ ] `cart.status` CHECK constraint includes: active, abandoned, recovered, converted, expired
- [ ] `exchange_rates` table created in core schema with UNIQUE(base_currency, target_currency)
- [ ] Migration ordering enforced: 000 → 001 (core) → 002 (template) → 003 (gdpr) → 004 (analytics)
- [ ] CI pipeline runs `migrate up → seed → migrate down` against throwaway Postgres container
- [ ] Failed migration rolls back cleanly (no partial state)

## Implementation Notes
- **Money as integer cents**: all monetary amounts stored as INTEGER (e.g., $19.99 = 1999). Every amount column paired with `currency CHAR(3)` (ISO 4217). `DEFAULT_CURRENCY` env var for deployment default. See ARCHITECTURE.md §2.9.
- **VARCHAR + CHECK constraints** for all status/type enum columns. No PostgreSQL ENUM types. See ARCHITECTURE.md §2.10.
- **Cart status lifecycle**: active → abandoned/converted/expired; abandoned → recovered → active. See ARCHITECTURE.md §2.11.
- **Migration ordering**: 000 (extensions+schemas) → 001 (core) → 002 (ecommerce XOR saas) → 003 (gdpr) → 004 (analytics). Core always first due to cross-schema FKs. See ARCHITECTURE.md §2.12.
- Use JSONB for flexible fields (variant attributes, addresses, product snapshots, plan features)
- UUID primary keys (uuid_generate_v4()) for all tables — requires `uuid-ossp` extension (migration 000)
- All timestamps with timezone (TIMESTAMPTZ)
- Soft-delete: deleted_at TIMESTAMPTZ DEFAULT NULL on user-facing tables
- created_at DEFAULT NOW(), updated_at managed by `core.update_timestamp()` trigger
- Foreign keys with ON DELETE CASCADE where parent deletion should cascade, RESTRICT otherwise
- The setup script from Phase 1 should be updated to call migrate + seed after template selection
- **PgBouncer compatibility**: asyncpg `statement_cache_size=0` in connect args, no session-level SET commands
- **Partition-ready note**: audit_log, page_views, and events tables will grow unbounded. Add a `-- FUTURE: range partition on created_at (monthly)` comment in their migration files. Actual partitioning deferred to a future phase when data volume warrants it.
- **GDPR + analytics guard**: if ENABLE_TRACKING is false, analytics schema migrations are skipped. GDPR consent_records still tracks consent_type='analytics' regardless — the consent UI can offer the toggle, but no data is collected without the analytics tables present.
- **Data retention note**: add `-- RETENTION: consider archival policy for rows older than N months` comments on audit_log, analytics_sessions, events, and page_views tables. Actual archival/purge logic deferred to Phase 7 (GDPR).

## Documented Deviations from ARCHITECTURE.md
- Analytics `sessions` table renamed to `analytics_sessions` to avoid collision with core `sessions` — update ARCHITECTURE.md §2.5 when building
- Tables organized into PG schemas (`core.*`, `ecommerce.*`, etc.) rather than flat public schema — update ARCHITECTURE.md §2 preamble when building
- E-commerce schema expanded from 18 to 21 tables: added `customer_metrics`, `abandoned_cart_events`, `product_associations` — update ARCHITECTURE.md §2.2 when building
- New `recommendations` module added to Module Registry — scaffolded in Phase 2, implementation deferred
- New `notifications` module added to Module Registry (required core) — EmailProvider interface, scaffolded in Phase 2
- GDPR schema expanded from 5 to 7 tables: added `email_preferences`, `email_events` — update ARCHITECTURE.md §2.4 when building
- Core schema expanded from 6 to 7 tables: added `exchange_rates` for multi-currency support
- All monetary columns changed from untyped to INTEGER cents + currency CHAR(3) — update ARCHITECTURE.md §2.2, §2.3 when building
- Cart status lifecycle defined: active/abandoned/recovered/converted/expired — not in original spec

## Files Created
- `migrations/000_extensions.sql` — uuid-ossp extension, PG schemas, updated_at trigger function
- `migrations/001_core_schema.sql` — 7 core tables (users, roles, permissions, sessions, api_keys, audit_log, exchange_rates)
- `migrations/002_ecommerce_schema.sql` — 21 e-commerce tables (template: ecommerce)
- `migrations/002_saas_schema.sql` — 6 SaaS tables (template: saas)
- `migrations/003_gdpr_schema.sql` — 7 GDPR tables (consent, export, deletion, cookies, email prefs/events)
- `migrations/004_analytics_schema.sql` — 6 analytics tables (page views, sessions, events, user agents, referrals, UTM)
- `scripts/migrate.py` — Migration runner (up, down, down --to, status)
- `scripts/seed.py` — Seed data runner (--reset flag)
- `seeds/common.sql` — Roles, permissions, test users, exchange rates, email preferences
- `seeds/ecommerce.sql` — Categories, products, variants, images, reviews, discounts, digital assets
- `seeds/saas.sql` — Plans, plan features, subscriptions
- `backend/core/database.py` — SQLAlchemy async engine, session factory, get_db(), health check
- `modules/notifications/` — Module scaffold (adapters, interfaces, models, routes, services)
- `modules/recommendations/` — Module scaffold (adapters, interfaces, models, routes, services)
- Modified: `backend/main.py` — Added db health check + shutdown
- Modified: `backend/core/config.py` — Added currency, recommendations, email settings
- Modified: `backend/requirements.txt` — Replaced alembic with psycopg2-binary
- Modified: `.env.template` — Added currency, cart, recommendations, email vars
- Modified: `.github/workflows/ci.yml` — Added migrate up/seed/down test step
