# Changelog

All notable changes to the boilerplate application after the initial 10-phase build are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Claude Code should read this file when returning to modify previously completed work.

---

## [Unreleased]
_Changes staged but not yet tagged._

## [2026-02-17] - Fix cart quantity/remove buttons and add-to-cart

### Fixed
- Cart +/- quantity buttons and remove button were non-functional (silent failure, no errors)
- Add-to-cart from product detail page broken by stale closure after initial optimistic update attempt
- UI flicker on cart item rows during quantity changes (opacity-50 toggle during async call)

### Changed
- `CartProvider.updateQuantity()` — changed HTTP method from `PATCH` to `PUT`, URL from single `{itemId}` to composite `{product_id}_{variant_id}`, signature from `(itemId, qty)` to `(productId, variantId, qty)`
- `CartProvider.removeItem()` — URL changed to composite key format, signature from `(itemId)` to `(productId, variantId)`
- All cart mutation callbacks (`addItem`, `updateQuantity`, `removeItem`, `applyDiscount`, `removeDiscount`) now set cart state directly from API response instead of calling `refreshCart()` — eliminates loading spinner flash
- `updateQuantity` and `removeItem` use optimistic local state updates with `useRef` rollback on failure
- All `useCallback` dependencies changed to `[]` (stable references) — prevents stale closures and unnecessary re-renders
- `CartItem` interface updated to match actual API response (removed non-existent `id`/`slug` fields, added `currency`)
- Cart item React keys use `cartItemKey()` composite helper instead of `item.id`

### Files Modified
- `frontend/lib/cart-context.tsx` — API methods, interface, optimistic updates, stable callbacks
- `frontend/app/cart/page.tsx` — composite keys, removed flicker state, removed stale `item.id`/`item.slug` refs
- `frontend/app/checkout/page.tsx` — cart item React keys use `cartItemKey()`
- `docs/phases/phase-9.md` — added Post-Build Fixes section
- `docs/test-plans/phase-9/test-plan.md` — added 8 new tests (E9–E15, K16), updated totals to 170

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
| 8 | 2026-02-16 | phase-8-complete | SEO module: dynamic meta tags (auto-generated from products/categories + custom overrides), sitemap.xml (Redis-cached, products/categories/static pages, large catalog index support), robots.txt, Open Graph + Twitter Card tags, JSON-LD structured data (Product with price/availability/reviews, Organization, BreadcrumbList, WebSite with SearchAction), 6 admin endpoints, nginx root-level routing. ~8 endpoints + 2 root-level, 5 services, 1 migration |
| 9 | 2026-02-16 | phase-9-complete | Frontend (Next.js): Tailwind CSS v4 with neurons.html-inspired dark theme (particle canvas, gradient mesh, glass morphism), landing page with scroll reveal, auth pages (login, register, forgot/reset password with OAuth), product catalog (grid/list view, search, sort, pagination), product detail (variants, images, reviews, add-to-cart), categories, shopping cart with discount codes, mock checkout (3-step), order confirmation, user dashboard (overview, orders, order detail, profile, wishlists, privacy/GDPR), admin panel (dashboard, products, orders, users, analytics, GDPR, SEO), cookie consent banner, responsive design. ~21 pages, 15 components, 2 contexts, 1 utility lib |
| 10 | — | — | — |
