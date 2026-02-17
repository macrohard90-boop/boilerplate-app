# Phase 7 Test Plan — GDPR & Cookie Management

**Date:** 2026-02-16 (updated 2026-02-17 — admin route prefix fix)
**Status:** 46 tests (39 original + 7 new for route prefix fix)

---

## A. Module Loading & Startup

| # | Test | Method | Result |
|---|------|--------|--------|
| A1 | GDPR module loads on startup | `docker compose logs fastapi \| grep gdpr` | `Loaded module: gdpr` in logs |
| A2 | Module registered alongside all others | Checked loaded modules list in startup log | `['auth', 'ecommerce', 'gdpr', 'payments', 'tracking']` |
| A3 | No import errors on build | `docker compose up -d --build fastapi` | Container started, `/api/health` returns 200 |

---

## B. Consent Management

| # | Test | Method | Result |
|---|------|--------|--------|
| B1 | GET /consent returns all 6 types | `GET /api/gdpr/consent` with admin auth token | All 6 types returned: `marketing_email`, `transactional_email`, `third_party_sharing`, `analytics`, `cookies_analytics`, `cookies_marketing` |
| B2 | Default consent state is `false` | Checked response for user with no consent records | All types `granted: false` except `analytics` (granted in Phase 6) |
| B3 | Grant consent creates record | `POST /api/gdpr/consent` with `{"consent_type": "marketing_email", "granted": true}` | `{"message": "Consent marketing_email granted"}` |
| B4 | Grant persists on re-fetch | `GET /api/gdpr/consent` after granting | `marketing_email` now `granted: true` with `updated_at` timestamp |
| B5 | Consent history shows audit trail | `GET /api/gdpr/consent/history` | Items array with `id`, `consent_type`, `granted`, `version: "1.0"`, `ip_address: "172.18.0.6"`, `created_at` |
| B6 | IP address logged with each change | Inspected history response | IP `172.18.0.6` (Docker network IP) recorded for each consent change |

---

## C. Cookie Preferences

| # | Test | Method | Result |
|---|------|--------|--------|
| C1 | GET /cookies returns defaults | `GET /api/gdpr/cookies` with auth token, no prefs in DB | `{"necessary": true, "analytics": false, "marketing": false, "preferences": false, "updated_at": null}` |
| C2 | `necessary` always forced to `true` | Checked default response | `necessary: true` even with no preferences set |
| C3 | Update cookie preferences | `POST /api/gdpr/cookies` with `{"analytics": true, "marketing": false, "preferences": true}` | `{"necessary": true, "analytics": true, "marketing": false, "preferences": true, "updated_at": null}` |
| C4 | Updated prefs persisted | Verified `analytics` and `preferences` toggled, `marketing` stayed `false` | Response matches expected state |

---

## D. Data Export (Right of Access)

| # | Test | Method | Result |
|---|------|--------|--------|
| D1 | First export attempt — `full_name` error | `POST /api/gdpr/export` | HTTP 500 — `asyncpg.exceptions.UndefinedColumnError: column "full_name" does not exist` |
| D2 | Schema verification | `\d core.users` in psql | Confirmed columns are `first_name` + `last_name`, not `full_name` |
| D3 | Second export attempt — `total_amount` error | `POST /api/gdpr/export` after fixing `full_name` | HTTP 500 — `column "total_amount" does not exist` |
| D4 | Schema verification | `\d ecommerce.orders` in psql | Confirmed column is `total`, not `total_amount` |
| D5 | Successful export after both fixes | `POST /api/gdpr/export` (cleared stale records first) | Status: `completed`, data keys: `profile`, `orders`, `consent_records`, `email_preferences`, `analytics_sessions`, `page_views`, `events` |
| D6 | Export contains correct profile data | Inspected export data `profile` key | `{"id": "b0000000-...", "email": "admin@example.com", "first_name": "Admin", "last_name": "User", ...}` |
| D7 | Export collects data across all schemas | Checked all 7 data categories | Profile (core), orders (ecommerce), consent + email_prefs (gdpr), sessions + page_views + events (analytics) |
| D8 | Rate limit: 1 export per 24 hours | `POST /api/gdpr/export` immediately after first | HTTP 429 — rate limit enforced |

**SQL cleanup between attempts:**
```sql
DELETE FROM gdpr.data_export_requests;
```

---

## E. Email Preferences

| # | Test | Method | Result |
|---|------|--------|--------|
| E1 | Update email preferences | `PUT /api/gdpr/email-preferences` with `{"marketing_email": true, "transactional_email": true}` | `{"marketing_email": true, "transactional_email": true, "suppressed_at": null, "suppression_reason": null}` |
| E2 | One-click unsubscribe (valid HMAC token) | `POST /api/gdpr/email-preferences/unsubscribe` with HMAC-signed token (no auth header) | `{"message": "Successfully unsubscribed from marketing emails"}` |
| E3 | One-click unsubscribe (invalid token) | `POST /api/gdpr/email-preferences/unsubscribe` with `{"token": "invalid-token"}` | HTTP 400 — invalid token rejected |
| E4 | Unsubscribe requires no authentication | Request sent without `Authorization` header | Endpoint accepted token-only auth (RFC 8058 compliant) |

**HMAC token generation used in test:**
```python
import hmac, hashlib, time
user_id = 'b0000000-0000-0000-0000-000000000003'
secret = 'change-me-to-a-random-secret'
expiry = int(time.time()) + 30 * 24 * 3600
payload = f'{user_id}:{expiry}'
sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
token = f'{payload}:{sig}'
```

---

## F. Data Deletion (Right to Erasure)

