# Boilerplate Application - Project Context

## What This Is
A reusable GitHub Template Repository for deploying fully independent web applications within 24 hours. Each deployment is a completely separate product (e.g., mining company vs shoe company) with its own VPS, database, and codebase. This is NOT a multi-tenant SaaS platform.

## Tech Stack
- Frontend: Next.js (React + SSR/SSG for SEO)
- Backend: Python FastAPI in Docker
- Database: PostgreSQL (self-hosted in Docker)
- Sessions/Cache: Redis
- Deployment: Docker Compose on VPS (one VPS per client)
- Payments: Stripe (default, provider-swappable via adapter pattern)
- Auth: Custom JWT + Redis sessions + OAuth (Google, Apple, MS, GitHub, OIDC) + M2M bot auth
- Architecture: ARM64 compatible (aarch64)

## Architecture Principles
1. MODULAR: Every feature is a module in /modules/{id}/. Three levels: config toggle, fully removable, swappable providers.
2. STATELESS SERVERS: No in-memory state. All shared state in Redis or PostgreSQL. Enables clustering.
3. SESSION ISOLATION: User ID comes from server-verified JWT/Redis session, never from client input.
4. SCALABLE: 10-20 concurrent users baseline, horizontally scalable to 100+ via Docker clustering + load balancer.
5. ADAPTER PATTERN: External services (payments, OAuth, analytics) use interfaces. Swap providers by implementing the interface.

## Module Registry

| Module ID  | Name                         | Status          | Interfaces                     |
|------------|------------------------------|-----------------|--------------------------------|
| auth       | Authentication & Authorization | Required (core) | AuthProvider (OAuth adapters)  |
| gdpr       | GDPR & Privacy               | Required (core) | —                              |
| seo        | SEO Module                   | Required (core) | —                              |
| payments   | Payment Processing           | Optional        | PaymentProvider (Stripe, etc.) |
| ecommerce  | E-commerce Engine            | Template choice | —                              |
| saas       | SaaS Subscriptions           | Template choice | —                              |
| tracking   | User Analytics               | Optional        | GeoProvider, AgentParser       |
| chatbot    | AI Chatbot                   | Optional        | ChatbotProvider                |
| marketing  | Marketing & Promotions       | Optional        | —                              |
| notifications | Email & Notifications       | Required (core) | EmailProvider                  |
| recommendations | Recommendations & Cart Recovery | Optional   | RecommendationProvider, ReminderStrategy |

## Module Structure (consistent for all)
```
/modules/{id}/
  adapters/       # Provider implementations
  interfaces/     # Abstract contracts (Python ABCs)
  models/         # DB models + Pydantic schemas
  routes/         # FastAPI router endpoints
  services/       # Business logic
  config.py       # Module feature flags
  README.md       # Module documentation
```

## Working Rules (for Claude Code)

### Progress Tracking
- Build ONE deliverable at a time. After each deliverable is complete and working:
  1. In the phase file (docs/phases/phase-{N}.md): change [ ] to [x] for the completed acceptance criterion
  2. In the phase file: add the created file paths to the "Files Created" section
  3. Brief status update to the user: "✓ Deliverable N done. Moving to next."
- When ALL deliverables for a phase are complete:
  1. Update CLAUDE.md Build Progress table: change status to [x] Complete and add the git tag
  2. Update CHANGELOG.md phase completion log with date and notes
  3. Git commit with message following pattern: "feat(phase-N): description"
  4. Git tag: phase-N-complete
  5. Git push (commit + tags)

### Before Building
- Always read the phase file (docs/phases/phase-{N}.md) before starting
- If the phase file says "Prerequisite Reading", read those files too
- If the user has questions, discuss FIRST, update the phase file with decisions, THEN build

### Documentation Updates
- When a build decision deviates from the spec, update the phase file immediately
- When new schema tables or interface methods are added, update docs/ARCHITECTURE.md
- When adding post-build features, update CLAUDE.md's Module Registry if a new module is created

### Git Discipline
- Never commit broken code (all services must start after each commit)
- Conventional commits: feat:, fix:, docs:, refactor:, test:, chore:
- Tag format: phase-N-complete (e.g., phase-1-complete)

## Conventions
- Python: Black formatting, type hints everywhere, async/await for all DB operations
- TypeScript: Strict mode, ESLint + Prettier
- API: RESTful, JSON responses, consistent error format: {error, message, details}
- Env vars: ALL config via .env, NEVER hardcode secrets
- Git: Conventional commits (feat:, fix:, docs:, refactor:, test:, chore:)
- After each phase: commit, tag (e.g., phase-1-complete), push

## Documentation Map
Read these files for detailed context when needed:

| File | Contains | Read when... |
|------|----------|--------------|
| docs/ARCHITECTURE.md | Full schemas, interface contracts, Redis keys, middleware chain, scaling tiers, connection pooling | Modifying existing code, building cross-module features, or any phase that touches shared infrastructure |
| docs/phases/phase-{N}.md | Detailed build spec for phase N: deliverables, acceptance criteria, implementation notes | Starting a new phase or resuming work on one |
| docs/features/feature-{name}.md | Spec for post-build features (same format as phase files) | Adding new functionality after initial build |
| CHANGELOG.md | What changed since initial build: new features, modified schemas, added interfaces | Returning to modify previously completed work |

## Build Progress

| Phase | Description | Status | Tag |
|-------|-------------|--------|-----|
| 1 | Project Skeleton & Modular Architecture | [x] Complete | phase-1-complete |
| 2 | Database Schema & Migration System | [x] Complete | phase-2-complete |
| 3 | Authentication System | [ ] Not started | — |
| 4 | Payment Processing | [ ] Not started | — |
| 5 | E-commerce Engine | [ ] Not started | — |
| 6 | User Tracking & Analytics | [ ] Not started | — |
| 7 | GDPR & Cookie Management | [ ] Not started | — |
| 8 | SEO Module | [ ] Not started | — |
| 9 | Frontend (Next.js) | [ ] Not started | — |
| 10 | Integration, Deployment & Docs | [ ] Not started | — |

## Environment
- Windows 11 + WSL2 (Ubuntu 24.04, ARM64 aarch64)
- Windows user: builduser | UNIX user: rootuser
- Home: /home/rootuser
- Project: ~/projects/boilerplate-app
- GitHub: macrohard90-boop/boilerplate-app (private)
- SSH key: ~/.ssh/id_ed25519_build
- Docker 29.2.0, Compose 5.0.2, Node.js v20.20.0, Python 3.11.8, Claude Code v2.1.42
