# Phase 10: Integration, Deployment & Docs

**Estimate:** 3-4 hours
**Depends on:** Phase 9, Phase 6
**Category:** Quality assurance & operations

## Goal
Final integration phase: end-to-end testing across all modules, SSL/TLS configuration, production hardening (security headers, environment validation, log management), deployment documentation, and the complete setup guide. At the end of this phase, the boilerplate is production-ready and can be deployed to a new VPS within 24 hours.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 7 (Docker Compose Services), 8 (Scaling Tiers), 9 (Connection Pooling), 11 (24-Hour Deployment Workflow), and 12 (Security Measures) for the deployment specification.

## Deliverables

1. **End-to-end test suite** (tests/):
   - **Auth flow**: register → login → refresh → logout → verify tokens invalidated
   - **Product flow**: create product → add variants → upload images → verify listing
   - **Cart flow**: add to cart (guest) → login → cart merge → apply discount → verify totals
   - **Checkout flow**: cart → checkout → Stripe payment (test mode) → order created → inventory decremented
   - **GDPR flow**: grant consent → request export → verify data collected → request deletion → verify anonymization
   - **Analytics flow**: page view → event → verify tracking records created (with consent)
   - **SEO flow**: verify sitemap contains products → verify meta tags → verify JSON-LD
   - **RBAC flow**: customer blocked from admin endpoints → admin can access all
   - **M2M flow**: create API key → authenticate → access scoped endpoint → rate limit hit
   - Test framework: pytest + httpx (async) for backend, Jest/Playwright for frontend
   - CI integration: tests run in GitHub Actions pipeline

2. **SSL/TLS configuration** (docker/):
   - Let's Encrypt / Certbot integration for automatic SSL certificates
   - Nginx SSL configuration: TLS 1.2+, strong cipher suites, HSTS header
   - Auto-renewal cron job or Certbot container
   - HTTP → HTTPS redirect in Nginx
   - Certificate volume mount for persistence across container restarts
   - Development mode: self-signed certificates or HTTP-only option

