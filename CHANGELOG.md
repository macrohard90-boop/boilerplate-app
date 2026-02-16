# Changelog

All notable changes to the boilerplate application after the initial 10-phase build are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Claude Code should read this file when returning to modify previously completed work.

---

## [Unreleased]
_Changes staged but not yet tagged._

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
| 8 | — | — | — |
| 9 | — | — | — |
| 10 | — | — | — |
