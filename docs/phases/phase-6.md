# Phase 6: User Tracking & Analytics

**Estimate:** 3-4 hours
**Depends on:** Phase 3
**Category:** Data & insights

## Goal
Build the server-side analytics module: page view tracking, session management, event capture, UTM parameter tracking, user agent parsing, and geo lookup via the GeoProvider interface. At the end of this phase, all user interactions are tracked in the analytics schema and queryable via admin API endpoints.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 1.3 (GeoProvider interface), 2.5 (Analytics Schema), 4 (Redis Key Architecture), and 10 (Environment Variables — ENABLE_TRACKING) for the analytics specification.

## Deliverables

1. **Page view tracking** (modules/tracking/services/):
   - Record page views: user_id (nullable for anonymous), session_id, path, referrer, duration_ms
   - Server-side collection via API endpoint: `POST /api/tracking/pageview`
   - Batch insert support for buffered client-side events
   - Respect `ENABLE_TRACKING` toggle — skip collection if disabled
   - GDPR guard: check `consent_records` for `analytics` consent before recording

2. **Analytics session management** (modules/tracking/services/):
   - Create `analytics_sessions` record on first page view
   - Session identification: use session_id from auth or generate anonymous session_id
   - Track: started_at, ended_at, page_count
   - Session timeout: configurable inactivity period
   - Link to user_id when authenticated (nullable for anonymous visitors)

3. **Event tracking** (modules/tracking/services/):
   - Generic event capture: `POST /api/tracking/events`
   - Event types: custom string (e.g., `add_to_cart`, `checkout_started`, `search`, `product_view`)
   - Event data: JSONB payload (flexible schema per event type)
   - Batch event submission for efficiency

4. **UTM parameter tracking** (modules/tracking/services/):
   - Capture UTM parameters from inbound URLs: source, medium, campaign, content, term
   - Store in `utm_tracking` table linked to analytics session
   - Referral source extraction: parse referrer URL into source and medium

5. **User agent parsing** (modules/tracking/services/):
   - Parse User-Agent header: browser, browser_version, OS, device_type
   - Store in `user_agents` table linked to session
   - AgentParser interface (placeholder): allows swapping parsing library
   - Default implementation: `user-agents` Python package or regex-based

6. **GeoProvider interface + placeholder** (modules/tracking/interfaces/ + adapters/):
   - GeoProvider ABC: `async def lookup(ip_address) -> GeoResult`
   - GeoResult: country, city, region, latitude, longitude
   - Placeholder adapter: returns "Unknown" for all fields (no external API call)
   - Ready for MaxMind GeoIP2 or similar integration

7. **Referral source tracking** (modules/tracking/services/):
   - Parse referrer URLs into source and medium categories
   - Known sources: google, facebook, twitter, linkedin, direct, email, etc.
   - Store in `referral_sources` table linked to session

8. **Admin analytics endpoints** (modules/tracking/routes/):
   - `GET /api/admin/analytics/pageviews` — page view stats (date range, top pages, unique visitors)
   - `GET /api/admin/analytics/sessions` — session stats (count, avg duration, bounce rate)
   - `GET /api/admin/analytics/events` — event counts by type (date range)
   - `GET /api/admin/analytics/sources` — traffic sources breakdown
   - `GET /api/admin/analytics/utm` — UTM campaign performance
   - All admin endpoints require `admin` role
   - Support date range filtering, pagination

9. **Tracking middleware** (modules/tracking/services/):
   - Automatic page view recording for all requests (configurable path exclusions)
   - Extract and store UTM parameters from query string
   - Parse and store user agent on session creation
   - Non-blocking: use background tasks to avoid adding latency to requests

10. **Data retention comments** (migrations/):
    - `-- RETENTION: consider archival policy for rows older than N months` on analytics_sessions, events, page_views
    - `-- FUTURE: range partition on created_at (monthly)` on high-volume tables

