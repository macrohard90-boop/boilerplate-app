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
| 4 | — | — | — |
| 5 | 2026-02-16 | phase-5-complete | E-commerce engine: product catalog (CRUD, variants, images, categories), shopping cart (guest Redis + auth PG + merge), orders with checkout + stock reservation, inventory management, discount codes, wishlists, reviews with moderation, digital assets with HMAC-signed downloads, pricing tiers. ~35 endpoints across 7 route files and 11 service files |
| 6 | — | — | — |
| 7 | — | — | — |
| 8 | — | — | — |
| 9 | — | — | — |
| 10 | — | — | — |
