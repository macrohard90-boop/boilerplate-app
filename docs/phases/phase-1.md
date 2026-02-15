# Phase 1: Project Skeleton & Modular Architecture

**Estimate:** 3-4 hours
**Depends on:** Nothing (first phase)
**Category:** Foundation

## Goal
Create the monorepo structure, Docker Compose stack, module auto-discovery system, Redis integration, CI/CD pipeline, and interactive setup script. At the end of this phase, `docker compose up` runs a working stack with FastAPI, Next.js, Redis, PostgreSQL, and Nginx — even though no business logic exists yet.

## Deliverables

1. **Repository structure:**
   ```
   /frontend/          # Next.js app
   /backend/           # FastAPI app
   /modules/           # All feature modules (empty dirs for now)
   /scripts/           # Setup script, migration runner, mirror script
   /docs/              # Documentation (this file and others)
   /docker/            # Dockerfiles, nginx config
   docker-compose.yml
   docker-compose.scale.yml
   .env.template
   .github/workflows/ci.yml
   CLAUDE.md
   ```

2. **Module loader** (backend/core/module_loader.py):
   - Reads .env flags (ENABLE_PAYMENTS, ENABLE_TRACKING, etc.)
   - Auto-discovers modules in /modules/ that have a config.py with `enabled` flag
   - Registers module routes with FastAPI app
   - Logs which modules are loaded at startup
   - Gracefully skips disabled/missing modules

3. **Docker Compose** (docker-compose.yml):
   - PostgreSQL 16 Alpine: persistent volume, :5432 internal
   - FastAPI: python:3.11-slim, Uvicorn, 2 workers, :8000 internal
   - Next.js: node:20-alpine, :3000 internal
   - Redis 7 Alpine: maxmemory 256mb, AOF persistence, :6379 internal
   - Nginx Alpine: reverse proxy, :80/:443 exposed, routes /api/* → fastapi, /* → nextjs
   - PgBouncer: optional service (commented out by default, enable at Growth tier)
   - Health checks on all services
   - Named network for service discovery

4. **Docker Compose scaling profile** (docker-compose.scale.yml):
   - FastAPI: deploy.replicas configurable (2-4)
   - Next.js: deploy.replicas configurable (2-3)
   - Nginx: upstream block with load balancing (round-robin)
   - Shared Redis and PostgreSQL

5. **Redis integration** (backend/core/redis.py):
   - Connection pool factory (pool_size from .env)
   - Health check endpoint: GET /api/health/redis
   - Configurable TTLs read from .env (SESSION_TTL, CART_TTL, RATE_LIMIT_WINDOW)
   - Async Redis client (aioredis or redis-py async)

6. **.env.template:**
   - All module toggles: ENABLE_PAYMENTS, ENABLE_TRACKING, ENABLE_CHATBOT, ENABLE_MARKETING
   - Database: DATABASE_URL, POOL_SIZE, MAX_OVERFLOW, POOL_TIMEOUT
   - Redis: REDIS_URL, REDIS_POOL_SIZE, SESSION_TTL, CART_TTL, RATE_LIMIT_WINDOW
   - Auth: JWT_SECRET, JWT_EXPIRY, REFRESH_TOKEN_TTL, MAX_SESSIONS_PER_USER
   - OAuth: all provider client IDs and secrets
   - Stripe: STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET, PLATFORM_FEE_PERCENT
   - SMTP: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL
   - Domain: DOMAIN, FRONTEND_URL, BACKEND_URL
   - Scaling: UVICORN_WORKERS, NEXTJS_WORKERS
   - SEO: SITE_NAME, DEFAULT_OG_IMAGE, SOCIAL_HANDLES

7. **Setup script** (scripts/setup.sh):
   - Interactive prompts: app name, brand, domain, template (ecommerce/saas)
   - Copies .env.template to .env, fills in prompted values
   - Builds Docker images
   - Starts containers
   - Runs health checks
   - Outputs next steps

8. **GitHub Actions CI/CD** (.github/workflows/ci.yml):
   - Trigger: push to main, pull requests
   - Lint: Python (flake8, black --check), JavaScript (ESLint, Prettier --check)
   - Test: pytest (backend), Jest (frontend)
   - Build: Docker images
   - Deploy: SSH to VPS, pull, restart (on main branch only)
   - Secrets: SSH_KEY, VPS_HOST, DOCKER_REGISTRY (stored in GitHub Secrets)

9. **Mirror script** (scripts/mirror.sh):
   - Pushes to secondary remote (GitLab or other)
   - Can be added as post-push hook or CI step

## Acceptance Criteria
- [x] `docker compose up -d` starts all services without errors
- [x] GET /api/health returns {status: "ok", services: {redis: "ok", db: "ok"}}
- [x] GET /api/health/redis returns Redis connection status
- [x] Next.js serves a placeholder page at http://localhost
- [x] Nginx routes /api/* to FastAPI and /* to Next.js
- [x] Module loader logs "Loaded modules: []" (empty, none built yet)
- [x] .env.template contains all expected variables with comments
- [x] CI pipeline runs lint + test steps (even if tests are placeholder)

## Implementation Notes
- Use multi-stage Dockerfiles for smaller images
- FastAPI app factory pattern: create_app() function that calls module_loader
- Next.js: use App Router (app/ directory)
- Nginx config should include proxy_set_header for X-Forwarded-For, X-Real-IP
- Redis connection should retry on startup (container may not be ready immediately)
- All ARM64 compatible images (no x86-only base images)

## Files Created

### Root
- `.dockerignore`
- `.env.template`
- `.gitignore`
- `docker-compose.yml`
- `docker-compose.scale.yml`

### Backend
- `backend/__init__.py`
- `backend/main.py`
- `backend/requirements.txt`
- `backend/core/__init__.py`
- `backend/core/config.py`
- `backend/core/module_loader.py`
- `backend/core/redis.py`

### Frontend
- `frontend/package.json`
- `frontend/next.config.js`
- `frontend/tsconfig.json`
- `frontend/.eslintrc.json`
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/public/.gitkeep`

### Docker
- `docker/backend.Dockerfile`
- `docker/frontend.Dockerfile`
- `docker/nginx.conf`

### Scripts
- `scripts/setup.sh`
- `scripts/mirror.sh`

### CI/CD
- `.github/workflows/ci.yml`

### Modules (empty directory scaffolds)
- `modules/auth/`
- `modules/gdpr/`
- `modules/seo/`
- `modules/payments/`
- `modules/ecommerce/`
- `modules/saas/`
- `modules/tracking/`
- `modules/chatbot/`
- `modules/marketing/`
