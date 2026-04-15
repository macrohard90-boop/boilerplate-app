# User Activity Page — Business Logic Documentation

> **Page:** `/admin/analytics/user/[id]`
> **Frontend:** `frontend/app/admin/analytics/user/[id]/page.tsx`
> **Backend endpoint:** `GET /api/tracking/admin/analytics/user/{user_id}/activity`
> **Backend file:** `modules/tracking/routes/admin_routes.py` (line ~899)
> **Schema:** `modules/tracking/models/schemas.py` → `UserActivity` class
> **Last validated:** 2026-04-14
>
> **See also:** `docs/analytics-module-logic.md` — Overview tab, User Activity tab, and data collection docs

---

## 1. Data Collection — How Tracking Data Gets Created

### Frontend Duration Tracker (`frontend/lib/page-duration-tracker.tsx`)

The `PageDurationTracker` component runs globally (mounted in layout). It tracks **active browsing time** — the time the user's tab is visible AND the user is not idle.

**Constants:**
- `MIN_DURATION_MS = 500` — pageviews under 500ms are discarded
- `IDLE_TIMEOUT_MS = 2 * 60 * 1000` (2 minutes) — no interaction → go idle
- `HEARTBEAT_INTERVAL_MS = 30 * 1000` (30 seconds) — regular presence pulse
- `HEARTBEAT_DEBOUNCE_MS = 5 * 1000` (5 seconds) — min gap between heartbeats

**Triggers (when a pageview record is created):**
| Trigger | When | What `duration_ms` means |
|---------|------|--------------------------|
| `navigated` | User navigates to new page (route change) | Active time on PREVIOUS page |
| `tab_switch` | Tab goes hidden (`visibilitychange`) | Active time since last flush |
| `idle` | No interaction for 2 minutes | Active time since last flush |
| `closed` | Component unmounts (tab close, SPA teardown) | Active time since last flush |
| `resumed` | (Legacy, no longer sent by current tracker) | — |
| `null` | Middleware-recorded pageviews (server-side) | No duration (null) |

**Key insight:** `duration_ms` is NOT wall-clock time. It's **active time only** — excludes idle periods and hidden-tab periods. Multiple pageview records can exist for the same page in the same session (one per trigger event).

**Heartbeat:** `POST /api/tracking/heartbeat` with `{path, status}`. Status is `"active"` or `"idle"`. Heartbeats do NOT create pageview records — they only update Redis presence data.

### Backend Session Lifecycle (`modules/tracking/services/session_service.py`)

**Redis key:** `analytics:session:{session_id}` — string value "1"
**TTL:** `settings.tracking_session_timeout * 60` seconds (default: 30 minutes = 1800s)

**Session creation flow:**
1. First request with new session_id → `SETEX` Redis key, INSERT into `analytics.analytics_sessions`
2. Subsequent requests → `EXPIRE` to refresh TTL, `UPDATE page_count + 1, ended_at = NOW()`
3. Session expires → Redis key disappears passively (no reaper). DB record persists with `ended_at` = time of last activity.

**Critical:** `ended_at` is updated to `NOW()` on EVERY pageview/heartbeat. It does NOT mean the session actually ended — it means "last activity timestamp." Active sessions are detected via Redis key existence, NOT `ended_at IS NULL`.

### Redis Presence Hash (`analytics:presence:{session_id}`)

Set by heartbeat endpoint. Fields:
| Field | Value | Set when |
|-------|-------|----------|
| `path` | Current page path | Every heartbeat |
| `status` | `"active"` or `"idle"` | Every heartbeat |
| `last_heartbeat` | Unix ms timestamp | Every heartbeat |
| `page_entered_at` | Unix ms timestamp | Path changes (new page) |
| `idle_since` | Unix ms timestamp or "0" | Transition to idle; cleared on active |
| `active_since` | Unix ms timestamp | Path changes or transition to active |