3. **Production hardening** (backend/ + docker/):
   - Security headers middleware:
     - `Strict-Transport-Security` (HSTS)
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: DENY`
     - `X-XSS-Protection: 1; mode=block`
     - `Content-Security-Policy` (configurable)
     - `Referrer-Policy: strict-origin-when-cross-origin`
   - Environment validation: startup check that all required env vars are set
   - Log management:
     - Structured JSON logging (not plain text)
     - Log levels configurable via .env (DEBUG/INFO/WARNING/ERROR)
     - Log rotation: size-based or time-based via Docker logging driver
     - Sensitive data scrubbing (no passwords, tokens, or PII in logs)
   - Error handling: global exception handler with consistent error format
   - Health check improvements: deep health check (DB + Redis + disk space)

4. **Nginx production configuration** (docker/nginx.conf):
   - SSL termination with optimized TLS settings
   - Gzip compression for static assets and JSON responses
   - Static asset caching headers (Cache-Control, ETag)
   - Rate limiting at Nginx level (backup to application-level)
   - Request size limits (prevent large payload attacks)
   - Proxy timeout configuration
   - Access logging with request timing
   - Security: hide server version, block suspicious paths

5. **Docker Compose production profile** (docker/):
   - `docker-compose.prod.yml` — production overrides:
     - Restart policies: `always` for all services
     - Resource limits: memory and CPU constraints
     - Log driver configuration
     - Volume backup strategy
     - No port exposure except Nginx 80/443
   - `docker-compose.scale.yml` — already exists, verify replica configs work:
     - Multiple FastAPI replicas (2-4) with Nginx upstream
     - Multiple Next.js replicas (2-3)
     - Health-check-based load balancing

6. **Database backup strategy** (scripts/):
   - `scripts/backup.sh` — PostgreSQL backup script (pg_dump)
   - Scheduled backups: daily full, configurable retention (default 7 days)
   - Backup storage: local volume + optional remote (S3/SFTP — placeholder)
   - `scripts/restore.sh` — restore from backup file
   - Backup verification: restore to temp DB and validate

7. **Setup script updates** (scripts/setup.sh):
   - Update interactive setup to include all new modules:
     - Template selection (ecommerce/saas)
     - OAuth provider configuration prompts
     - Stripe key configuration
     - Email provider selection
     - Module toggle selections
   - Post-setup: run migrations → seed → health check → show summary
   - First-run guide: print next steps after setup completes

8. **Deployment documentation** (docs/):
   - `docs/DEPLOYMENT.md` — complete deployment guide:
     - VPS requirements (RAM, CPU, disk, OS)
     - Docker + Compose installation
     - Clone, configure, deploy steps
     - SSL setup (Certbot)
     - DNS configuration
     - Monitoring recommendations
     - Scaling guide (when and how to scale up)
   - `docs/TROUBLESHOOTING.md` — common issues and fixes:
     - Container won't start
     - Database connection issues
     - SSL certificate problems
     - Memory/disk issues
     - Migration failures
   - `docs/API.md` — API reference (auto-generated from FastAPI OpenAPI spec or manual)

9. **CI/CD pipeline updates** (.github/workflows/ci.yml):
   - Add e2e test job that runs full integration tests
   - Add security scanning step (dependency audit)
   - Add Docker image build verification
   - Deployment job: SSH to VPS, pull, rebuild, restart, health check
   - Rollback capability: if health check fails after deploy, revert to previous version
   - Environment-specific configs: staging vs production

10. **Monitoring and observability** (backend/):
    - `GET /api/health` — enhanced health check (DB, Redis, disk, memory)
    - Request logging: structured logs with request_id, duration, status
    - Error alerting: configurable webhook for critical errors (placeholder)
    - Uptime endpoint: lightweight ping for external monitoring services

## Acceptance Criteria
- [ ] E2E auth flow passes: register → login → refresh → logout
- [ ] E2E checkout flow passes: cart → checkout → payment → order confirmed
- [ ] E2E GDPR flow passes: consent → export → deletion
- [ ] SSL works: HTTPS serves valid certificate, HTTP redirects to HTTPS
- [ ] Security headers present on all responses
- [ ] Environment validation catches missing required vars on startup
- [ ] Structured JSON logging enabled with configurable log level
- [ ] Nginx gzip compression active for JSON and static assets
- [ ] Docker Compose production profile works with resource limits
- [ ] Database backup script creates valid backup
- [ ] Database restore script restores successfully
- [ ] Setup script runs end-to-end on fresh clone
- [ ] Deployment documentation covers full VPS setup
- [ ] CI pipeline runs e2e tests and reports results
- [ ] Health check endpoint reports all service statuses
- [ ] No sensitive data (passwords, tokens) in logs
- [ ] All 10 phases verified working together as integrated system

## Implementation Notes
- E2E tests: use pytest + httpx AsyncClient against a running test stack (Docker Compose with test DB)
- Frontend e2e: Playwright or Cypress for browser-based testing (optional, can defer)
- SSL: Let's Encrypt with `certbot/certbot` Docker image or manual certbot install on VPS
- Structured logging: use Python `structlog` or `python-json-logger`
- Backup timing: cron job inside a dedicated backup container or host cron
- CI secrets: Stripe test keys, OAuth test credentials stored in GitHub Secrets
- Rollback: use git tags (phase-N-complete) — deploy = checkout tag + rebuild
- Monitor: recommend external uptime services (UptimeRobot, Hetrix) — not built-in

## Files to Create
- `tests/e2e/test_auth_flow.py` — Auth integration tests
- `tests/e2e/test_checkout_flow.py` — Checkout integration tests
- `tests/e2e/test_gdpr_flow.py` — GDPR integration tests
- `tests/e2e/test_analytics_flow.py` — Analytics integration tests
- `tests/e2e/test_seo_flow.py` — SEO integration tests
- `tests/e2e/conftest.py` — Test fixtures and setup
- `docker/nginx-ssl.conf` — Production Nginx config with SSL
- `docker/docker-compose.prod.yml` — Production overrides
- `scripts/backup.sh` — Database backup script
- `scripts/restore.sh` — Database restore script
- `backend/core/security_headers.py` — Security headers middleware
- `backend/core/logging_config.py` — Structured logging setup
- `backend/core/startup_checks.py` — Environment validation on startup
- `docs/DEPLOYMENT.md` — Deployment guide
- `docs/TROUBLESHOOTING.md` — Troubleshooting guide
- `docs/API.md` — API reference
- Modified: `scripts/setup.sh` — Updated interactive setup
- Modified: `.github/workflows/ci.yml` — E2E tests, security scanning
- Modified: `docker/nginx.conf` — Production hardening
- Modified: `backend/main.py` — Security headers, structured logging, startup checks
