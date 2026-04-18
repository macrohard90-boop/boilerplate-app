# Boilerplate Application — Project Context & Engineering Contract

> This file defines project context, architecture, and how Claude Code should think, review, and interact across all work in this repository.

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

## Engineering Preferences

Use these to guide every recommendation and code change:

- **DRY is important** — flag repetition aggressively.
- **Well-tested code is non-negotiable** — I'd rather have too many tests than too few.
- **"Engineered enough"** — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity).
- **Edge cases matter** — err on the side of handling more edge cases, not fewer. Thoughtfulness > speed.
- **Explicit over clever** — bias toward readable, predictable code.
- **Template portability first** — this is a reusable boilerplate. Before finalizing any implementation, flag whether the code is template-generic or project-specific. Anything project-specific must be isolated and documented as a customization point.

## Architecture Principles
1. TOGGLE-FIRST: Every feature must be toggleable via `.env`. Design for the operator who spins up a new instance and chooses what to enable. See "Toggle-First Design Rules" below.
2. STATELESS SERVERS: No in-memory state. All shared state in Redis or PostgreSQL. Enables clustering.
3. SESSION ISOLATION: User ID comes from server-verified JWT/Redis session, never from client input.
4. SCALABLE: 10-20 concurrent users baseline, horizontally scalable to 100+ via Docker clustering + load balancer.
5. ADAPTER PATTERN: External services (payments, OAuth, analytics) use interfaces. Swap providers by implementing the interface.

## Toggle-First Design Rules

This is a template repository. Every instance is a different business (shoe store, SaaS tool, consulting firm). Features that exist in the template must be toggleable so each deployment only exposes what it needs. **This is the #1 architectural priority.**

### The Core Idea
When an operator runs `cp .env.template .env` and sets `ENABLE_SUBSCRIPTIONS=false`, subscriptions must vanish completely — no nav links, no API routes, no admin pages, no checkout references. The app should look and behave as if subscriptions were never built.

### The 4-Layer Enforcement Pattern
Every toggleable feature must be gated at ALL four layers. Missing any layer creates leaks.

```
Layer 1: .env / config.py          → ENABLE_FEATURE=true/false
Layer 2: Backend routes             → Conditional route registration or 404
Layer 3: /api/config endpoint       → Expose flag to frontend
Layer 4: Frontend UI                → Conditional rendering via useConfig()
```

**Layer 1 — Environment & Config:**
- Add `ENABLE_X=true` to `.env.template` under "Module Toggles" or "Feature toggles"
- Add `enable_x: bool = True` to `backend/core/config.py` Settings class
- For whole modules: add to `MODULE_TOGGLES` dict in `backend/core/module_loader.py`
- For sub-features (like products vs subscriptions within ecommerce): add as feature toggles in config

**Layer 2 — Backend Route Gating:**
- Whole modules: `module_loader.py` already handles this via `MODULE_TOGGLES`
- Sub-features: gate in the module's `routes/__init__.py` with `if settings.enable_x:`
- Services that create/query toggled resources should respect flags too
- Example: `modules/ecommerce/routes/__init__.py` conditionally includes `subscription_routes`

**Layer 3 — /api/config Endpoint:**
- Add new flags to the `/api/config` response in `backend/main.py`
- This is what the frontend reads to know what's enabled — keep it in sync with Layer 1

**Layer 4 — Frontend Conditional UI:**
- Use `const { enable_x } = useConfig()` from `frontend/lib/config-context.tsx`
- Gate ALL UI touchpoints: nav links, page tabs, admin sidebar items, homepage sections, CTA buttons
- The `ConfigProvider` in `frontend/app/layout.tsx` fetches `/api/config` once on mount

### Current Toggle Map