**TTL:** 90 seconds if active (3x heartbeat interval), full session timeout if idle.

---

## 2. Expanded Timeline (JourneyView) — Bottom Level

**Component:** `JourneyView` (line ~441)
**Data source:** `GET /api/tracking/admin/analytics/session/{session_id}/pages` → `SessionDetail`

### Page Grouping (`groupPageSegments`, line ~234)

Raw pageview records are grouped by consecutive same-path visits:
```
[/home, /home, /home, /about, /about, /home]
→ Group 1: /home (3 segments), Group 2: /about (2 segments), Group 3: /home (1 segment)
```

Each `PageGroup` has:
- `totalActiveMs`: SUM of `duration_ms` across segments in group
- `totalWallMs`: `max(lastSegment.created_at - firstSegment.created_at, totalActiveMs)`
- `segments`: raw `SessionPageView[]` for expanding

### Live Page Ordering Fix (line ~448)

Race condition: when navigating from Page A to Page B, the browser's async "close" POST for Page A can arrive at the server AFTER Page B's records. This causes Page A to appear chronologically after Page B.

**Fix:** After grouping, if a live page is detected (via `liveState`), any groups appearing AFTER the live group are merged back into earlier groups with matching paths. This keeps the active page always at the end.

### Engagement Bar Per Page

For each page group row:
- **Active time**: `totalActiveMs` (green portion of bar)
- **Wall time**: `totalWallMs` (full bar width)
- **Engagement %**: `(activeMs / wallMs) * 100`, capped at 100%
- **Share %**: Each page's activeMs as percentage of total session activeMs (uses `distributeShares` for exact 100% sum)

For live pages, active time includes Redis `active_segment_duration_sec + tickOffset`.

### Expanded Timeline Rows (`buildTimeline`, line ~295)

When you click a page group to expand, each segment becomes timeline rows:

| Row Type | Color | When |
|----------|-------|------|
| Active (green) | `#22c55e` | `duration_ms >= 500ms` — shows active browsing time |
| Tab Switch (yellow) | `#eab308` | `trigger = "tab_switch"` AND away time >= 5s |
| Idle (orange) | `#f97316` | `trigger = "idle"` AND away time >= 5s |
| Exit/Navigate (blue) | `#3b82f6` | `trigger = "navigated"` — user left this page |
| Refresh detection | — | `trigger = "closed"` followed by same path within 10s → skipped |

**Live tail:** Active sessions get an animated pulsing green "Active" row or colored "Away"/"Idle" row at the bottom of the timeline.

---

## 3. Session Card — One Level Up

**Component:** `SessionCard` (line ~697)
**Data:** `UserSession` from activity response + lazy-loaded `SessionDetail`

### Displayed Fields

| Field | Calculation | Source |
|-------|------------|--------|
| **Device label** | `{browser} / {os} / {device_type}` | `user_agents` table via session JOIN |
| **Session ID** | First 8 chars, full ID in tooltip | `session_id` |
| **Presence badge** | See below | Redis presence hash |
| **Started** | Full locale datetime | `started_at` |
| **Duration** | `ended_at - started_at` (ended) or `now - started_at` (live, ticks every 1s) | Computed client-side |
| **Pages** | Page count | `page_count` from session |
| **Engagement %** | `min(100, (totalActiveMs + liveExtra) / sessionWallMs * 100)` | Computed client-side |

### Presence Badge Logic

| Condition | Badge | Color |
|-----------|-------|-------|
| `is_active && presence.status == "active"` | "Active on {page} ({duration})" | Green |
| `is_active && presence.status == "idle"` | "Idle on {page} ({idle_duration})" | Yellow |
| `is_active && no presence data` | "Session open" | Blue |
| `!is_active` | "Ended" | Gray |

### Session-Level Engagement Calculation (line ~754)

