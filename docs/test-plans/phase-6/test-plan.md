# Phase 6 Test Plan — User Tracking & Analytics

**Date:** 2026-02-16 (updated 2026-02-17 — device analytics endpoint)
**Status:** 37 tests (30 original + 7 new for device endpoint)

---

## A. Module Loading & Startup

| # | Test | Method | Result |
|---|------|--------|--------|
| A1 | Tracking module loads on startup when `enable_tracking=true` | `docker compose logs fastapi \| grep tracking` | `Loaded module: tracking` in logs |
| A2 | Module registered at `/api/tracking` prefix | Checked loaded modules list in startup log | `['auth', 'ecommerce', 'payments', 'tracking']` |
| A3 | TrackingMiddleware registered in middleware chain | Server starts without import errors after adding to `main.py` | 200 OK on `/api/health` |

---

## B. GDPR Consent Gate

| # | Test | Method | Result |
|---|------|--------|--------|
| B1 | Pageview rejected when no consent record exists | `POST /api/tracking/pageview` with auth token, no consent in DB | `{"recorded": 0, "session_id": "..."}` |
| B2 | Pageview accepted after granting analytics consent | Inserted `gdpr.consent_records` row with `consent_type='analytics', granted=true`, then retried | `{"recorded": 1, "session_id": "..."}` |

**SQL used to grant consent:**
```sql
INSERT INTO gdpr.consent_records (user_id, consent_type, granted, ip_address)
VALUES ('b0000000-0000-0000-0000-000000000001', 'analytics', true, '127.0.0.1');
```

---

## C. Pageview Endpoints

| # | Test | Method | Result |
|---|------|--------|--------|
| C1 | Single pageview recorded | `POST /api/tracking/pageview` with `{"path": "/test-page", "referrer": "https://google.com"}` | `{"recorded": 1, "session_id": "6e1f4746-..."}` |
| C2 | Pageview stored in DB with correct fields | `SELECT * FROM analytics.page_views` | Row with path `/test-page`, referrer `https://google.com`, user_id set |
| C3 | Batch pageviews recorded | `POST /api/tracking/pageviews/batch` with 3 items (`/products`, `/products/shoes`, `/cart`) | `{"recorded": 3, "session_id": "6e1f4746-..."}` |
| C4 | Batch items include optional fields | Second batch item had `duration_ms: 5000` | Stored correctly in DB |

---

## D. Event Endpoints

| # | Test | Method | Result |
|---|------|--------|--------|
| D1 | Single event recorded | `POST /api/tracking/events` with `{"event_type": "add_to_cart", "event_data": {"product_id": "123", "quantity": 2}}` | `{"recorded": 1, "session_id": "..."}` |
| D2 | Event stored with JSONB payload | `SELECT event_type, event_data FROM analytics.events` | `add_to_cart` with `{"quantity": 2, "product_id": "123"}` |
| D3 | Batch events recorded | `POST /api/tracking/events/batch` with 2 items (`click`, `scroll`) | `{"recorded": 2, "session_id": "..."}` |
| D4 | All 3 events in DB after batch | `SELECT event_type FROM analytics.events` | `add_to_cart`, `click`, `scroll` — 3 rows |

---

## E. Analytics Session Management

| # | Test | Method | Result |
|---|------|--------|--------|
| E1 | Session created on first pageview | `SELECT * FROM analytics.analytics_sessions` after first pageview | 1 row with `session_id`, `user_id`, `started_at`, `page_count=1` |
| E2 | Session page_count increments | After recording 4 more pageviews (batch of 3 + middleware auto-track) | `page_count=5` in DB |
| E3 | Session reuses auth session_id | Authenticated user's JWT `sid` claim used as session_id | Session ID matches JWT `sid`: `6e1f4746-397c-4e3f-85fc-c3f5c0173e49` |

---

## F. Tracking Middleware (Auto-Tracking)

| # | Test | Method | Result |
|---|------|--------|--------|
| F1 | Middleware auto-tracks non-excluded endpoints | `GET /api/auth/me` with auth token, then checked DB | New pageview row with path `/api/auth/me` |
| F2 | Middleware is non-blocking | Response returned immediately; DB write happened async | 200 OK response, pageview appeared in DB after `sleep 2` |
| F3 | User agent stored by middleware | `SELECT browser, os, device_type FROM analytics.user_agents` | `Unknown`, `Unknown`, `desktop` (Python urllib UA — correct behavior) |