| Env Var | Config Field | Controls | Layers Done |
|---------|-------------|----------|-------------|
| `ENABLE_PAYMENTS` | `enable_payments` | Payment module loading, order reaper | 1,2 |
| `ENABLE_TRACKING` | `enable_tracking` | Analytics middleware, tracking module | 1,2 |
| `ENABLE_CHATBOT` | `enable_chatbot` | Chatbot module loading | 1,2 |
| `ENABLE_MARKETING` | `enable_marketing` | Marketing module loading | 1,2 |
| `ENABLE_RECOMMENDATIONS` | `enable_recommendations` | Recommendation module loading | 1,2 |
| `ENABLE_PRODUCTS` | `enable_products` | Product catalog, product-related UI | 1,2,3,4 |
| `ENABLE_SUBSCRIPTIONS` | `enable_subscriptions` | Subscription routes, subscription UI | 1,2,3,4 |
| `ENABLE_SEO_SCORING` | `enable_seo_scoring` | SEO scoring engine, audit dashboard tab, rescorer background task | 1,2,3,4 |
| `ENABLE_SEO_CRAWLER` | `enable_seo_crawler` | Live HTML crawler, crawler dashboard tab, Playwright install | 1,2,3,4 |

### Rules for New Features

1. **Before writing any code**, ask: "If an operator disables this, what should disappear?" Write down the list.
2. **Add the env var first** (`.env.template` + `config.py`). This forces toggle-first thinking.
3. **Gate backend routes** before building services. Don't build an endpoint you can't turn off.
4. **Expose to frontend** via `/api/config` if the feature has ANY UI component.
5. **Gate every UI touchpoint** — nav links, tabs, cards, admin pages, CTAs, homepage sections. Search the whole frontend for references to the feature.
6. **Test both states**: rebuild with the flag `true`, verify it works. Set to `false`, rebuild, verify it's completely gone. No dead links, no empty sections, no console errors.

### Rules for Modifying Existing Features

1. **Check if the feature is already toggled** — look at the Toggle Map above. If it is, your changes must respect the existing flag.
2. **If you're adding a new UI entry point** to a toggled feature (e.g., a new admin page for products), wrap it in the same `useConfig()` check.
3. **If you're adding a new API route** to a toggled module, add it inside the conditional block in `routes/__init__.py`, not outside.
4. **Never hardcode feature assumptions** — don't write `if (product.pricing_type === "recurring")` in shared components without checking `enable_subscriptions`. The concept of "recurring" shouldn't exist in the UI when subscriptions are off.

### Common Deployment Configurations

| Business Type | Products | Subscriptions | Example |
|--------------|----------|---------------|---------|
| E-commerce store | true | false | Shoe store, electronics shop |
| SaaS / membership | false | true | Software tool, content platform |
| Hybrid | true | true | Store with premium membership |
| Service business | false | false | Consulting firm (auth + content only) |

## Module Registry

| Module ID  | Name                         | Status          | Toggle | Interfaces |
|------------|------------------------------|-----------------|--------|------------|
| auth       | Authentication & Authorization | Required (core) | Always on | AuthProvider (OAuth adapters) |
| gdpr       | GDPR & Privacy               | Required (core) | Always on | — |
| seo        | SEO Module                   | Required (core) | Always on | — |
| payments   | Payment Processing           | Optional        | `ENABLE_PAYMENTS` | PaymentProvider (Stripe, etc.) |
| ecommerce  | E-commerce Engine            | Template choice | Always on when `APP_TEMPLATE=ecommerce` | — |
| — products | One-time product catalog     | Sub-feature     | `ENABLE_PRODUCTS` | — |
| — subscriptions | Recurring plans/memberships | Sub-feature   | `ENABLE_SUBSCRIPTIONS` | — |
| saas       | SaaS Subscriptions           | Template choice | Always on when `APP_TEMPLATE=saas` | — |
| tracking   | User Analytics               | Optional        | `ENABLE_TRACKING` | GeoProvider, AgentParser |
| chatbot    | AI Chatbot                   | Optional        | `ENABLE_CHATBOT` | ChatbotProvider |
| marketing  | Marketing & Promotions       | Optional        | `ENABLE_MARKETING` | — |
| notifications | Email & Notifications       | Required (core) | Always on | EmailProvider |
| recommendations | Recommendations & Cart Recovery | Optional   | `ENABLE_RECOMMENDATIONS` | RecommendationProvider, ReminderStrategy |

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

### Before You Start Any Task
Ask if I want one of two modes:

**1/ BIG CHANGE** — Work through the review protocol interactively, one section at a time (Architecture, Code Quality, Tests, Performance) with at most 4 top issues per section.

**2/ SMALL CHANGE** — Work through interactively ONE question per review section.

### Review Protocol (Always On)
Review thoroughly before making any code changes. For every issue or recommendation: explain the concrete tradeoffs, give an opinionated recommendation, and ask for my input before assuming a direction.

**1. Architecture Review** — Evaluate:
- Overall system design and component boundaries
- Dependency graph and coupling concerns
- Data flow patterns and potential bottlenecks
- Security architecture (auth, data access, API boundaries)
- **Template boundary check**: Is the decision generic enough to survive across different projects, or does it bake in assumptions?

**2. Code Quality Review** — Evaluate:
- Code organization and module structure
- DRY violations — be aggressive here
- Error handling patterns and missing edge cases (call these out explicitly)
- Technical debt hotspots
- Areas that are over-engineered or under-engineered
- **Customization surface**: Are config points, env vars, and extension hooks separated from core logic?

**3. Test Review** — Evaluate:
- Test coverage gaps (unit, integration, e2e)
- Test quality and assertion strength
- Missing edge case coverage — be thorough
- Untested failure modes and error paths

**4. Performance Review** — Evaluate:
- N+1 queries and database access patterns
- Memory-usage concerns
- Caching opportunities
- Slow or high-complexity code paths

### For Each Issue Found
- Describe the problem concretely, with file and line references
- Present 2-3 options, including "do nothing" where reasonable
- For each option: implementation effort, risk, impact on other code, maintenance burden
- Give recommended option and why, mapped to Engineering Preferences above
- **NUMBER** each issue, **LETTER** each option
- Make the recommended option the 1st option
- Ask whether I agree or want a different direction before proceeding
- If an issue is minor and clearly correct to fix, group it as a "quick wins" batch

### Progress Tracking
- Build ONE deliverable at a time. After each deliverable is complete and working:
  1. In the phase file (docs/phases/phase-{N}.md): change [ ] to [x] for the completed acceptance criterion
  2. In the phase file: add the created file paths to the "Files Created" section
  3. Brief status update to the user: "✓ Deliverable N done. Moving to next."
- When ALL deliverables for a phase are complete:
  1. Update CLAUDE.md Build Progress table: change status to [x] Complete and add the git tag
  2. Update CHANGELOG.md phase completion log with date and notes
  3. Update `docs/ARCHITECTURE.md` if any schemas, interfaces, Redis keys, middleware, or data flows changed during this phase
  4. Update the phase test plan at `docs/test-plans/phase-{N}/test-plan.md` — add test sections for new functionality, mark executed tests with pass/fail, update the test summary counts. If no test plan exists for this phase, create one following the format of existing plans (see `docs/test-plans/phase-10/test-plan.md` for reference). Also update `tests/COVERAGE_GAPS.md` to reflect any remaining gaps.
  5. Create `docs/diagrams/phase-N-flow.html` — a Mermaid.js flow diagram showing everything built in that phase (files, data flows, dependencies, startup sequences). Use dark theme, colored subgraphs per section. Self-contained HTML (Mermaid CDN). See existing diagrams for style reference.
  6. Update `docs/diagrams/project-overview.html` — mark the completed phase, update connections to subsequent phases
  7. Git commit with message following pattern: "feat(phase-N): description"
  8. Git tag: phase-N-complete
  9. Git push (commit + tags)

### Before Building
- Always read the phase file (docs/phases/phase-{N}.md) before starting
- If the phase file says "Prerequisite Reading", read those files too
- If the user has questions, discuss FIRST, update the phase file with decisions, THEN build
- **Toggle check**: If the feature you're building could reasonably be disabled for some deployments, implement the 4-layer toggle pattern BEFORE building the feature logic. Don't build first and toggle later — that's how we end up retrofitting

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
| docs/diagrams/phase-N-flow.html | Visual flow diagram for phase N: files created, data flows, dependencies, startup sequences | Onboarding, reviewing what a phase built, understanding flow at a glance |
| docs/diagrams/project-overview.html | Master diagram: all 10 phases, completion status, inter-phase dependencies | Understanding the big picture, planning next steps, onboarding new developers |
| docs/features/feature-{name}.md | Spec for post-build features (same format as phase files) | Adding new functionality after initial build |
| CHANGELOG.md | What changed since initial build: new features, modified schemas, added interfaces | Returning to modify previously completed work |

