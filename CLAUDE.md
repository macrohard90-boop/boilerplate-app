# Boilerplate Application - Project Context

## What This Is
A reusable GitHub Template Repository for deploying fully independent web applications within 24 hours. Each deployment is a completely separate product (e.g., mining company vs shoe company) with its own VPS, database, and codebase. This is NOT a multi-tenant SaaS platform.

## Tech Stack
- Frontend: Next.js (React + SSR/SSG for SEO)
- Backend: Python FastAPI in Docker
- Database: PostgreSQL (self-hosted in Docker, maximum control)
- Sessions/Cache: Redis
- Deployment: Docker Compose on VPS (one VPS per client)
- Payments: Stripe (default, provider-swappable)
- Auth: Custom JWT + Redis sessions + OAuth (Google, Apple, MS, GitHub, OIDC) + M2M bot auth
- Architecture: ARM64 compatible (aarch64)

## Architecture Principles
1. MODULAR: Every feature is a module in /modules/{id}/. Three levels: config toggle, fully removable, swappable providers.
2. STATELESS SERVERS: No in-memory state. All shared state in Redis or PostgreSQL. Enables clustering.
3. SESSION ISOLATION: User ID comes from server-verified JWT/Redis session, never from client input.
4. SCALABLE: 10-20 concurrent users baseline, horizontally scalable to 100+ via Docker clustering + load balancer.
5. ADAPTER PATTERN: External services (payments, OAuth, analytics) use interfaces. Swap providers by implementing the interface.

## Module Structure
Each module follows: /modules/{id}/adapters/, interfaces/, models/, routes/, services/, config.py, README.md

## Core Modules (always included)
- auth: JWT, OAuth social login, M2M bot auth, RBAC, Redis sessions
- gdpr: Consent management, data export, deletion, cookies, audit log
- seo: Meta/OG tags, sitemap, JSON-LD, robots.txt, Core Web Vitals

## Optional Modules (toggle via .env)
- payments: Stripe (swappable), Express/Connect, payment lifecycle
- ecommerce: Products, variants, inventory, cart, orders, reviews, wishlists, discounts, digital products, bulk pricing
- saas: Plans, subscriptions, usage tracking, invoicing
- tracking: Page views, user agent, geo, referrals, UTM (pluggable into any analytics platform)
- chatbot: AI assistant placeholder
- marketing: Discount codes, email preferences, campaigns

## Build Phases (current progress)
- [ ] Phase 1: Project skeleton, Docker, module loader, Redis, CI/CD
- [ ] Phase 2: Database schemas, migrations, connection pooling
- [ ] Phase 3: Auth (JWT + OAuth + M2M + Redis sessions)
- [ ] Phase 4: Payments (Stripe, swappable)
- [ ] Phase 5: E-commerce engine
- [ ] Phase 6: User tracking & analytics
- [ ] Phase 7: GDPR & cookies
- [ ] Phase 8: SEO module
- [ ] Phase 9: Frontend (Next.js)
- [ ] Phase 10: Integration, deployment, docs

## Conventions
- Python: Black formatting, type hints, async/await for DB operations
- TypeScript: Strict mode, ESLint + Prettier
- API: RESTful, JSON responses, consistent error format {error, message, details}
- Env vars: All config via .env, never hardcoded secrets
- Git: Conventional commits (feat:, fix:, docs:, refactor:)
- After each phase: commit, tag (e.g., phase-1-complete), push

## Docker Compose Services (Phase 1)
- nginx: Reverse proxy, SSL, :80/:443 exposed
- fastapi: Python backend, :8000 internal
- nextjs: Frontend, :3000 internal
- redis: Sessions/cache, :6379 internal
- postgres: Database, :5432 internal
- pgbouncer: Connection pooler, :6432 internal (optional, Growth+ tier)

## Scaling Tiers
- Starter (10-20 users): 1 FastAPI + 1 Next.js + Redis on single VPS ($5-12/mo)
- Growth (50-100 users): 2-3 FastAPI + 2 Next.js + dedicated Redis + PgBouncer ($30-60/mo)
- Scale (100-500+): 4+ FastAPI + 3+ Next.js + Redis Cluster + external LB + DB read replicas ($80-200/mo)
