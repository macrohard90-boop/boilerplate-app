# Analytics Module — Business Logic Documentation

> **Module:** `modules/tracking/`
> **Frontend pages:** `frontend/app/admin/analytics/page.tsx` (Overview + User Activity tabs)
> **Frontend tracker:** `frontend/lib/page-duration-tracker.tsx`
> **Backend routes:** `modules/tracking/routes/admin_routes.py`
> **Backend services:** `modules/tracking/services/`
> **Schemas:** `modules/tracking/models/schemas.py`
> **Last validated:** 2026-04-15

This document covers the analytics **Overview tab** and **User Activity tab** on `/admin/analytics`. For the per-user detail page (`/admin/analytics/user/[id]`), see `docs/user-activity-page-logic.md`.

---

## Table of Contents

1. [Data Collection](#1-data-collection)
2. [Overview Tab — Active Sessions Banner](#2-overview-tab--active-sessions-banner)
3. [Overview Tab — Conversion Funnel](#3-overview-tab--conversion-funnel)
4. [Overview Tab — KPI Cards](#4-overview-tab--kpi-cards)
5. [Overview Tab — Traffic Over Time Chart](#5-overview-tab--traffic-over-time-chart)
6. [Overview Tab — Top Pages](#6-overview-tab--top-pages)
7. [Overview Tab — Traffic Sources](#7-overview-tab--traffic-sources)
8. [Overview Tab — Device / Browser / OS](#8-overview-tab--device--browser--os)
9. [Overview Tab — UTM Campaigns & Events](#9-overview-tab--utm-campaigns--events)
10. [User Activity Tab — Enriched User Table](#10-user-activity-tab--enriched-user-table)
11. [Data Fetching Architecture](#11-data-fetching-architecture)
12. [Duration Formatting Rules](#12-duration-formatting-rules)
13. [Known Edge Cases & Gotchas](#13-known-edge-cases--gotchas)
14. [API Endpoints Reference](#14-api-endpoints-reference)
15. [Validation Checklist](#15-validation-checklist)

---

## 1. Data Collection

### How Pageview Records Are Created

**Frontend tracker:** `frontend/lib/page-duration-tracker.tsx` (`PageDurationTracker` component)

Mounted globally in the app layout. Tracks **active browsing time** — time the tab is visible AND user is not idle. Sends `POST /api/tracking/pageview` with:

```json
{ "path": "/some/page", "duration_ms": 45000, "trigger": "navigated", "referrer": "https://google.com" }
```

**Constants:**
| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_DURATION_MS` | 500ms | Pageviews under 500ms are discarded |
| `IDLE_TIMEOUT_MS` | 2 minutes | No interaction → go idle, flush active time |
| `HEARTBEAT_INTERVAL_MS` | 30 seconds | Regular presence pulse to Redis |
| `HEARTBEAT_DEBOUNCE_MS` | 5 seconds | Min gap between heartbeats |

**Triggers:**
| Trigger | When Fired | What `duration_ms` Measures |
|---------|-----------|---------------------------|
| `navigated` | Route change (SPA navigation) | Active time on PREVIOUS page |
| `tab_switch` | Tab goes hidden (`visibilitychange`) | Active time since last flush |
| `idle` | No interaction for 2 minutes | Active time since last flush |
| `closed` | Component unmounts (tab close) | Active time since last flush |

**Key insight:** `duration_ms` is **active time only** — excludes idle periods and hidden-tab time. Multiple records can exist for the same page visit (one per trigger event).

### Referrer / Traffic Source Recording

On the very first pageview of a browser session, the frontend sends `document.referrer`:
- Empty string `""` → classified as `direct / none`
- `https://www.google.com/...` → classified as `google / organic`
- Unknown domain → classified as `{domain} / referral`

This is recorded once per analytics session via `ON CONFLICT (session_id) DO NOTHING`.

**Classification logic:** `modules/tracking/services/referral_service.py` → `parse_referrer()`

Known source mappings:
| Domain Pattern | Source | Medium |
|---------------|--------|--------|
| `google.com`, `google.co` | google | organic |
| `bing.com` | bing | organic |
| `facebook.com`, `fb.com` | facebook | social |
| `twitter.com`, `x.com`, `t.co` | twitter | social |
| `linkedin.com` | linkedin | social |
| `reddit.com` | reddit | social |
| No referrer / empty | direct | none |
| Unknown domain | `{hostname}` | referral |

### Event Recording (Funnel Events)

Events like `add_to_cart` and `checkout_started` are recorded server-side in cart/checkout route handlers.

**Session resolution:** When `X-Session-ID` header is absent but user is authenticated, the backend resolves the most recent analytics session:

```python
# modules/ecommerce/routes/cart_routes.py (line 58)
if settings.enable_tracking and not session_id and user:
    _row = (await db.execute(text(
        "SELECT session_id FROM analytics.analytics_sessions "
        "WHERE user_id = :uid ORDER BY ended_at DESC NULLS FIRST LIMIT 1"
    ), {"uid": user["user_id"]})).mappings().first()
```

This allows funnel events to be recorded without frontend changes.

---

## 2. Overview Tab — Active Sessions Banner

**Component:** `OverviewTab` → Row 1 (line ~423)
**Endpoint:** `GET /api/tracking/admin/analytics/active-sessions`
**Polling:** Every 30 seconds, independent of filter bar

### What It Shows

Real-time table of visitors currently on the site. Top 5 by page duration, with overflow count.

| Column | Source | Calculation |
|--------|--------|-------------|
| **Visitor** | `user_email` from session → users JOIN | Anonymous shows "(anonymous)" |
| **Page** | `current_page` from last pageview in session | Run through `friendlyPageName()` |
| **Status** | Redis presence hash `status` field | Green "Active" / Yellow "Idle ({duration})" / Blue "Session Open" |
| **On Page** | `page_duration_sec` + `tickOffset` | Live tick every 1 second |
| **Session** | `duration_sec` + `tickOffset` | Live tick every 1 second |

### How Active Sessions Are Detected

Backend scans Redis for keys matching `analytics:session:*`, then batch-queries DB for session details + presence hashes.

**Tick counter:** Frontend increments `tickOffset` every 1 second. Resets to 0 when fresh data arrives from polling. This gives a smooth real-time feel without per-second API calls.

---

## 3. Overview Tab — Conversion Funnel

**Component:** `OverviewTab` → Row 2 (line ~506)
**Data sources:** `DashboardSummary.unique_visitors` + `EventStats.by_type`
**Layout:** Full-width card, 3-column grid, blue-to-teal gradient bars

### Funnel Steps

| Step | Source | Count |
|------|--------|-------|
| **Visitors** | `dashboard.unique_visitors.current` | Unique visitors in date range |
| **Add to Cart** | `events.by_type` where `event_type = "add_to_cart"` | Count of add_to_cart events |
| **Checkout** | `events.by_type` where `event_type = "checkout_started"` | Count of checkout_started events |

### Conversion Rate Calculation

Each step shows a percentage relative to the previous step:

```
Add to Cart rate = (add_to_cart count / visitors) × 100
Checkout rate    = (checkout_started count / add_to_cart count) × 100
```

**Empty state:** Shows "No funnel data yet" when `visitors == 0 AND atcCount == 0`.

### Bar Width

Bars scale proportionally to the maximum count:

```
barWidth = max((step.count / maxCount) × 100, 4)
```

The `4` ensures even zero-count steps get a visible sliver.

---

## 4. Overview Tab — KPI Cards

**Component:** `OverviewTab` → Row 3 (line ~561)
**Endpoint:** `GET /api/tracking/admin/analytics/dashboard`
**Layout:** 4-column grid

### Card 1: Total Pageviews

```sql
COUNT(*) FROM analytics.page_views
WHERE created_at >= :ts_from AND created_at < :ts_end
```

Counts every pageview record (including multiple records per page visit due to triggers).

### Card 2: Unique Visitors

```sql
COUNT(DISTINCT COALESCE(CAST(user_id AS text), session_id))
FROM analytics.page_views
WHERE created_at >= :ts_from AND created_at < :ts_end
```

Deduplicates by `user_id` (authenticated) or `session_id` (anonymous).

### Card 3: New vs Returning

**SQL (backend line ~462):**
```sql
WITH user_firsts AS (
  SELECT user_id, MIN(created_at) AS first_visit
  FROM analytics.page_views WHERE user_id IS NOT NULL
  GROUP BY user_id
)
SELECT
  COUNT(DISTINCT CASE WHEN first_visit >= :ts_from AND first_visit < :ts_end THEN user_id END) AS new_visitors,
  COUNT(DISTINCT CASE WHEN first_visit < :ts_from THEN pv.user_id END) AS returning_visitors
FROM user_firsts uf
LEFT JOIN analytics.page_views pv ON pv.user_id = uf.user_id
  AND pv.created_at >= :ts_from AND pv.created_at < :ts_end
```

| Metric | Definition |
|--------|-----------|
| **New** | User whose first-ever pageview (across ALL time) falls within the selected date range |
| **Returning** | User whose first-ever pageview was BEFORE the date range, but who has at least one pageview within the range |

**Important:** Only authenticated users (with `user_id`) are counted. Anonymous visitors are excluded.

**Tooltip:** Hover over `?` icon to see definitions. Tooltip also notes dates are set by the filter bar (default: last 30 days).

### Card 4: Avg Active / Session

```sql
-- Total active time in date range
SELECT COALESCE(SUM(duration_ms), 0) / 1000.0 AS total_active_sec
FROM analytics.page_views WHERE created_at >= :ts_from AND created_at < :ts_end

-- Total sessions in date range
SELECT COUNT(*) AS total_sessions
FROM analytics.analytics_sessions WHERE started_at >= :ts_from AND started_at < :ts_end

-- Result:
avg_active_per_session = total_active_sec / total_sessions
```

Displayed as formatted duration (e.g., "3m 45s", "1.2h").

### Period-Over-Period Comparison (Change Badge)

Each KPI shows a change percentage badge (green ↑ or red ↓).

**Calculation (backend line ~494):**
```python
period_length = ts_end - ts_from            # e.g., 30 days
previous_start = ts_from - period_length    # e.g., 30 days before ts_from
previous_end = ts_from

# Same KPI queries run for both current and previous period
change_pct = ((current - previous) / previous) × 100
# If previous == 0 and current > 0: change_pct = 100
# If previous == 0 and current == 0: change_pct = null (shows "-")
```

---

## 5. Overview Tab — Traffic Over Time Chart

**Component:** `OverviewTab` → Row 4 (line ~587)
**Endpoint:** `GET /api/tracking/admin/analytics/pageviews/timeseries`
**Chart:** `AreaSparkChart` with 3 lines (left Y-axis: Pageviews + Unique Visitors, right Y-axis: Engagement %)

### Granularity Selector

Pills: `Hourly | Daily | Weekly | Monthly | Yearly`

Each granularity has its own **lookback window** (independent of the filter bar date range) and **bucket size**:

| Granularity | Lookback Window | Bucket Size | ~Data Points |
|-------------|----------------|-------------|-------------|
| Hourly | Last 60 minutes | 1 minute | ~60 |
| Daily | Last 24 hours | 30 minutes | ~48 |
| Weekly | Last 7 days | 3 hours | ~56 |
| Monthly | Last 30 days | 12 hours | ~60 |
| Yearly | Last 365 days | 1 week | ~52 |

### Bucketing Method (Epoch-Based)

**Backend (line ~531):**
```python
bucket_secs_map = {"hour": 60, "day": 1800, "week": 10800, "month": 43200, "year": 604800}
trunc = f"TO_TIMESTAMP(FLOOR(EXTRACT(EPOCH FROM pv.created_at) / {bsec}) * {bsec})"
```

This creates fixed-width time buckets by truncating timestamps to the nearest bucket boundary using epoch arithmetic. More flexible than `date_trunc()` which only supports standard intervals.

### Pageviews Per Bucket

```sql
SELECT bucket, COUNT(*) AS pageviews
FROM analytics.page_views pv
WHERE created_at >= :ts_from AND created_at < :ts_end
GROUP BY bucket
```

### Unique Visitors Per Bucket

```sql
COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors
```

Same deduplication logic as the KPI card, applied per bucket.

### Engagement % Per Bucket — 3-Level Averaging

This is the most complex calculation. Engagement is computed bottom-up: **session → user → bucket**.

**Step 1 — Per-session active time in each bucket:**
```sql
-- CTE: pv_sess
SELECT bucket, session_id, user_id,
       SUM(COALESCE(duration_ms, 0)) / 1000.0 AS active_sec
FROM analytics.page_views
GROUP BY bucket, session_id, user_id
```

**Step 2 — Wall-time overlap for each session in each bucket:**
```sql
-- CTE: sess_wall
SELECT bucket, session_id, uid, active_sec,
  GREATEST(0, EXTRACT(EPOCH FROM (
    LEAST(COALESCE(s.ended_at, CURRENT_TIMESTAMP), bucket_end)
    - GREATEST(s.started_at, bucket_start)
  ))) AS wall_sec
FROM pv_sess ps
JOIN analytics.analytics_sessions s ON s.session_id = ps.session_id
```

The wall-time overlap is `min(session_end, bucket_end) - max(session_start, bucket_start)`. This correctly handles sessions that span multiple buckets — only the portion within this specific bucket counts.

For active sessions (`ended_at IS NULL`), `CURRENT_TIMESTAMP` is used as the session end.

**Step 3 — Per-session engagement, capped at 100%:**
```sql
-- CTE: sess_eng
CASE WHEN wall_sec > 0
  THEN LEAST(active_sec / wall_sec * 100, 100)
  ELSE NULL
END AS eng
```

**Step 4 — Average sessions per user per bucket:**
```sql
-- CTE: user_eng
SELECT bucket, uid, AVG(eng) AS eng
FROM sess_eng WHERE eng IS NOT NULL
GROUP BY bucket, uid
```

If a user has multiple sessions in the same bucket (e.g., two sessions in the same 30-minute window), their session engagements are averaged first.

**Step 5 — Average users per bucket:**
```sql
-- CTE: bucket_eng
SELECT bucket, ROUND(AVG(eng)::numeric, 1) AS engagement_pct
FROM user_eng
GROUP BY bucket
```

### Why This Matters

The old calculation was `SUM(all duration_ms) / SUM(all session wall time)` — a global ratio that didn't respect per-user or per-session boundaries. A single long idle session would drag down the engagement for all users.

The new calculation ensures:
- A user with 90% engagement on one session and 50% on another gets 70% (not a skewed global ratio)
- Each user's engagement is weighted equally in the bucket average
- Sessions that span multiple buckets only contribute their proportional wall time per bucket

---

## 6. Overview Tab — Top Pages

**Component:** `OverviewTab` → Row 5, left (line ~623)
**Endpoint:** `GET /api/tracking/admin/analytics/pages/engagement`
**Layout:** Table, top 10 pages

### Columns

| Column | Calculation |
|--------|-------------|
| **Page** | `path` run through `friendlyPageName()` (capitalize, replace `/` with ` / `) |
| **Views** | `COUNT(*)` of pageview records for this path |
| **Avg Duration** | `AVG(duration_ms)` across all pageview records for this path |
| **Bounce Rate** | `bounce_count / entry_count × 100` (per-page) |

### Bounce Rate Calculation

**Backend (line ~724):**
```sql
WITH entry_pages AS (
  -- First page visited in each session
  SELECT session_id, MIN(path) AS entry_path
  FROM analytics.page_views
  WHERE created_at = (SELECT MIN(created_at) FROM page_views WHERE same session)
  GROUP BY session_id
),
bounced_sessions AS (
  -- Sessions with exactly 1 page
  SELECT session_id FROM analytics.analytics_sessions WHERE page_count = 1
)

-- Per page:
entry_count  = sessions where this page was the entry page
bounce_count = sessions where this page was the entry page AND session had only 1 page
bounce_rate  = bounce_count / entry_count × 100
```

**Visual indicators:**
- Avg duration < 5 seconds → amber text (warning)
- Bounce rate > 60% → red text (warning)

---

## 7. Overview Tab — Traffic Sources

**Component:** `OverviewTab` → Row 5, right (line ~666)
**Endpoint:** `GET /api/tracking/admin/analytics/sources`
**Layout:** Breakdown bar chart, top 8 sources

### How Sources Are Counted

```sql
SELECT rs.source, rs.medium, COUNT(*) AS sessions
FROM analytics.referral_sources rs
JOIN analytics.analytics_sessions s ON rs.session_id = s.session_id
WHERE s.started_at >= :ts_from AND s.started_at < :ts_end
GROUP BY rs.source, rs.medium
ORDER BY sessions DESC
```

Each source shows `{Source} / {medium}` (e.g., "Google / organic", "Direct"). The medium "none" is hidden from display.

### How Data Gets Into `referral_sources`

1. Frontend sends `document.referrer` on first pageview → `POST /api/tracking/pageview`
2. Backend `record_pageview` handler calls `referral_service.parse_referrer(referrer)`
3. Result inserted with `ON CONFLICT (session_id) DO NOTHING` (one source per session)

---

## 8. Overview Tab — Device / Browser / OS

**Component:** `OverviewTab` → Row 6 (line ~679)
**Endpoint:** `GET /api/tracking/admin/analytics/devices`
**Layout:** Single combined card with 3 sections (purple/blue/green bars)

### Independent Time Range

This card has its own time range selector, independent of the main filter bar:

| Pill | Lookback |
|------|----------|
| Last Hour | 60 minutes |
| Last 24h | 24 hours |
| 7 Days | 7 days |
| 30 Days | 30 days |
| Yearly | 365 days |

Default: **Last Hour**.

### Data Source (Backend)

```sql
SELECT ua.device_type, COUNT(*) AS count,
       SUM(pv_dur.total_ms) AS total_duration_ms
FROM analytics.user_agents ua
JOIN analytics.analytics_sessions s ON ua.session_id = s.session_id
LEFT JOIN (
  SELECT session_id, SUM(duration_ms) AS total_ms
  FROM analytics.page_views GROUP BY session_id
) pv_dur ON pv_dur.session_id = s.session_id
WHERE s.started_at >= :ts_from AND s.started_at < :ts_end
GROUP BY ua.device_type
```

Same pattern for `browser` and `os` fields.

### Display

Each item shows:
- Name (colored by section: purple for devices, blue for browsers, green for OS)
- Count + percentage of total + formatted duration
- Proportional bar

---

## 9. Overview Tab — UTM Campaigns & Events

**Component:** `OverviewTab` → Row 7 (line ~779)
**Layout:** 2-column grid, breakdown bars

### UTM Campaigns

**Endpoint:** `GET /api/tracking/admin/analytics/utm`

```sql
SELECT utm_source, utm_medium, utm_campaign, COUNT(*) AS sessions
FROM analytics.utm_tracking u
JOIN analytics.analytics_sessions s ON u.session_id = s.session_id
WHERE s.started_at >= :ts_from AND s.started_at < :ts_end
GROUP BY utm_source, utm_medium, utm_campaign
ORDER BY sessions DESC
```

Labels show `utm_campaign || utm_source || "Unknown"`.

### Events

**Endpoint:** `GET /api/tracking/admin/analytics/events`

```sql
SELECT event_type, COUNT(*) AS count
FROM analytics.events
WHERE created_at >= :ts_from AND created_at < :ts_end
GROUP BY event_type
ORDER BY count DESC
```

Currently recorded event types: `add_to_cart`, `checkout_started`.

---

## 10. User Activity Tab — Enriched User Table

**Component:** `UserActivityTab` (line ~815)
**Endpoint:** `GET /api/tracking/admin/analytics/users/enriched`

### Table Columns

| Column | Source | Calculation |
|--------|--------|-------------|
| **Email** | `core.users.email` | Green pulsing dot if user has active Redis session |
| **Last Active** | `MAX(pv.created_at)` | Displayed as relative time ("3h ago") |
| **Sessions** | `COUNT(DISTINCT s.session_id)` | Within date range |
| **Active Time** | `SUM(pv.duration_ms) / 1000` | Total active browsing time in date range |
| **Engagement %** | See below | Color-coded: ≥60% green, ≥30% yellow, <30% red |
| **Top Page** | Most visited path (all time) | Via correlated subquery |

### Engagement % Per User (User Activity Tab)

```sql
-- Total active time (from pageviews)
total_active_sec = SUM(pv.duration_ms) / 1000.0
  WHERE pv.user_id = u.id AND pv.created_at IN date range

-- Total wall time (from sessions)
total_wall_sec = SUM(EXTRACT(EPOCH FROM (s.ended_at - s.started_at)))
  WHERE s.user_id = u.id AND s.started_at IN date range

-- Engagement
engagement_pct = LEAST(total_active_sec / total_wall_sec * 100, 100)
```

**Note:** This is a simpler calculation than the timeseries engagement. It divides total active time by total wall time for the entire date range — no per-session or per-bucket averaging. This is appropriate for a per-user summary.

### Segment Filters

| Segment | SQL Condition |
|---------|--------------|
| All | No additional filter |
| Active Today | `HAVING MAX(pv.created_at) >= NOW() - 1 day` |
| Active This Week | `HAVING MAX(pv.created_at) >= NOW() - 7 days` |
| Inactive (7+ days) | `HAVING MAX(pv.created_at) < NOW() - 7 days` |

### Sortable Columns

| Sort Key | SQL Column |
|----------|-----------|
| `last_active` | `MAX(pv.created_at)` |
| `pageviews` | `COUNT(DISTINCT pv.id)` |
| `sessions` | `COUNT(DISTINCT s.session_id)` |
| `active_time` | `total_active_sec` |
| `engagement` | `engagement_pct` |

### Live Detection

Backend scans all `analytics:session:*` Redis keys, queries which `user_id`s own those sessions, returns `is_live: true` for matches. Frontend shows animated green dot.

### Search

Debounced (300ms) email search: `WHERE u.email ILIKE '%query%'`.

---

## 11. Data Fetching Architecture

### Overview Tab — Fetch Strategy

The Overview tab uses a split-fetch architecture to avoid unnecessary re-renders:

```
Main effect [fetchKey, buildQS]
  └─ Fetches: dashboard, engagement, sources, utm, events
  └─ Also triggers: fetchTimeseriesFor(granularity), fetchDevicesFor(deviceRange)

Timeseries effect [granularity, excludeBots]
  └─ Only refetches timeseries

Device effect [deviceRange, excludeBots]
  └─ Only refetches devices

Active sessions poll [every 30s, independent]
  └─ Fetches active-sessions
```

**Why split?** Changing granularity pills should only refetch the chart, not all 9 endpoints. Changing device range pills should only refetch devices. This was redesigned after a cascade bug where changing any pill triggered all fetches → 429 rate limiting.

**Stable fetch helpers:** `fetchTimeseriesFor(g, bots)` and `fetchDevicesFor(range, bots)` take params as arguments (not captured in `useCallback` closures). This gives them a stable function identity, preventing effect cascades.

### Rate Limiting Exemption

Admin analytics routes are exempt from rate limiting:

```python
# backend/core/middleware.py
_EXEMPT_PREFIXES = ("/api/tracking/admin/",)
```

This prevents 429 errors when rapidly switching between pills/filters.

---

## 12. Duration Formatting Rules

### `formatDurationSec(sec)` — for second values

| Range | Format | Example |
|-------|--------|---------|
| `null` or `≤ 0` | `"-"` | - |
| `< 60s` | `"{X}s"` | 45s |
| `< 60m` | `"{X}m {Y}s"` | 3m 45s |
| `< 24h` | `"{X.X}h"` | 1.2h |
| `≥ 24h` | `"{X.X}d"` | 2.3d |

### `formatDurationMs(ms)` — for millisecond values

Delegates to `formatDurationSec(ms / 1000)`.

### `relativeTime(iso)` — for timestamps

| Range | Format | Example |
|-------|--------|---------|
| `< 1m` | "just now" | just now |
| `< 60m` | `"{X}m ago"` | 5m ago |
| `< 24h` | `"{X}h ago"` | 3h ago |
| `≥ 24h` | `"{X}d ago"` | 7d ago |

### `friendlyPageName(path)` — for page paths

Strips leading `/`, capitalizes each segment, joins with ` / `.
- `/admin/analytics` → "Admin / Analytics"
- `/` → "Home"

---

## 13. Known Edge Cases & Gotchas

1. **`duration_ms` is NOT wall-clock time** — It's active browsing time only. A user on a page for 5 minutes but idle for 3 of them will have ~2 minutes of `duration_ms` across multiple pageview records.

2. **Multiple pageview records per page visit** — Each trigger (navigated, tab_switch, idle, closed) creates a separate record. The `SUM(duration_ms)` for a page visit spans all its trigger records.

3. **Engagement can theoretically exceed 100%** — If `duration_ms` sums exceed wall time due to timing race conditions (async POSTs). Capped with `LEAST(..., 100)` in all SQL queries.

4. **Sessions with no `ended_at`** — Old sessions where the tracker didn't fire a final update. The timeseries engagement query uses `COALESCE(ended_at, CURRENT_TIMESTAMP)` to handle this.

5. **Referrer sent only once per browser session** — The `initialReferrerSent` module-level flag in `page-duration-tracker.tsx` ensures `document.referrer` is sent only on the first pageview POST. Subsequent pageviews don't include it.

6. **Traffic sources require analytics sessions** — Sources are stored per-session in `analytics.referral_sources`. If a session has no referral record (from before this feature was added), it won't appear in traffic source stats.

7. **Conversion funnel events require session resolution** — Cart/checkout events need a `session_id`. When the frontend doesn't send `X-Session-ID`, the backend resolves it from the user's most recent analytics session. If no session exists, the event is silently skipped.

8. **Bot filtering** — All queries support `exclude_bots` parameter. Bots are detected by `device_type = 'bot'` in `analytics.user_agents`. Filter uses `session_id NOT IN (SELECT session_id FROM user_agents WHERE device_type = 'bot')`.

9. **Timeseries lookback is independent of filter bar** — The granularity pills compute their own date range (e.g., "last 60 minutes" for hourly). This is separate from the filter bar's date range which affects KPIs, funnel, sources, etc.

10. **Device card lookback is also independent** — The device time range pills have their own lookback window, separate from both the filter bar and the timeseries granularity.

11. **New vs Returning only counts authenticated users** — Anonymous visitors (no `user_id`) are excluded. This is by design — you can't track a "returning" visitor without a persistent identifier.

12. **`ended_at` is updated on every heartbeat/pageview** — It means "last activity timestamp", not "session ended at". Active sessions are detected via Redis key existence, not `ended_at IS NULL`.

---

## 14. API Endpoints Reference

### Overview Tab

| Endpoint | When Called | Returns |
|----------|-----------|---------|
| `GET /tracking/admin/analytics/dashboard` | Filter apply/reset | `DashboardSummary` — KPI metrics with period comparison |
| `GET /tracking/admin/analytics/pageviews/timeseries` | Granularity change or filter apply | `PageviewTimeSeries` — bucketed pageviews, visitors, engagement |
| `GET /tracking/admin/analytics/active-sessions` | Every 30s (poll) | `ActiveSessionsResponse` — live visitors from Redis |
| `GET /tracking/admin/analytics/pages/engagement` | Filter apply/reset | `PagesEngagementResponse` — top pages with bounce rate |
| `GET /tracking/admin/analytics/sources` | Filter apply/reset | `SourceStats` — traffic source breakdown |
| `GET /tracking/admin/analytics/utm` | Filter apply/reset | `UTMStats` — UTM campaign performance |
| `GET /tracking/admin/analytics/devices` | Device range change or filter apply | `DeviceStats` — device/browser/OS breakdown |
| `GET /tracking/admin/analytics/events` | Filter apply/reset | `EventStats` — event counts by type |

### User Activity Tab

| Endpoint | When Called | Returns |
|----------|-----------|---------|
| `GET /tracking/admin/analytics/users/enriched` | Filter apply/reset, search, segment/sort change | `EnrichedUserList` — user table with engagement scoring |

### Common Query Parameters

| Parameter | Type | Default | Used By |
|-----------|------|---------|---------|
| `date_from` | ISO datetime | 30 days ago | All endpoints |
| `date_to` | ISO datetime | Now | All endpoints |
| `exclude_bots` | boolean | `true` | All endpoints |
| `granularity` | `hour\|day\|week\|month\|year` | `day` | Timeseries only |
| `user_id` | UUID string | None | Sources, UTM, Events, Devices |
| `q` | string | `""` | Enriched users (email search) |
| `segment` | `all\|active_today\|active_week\|inactive` | `all` | Enriched users |
| `sort_by` | `last_active\|pageviews\|sessions\|active_time\|engagement` | `last_active` | Enriched users |
| `sort_dir` | `asc\|desc` | `desc` | Enriched users |

---

## 15. Validation Checklist

When modifying the analytics module, verify:

### Overview Tab
- [ ] Active sessions banner polls every 30s, tick counter increments every 1s
- [ ] Conversion funnel pulls from events table (not hardcoded), shows correct step-to-step percentages
- [ ] KPI change badges compare current period to previous period of same length
- [ ] Timeseries chart shows ~50-60 data points per granularity level
- [ ] Engagement line stays ≤ 100% (3-level averaging: session → user → bucket)
- [ ] Granularity pills only refetch timeseries, not all endpoints
- [ ] Device pills only refetch devices, not all endpoints
- [ ] No 429 errors when rapidly clicking pills (admin routes exempt from rate limiting)
- [ ] Traffic sources show "Direct" for typed-in URLs (not empty)
- [ ] New vs Returning tooltip explains calculation and mentions filter-bar date range

### User Activity Tab
- [ ] Search debounces at 300ms
- [ ] Segment filters work: All, Active Today, Active This Week, Inactive (7+ days)
- [ ] All columns sortable (click toggles asc/desc)
- [ ] Live dot appears for users with active Redis sessions
- [ ] Engagement % color-coded: ≥60% green, ≥30% yellow, <30% red
- [ ] Top Page column not truncated too aggressively (max-w-[200px])

### Cross-Cutting
- [ ] Bot exclusion works across all endpoints
- [ ] Duration formatting follows rules (no raw milliseconds, no "465m" — use "7.8h")
- [ ] No `datetime.utcnow()` in backend — use `datetime.now(timezone.utc)`
- [ ] All new endpoints added inside conditional tracking route registration