## Build Progress

| Phase | Description | Status | Tag |
|-------|-------------|--------|-----|
| 1 | Project Skeleton & Modular Architecture | [x] Complete | phase-1-complete |
| 2 | Database Schema & Migration System | [x] Complete | phase-2-complete |
| 3 | Authentication System | [x] Complete | phase-3-complete |
| 4 | Payment Processing | [x] Complete | phase-4-complete |
| 5 | E-commerce Engine | [x] Complete | phase-5-complete |
| 6 | User Tracking & Analytics | [x] Complete | phase-6-complete |
| 7 | GDPR & Cookie Management | [x] Complete | phase-7-complete |
| 8 | SEO Module | [x] Complete | phase-8-complete |
| 9 | Frontend (Next.js) | [x] Complete | phase-9-complete |
| 10 | Stripe Integration & Payment Frontend | [x] Complete | phase-10-complete |
| 11 | Integration, Deployment & Docs | [ ] Not started | — |
| 12 | Audit Logging & User Analytics | [ ] Not started | — |

## Environment

### CRITICAL: Two Environments Exist — Never Confuse Them

Claude Code runs on the **LOCAL machine (WSL2)**. It does NOT run on the VM. Every `docker compose exec`, `psql`, and log command runs against the **local** Docker stack, NOT the production VM.

| | LOCAL (where Claude Code runs) | VM (production) |
|---|---|---|
| **Machine** | Windows 11 + WSL2 (Ubuntu 24.04) | GCP VM |
| **Hostname** | `Adrian` | Unknown (NOT Adrian) |
| **Kernel** | `microsoft-standard-WSL2` | Standard Linux |
| **External IP** | `213.58.224.119` (NAT, changes) | `34.30.88.59` (static) |
| **URL** | `http://localhost` | `http://34.30.88.59` |
| **Database** | Local Docker postgres | VM Docker postgres |
| **Stripe webhooks** | Will NOT work (localhost) | Works (public URL) |
| **Use for** | Code editing, builds, tests | Full payment/email E2E testing |

**Rules:**
1. When the user reports behavior from `http://34.30.88.59/`, that data is in the **VM database** — you CANNOT query it directly. Do NOT look at the local DB and claim the data isn't there.
2. To inspect the VM database, the user must either: (a) SSH into the VM, or (b) use a remote DB client (pgAdmin, etc.), or (c) read the browser DevTools Network tab.
3. When debugging issues on the VM, rely on **browser DevTools** (Network tab, Console) for evidence — the user can share those. Do NOT rely on local Docker logs.
4. If unsure which environment a problem is in, **ASK FIRST** before running any local queries.
5. After code changes on the local machine, the user must `git push` and redeploy on the VM for changes to take effect there.

### Local Machine Details
- Windows 11 + WSL2 (Ubuntu 24.04, ARM64 aarch64)
- Windows user: builduser | UNIX user: rootuser
- Home: /home/rootuser
- Project: ~/projects/boilerplate-app
- GitHub: macrohard90-boop/boilerplate-app (private)
- SSH key: ~/.ssh/id_ed25519_build
- Docker 29.2.0, Compose 5.0.2, Node.js v20.20.0, Python 3.11.8, Claude Code v2.1.42

### VM Details
- GCP VM at `34.30.88.59`
- VM hostname: `instance-20260416-162856`
- VM username: `adrian_radoi` (NOT rootuser)
- Project path: `~/boilerplate-app` (NOT ~/projects/boilerplate-app)
- Same Docker stack deployed via git pull + docker compose (CI/CD in `.github/workflows/ci.yml`)
- Stripe webhook endpoint: `http://34.30.88.59/api/payments/webhook`
- Access via: GCP Console → Compute Engine → SSH button (browser terminal)
- This is where full E2E payment/email testing happens