```
totalActiveMs = SUM(page.duration_ms for all pages in session)
liveActiveExtra = (detail.active_segment_duration_sec + tickOffset) * 1000  [if active]
sessionWallMs = ended_at ? (ended_at - started_at) : (now - started_at)
engagement = min(100, (totalActiveMs + liveActiveExtra) / sessionWallMs * 100)
```

### Active Session Polling

For active sessions:
- **Tick interval:** 1 second — updates `tickOffset` for live counters
- **Poll interval:** 30 seconds — re-fetches session detail from API
- **Immediate fetch:** On mount, fetches session detail so presence badge shows right away

---

## 4. Session Timeline Section — Overall Card

**Location:** Bottom section of the page (line ~1231)

### Session Filters

| Filter | Logic |
|--------|-------|
| All | Show all sessions |
| Active | `activeSessionIds.has(session.session_id)` |
| Ended | `!activeSessionIds.has(session.session_id)` |

### Device/Browser/OS Dropdowns

Dynamically populated from session data. Applied as AND filters with session filter.

### Active Session Detection (line ~1084)

On mount, after activity data loads:
1. Takes up to 10 most recent sessions
2. Fetches `SessionDetail` for each in parallel
3. Checks `is_active` flag (which comes from Redis key existence check on backend)
4. Populates `activeSessionIds` Set

---

## 5. Top Pages Card

**Component:** `TopPagesCard` (line ~923)
**Endpoint:** `GET /api/tracking/admin/analytics/pageviews?user_id={id}&date_from=...&date_to=...`

### What It Shows

Top pages ranked by **total active time** (`total_duration_ms`), with view count as secondary metric.

### Data Source (backend, line ~93)

```sql
SELECT pv.path, COUNT(*) AS views,
       COUNT(DISTINCT COALESCE(CAST(pv.user_id AS text), pv.session_id)) AS unique_visitors,
       COALESCE(SUM(pv.duration_ms), 0) AS total_duration_ms
FROM analytics.page_views pv
WHERE pv.created_at >= :ts_from AND pv.created_at < :ts_end
  AND pv.user_id = :user_id
GROUP BY pv.path ORDER BY views DESC LIMIT :lim
```

**Note:** This sums duration_ms across ALL sessions for the date range. Different scope from JourneyView which shows one session.

### Date Presets

`All Time | Last Hour | Last 24h | Last 36h | 7 Days | 30 Days | Custom`

- "All Time" uses `2020-01-01` as start date
- Hour presets use `new Date(now - X * 60 * 60 * 1000)`

### Chart

`HorizontalBarChart` component — green bars, primary value is formatted duration (`formatChartDuration`), secondary value is view count.

---

## 6. Device / Browser / OS Card

**Component:** `DeviceCard` (line ~983)
**Endpoint:** `GET /api/tracking/admin/analytics/devices?user_id={id}&date_from=...&date_to=...`

### What It Shows

Three breakdown sections:
1. **By Device Type** — desktop/mobile/tablet (purple bars)
2. **By Browser** — Edge/Chrome/Firefox/etc. (blue bars)
3. **By OS** — Windows/Mac/Linux/etc. (green bars)

Each item shows: session count + percentage + total duration.

### Data Source (backend, line ~333)

Joins `user_agents` → `analytics_sessions` → aggregated `page_views` duration.

```sql
-- Each section is a GROUP BY on the respective field
SELECT ua.device_type, COUNT(*) AS count, SUM(pv_dur.total_ms) AS total_duration_ms
FROM analytics.user_agents ua
JOIN analytics.analytics_sessions s ON ua.session_id = s.session_id
LEFT JOIN (SELECT session_id, SUM(duration_ms) AS total_ms FROM analytics.page_views GROUP BY session_id) pv_dur
  ON pv_dur.session_id = s.session_id
WHERE s.started_at >= :ts_from AND s.started_at < :ts_end AND s.user_id = :user_id
GROUP BY ua.device_type
```

**Note:** Session `1fc5f5fe...` has no user_agent data (from before UA parser was added). It won't appear in device stats but WILL appear in session count/pageview totals.