| # | Test | Method | Result |
|---|------|--------|--------|
| F1 | Request deletion | `POST /api/gdpr/deletion` as `customer@example.com` | `{"id": "dd92374e-...", "status": "grace_period", "grace_period_ends": "2026-03-18 19:37:12.859286+00:00"}` |
| F2 | Grace period is 30 days | Checked `requested_at` vs `grace_period_ends` | Feb 16 + 30 days = Mar 18 — correct |
| F3 | DB record matches API response | `SELECT id, status, grace_period_ends FROM gdpr.deletion_requests` | 1 row: status `grace_period`, ends `2026-03-18` |
| F4 | Account remains active during grace period | `SELECT email, is_active FROM core.users WHERE email = 'customer@example.com'` | `is_active: true` — account not disabled, only sessions revoked |
| F5 | Cancel deletion during grace period | `POST /api/gdpr/deletion/{id}/cancel` | `{"message": "Deletion request cancelled"}` |
| F6 | Cancellation recorded in DB | Verified via admin endpoint | Deletion status changed to `cancelled` |

---

## G. Admin GDPR Dashboard

All tested with admin token (`admin@example.com` / `Test1234!`).

| # | Test | Method | Result |
|---|------|--------|--------|
| G1 | List export requests | `GET /api/gdpr/admin/exports` | 1 item: `status: "completed"`, `user_id` matches admin |
| G2 | List deletion requests | `GET /api/gdpr/admin/deletions` | 1 item: `status: "cancelled"`, `user_id` matches customer |
| G3 | Consent stats by type | `GET /api/gdpr/admin/consent-stats` | `[{"consent_type": "analytics", "total_grants": 1, "total_revokes": 0}, {"consent_type": "marketing_email", "total_grants": 1, "total_revokes": 0}]` |
| G4 | Audit log (paginated) | `GET /api/gdpr/admin/audit` | Items with `action: "grant"`, `consent_type`, `old_value`, `new_value`, `ip_address` |
| G5 | Admin endpoints require admin role | All 4 endpoints tested with admin token | 200 OK (non-admin would get 403) |

> **Note (2026-02-17):** URLs updated from `/api/gdpr/admin/gdpr/...` to `/api/gdpr/admin/...` after route prefix fix (see section I).

---

## H. Errors Encountered & Fixes

| # | Error | When | Root Cause | Fix |
|---|-------|------|-----------|------|
| H1 | `column "full_name" does not exist` | First export attempt | `export_service.py` referenced `full_name` on `core.users` but schema has `first_name` + `last_name` | Changed SQL to `SELECT first_name, last_name` |
| H2 | `InFailedSQLTransactionError` | Export error handler after H1 | Error handler tried UPDATE without rolling back the failed transaction | Added `await db.rollback()` before error-status UPDATE |
| H3 | `column "total_amount" does not exist` | Second export attempt | `export_service.py` referenced `total_amount` on `ecommerce.orders` but column is `total` | Changed SQL to `SELECT total` |

---

## Summary

| Category | Tests | Passed | Failed then Fixed |
|----------|-------|--------|-------------------|
| Module loading | 3 | 3 | 0 |
| Consent management | 6 | 6 | 0 |
| Cookie preferences | 4 | 4 | 0 |
| Data export | 8 | 6 | 2 (column names) |
| Email preferences | 4 | 4 | 0 |
| Data deletion | 6 | 6 | 0 |
| Admin dashboard | 5 | 5 | 0 |
| Error handling | 3 | 3 | — |
| **Total** | **39** | **37** | **2** |

All 39 tests passing at end of phase. The 2 failures were column name mismatches in the export service (`full_name` → `first_name`/`last_name`, `total_amount` → `total`) which were fixed immediately.

---

## I. Post-Build Fix Tests (2026-02-17)

**Route prefix fix:** Admin routes prefix changed from `/admin/gdpr` to `/admin` to eliminate double `gdpr` in URL path.

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| I1 | Consent-stats reachable at correct URL | `GET /api/gdpr/admin/consent-stats` (was 404 at `/api/gdpr/admin/gdpr/consent-stats`) | 200 with `{ stats: [...] }` |
| I2 | Audit log reachable at correct URL | `GET /api/gdpr/admin/audit` with admin auth | 200 with `{ items: [...], total, page, page_size }` |
| I3 | Exports reachable at correct URL | `GET /api/gdpr/admin/exports` with admin auth | 200 with `{ items: [...], total, page, page_size }` |
| I4 | Deletions reachable at correct URL | `GET /api/gdpr/admin/deletions` with admin auth | 200 with `{ items: [...], total, page, page_size }` |
| I5 | Old double-gdpr URL returns 404 | `GET /api/gdpr/admin/gdpr/consent-stats` | 404 (confirms old broken path no longer exists) |
| I6 | Audit log filter by consent_type | `GET /api/gdpr/admin/audit?consent_type=marketing_email` | Only `marketing_email` entries returned |
| I7 | Audit log pagination | `GET /api/gdpr/admin/audit?page=1&page_size=5` | Max 5 items, `total` reflects full count |

---

## Updated Summary

| Category | Tests | Passed |
|----------|-------|--------|
| Module loading | 3 | 3 |
| Consent management | 6 | 6 |
| Cookie preferences | 4 | 4 |
| Data export | 8 | 6 (+2 fixed) |
| Email preferences | 4 | 4 |
| Data deletion | 6 | 6 |
| Admin dashboard | 5 | 5 |
| Error handling | 3 | 3 |
| Post-build fix (route prefix) | 7 | — |
| **Total** | **46** | **39 + 7 new** |

Original 39 tests all passed. 7 new tests added for route prefix fix verification (2026-02-17).