---

## G. Admin Analytics Endpoints

All tested with admin token (`admin@example.com` / `Test1234!`).

| # | Test | Method | Result |
|---|------|--------|--------|
| G1 | Pageview stats | `GET /api/tracking/admin/analytics/pageviews` | `{"total_views": 5, "unique_visitors": 1, "top_pages": [...5 entries...]}` |
| G2 | Session stats | `GET /api/tracking/admin/analytics/sessions` | `{"total_sessions": 1, "avg_page_count": 5.0, "by_day": [{"date": "2026-02-16", "sessions": 1}]}` |
| G3 | Event stats | `GET /api/tracking/admin/analytics/events` | `{"total_events": 3, "by_type": [{"event_type": "add_to_cart", "count": 1}, {"event_type": "click", "count": 1}, {"event_type": "scroll", "count": 1}]}` |
| G4 | Source stats | `GET /api/tracking/admin/analytics/sources` | `{"total_sources": 0, "sources": []}` (no referrals via middleware path) |
| G5 | UTM stats | `GET /api/tracking/admin/analytics/utm` | `{"total_campaigns": 0, "campaigns": []}` (no UTM params in test URLs) |
| G6 | Default date range applied | All endpoints called without `date_from`/`date_to` params | Defaulted to 30-day window (`2026-01-17` to `2026-02-16`) |

---

## H. Error Handling & Edge Cases

| # | Test | Method | Result |
|---|------|--------|--------|
| H1 | `enable_tracking=false` returns early | Checked route code: first line checks `settings.enable_tracking` | Returns `{"recorded": 0}` without DB call |
| H2 | Middleware skips excluded paths | `/api/health`, `/api/docs`, `/api/tracking/*` in exclude list | No pageview rows for these paths in DB |
| H3 | Import error: `async_session_factory` | Middleware initially imported non-existent name | Fixed to `get_session_factory()()` — server starts cleanly |
| H4 | Import error: `get_redis_pool` (sync call) | Middleware called async `get_redis_pool()` without await | Fixed to `await get_redis()` — returns proper Redis client |
| H5 | asyncpg date type error | Admin queries used `date + INTERVAL` which asyncpg rejected | Fixed: pre-compute `datetime` objects with `timezone.utc` |

---

## I. Post-Build Fix Tests (2026-02-17)

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| I1 | Device stats endpoint exists | `GET /api/tracking/admin/analytics/devices` with admin auth | 200 OK with `DeviceStats` response |
| I2 | Device stats returns `by_device_type` breakdown | Inspect response `by_device_type` array | Array of `{device_type, count}` objects (e.g., `desktop`, `mobile`) |
| I3 | Device stats returns `by_browser` breakdown | Inspect response `by_browser` array | Array of `{browser, count}` objects (top 10) |
| I4 | Device stats returns `by_os` breakdown | Inspect response `by_os` array | Array of `{os, count}` objects (top 10) |
| I5 | Device stats respects date range | `GET /api/tracking/admin/analytics/devices?date_from=2026-01-01&date_to=2026-01-01` | Empty or zero results for date range with no data |
| I6 | Device stats defaults to 30 days | `GET /api/tracking/admin/analytics/devices` (no params) | `date_from` and `date_to` fields show 30-day window |
| I7 | Device stats requires admin role | Call endpoint without auth or with non-admin token | 401 or 403 |

---

## Summary

| Category | Tests | Passed |
|----------|-------|--------|
| Module loading | 3 | 3 |
| GDPR consent | 2 | 2 |
| Pageview endpoints | 4 | 4 |
| Event endpoints | 4 | 4 |
| Session management | 3 | 3 |
| Middleware | 3 | 3 |
| Admin endpoints | 6 | 6 |
| Error handling | 5 | 5 |
| Post-build fix (devices) | 7 | — |
| **Total** | **37** | **30 + 7 new** |

Original 30 tests all passed. 7 new tests added for the device/browser analytics endpoint (2026-02-17).
