"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../../lib/api";
import { useConfig } from "../../../../../lib/config-context";
import LoadingSpinner from "../../../../../components/LoadingSpinner";

import HorizontalBarChart from "../../../../../components/charts/HorizontalBarChart";

interface UserPageView {
  path: string;
  duration_ms: number | null;
  created_at: string;
}

interface UserSession {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  page_count: number;
  browser: string | null;
  os: string | null;
  device_type: string | null;
}

interface UserTopPage {
  path: string;
  views: number;
}

interface UserActivity {
  user_id: string;
  email: string;
  total_pageviews: number;
  total_sessions: number;
  first_visit: string | null;
  last_visit: string | null;
  total_time_sec: number | null;
  avg_session_duration_sec: number | null;
  total_session_time_sec: number | null;
  live_session_count: number;
  avg_active_per_session_sec: number | null;
  avg_engagement_all_pct: number | null;
  avg_engagement_live_pct: number | null;
  top_pages: UserTopPage[];
  recent_pageviews: UserPageView[];
  sessions: UserSession[];
}

interface SessionPageView {
  path: string;
  duration_ms: number | null;
  trigger: string | null;
  created_at: string;
}

interface SessionDetail {
  session_id: string;
  user_id: string | null;
  user_email: string | null;
  started_at: string;
  ended_at: string | null;
  is_active: boolean;
  device_type: string | null;
  browser: string | null;
  os: string | null;
  pages: SessionPageView[];
  presence_status: string | null;
  current_page_live: string | null;
  current_page_duration_sec: number | null;
  idle_duration_sec: number | null;
  active_segment_duration_sec: number | null;
}

function friendlyPageName(path: string): string {
  const clean = path.replace(/^\//, "");
  if (!clean) return "Home";
  return clean
    .split("/")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" / ");
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms}ms`;
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (min < 60) return remSec > 0 ? `${min}m ${remSec}s` : `${min}m`;
  const hr = sec / 3600;
  if (hr < 24) return `${Math.round(hr * 10) / 10}h`;
  const days = hr / 24;
  return `${Math.round(days * 10) / 10}d`;
}

function formatDurationSec(sec: number | null): string {
  if (sec == null || sec <= 0) return "-";
  if (sec < 60) return `${Math.round(sec)}s`;
  const min = Math.floor(sec / 60);
  const remSec = Math.round(sec % 60);
  if (min < 60) return remSec > 0 ? `${min}m ${remSec}s` : `${min}m`;
  const hr = sec / 3600;
  if (hr < 24) return `${Math.round(hr * 10) / 10}h`;
  const days = hr / 24;
  return `${Math.round(days * 10) / 10}d`;
}

/** Chart-friendly duration: no seconds, clean rounding at each scale. */
function formatChartDuration(ms: number): string {
  if (ms <= 0) return "0m";
  const min = ms / 60000;
  if (min < 60) return `${Math.max(1, Math.round(min))}m`;
  const hr = min / 60;
  if (hr < 24) return `${Math.round(hr * 2) / 2}h`; // 0.5h precision
  const days = hr / 24;
  if (days < 365) return `${Math.round(days * 10) / 10}d`; // 0.1d precision
  const years = days / 365;
  return `${Math.round(years * 10) / 10}y`; // 0.1y precision
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function relativeTime(iso: string | null): string {
  if (!iso) return "-";
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

/** Hover tooltip that appears above the trigger element. */
function InfoTip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  return (
    <span
      className="relative inline-flex cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-max max-w-sm rounded-lg border border-white/10 bg-gray-900 px-3 py-2 text-xs text-gray-300 shadow-xl pointer-events-none whitespace-pre-line leading-relaxed">
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </span>
  );
}

function BreakdownBar({
  items,
  colorClass,
}: {
  items: { label: string; count: number; durationMs?: number }[];
  colorClass: string;
}) {
  const total = items.reduce((sum, i) => sum + i.count, 0);
  if (total === 0)
    return <p className="text-sm text-text-muted">No data available</p>;
  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const pct = Math.round((item.count / total) * 100);
        return (
          <div key={i}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-text-secondary">{item.label}</span>
              <span className="text-text-muted text-xs">
                {item.count} ({pct}%)
                {item.durationMs != null && item.durationMs > 0 && (
                  <span className="ml-2 text-text-secondary">
                    {formatChartDuration(item.durationMs)}
                  </span>
                )}
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
              <div
                className={`h-full rounded-full ${colorClass} transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface PageGroup {
  path: string;
  totalActiveMs: number;
  totalWallMs: number;
  segments: SessionPageView[];
}

function groupPageSegments(pages: SessionPageView[]): PageGroup[] {
  const groups: PageGroup[] = [];
  for (const p of pages) {
    const last = groups[groups.length - 1];
    if (last && last.path === p.path) {
      last.totalActiveMs += p.duration_ms ?? 0;
      last.segments.push(p);
    } else {
      groups.push({
        path: p.path,
        totalActiveMs: p.duration_ms ?? 0,
        totalWallMs: 0,
        segments: [p],
      });
    }
  }
  // Compute wall-clock time per group from first segment start to last segment created_at
  for (const g of groups) {
    if (g.segments.length > 0) {
      const first = g.segments[0];
      const last = g.segments[g.segments.length - 1];
      const startMs =
        new Date(first.created_at).getTime() - (first.duration_ms ?? 0);
      const endMs = new Date(last.created_at).getTime();
      g.totalWallMs = Math.max(endMs - startMs, g.totalActiveMs);
    }
  }
  return groups;
}

interface TimelineRow {
  label: string;
  durationMs: number;
  time: string;
  dotColor: string;
  textColor: string;
  isLive?: boolean;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const time = d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return `${date} ${time}`;
}