## Acceptance Criteria
- [x] Page views recorded with path, referrer, duration, user/session link
- [x] Analytics sessions created and updated (started_at, ended_at, page_count)
- [x] Custom events captured with JSONB payload
- [x] UTM parameters extracted and stored per session
- [x] User agent parsed into browser, OS, device_type
- [x] GeoProvider interface defined with placeholder implementation
- [x] Referral sources categorized from referrer URLs
- [x] Admin analytics endpoints return aggregated data with date filtering
- [x] ENABLE_TRACKING=false disables all data collection
- [x] GDPR consent check: analytics data only collected if user consented
- [x] Tracking is non-blocking (background tasks, no request latency impact)
- [x] Anonymous visitors tracked with session_id (no user_id required)
- [x] All tracking endpoints return consistent error format

## Implementation Notes
- Non-blocking tracking: use FastAPI `BackgroundTasks` or asyncio fire-and-forget
- GDPR check flow: if user authenticated → check consent_records for analytics consent; if anonymous → check cookie_preferences
- Analytics schema is optional: guarded by `ENABLE_TRACKING` env var (migrations skip if false)
- High-volume tables (page_views, events): partition-ready comments in place, actual partitioning deferred
- User agent parsing: `user-agents` pip package or lightweight regex — avoid heavy dependencies
- Session timeout: 30 minutes of inactivity (configurable)
- Batch inserts: accept array of events in single POST for client-side batching

## Files to Create
- `modules/tracking/interfaces/geo_provider.py` — GeoProvider ABC + GeoResult model
- `modules/tracking/interfaces/agent_parser.py` — AgentParser interface
- `modules/tracking/adapters/placeholder_geo.py` — Placeholder geo implementation
- `modules/tracking/adapters/default_agent_parser.py` — User agent parser implementation
- `modules/tracking/services/pageview_service.py` — Page view recording and querying
- `modules/tracking/services/session_service.py` — Analytics session management
- `modules/tracking/services/event_service.py` — Custom event capture
- `modules/tracking/services/utm_service.py` — UTM parameter extraction and storage
- `modules/tracking/services/referral_service.py` — Referral source parsing
- `modules/tracking/services/tracking_middleware.py` — Auto-tracking middleware
- `modules/tracking/models/schemas.py` — Pydantic request/response models
- `modules/tracking/routes/tracking_routes.py` — Page view, event collection endpoints
- `modules/tracking/routes/admin_routes.py` — Admin analytics endpoints
- `modules/tracking/config.py` — Tracking module configuration
- Modified: `backend/main.py` — Register TrackingMiddleware
- Modified: `backend/core/config.py` — Added tracking_session_timeout, geo_provider, tracking_exclude_paths

## Post-Build Fix (2026-02-17)

**Device/browser analytics endpoint added:**
- New `GET /api/tracking/admin/analytics/devices` endpoint — queries `analytics.user_agents` joined to `analytics.analytics_sessions` for date-range filtering, returns 3 breakdowns: device type, browser (top 10), OS (top 10)
- New Pydantic schemas: `DeviceStats`, `DeviceTypeStat`, `BrowserStat`, `OSStat` in `modules/tracking/models/schemas.py`
- The `user_agents` table was already populated by the tracking middleware but had no admin query endpoint

**Files modified:**
- `modules/tracking/routes/admin_routes.py` — added `/devices` endpoint
- `modules/tracking/models/schemas.py` — added 4 new response models

## Files Created
- `modules/tracking/__init__.py`
- `modules/tracking/config.py`
- `modules/tracking/interfaces/__init__.py`
- `modules/tracking/interfaces/geo_provider.py`
- `modules/tracking/interfaces/agent_parser.py`
- `modules/tracking/adapters/__init__.py`
- `modules/tracking/adapters/placeholder_geo.py`
- `modules/tracking/adapters/default_agent_parser.py`
- `modules/tracking/models/__init__.py`
- `modules/tracking/models/schemas.py`
- `modules/tracking/services/__init__.py`
- `modules/tracking/services/consent_service.py`
- `modules/tracking/services/session_service.py`
- `modules/tracking/services/pageview_service.py`
- `modules/tracking/services/event_service.py`
- `modules/tracking/services/utm_service.py`
- `modules/tracking/services/referral_service.py`
- `modules/tracking/services/agent_service.py`
- `modules/tracking/services/tracking_middleware.py`
- `modules/tracking/routes/__init__.py`
- `modules/tracking/routes/tracking_routes.py`
- `modules/tracking/routes/admin_routes.py`
