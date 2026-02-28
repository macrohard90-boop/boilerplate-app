# Phase 12: Audit Logging & User Analytics

**Estimate:** 6-8 hours
**Depends on:** Phase 11 (Deployment)
**Category:** Observability & analytics

## Goal
Build a complete observability layer: admin action audit logging using the existing `core.audit_log` infrastructure, and a generic frontend behavior analytics SDK that tracks user interactions (clicks, page views, idle time, session duration) in a template-portable way that survives UI changes across spawned apps.

## Prerequisite Reading
- `modules/auth/services/audit_service.py` — existing `log_audit()` function
- `migrations/001_core_schema.sql` — `core.audit_log` table schema
- `modules/tracking/` — existing tracking middleware (page views, user agents, UTM params)
- `docs/ARCHITECTURE.md` — data flow and middleware chain

## Deliverables

### Part A: Admin Audit Logging

1. **Wire audit logging into all admin routes** (modules/ecommerce/routes/admin_routes.py, modules/auth/routes/admin_routes.py):
   - [ ] Import and call `audit_service.log_audit()` on every admin action
   - [ ] Actions to log: discount create/update/delete, order status change, inventory adjust, subscription cancel, review moderate, digital asset CRUD, fee tier CRUD, user role changes
   - [ ] Each log entry captures: user_id, action name, resource type, resource ID, IP address, timestamp
   - [ ] Payload hash (SHA-256) of request body for tamper evidence

2. **Admin audit log viewer** (frontend/app/admin/audit/):
   - [ ] Paginated table showing recent admin actions
   - [ ] Filters: by action type, by admin user, by date range
   - [ ] Backend endpoint: `GET /admin/audit-log` with query params

3. **Tests**:
   - [ ] Unit: verify `log_audit()` is called with correct params on each admin route
   - [ ] Integration: create discount, verify audit_log row exists with correct action/resource

### Part B: Frontend Behavior Analytics SDK

4. **Generic event collector SDK** (frontend/lib/analytics.ts):
   - [ ] Document-level listeners — NOT tied to specific components (template-portable)
   - [ ] Events captured:
     - `page_view` — path, referrer, timestamp
     - `page_exit` — path, time_on_page_ms
     - `click` — element tag, CSS selector or `data-track` attribute, text content (truncated)
     - `idle_start` / `idle_end` — triggered after X seconds of no mouse/keyboard activity
     - `scroll_depth` — max scroll percentage reached per page
     - `session_start` / `session_end` — tab focus/blur, beforeunload
   - [ ] Batched sends: collect events in memory, flush every 10 seconds or on page exit via `sendBeacon()`
   - [ ] Lightweight: no external dependencies, < 3KB gzipped
   - [ ] Respects GDPR consent: check `analytics` consent before tracking

5. **Batch event endpoint** (modules/tracking/routes/):
   - [ ] `POST /api/tracking/events` — accepts array of events
   - [ ] High-throughput write: append to JSONL file (rotated daily) or dedicated table
   - [ ] No auth required (anonymous + authenticated users), but attach user_id if available
   - [ ] Rate limited: max 100 events per request, 10 requests per minute per IP

6. **Analytics provider wrapper** (frontend/components/AnalyticsProvider.tsx):
   - [ ] Wraps app layout, initializes SDK on mount
   - [ ] Reads GDPR consent state before enabling
   - [ ] Gated behind `enable_tracking` feature flag

7. **Tests**:
   - [ ] Unit: SDK emits correct events on simulated interactions
   - [ ] Integration: batch endpoint writes events, respects rate limit

### Part C: Optional — Third-Party Integration

8. **PostHog adapter** (modules/tracking/adapters/):
   - [ ] If session replay or heatmaps are needed, integrate PostHog (open-source, self-hostable)
   - [ ] Implement via adapter pattern (`AnalyticsProvider` interface)
   - [ ] Toggle between built-in SDK and PostHog via config flag
   - [ ] Self-hosted PostHog Docker service in docker-compose.yml (optional)

## Architecture Notes

- The frontend SDK must be **generic** — it captures raw interaction data (element type, CSS path, page URL) rather than domain-specific events. This means it works unchanged when you spawn a new app with different UI components.
- Admin audit logging uses the **existing** `core.audit_log` table and `audit_service.log_audit()`. No new tables needed.
- Frontend events go to a **separate store** from the audit log — these are high-volume, low-value-per-event data. PostgreSQL is fine for audit logs (low volume, high value) but frontend events should use JSONL files or a lightweight append-only table with periodic archival.
- All analytics must respect GDPR consent state (`analytics` consent type in `gdpr.consent_preferences`).

## Acceptance Criteria

- [ ] Every admin action (create, update, delete across all admin routes) produces a row in `core.audit_log`
- [ ] Admin can view audit history in `/admin/audit` with filters
- [ ] Frontend SDK tracks page views, clicks, idle time, scroll depth without any component-specific wiring
- [ ] Events batch-sent to backend every 10s and on page exit
- [ ] GDPR consent is checked before any tracking fires
- [ ] SDK is < 3KB gzipped, zero external dependencies
- [ ] Spawning a new app (different UI) requires zero changes to the analytics SDK

## Files Created
_(to be filled on completion)_