/** Compute how long the user was away after segment at index i. */
function computeAwayMs(segments: SessionPageView[], i: number): number {
  if (i + 1 >= segments.length) return 0;
  const leftAt = new Date(segments[i].created_at).getTime();
  const next = segments[i + 1];
  const returnedAt =
    new Date(next.created_at).getTime() - (next.duration_ms ?? 0);
  return Math.max(0, returnedAt - leftAt);
}

/**
 * Build a clean timeline from raw segments.
 * - Active segments show green with their duration.
 * - tab_switch / idle show the time the user was *away*.
 * - navigated / closed are exit events.
 * - Refresh detection: "closed" followed by same-path within 10s = refresh.
 */
function buildTimeline(segments: SessionPageView[]): TimelineRow[] {
  const rows: TimelineRow[] = [];
  let prevWasRefresh = false;

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const dur = seg.duration_ms ?? 0;

    // Active segment — time = when the active period started (created_at minus duration)
    if (dur >= 500) {
      const startMs = new Date(seg.created_at).getTime() - dur;
      const label = prevWasRefresh ? "Active (page refreshed)" : "Active";
      rows.push({
        label,
        durationMs: dur,
        time: fmtTime(new Date(startMs).toISOString()),
        dotColor: "bg-green-400",
        textColor: "text-green-400",
      });
    }
    prevWasRefresh = false;

    // Exit trigger — always show breaks so timeline is accurate
    if (seg.trigger === "tab_switch") {
      const awayMs = computeAwayMs(segments, i);
      rows.push({
        label: "Switched tab",
        durationMs: awayMs,
        time: fmtTime(seg.created_at),
        dotColor: "bg-yellow-400",
        textColor: "text-yellow-400",
      });
    } else if (seg.trigger === "idle") {
      const awayMs = computeAwayMs(segments, i);
      rows.push({
        label: "Went idle",
        durationMs: awayMs,
        time: fmtTime(seg.created_at),
        dotColor: "bg-orange-400",
        textColor: "text-orange-400",
      });
    } else if (seg.trigger === "navigated") {
      rows.push({
        label: "Navigated away",
        durationMs: 0,
        time: fmtTime(seg.created_at),
        dotColor: "bg-blue-400",
        textColor: "text-blue-400",
      });
    } else if (seg.trigger === "closed") {
      // Refresh detection: "closed" followed by same-path segment within 10s
      const isRefresh =
        i + 1 < segments.length &&
        segments[i + 1].path === seg.path &&
        new Date(segments[i + 1].created_at).getTime() -
          new Date(seg.created_at).getTime() <
          10000;
      if (isRefresh) {
        prevWasRefresh = true;
        // Skip "Page closed" row — it was a refresh
      } else {
        rows.push({
          label: "Page closed",
          durationMs: 0,
          time: fmtTime(seg.created_at),
          dotColor: "bg-red-400",
          textColor: "text-red-400",
        });
      }
    }
  }
  return rows;
}

/** Largest remainder method — ensures shares sum to exactly 100.00%. */
function distributeShares(values: number[]): number[] {
  const total = values.reduce((s, v) => s + v, 0);
  if (total === 0) return values.map(() => 0);
  const raw = values.map((v) => (v / total) * 10000); // basis points
  const floored = raw.map((v) => Math.floor(v));
  let deficit = 10000 - floored.reduce((s, v) => s + v, 0);
  const remainders = raw.map((v, i) => ({ i, r: v - floored[i] }));
  remainders.sort((a, b) => b.r - a.r);
  for (let k = 0; k < deficit; k++) floored[remainders[k].i]++;
  return floored.map((v) => v / 100);
}

// ── Date-filtered card types ──────────────────────────────

interface TopPageFiltered {
  path: string;
  views: number;
  unique_visitors: number;
  total_duration_ms: number;
}

interface PageViewStatsResponse {
  total_views: number;
  unique_visitors: number;
  top_pages: TopPageFiltered[];
  date_from: string | null;
  date_to: string | null;
}

interface DeviceStatsResponse {
  total_agents: number;
  by_device_type: {
    device_type: string;
    count: number;
    total_duration_ms: number;
  }[];
  by_browser: { browser: string; count: number; total_duration_ms: number }[];
  by_os: { os: string; count: number; total_duration_ms: number }[];
  date_from: string | null;
  date_to: string | null;
}

type DatePreset = "all" | "1h" | "24h" | "36h" | "7d" | "30d" | "custom";

function buildDateQS(
  preset: DatePreset,
  customFrom: string,
  customTo: string,
  userId: string,
): string {
  const qs = new URLSearchParams();
  qs.set("user_id", userId);
  const now = new Date();
  if (preset === "1h") {
    const from = new Date(now.getTime() - 60 * 60 * 1000);
    qs.set("date_from", from.toISOString());
    qs.set("date_to", now.toISOString());
  } else if (preset === "24h") {
    const from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    qs.set("date_from", from.toISOString());
    qs.set("date_to", now.toISOString());
  } else if (preset === "36h") {
    const from = new Date(now.getTime() - 36 * 60 * 60 * 1000);
    qs.set("date_from", from.toISOString());
    qs.set("date_to", now.toISOString());
  } else if (preset === "7d") {
    const from = new Date(now);
    from.setDate(from.getDate() - 7);
    qs.set("date_from", from.toISOString());
    qs.set("date_to", now.toISOString());
  } else if (preset === "30d") {
    const from = new Date(now);
    from.setDate(from.getDate() - 30);
    qs.set("date_from", from.toISOString());
    qs.set("date_to", now.toISOString());
  } else if (preset === "custom" && customFrom) {
    qs.set("date_from", new Date(customFrom).toISOString());
    if (customTo) qs.set("date_to", new Date(customTo).toISOString());
  } else {
    // "all" — set very old date since backend defaults to last 30 days
    qs.set("date_from", "2020-01-01T00:00:00Z");
    qs.set("date_to", now.toISOString());
  }
  return qs.toString();
}

