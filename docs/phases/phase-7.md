# Phase 7: GDPR & Cookie Management

**Estimate:** 4-5 hours
**Depends on:** Phase 3, Phase 6
**Category:** Privacy & compliance

## Goal
Build the GDPR compliance module: consent management with granular consent types, cookie preference UI data layer, data export (right of access), data deletion (right to erasure) with grace period, email preference management, and the consent audit log. At the end of this phase, the application is GDPR-compliant for EU users with full consent tracking and data subject rights.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 1.6 (EmailProvider interface), 2.4 (GDPR Schema), and 5 (Middleware Chain — GDPR Consent step) for the GDPR specification.

## Deliverables

1. **Consent management** (modules/gdpr/services/ + routes/):
   - `GET /api/gdpr/consent` — current consent state for authenticated user
   - `POST /api/gdpr/consent` — grant or revoke consent for specific types
   - `GET /api/gdpr/consent/history` — consent change history for user
   - Consent types taxonomy: `marketing_email`, `transactional_email`, `third_party_sharing`, `analytics`, `cookies_analytics`, `cookies_marketing`
   - Version tracking: each consent record includes version number
   - IP address logged with each consent change
   - Consent audit log: every grant/revoke recorded in `consent_audit_log`

2. **Cookie preference management** (modules/gdpr/services/ + routes/):
   - `GET /api/gdpr/cookies` — current cookie preferences (auth or session-based)
   - `POST /api/gdpr/cookies` — update preferences (necessary always true)
   - Cookie categories: necessary (always on), analytics, marketing, preferences
   - Guest support: preferences stored by session_id (no user_id required)
   - Preferences persisted in `cookie_preferences` table
   - Frontend cookie banner data layer (API provides state, frontend renders)

3. **Data export (Right of Access)** (modules/gdpr/services/ + routes/):
   - `POST /api/gdpr/export` — request data export
   - `GET /api/gdpr/export/{id}` — check export status / download
   - Background job: collect all user data across schemas (users, orders, consent, analytics, etc.)
   - Export format: JSON (machine-readable) — include all personal data
   - File generation: create downloadable file, store URL in `data_export_requests`
   - Expiry: export files expire after configurable period (default 7 days)
   - Status flow: pending → processing → completed → expired
   - Rate limit: max 1 export request per 24 hours per user

4. **Data deletion (Right to Erasure)** (modules/gdpr/services/ + routes/):
   - `POST /api/gdpr/deletion` — request account deletion
   - `GET /api/gdpr/deletion/{id}` — check deletion status
   - `POST /api/gdpr/deletion/{id}/cancel` — cancel during grace period
   - Grace period: configurable (default 30 days) before permanent deletion
   - Deletion process:
     1. Mark user as pending deletion
     2. Immediately: revoke all sessions, disable login
     3. After grace period: anonymize personal data (email, name, addresses)
     4. Retain order history with anonymized references (legal/tax requirement)
     5. Delete analytics data, consent records, session history
     6. Mark as completed
   - Status flow: pending → grace_period → processing → completed (or cancelled)

5. **Email preference management** (modules/gdpr/services/ + routes/):
   - `GET /api/gdpr/email-preferences` — current email preferences for user
   - `PUT /api/gdpr/email-preferences` — update preferences (marketing_email, transactional_email booleans)
   - `POST /api/gdpr/email-preferences/unsubscribe` — one-click unsubscribe (from email link)
   - Suppression list management: track `suppressed_at` and `suppression_reason`
   - Sync to email provider: when preferences change, call `EmailProvider.sync_suppression()`
   - Email preferences are the app-side source of truth (provider syncs from here)
   - Checked before every email send (see notifications module consent flow)

6. **Consent audit log** (modules/gdpr/services/):
   - Record every consent change: user_id, action (grant/revoke), consent_type, old_value, new_value, ip_address
   - Immutable: no updates or deletes on audit records
   - Queryable by admin for compliance reporting
   - `GET /api/admin/gdpr/audit` — admin endpoint for consent audit trail