### Same date presets as Top Pages (independent filters per card).

---

## 7. KPI Score Cards

**Location:** 4-card grid below profile header (line ~1179)

### Card 1: Avg Engagement

- **Toggle:** "All" / "Live" (state: `engToggle`)
- **All:** `activity.avg_engagement_all_pct` → `{X}%`
- **Live:** `activity.avg_engagement_live_pct` → `{X}%` or "—" if no live sessions

**Backend calculation:**
```python
# All-time engagement
avg_eng_all = total_active_sec / total_session_wall_sec * 100

# Live engagement (only for Redis-detected live sessions)
live_active = SUM(duration_ms) / 1000 FROM page_views WHERE session_id IN (live_sessions)
live_wall = SUM(now - started_at) for live sessions
avg_eng_live = live_active / live_wall * 100
```

### Card 2: Live Sessions

- **Value:** `activeSessionIds.size` (frontend Set, populated by checking SessionDetail.is_active)
- **NOT** from `activity.live_session_count` — that's the backend's Redis check at fetch time
- Both should agree, but frontend uses its own check

**Backend calculation:** Iterates all session_ids, checks `redis.exists(f"analytics:session:{sid}")`

### Card 3: Avg Active per Session

- **Value:** `formatDurationSec(activity.avg_active_per_session_sec)`

**Backend calculation:**
```python
SUM(pv.duration_ms) / 1000.0 / NULLIF(session_count, 0)
FROM page_views pv
JOIN analytics_sessions s ON pv.session_id = s.session_id
WHERE s.user_id = :uid
```

This divides total active time across ALL sessions (including ended ones).

### Card 4: Total Active Time

- **Value:** `formatDurationSec(activity.total_time_sec)`

**Backend calculation:**
```python
SUM(duration_ms) / 1000.0 FROM analytics.page_views WHERE user_id = :uid
```

Sum of ALL `duration_ms` across all pageview records. This is total active browsing time — excludes idle and hidden-tab time.

---

## 8. Profile Header Card — Top Level

**Location:** Top of page (line ~1157)

### Fields Displayed

| Field | Value | Source |
|-------|-------|--------|
| **Email** | `activity.email` | `core.users.email` |
| **Engagement level** | `EngagementBadge` (high/medium/low) | Computed by `_compute_engagement()` |
| **First visit** | `formatDate(activity.first_visit)` | `MIN(page_views.created_at)` |
| **Last visit** | `relativeTime(activity.last_visit)` | `MAX(page_views.created_at)` |
| **Total session time** | `formatDurationSec(activity.total_session_time_sec)` | See below |
| **Total active time** | `formatDurationSec(activity.total_time_sec)` | `SUM(duration_ms)/1000` |

### Total Session Time Calculation

```python
# Ended sessions: wall-clock time from DB
total_session_sec = SUM(EXTRACT(EPOCH FROM (ended_at - started_at)))
                    FROM analytics_sessions WHERE user_id = :uid AND ended_at IS NOT NULL

# Live sessions: add (now - started_at) for each Redis-detected live session
for sr in sess_rows:
    if sr["session_id"] in live_session_ids:
        total_session_sec += (now - sr["started_at"]).total_seconds()
```

**Key distinction:**
- **Total session time** = wall-clock time with session open (includes idle, tab switches, everything)
- **Total active time** = only time user was actively browsing (tab visible + interacting)
- Total session time >= Total active time (always)

### Engagement Level Thresholds (`_compute_engagement`, line ~684)

| Level | Criteria |
|-------|----------|
| **High** | sessions >= 5 AND avg_duration > 120s AND last_active within 7 days |
| **Medium** | sessions >= 2 OR (sessions >= 1 AND avg_duration > 60s) |
| **Low** | Default / everything else |

---

## 9. Duration Formatting Rules