function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

const DATE_PRESETS: { id: DatePreset; label: string }[] = [
  { id: "all", label: "All Time" },
  { id: "1h", label: "Last Hour" },
  { id: "24h", label: "Last 24h" },
  { id: "36h", label: "Last 36h" },
  { id: "7d", label: "7 Days" },
  { id: "30d", label: "30 Days" },
  { id: "custom", label: "Custom" },
];

interface LiveState {
  status: "active" | "idle";
  currentPath: string;
  activeSegSec: number | null;
  idleSec: number | null;
}

function JourneyView({
  pages,
  liveState,
  tickOffset,
  isActive,
}: {
  pages: SessionPageView[];
  liveState: LiveState | null;
  tickOffset: number;
  isActive: boolean;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const rawGroups = groupPageSegments(pages);

  // Determine which group is the live page
  let finalLiveIdx = liveState
    ? rawGroups.findLastIndex((g) => g.path === liveState.currentPath)
    : -1;

  // Fix ordering: when the user navigates from Page A to Page B, the browser
  // sends a "close" record for A asynchronously. If it arrives after B's first
  // record, A's group appears after the active page. Merge any trailing groups
  // back into their earlier counterparts so the active page is always last.
  let groups = rawGroups;
  if (finalLiveIdx >= 0 && finalLiveIdx < rawGroups.length - 1) {
    groups = rawGroups.slice(0, finalLiveIdx + 1).map((g) => ({
      ...g,
      segments: [...g.segments],
    }));
    const trailing = rawGroups.slice(finalLiveIdx + 1);
    for (const t of trailing) {
      const matchIdx = groups.findIndex(
        (g, i) => g.path === t.path && i !== finalLiveIdx,
      );
      if (matchIdx >= 0) {
        groups[matchIdx].totalActiveMs += t.totalActiveMs;
        groups[matchIdx].segments.push(...t.segments);
      } else {
        // No earlier match — insert just before the live page
        groups.splice(finalLiveIdx, 0, t);
        finalLiveIdx++;
      }
    }
    // Recompute wall times for merged groups
    for (const g of groups) {
      if (g.segments.length > 0) {
        const first = g.segments[0];
        const last = g.segments[g.segments.length - 1];
        const startMs =
          new Date(first.created_at).getTime() - (first.duration_ms ?? 0);
        const endMs = new Date(last.created_at).getTime();
        g.totalWallMs = Math.max(endMs - startMs, g.totalActiveMs);
      }
    }
  }

  const liveGroupIdx = finalLiveIdx;

  // Compute live active ms for the live page group
  const liveExtraMs =
    liveState &&
    liveGroupIdx >= 0 &&
    liveState.status === "active" &&
    liveState.activeSegSec != null
      ? (liveState.activeSegSec + tickOffset) * 1000
      : 0;

  // Build active values for share % distribution
  const activeValues = groups.map((g, i) =>
    i === liveGroupIdx ? g.totalActiveMs + liveExtraMs : g.totalActiveMs,
  );
  const shares = distributeShares(activeValues);

  return (
    <div className="space-y-1">
      {/* Column headers */}
      <div className="flex items-center gap-3 text-xs text-text-muted px-1 pb-1 border-b border-glass-border/20 mb-1">
        <span className="w-5" />
        <span className="w-40">Page</span>
        <span className="flex-1">Engagement</span>
        <span className="w-16 text-right">Active</span>
        <span className="w-14 text-right">Share</span>
        <span className="w-6" />
      </div>
      {groups.map((g, i) => {
        const isExpanded = expandedIdx === i;
        const isLivePage = i === liveGroupIdx;

        // Engagement bar — live page uses real-time values
        let displayActiveMs = g.totalActiveMs;
        let engagementPct: number;
        let wallMs = g.totalWallMs;

        if (isLivePage && liveState) {
          displayActiveMs = g.totalActiveMs + liveExtraMs;
          // Wall time = now minus when first segment started
          const firstStart =
            new Date(g.segments[0].created_at).getTime() -
            (g.segments[0].duration_ms ?? 0);
          wallMs = Math.max(Date.now() - firstStart, displayActiveMs);
          engagementPct =
            wallMs > 0
              ? Math.min(100, Math.round((displayActiveMs / wallMs) * 100))
              : 100;
        } else {
          engagementPct =
            wallMs > 0
              ? Math.min(100, Math.round((displayActiveMs / wallMs) * 100))
              : 100;
        }

        const shareDisplay = shares[i]?.toFixed(2) ?? "0.00";

        // Build timeline + live tail
        const timeline = buildTimeline(g.segments);

        // Add live tail row for the live page
        if (isLivePage && liveState) {
          const lastSeg = g.segments[g.segments.length - 1];

          if (liveState.status === "active") {
            // If user just returned from idle/tab_switch, the trigger row may have been
            // filtered by buildTimeline (awayMs=0 for last segment with no next segment).
            // Insert a frozen trigger row with computed away time before the live Active row.
            if (
              lastSeg?.trigger === "tab_switch" ||
              lastSeg?.trigger === "idle"
            ) {
              // Compute away time: gap between trigger record and when current active segment started
              const triggerTime = new Date(lastSeg.created_at).getTime();
              const activeSegStartMs =
                Date.now() -
                ((liveState.activeSegSec ?? 0) + tickOffset) * 1000;
              const awayMs = Math.max(0, activeSegStartMs - triggerTime);
              const triggerLabel =
                lastSeg.trigger === "tab_switch"
                  ? "Switched tab"
                  : "Went idle";
              const triggerDotColor =
                lastSeg.trigger === "tab_switch"
                  ? "bg-yellow-400"
                  : "bg-orange-400";
              const triggerTextColor =
                lastSeg.trigger === "tab_switch"
                  ? "text-yellow-400"
                  : "text-orange-400";
              timeline.push({
                label: triggerLabel,
                durationMs: awayMs,
                time: fmtTime(lastSeg.created_at),
                dotColor: triggerDotColor,
                textColor: triggerTextColor,
              });
            }

            const label =
              lastSeg?.trigger === "closed"
                ? "Active (page refreshed)"
                : "Active";
            const liveSec = (liveState.activeSegSec ?? 0) + tickOffset;
            timeline.push({
              label,
              durationMs: liveSec * 1000,
              time: "",
              dotColor: "bg-green-400",
              textColor: "text-green-400",
              isLive: true,
            });
          } else {
            // Idle — determine label from last DB record trigger
            let label = "Away";
            let dotColor = "bg-blue-400";
            let textColor = "text-blue-400";
            if (lastSeg?.trigger === "tab_switch") {
              label = "Switched tab";
              dotColor = "bg-yellow-400";
              textColor = "text-yellow-400";
            } else if (lastSeg?.trigger === "idle") {
              label = "Went idle";
              dotColor = "bg-orange-400";
              textColor = "text-orange-400";
            }
            const liveSec = (liveState.idleSec ?? 0) + tickOffset;
            timeline.push({
              label,
              durationMs: liveSec * 1000,
              time: "",
              dotColor,
              textColor,
              isLive: true,
            });
          }
        }

        // Add "Away" row for active session with no presence (blue badge state)
        if (!liveState && isActive && i === groups.length - 1) {
          timeline.push({
            label: "Away",
            durationMs: 0,
            time: "",
            dotColor: "bg-blue-400",
            textColor: "text-blue-400",
          });
        }

        const hasEvents = timeline.length > 1 || (isLivePage && liveState);

        return (
          <div key={i}>
            <div
              className={`flex items-center gap-3 text-sm py-1.5 rounded px-1 ${hasEvents ? "cursor-pointer hover:bg-glass-bg/50" : ""}`}
              onClick={() => hasEvents && setExpandedIdx(isExpanded ? null : i)}
            >
              <span className="text-text-muted text-xs w-5 text-right">
                {i + 1}.
              </span>
              <span
                className="text-text-secondary flex-shrink-0 w-40 truncate"
                title={g.path}
              >
                {friendlyPageName(g.path)}
              </span>
              {/* Engagement bar — green for live, pink for frozen */}
              <div className="flex-1 flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-glass-bg/50 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${isLivePage ? "bg-green-400/40" : "bg-accent-pink/40"}`}
                    style={{ width: `${engagementPct}%` }}
                  />
                </div>
                <span className="text-text-muted text-xs tabular-nums w-8 text-right">
                  {engagementPct}%
                </span>
              </div>
              {/* Active time — ticks for live page */}
              <span className="text-text-primary text-xs font-medium tabular-nums w-16 text-right">
                {formatDuration(displayActiveMs)}
              </span>
              {/* Share % — 2 decimal places */}
              <span className="text-text-muted text-xs tabular-nums w-14 text-right">
                {shareDisplay}%
              </span>
              {hasEvents ? (
                <span className="text-text-muted text-xs w-6 text-right">
                  {isExpanded ? "\u25B4" : "\u25BE"}
                </span>
              ) : (
                <span className="w-6" />
              )}
            </div>
            {isExpanded && (
              <div className="ml-10 pl-1 py-1">
                {/* Expanded timeline headers */}
                <div className="flex items-center text-xs py-0.5 text-text-muted mb-1">
                  <div className="w-3 flex-shrink-0" />
                  <span className="ml-2 w-40">State</span>
                  <span className="ml-auto flex items-center gap-3">
                    <span className="w-16 text-right">Duration</span>
                    <span className="text-right w-44">Started at</span>
                  </span>
                </div>
                {timeline.map((row, j) => (
                  <div key={j} className="flex items-center text-xs py-0.5">
                    {/* Connector line + dot */}
                    <div className="flex flex-col items-center w-3 self-stretch flex-shrink-0">
                      <div
                        className={`w-0.5 flex-1 ${j === 0 ? "bg-transparent" : "bg-glass-border/30"}`}
                      />
                      {row.isLive ? (
                        <span className="relative flex w-2 h-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                          <span
                            className={`relative inline-block w-2 h-2 rounded-full flex-shrink-0 ${row.dotColor}`}
                          />
                        </span>
                      ) : (
                        <span
                          className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${row.dotColor}`}
                        />
                      )}
                      <div
                        className={`w-0.5 flex-1 ${j === timeline.length - 1 ? "bg-transparent" : "bg-glass-border/30"}`}
                      />
                    </div>
                    {/* Label */}
                    <span className={`ml-2 ${row.textColor}`}>{row.label}</span>
                    {/* Duration + timestamp right-aligned */}
                    <span className="ml-auto flex items-center gap-3">
                      <span className="text-text-primary font-medium tabular-nums w-16 text-right">
                        {row.durationMs > 0
                          ? formatDuration(row.durationMs)
                          : ""}
                      </span>
                      <span className="text-text-muted tabular-nums text-right whitespace-nowrap w-44">
                        {row.time}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SessionCard({
  session,
  isActive,
}: {
  session: UserSession;
  isActive: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loadingPages, setLoadingPages] = useState(false);
  const [tickOffset, setTickOffset] = useState(0);
  const fetchTime = useRef(Date.now());

  const deviceParts: string[] = [];
  if (session.browser) deviceParts.push(session.browser);
  if (session.os) deviceParts.push(session.os);
  if (session.device_type) deviceParts.push(session.device_type);
  const deviceLabel =
    deviceParts.length > 0 ? deviceParts.join(" / ") : "Unknown device";

  const handleExpand = () => {
    if (!expanded && !detail) {
      setLoadingPages(true);
      fetchTime.current = Date.now();
      setTickOffset(0);
      apiFetch<SessionDetail>(
        `/tracking/admin/analytics/session/${session.session_id}/pages`,
      )
        .then(setDetail)
        .catch(() => {})
        .finally(() => setLoadingPages(false));
    }
    setExpanded(!expanded);
  };

  // Fetch session detail immediately for active sessions, then poll every 30s
  useEffect(() => {
    if (!isActive) return;
    // Immediate fetch so presence badge shows right away
    fetchTime.current = Date.now();
    setTickOffset(0);
    apiFetch<SessionDetail>(
      `/tracking/admin/analytics/session/${session.session_id}/pages`,
    )
      .then(setDetail)
      .catch(() => {});
    const tickInterval = setInterval(() => {
      setTickOffset(Math.floor((Date.now() - fetchTime.current) / 1000));
    }, 1000);
    const pollInterval = setInterval(() => {
      fetchTime.current = Date.now();
      setTickOffset(0);
      apiFetch<SessionDetail>(
        `/tracking/admin/analytics/session/${session.session_id}/pages`,
      )
        .then(setDetail)
        .catch(() => {});
    }, 30000);
    return () => {
      clearInterval(tickInterval);
      clearInterval(pollInterval);
    };
  }, [isActive, session.session_id]);

  const pages = detail?.pages || [];
  const pres = detail?.presence_status;
  const livePage = detail?.current_page_live;
  const pageDur = detail?.current_page_duration_sec;
  const idleDur = detail?.idle_duration_sec;

  // Compute session-level engagement % (total active / session wall time)
  const totalActiveMs = pages.reduce((sum, p) => sum + (p.duration_ms ?? 0), 0);
  const liveActiveExtra =
    pres === "active" && detail?.active_segment_duration_sec != null
      ? (detail.active_segment_duration_sec + tickOffset) * 1000
      : 0;
  const sessionStartMs = new Date(session.started_at).getTime();
  const sessionWallMs = Math.max(Date.now() - sessionStartMs, 1);
  const sessionEngagementPct = Math.min(
    100,
    Math.round(((totalActiveMs + liveActiveExtra) / sessionWallMs) * 100),
  );

  // Build presence badge text
  let badgeClass = "bg-gray-500/20 text-gray-400";
  let badgeText = "Ended";
  if (isActive) {
    if (pres === "active") {
      badgeClass = "bg-green-500/20 text-green-400";
      const durDisplay =
        pageDur != null ? formatDurationSec(pageDur + tickOffset) : "";
      badgeText = `Active on ${livePage ? friendlyPageName(livePage) : "..."}${durDisplay ? ` (${durDisplay})` : ""}`;
    } else if (pres === "idle") {
      badgeClass = "bg-yellow-500/20 text-yellow-400";
      const idleDisplay =
        idleDur != null ? formatDurationSec(idleDur + tickOffset) : "";
      badgeText = `Idle on ${livePage ? friendlyPageName(livePage) : "..."}${idleDisplay ? ` (idle ${idleDisplay})` : ""}`;
    } else {
      badgeClass = "bg-blue-500/20 text-blue-400";
      const lastPage = pages.length > 0 ? pages[pages.length - 1].path : null;
      badgeText = lastPage
        ? `Session Open on ${friendlyPageName(lastPage)}`
        : "Session Open";
    }
  }

  return (
    <div className="relative pl-6 pb-6 last:pb-0">
      {/* Timeline dot and line */}
      <div className="absolute left-0 top-1">
        {isActive && pres === "active" ? (
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
          </span>
        ) : isActive && pres === "idle" ? (
          <span className="inline-flex rounded-full h-3 w-3 bg-yellow-500" />
        ) : isActive ? (
          <span className="inline-flex rounded-full h-3 w-3 bg-blue-500" />
        ) : (
          <span className="inline-flex rounded-full h-3 w-3 bg-gray-500" />
        )}
      </div>
      <div className="absolute left-[5px] top-4 bottom-0 w-0.5 bg-glass-border/30 last:hidden" />

      {/* Session header */}
      <div
        className="glass rounded-lg p-4 cursor-pointer"
        onClick={handleExpand}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-text-primary text-sm font-medium">Session</span>
          <span className="text-text-muted text-xs">{deviceLabel}</span>
          <span
            className="ml-auto text-text-muted/50 text-xs font-mono"
            title={session.session_id}
          >
            id: {session.session_id.slice(0, 8)}
          </span>
        </div>
        <div className="mb-1">
          <InfoTip
            text={
              isActive && pres === "active"
                ? "The user's browser tab is in focus and they have been active within the last 30 seconds.\n\nThe time in parentheses shows how long they have been on this specific page.\n\nThis resets each time they navigate to a different page."
                : isActive && pres === "idle"
                  ? "The user's browser tab is open but there has been no mouse or keyboard activity for more than 30 seconds.\n\nThe time in parentheses shows how long they have been idle.\n\nThis resets when the user moves their mouse or presses a key."
                  : isActive
                    ? "A session exists but no recent heartbeat has been received.\n\nThe user may have the tab open in the background or their connection was interrupted."
                    : "No heartbeat was received for more than 30 minutes.\n\nThe session has been closed."
            }
          >
            <span
              className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}
            >
              {badgeText}
            </span>
          </InfoTip>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-text-muted">
          <InfoTip
            text={
              "The timestamp when this session first began.\n\nThis is recorded when the user's first page load is detected for this session."
            }
          >
            <span>Started: {formatTime(session.started_at)}</span>
          </InfoTip>
          <InfoTip
            text={
              "Total wall-clock time from when the session started to when it ended.\n\nThis includes everything — active browsing, idle periods, and time spent on other tabs."
            }
          >
            <span>
              Duration:{" "}
              {formatDuration(
                session.ended_at
                  ? new Date(session.ended_at).getTime() -
                      new Date(session.started_at).getTime()
                  : Date.now() - new Date(session.started_at).getTime(),
              )}
            </span>
          </InfoTip>
          <InfoTip
            text={
              "Total number of page visits recorded in this session.\n\nEach time the user navigates to a page or returns to a previously visited page, one record is created."
            }
          >
            <span>
              {session.page_count} page{session.page_count !== 1 ? "s" : ""}
            </span>
          </InfoTip>
          <InfoTip
            text={
              "The percentage of the session spent actively browsing.\n\nCalculated by dividing the total active browsing time by the total session duration.\n\nActive time only counts when the browser tab is visible and the user is interacting. Idle time and time on other tabs are not included."
            }
          >
            <span>Engagement: {sessionEngagementPct}%</span>
          </InfoTip>
        </div>
        <div className="text-xs text-accent-pink/60 mt-1">
          {expanded ? "Click to collapse" : "Click to expand journey"}
        </div>
      </div>

      {/* Expanded pages — Option B: merged rows, expandable segments with triggers */}
      {expanded && (
        <div className="mt-2 ml-4">
          {loadingPages ? (
            <LoadingSpinner className="py-4" />
          ) : pages.length > 0 ? (
            <JourneyView
              pages={pages}
              liveState={
                isActive && pres
                  ? {
                      status: pres as "active" | "idle",
                      currentPath: livePage || "",
                      activeSegSec: detail?.active_segment_duration_sec ?? null,
                      idleSec: idleDur ?? null,
                    }
                  : null
              }
              tickOffset={tickOffset}
              isActive={isActive}
            />
          ) : (
            <p className="text-xs text-text-muted py-2">
              No pageview data for this session
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Date-Filtered Card: Top Pages ──────────────────────────

function DatePresetPills({
  preset,
  onPresetChange,
  customFrom,
  customTo,
  onCustomFromChange,
  onCustomToChange,
  onApply,
  accentClass,
}: {
  preset: DatePreset;
  onPresetChange: (p: DatePreset) => void;
  customFrom: string;
  customTo: string;
  onCustomFromChange: (v: string) => void;
  onCustomToChange: (v: string) => void;
  onApply: () => void;
  accentClass?: string;
}) {
  const active = accentClass || "bg-white/10 text-text-primary";
  return (
    <div className="space-y-2 mb-3">
      <div className="flex flex-wrap gap-1.5">
        {DATE_PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => onPresetChange(p.id)}
            className={`px-2.5 py-0.5 text-xs rounded-full transition-colors ${
              preset === p.id
                ? active
                : "bg-glass-bg text-text-muted hover:text-text-secondary"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {preset === "custom" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="datetime-local"
            value={customFrom}
            max={customTo || nowLocal()}
            onChange={(e) => onCustomFromChange(e.target.value)}
            className="bg-glass-bg border border-glass-border/30 rounded px-2 py-0.5 text-xs text-text-primary"
          />
          <span className="text-text-muted text-xs">to</span>
          <input
            type="datetime-local"
            value={customTo}
            max={nowLocal()}
            onChange={(e) => onCustomToChange(e.target.value)}
            className="bg-glass-bg border border-glass-border/30 rounded px-2 py-0.5 text-xs text-text-primary"
          />
          <button
            onClick={onApply}
            className="px-2.5 py-0.5 text-xs rounded bg-white/10 text-text-primary hover:bg-white/15 transition-colors"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}

const TOP_PAGES_TIP =
  "Total active browsing time per page in the selected date range.\n\n" +
  "Only counts time when the browser tab was visible and the user was interacting.\n\n" +
  "Time spent on other tabs or while idle is not included.";

function TopPagesCard({ userId }: { userId: string }) {
  const [preset, setPreset] = useState<DatePreset>("all");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [data, setData] = useState<TopPageFiltered[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchKey, setFetchKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    const qs = buildDateQS(preset, customFrom, customTo, userId);
    apiFetch<PageViewStatsResponse>(`/tracking/admin/analytics/pageviews?${qs}`)
      .then((res) => setData(res.top_pages))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId, preset, fetchKey]);

  return (
    <div className="glass rounded-xl p-6">
      <h2 className="text-lg font-semibold text-text-primary mb-2">
        <InfoTip text={TOP_PAGES_TIP}>
          <span>
            Top Pages{" "}
            <span className="text-text-muted text-sm font-normal">
              (Active Time)
            </span>
          </span>
        </InfoTip>
      </h2>
      <DatePresetPills
        preset={preset}
        onPresetChange={setPreset}
        customFrom={customFrom}
        customTo={customTo}
        onCustomFromChange={setCustomFrom}
        onCustomToChange={setCustomTo}
        onApply={() => setFetchKey((k) => k + 1)}
        accentClass="bg-green-500/20 text-green-400"
      />
      {loading ? (
        <LoadingSpinner className="py-8" />
      ) : data && data.length > 0 ? (
        <HorizontalBarChart
          data={data.map((p) => ({
            label: friendlyPageName(p.path),
            value: p.total_duration_ms,
            secondary: p.views,
          }))}
          color="#22c55e"
          formatValue={formatChartDuration}
          formatSecondary={(v) => `${v} views`}
        />
      ) : (
        <p className="text-sm text-text-muted py-4">
          No page data for this period
        </p>
      )}
    </div>
  );
}

const DEVICE_TIP =
  "How many sessions used each device type, browser, and operating system.\n\n" +
  "The percentage shows what fraction of all sessions used that device, browser, or OS.\n\n" +
  "The time shown is the total active browsing time across all sessions using that device, browser, or OS.\n\n" +
  "Device information is detected automatically from the browser on the first page load of each session.";

function DeviceCard({ userId }: { userId: string }) {
  const [preset, setPreset] = useState<DatePreset>("all");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [data, setData] = useState<DeviceStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchKey, setFetchKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    const qs = buildDateQS(preset, customFrom, customTo, userId);
    apiFetch<DeviceStatsResponse>(`/tracking/admin/analytics/devices?${qs}`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId, preset, fetchKey]);

  return (
    <div className="glass rounded-xl p-6">
      <h2 className="text-lg font-semibold text-text-primary mb-2">
        <InfoTip text={DEVICE_TIP}>
          <span>
            Device / Browser / OS{" "}
            <span className="text-text-muted text-sm font-normal">
              (Sessions)
            </span>
          </span>
        </InfoTip>
      </h2>
      <DatePresetPills
        preset={preset}
        onPresetChange={setPreset}
        customFrom={customFrom}
        customTo={customTo}
        onCustomFromChange={setCustomFrom}
        onCustomToChange={setCustomTo}
        onApply={() => setFetchKey((k) => k + 1)}
        accentClass="bg-accent-purple/20 text-accent-purple"
      />
      {loading ? (
        <LoadingSpinner className="py-8" />
      ) : data ? (
        <div className="space-y-4">
          {data.by_device_type.length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-2">Devices</p>
              <BreakdownBar
                items={data.by_device_type.map((d) => ({
                  label: d.device_type,
                  count: d.count,
                  durationMs: d.total_duration_ms,
                }))}
                colorClass="bg-accent-purple/60"
              />
            </div>
          )}
          {data.by_browser.length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-2">Browsers</p>
              <BreakdownBar
                items={data.by_browser.map((b) => ({
                  label: b.browser,
                  count: b.count,
                  durationMs: b.total_duration_ms,
                }))}
                colorClass="bg-accent-blue/60"
              />
            </div>
          )}
          {data.by_os.length > 0 && (
            <div>
              <p className="text-xs text-text-muted mb-2">Operating Systems</p>
              <BreakdownBar
                items={data.by_os.map((o) => ({
                  label: o.os,
                  count: o.count,
                  durationMs: o.total_duration_ms,
                }))}
                colorClass="bg-accent-green/60"
              />
            </div>
          )}
          {data.by_device_type.length === 0 &&
            data.by_browser.length === 0 &&
            data.by_os.length === 0 && (
              <p className="text-sm text-text-muted py-4">
                No device data for this period
              </p>
            )}
        </div>
      ) : (
        <p className="text-sm text-text-muted py-4">
          No device data for this period
        </p>
      )}
    </div>
  );
}

type SessionFilter = "all" | "active" | "ended";

export default function UserActivityPage() {
  const { enable_tracking } = useConfig();
  const params = useParams();
  const userId = params.id as string;
  const [activity, setActivity] = useState<UserActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeSessionIds, setActiveSessionIds] = useState<Set<string>>(
    new Set(),
  );
  const [sessionFilter, setSessionFilter] = useState<SessionFilter>("all");
  const [engToggle, setEngToggle] = useState<"all" | "current">("all");
  const [browserFilter, setBrowserFilter] = useState<string | null>(null);
  const [osFilter, setOsFilter] = useState<string | null>(null);
  const [deviceFilter, setDeviceFilter] = useState<string | null>(null);

  useEffect(() => {
    if (!enable_tracking || !userId) return;
    apiFetch<UserActivity>(`/tracking/admin/analytics/user/${userId}/activity`)
      .then(setActivity)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [enable_tracking, userId]);

  // Check which sessions are active via Redis by fetching session details
  useEffect(() => {
    if (!activity?.sessions.length) return;
    const checkActive = async () => {
      const activeIds = new Set<string>();
      const checks = activity.sessions.map(async (s) => {
        try {
          const detail = await apiFetch<SessionDetail>(
            `/tracking/admin/analytics/session/${s.session_id}/pages`,
          );
          if (detail.is_active) activeIds.add(s.session_id);
        } catch {
          // ignore
        }
      });
      await Promise.all(checks);
      setActiveSessionIds(activeIds);
    };
    checkActive();
  }, [activity?.sessions]);

  if (!enable_tracking) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-text-muted">Tracking is disabled.</p>
      </div>
    );
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  if (error || !activity) {
    return (
      <div>
        <Link
          href="/admin/analytics"
          className="text-sm text-accent-pink hover:underline mb-4 inline-block"
        >
          &larr; Back to Analytics
        </Link>
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted">No activity recorded for this user.</p>
        </div>
      </div>
    );
  }

  // Collect unique values for filter dropdowns
  const uniqueBrowsers = Array.from(
    new Set(
      activity.sessions.map((s) => s.browser).filter((v): v is string => !!v),
    ),
  );
  const uniqueOS = Array.from(
    new Set(activity.sessions.map((s) => s.os).filter((v): v is string => !!v)),
  );
  const uniqueDevices = Array.from(
    new Set(
      activity.sessions
        .map((s) => s.device_type)
        .filter((v): v is string => !!v),
    ),
  );

  // Filter sessions (status + browser + OS + device combined with AND)
  const filteredSessions = activity.sessions.filter((s) => {
    if (sessionFilter === "active" && !activeSessionIds.has(s.session_id))
      return false;
    if (sessionFilter === "ended" && activeSessionIds.has(s.session_id))
      return false;
    if (browserFilter && s.browser !== browserFilter) return false;
    if (osFilter && s.os !== osFilter) return false;
    if (deviceFilter && s.device_type !== deviceFilter) return false;
    return true;
  });

  const activeCount = activity.sessions.filter((s) =>
    activeSessionIds.has(s.session_id),
  ).length;

  const sessionFilters: { id: SessionFilter; label: string }[] = [
    { id: "all", label: `All (${activity.sessions.length})` },
    { id: "active", label: `Active (${activeCount})` },
    { id: "ended", label: `Ended (${activity.sessions.length - activeCount})` },
  ];

  return (
    <div>
      <Link
        href="/admin/analytics"
        className="text-sm text-accent-pink hover:underline mb-4 inline-block"
      >
        &larr; Back to Analytics
      </Link>

      {/* User Profile Header */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">User Activity</span>
        </h1>
      </div>
      <div className="glass rounded-xl p-4 mb-6">
        <p className="text-text-primary font-medium mb-2">{activity.email}</p>
        <div className="flex flex-wrap gap-4 text-xs text-text-muted">
          <span>First visit: {formatDate(activity.first_visit)}</span>
          <span>Last visit: {relativeTime(activity.last_visit)}</span>
          <InfoTip
            text={
              "Total wall-clock time across all sessions.\n\nIncludes active time, idle time, and time on other tabs."
            }
          >
            <span>
              Total session time:{" "}
              {formatDurationSec(activity.total_session_time_sec)}
            </span>
          </InfoTip>
          <InfoTip
            text={
              "Total time spent actively browsing across all sessions.\n\nOnly counts time when the tab was visible and the user was interacting."
            }
          >
            <span>
              Total active time: {formatDurationSec(activity.total_time_sec)}
            </span>
          </InfoTip>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between mb-1">
            <InfoTip
              text={
                "The percentage of session time spent actively browsing.\n\nCalculated by dividing total active time by total session time.\n\nToggle between all-time average and current live sessions."
              }
            >
              <p className="text-xs text-text-muted cursor-help">
                Avg Engagement
              </p>
            </InfoTip>
            <div className="flex gap-0.5">
              <button
                onClick={() => setEngToggle("all")}
                className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${engToggle === "all" ? "bg-accent-pink/20 text-accent-pink" : "text-text-muted hover:text-text-secondary"}`}
              >
                All
              </button>
              <button
                onClick={() => setEngToggle("current")}
                className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${engToggle === "current" ? "bg-accent-pink/20 text-accent-pink" : "text-text-muted hover:text-text-secondary"}`}
              >
                Live
              </button>
            </div>
          </div>
          <p className="text-2xl font-bold text-text-primary">
            {engToggle === "all"
              ? `${activity.avg_engagement_all_pct ?? 0}%`
              : activity.avg_engagement_live_pct != null
                ? `${activity.avg_engagement_live_pct}%`
                : "\u2014"}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <InfoTip
            text={
              "Number of sessions currently open.\n\nA session stays live until no activity is detected for 30 minutes."
            }
          >
            <p className="text-xs text-text-muted mb-1 cursor-help">
              Live Sessions
            </p>
          </InfoTip>
          <p className="text-2xl font-bold text-text-primary">
            {activeSessionIds.size}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <InfoTip
            text={
              "Average active browsing time per session.\n\nDivides total active time across all sessions by the number of sessions."
            }
          >
            <p className="text-xs text-text-muted mb-1 cursor-help">
              Avg Active per Session
            </p>
          </InfoTip>
          <p className="text-2xl font-bold text-text-primary">
            {formatDurationSec(activity.avg_active_per_session_sec)}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <InfoTip
            text={
              "Total active browsing time across all sessions.\n\nOnly counts time when the tab was visible and the user was interacting."
            }
          >
            <p className="text-xs text-text-muted mb-1 cursor-help">
              Total Active Time
            </p>
          </InfoTip>
          <p className="text-2xl font-bold text-text-primary">
            {formatDurationSec(activity.total_time_sec)}
          </p>
        </div>
      </div>

      {/* Top Pages + Device Breakdown — each with independent date filters */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <TopPagesCard userId={userId} />
        <DeviceCard userId={userId} />
      </div>

      {/* Session Timeline */}
      <div className="glass rounded-xl p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-text-primary">
            Session Timeline
          </h2>
          <div className="flex gap-2">
            {sessionFilters.map((f) => (
              <button
                key={f.id}
                onClick={() => setSessionFilter(f.id)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  sessionFilter === f.id
                    ? "bg-accent-pink/20 text-accent-pink"
                    : "bg-glass-bg text-text-muted hover:text-text-secondary"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        {/* Device / Browser / OS filters */}
        {(uniqueBrowsers.length > 0 ||
          uniqueOS.length > 0 ||
          uniqueDevices.length > 0) && (
          <div className="flex flex-wrap gap-3 mb-4">
            {uniqueBrowsers.length > 0 && (
              <label className="flex items-center gap-1 text-xs text-text-muted">
                Browser:
                <select
                  value={browserFilter ?? ""}
                  onChange={(e) => setBrowserFilter(e.target.value || null)}
                  className="bg-glass-bg border border-glass-border/30 rounded px-2 py-0.5 text-xs text-text-secondary"
                >
                  <option value="">All</option>
                  {uniqueBrowsers.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {uniqueOS.length > 0 && (
              <label className="flex items-center gap-1 text-xs text-text-muted">
                OS:
                <select
                  value={osFilter ?? ""}
                  onChange={(e) => setOsFilter(e.target.value || null)}
                  className="bg-glass-bg border border-glass-border/30 rounded px-2 py-0.5 text-xs text-text-secondary"
                >
                  <option value="">All</option>
                  {uniqueOS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {uniqueDevices.length > 0 && (
              <label className="flex items-center gap-1 text-xs text-text-muted">
                Device:
                <select
                  value={deviceFilter ?? ""}
                  onChange={(e) => setDeviceFilter(e.target.value || null)}
                  className="bg-glass-bg border border-glass-border/30 rounded px-2 py-0.5 text-xs text-text-secondary"
                >
                  <option value="">All</option>
                  {uniqueDevices.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        {filteredSessions.length > 0 ? (
          <div>
            {filteredSessions.map((s) => (
              <SessionCard
                key={s.session_id}
                session={s}
                isActive={activeSessionIds.has(s.session_id)}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            {sessionFilter === "all"
              ? "No sessions recorded"
              : `No ${sessionFilter} sessions`}
          </p>
        )}
      </div>
    </div>
  );
}