7. **GDPR middleware integration** (modules/gdpr/services/):
   - Middleware step in request pipeline: check consent before tracking/analytics
   - If analytics consent not granted → skip tracking middleware
   - If marketing cookies not consented → don't set marketing cookies
   - Consent state available in request context for downstream handlers

8. **Abandoned cart consent integration** (modules/gdpr/services/):
   - Before sending abandoned cart reminders: check `email_preferences.marketing_email` consent
   - Before collecting cart analytics: check `consent_records` for `analytics` consent
   - Email events logged with consent snapshot at send time (proves consent existed)

9. **Admin GDPR dashboard endpoints** (modules/gdpr/routes/):
   - `GET /api/admin/gdpr/exports` — list all export requests (paginated, filterable)
   - `GET /api/admin/gdpr/deletions` — list all deletion requests (paginated, filterable)
   - `GET /api/admin/gdpr/consent-stats` — consent grant/revoke rates by type
   - `GET /api/admin/gdpr/audit` — consent audit log (paginated, filterable by user, type, date)

## Acceptance Criteria
- [ ] Consent types match taxonomy: marketing_email, transactional_email, third_party_sharing, analytics, cookies_analytics, cookies_marketing
- [ ] Consent grant/revoke creates audit log entry
- [ ] Cookie preferences work for both authenticated and guest users
- [ ] Data export collects all personal data across schemas
- [ ] Data export file expires after configured period
- [ ] Export rate limited to 1 per 24 hours per user
- [ ] Deletion request has configurable grace period
- [ ] Deletion can be cancelled during grace period
- [ ] After grace period, personal data is anonymized (not hard-deleted for legal retention)
- [ ] All sessions revoked immediately on deletion request
- [ ] Email preferences sync to email provider on change
- [ ] Email preference suppression blocks all email delivery
- [ ] One-click unsubscribe endpoint works from email links
- [ ] GDPR middleware blocks tracking when analytics consent not granted
- [ ] Abandoned cart reminders check marketing_email consent before sending
- [ ] Admin endpoints require admin role
- [ ] Consent audit log is immutable (append-only)

## Implementation Notes
- Deletion is anonymization, not hard delete: replace personal data with `[DELETED]` or hash, keep order records for tax/legal
- Data export background job: use FastAPI BackgroundTasks or a simple async task
- Email preference changes trigger `EmailProvider.sync_suppression()` — fire-and-forget
- One-click unsubscribe: use signed URL token (no login required, RFC 8058 compliant)
- Cookie preferences for guests: keyed by session_id, migrate to user_id on login
- Grace period countdown: background job or on-demand check (check if `grace_period_ends < NOW()`)
- Data retention: analytics data deleted on erasure request, audit logs retained (legal basis: legitimate interest)

## Files to Create
- `modules/gdpr/services/consent_service.py` — Consent management, audit logging
- `modules/gdpr/services/cookie_service.py` — Cookie preference management
- `modules/gdpr/services/export_service.py` — Data export request processing
- `modules/gdpr/services/deletion_service.py` — Data deletion with grace period
- `modules/gdpr/services/email_pref_service.py` — Email preference management, suppression
- `modules/gdpr/services/gdpr_middleware.py` — Consent checking middleware
- `modules/gdpr/models/schemas.py` — Pydantic request/response models
- `modules/gdpr/routes/consent_routes.py` — Consent and cookie endpoints
- `modules/gdpr/routes/export_routes.py` — Data export endpoints
- `modules/gdpr/routes/deletion_routes.py` — Data deletion endpoints
- `modules/gdpr/routes/email_pref_routes.py` — Email preference endpoints
- `modules/gdpr/routes/admin_routes.py` — Admin GDPR dashboard endpoints
- `modules/gdpr/config.py` — GDPR module configuration (grace period, export expiry)
- Modified: `backend/main.py` — Mount GDPR routes, register middleware
- Modified: `backend/core/middleware.py` — Add GDPR consent check step