### `formatDuration(ms)` — for millisecond values
- `null` → `"-"`
- `< 1000ms` → `"Xms"`
- `< 60s` → `"Xs"`
- `< 60m` → `"Xm Ys"` (only dual-unit format)
- `< 24h` → `"X.Xh"` (0.1h precision)
- `>= 24h` → `"X.Xd"` (0.1d precision)

### `formatDurationSec(sec)` — for second values
Same rules as above but input is seconds, not milliseconds.

### `formatChartDuration(ms)` — for chart labels
- `< 60m` → `"Xm"`
- `< 24h` → `"X.Xh"` (0.5h precision)
- `< 365d` → `"X.Xd"` (0.1d precision)
- `>= 365d` → `"X.Xy"`

---

## 10. Known Edge Cases & Gotchas

1. **`ended_at` is NOT session end** — it's last activity timestamp. All sessions have `ended_at` set. Active sessions detected via Redis only.

2. **Multiple pageview records per page** — A single page visit can generate multiple records (navigated, then tab_switch, then idle, then resumed). Each records the active time since the last flush.

3. **Session with no user_agent** — Possible for old sessions. Shows blank device/browser/OS in session card. Not counted in device stats.

4. **`duration_ms` can be null** — Middleware-recorded pageviews (server-side) have no duration. Frontend minimum is 500ms.

5. **Race condition in page ordering** — Async "close" POSTs can arrive out of order. Fixed by JourneyView's merge-trailing-groups logic.

6. **Naive vs aware datetime** — PostgreSQL returns timezone-aware datetimes. Python code must use `datetime.now(timezone.utc)` not `datetime.utcnow()`.

7. **Live session count disagreement** — Frontend `activeSessionIds.size` and backend `live_session_count` may differ if checked at different times (Redis TTL expiry between checks).

8. **Engagement > 100%** — Theoretically possible if active segments overlap or rounding. Capped at 100% in frontend.

9. **Heartbeat TTL** — Active presence hash: 90s. If heartbeats stop (tab closed), presence data disappears within 90s but session key lives up to 30 minutes.

10. **Idle timeout** — Frontend idle timeout is 2 minutes (sends "idle" trigger). Backend session timeout is 30 minutes (Redis key expiry). These are different concepts.

---

## 11. API Endpoints Used by This Page

| Endpoint | When Called | Returns |
|----------|-----------|---------|
| `GET /tracking/admin/analytics/user/{id}/activity` | On mount | Full `UserActivity` with sessions, pageviews, engagement |
| `GET /tracking/admin/analytics/session/{id}/pages` | On session expand + every 30s for active | `SessionDetail` with pages, presence, is_active |
| `GET /tracking/admin/analytics/pageviews` | Top Pages card (with `user_id` param) | `PageViewStats` with top pages and duration |
| `GET /tracking/admin/analytics/devices` | Device card (with `user_id` param) | `DeviceStats` with device/browser/OS breakdown |

---

## 12. Validation Checklist (For Future Changes)

When modifying this page, verify:

- [ ] Duration formatting follows rules (no "465m", shows "7.8h" instead)
- [ ] Active session Duration ticks every second (not static "ongoing")
- [ ] Presence badge shows correct status (active/idle/ended) with page name
- [ ] Session engagement % <= 100%
- [ ] Total active time <= Total session time (always)
- [ ] Live Sessions count matches Redis key count
- [ ] Top Pages sums across ALL sessions (not per-session)
- [ ] Device stats join correctly (sessions without user_agent excluded)
- [ ] Date presets work: All Time, 1h, 24h, 36h, 7d, 30d, Custom
- [ ] JourneyView: active page always appears last (ordering fix)
- [ ] Timeline rows: refresh detection works (closed + same path < 10s = skip)
- [ ] Tooltips render newlines properly (use `text={"..."}` not `text="..."`)
- [ ] No `datetime.utcnow()` in backend — use `datetime.now(timezone.utc)`
- [ ] Engagement toggle (All/Live) works, "—" when no live sessions
