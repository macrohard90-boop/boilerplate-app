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
   - users, roles, permissions, sessions, api_keys, audit_log
   - See ARCHITECTURE.md §2.1 for full column definitions

2. **E-commerce schema** (18 tables, template choice):
   - products, categories, product_categories, product_variants, product_images,
     product_reviews, related_items, inventory_records, wishlists, wishlist_items,
     discount_codes, digital_assets, pricing_tiers, cart, cart_items, orders,
     order_items, payment_records
   - See ARCHITECTURE.md §2.2 for full column definitions

3. **SaaS schema** (6 tables, alternative template):
   - plans, plan_features, subscriptions, usage_records, invoices, invoice_items
   - See ARCHITECTURE.md §2.3 for full column definitions

4. **GDPR schema** (5 tables, always present):
   - consent_records, data_export_requests, deletion_requests, cookie_preferences, consent_audit_log
   - See ARCHITECTURE.md §2.4 for full column definitions

5. **Analytics schema** (6 tables, optional module):
   - page_views, sessions, events, user_agents, referral_sources, utm_tracking
   - See ARCHITECTURE.md §2.5 for full column definitions

6. **SQLAlchemy async engine** (backend/core/database.py):
   - Async engine using asyncpg
   - Connection pool: pool_size, max_overflow, pool_timeout from .env
   - Session factory: async_sessionmaker
   - Dependency injection: get_db() for FastAPI routes
   - Engine disposal on shutdown

7. **Indexing strategy:**
   - All foreign keys
   - All user_id columns
   - All created_at columns
   - Frequently filtered: status, type, active, slug, email
   - Composite: user_id + status, product_id + variant_id where relevant

8. **Migration system** (scripts/migrate.py + /migrations/):
   - Numbered SQL files: 001_core_schema.sql, 002_ecommerce_schema.sql, etc.
   - Each file has -- UP and -- DOWN sections
   - Version tracking table: schema_migrations (version, applied_at)
   - Commands: migrate up, migrate down, migrate status
   - Template-aware: only runs e-commerce OR SaaS migrations based on config

9. **Seed data** (scripts/seed.py + /seeds/):
   - E-commerce seeds: 10 products with variants and images, 5 categories (2 levels deep), 3 test users (admin, merchant, customer), sample discount codes, sample reviews
   - SaaS seeds: 3 plans (free, pro, enterprise) with features, 3 test users, sample subscriptions
   - Common seeds: roles (admin, merchant, customer), default permissions

## Acceptance Criteria
- [ ] `python scripts/migrate.py up` creates all tables without errors
- [ ] `python scripts/migrate.py down` drops all tables cleanly
- [ ] `python scripts/migrate.py status` shows applied migrations
- [ ] `python scripts/seed.py` populates database with template-appropriate sample data
- [ ] SQLAlchemy async session works from a FastAPI route (test endpoint)
- [ ] All indexes created (verify with \di in psql)
- [ ] Soft-delete columns (deleted_at) present on all user-facing tables
- [ ] Schema matches ARCHITECTURE.md exactly

## Implementation Notes
- Use JSONB for flexible fields (variant attributes, addresses, product snapshots, plan features)
- UUID primary keys (uuid_generate_v4()) for all tables
- All timestamps with timezone (TIMESTAMPTZ)
- Soft-delete: deleted_at TIMESTAMPTZ DEFAULT NULL on user-facing tables
- created_at DEFAULT NOW(), updated_at with trigger or application-level update
- Foreign keys with ON DELETE CASCADE where parent deletion should cascade, RESTRICT otherwise
- The setup script from Phase 1 should be updated to call migrate + seed after template selection

## Files Created
_Update this section after building. List every file created with its path._
