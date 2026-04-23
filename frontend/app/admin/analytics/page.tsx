"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { useConfig } from "../../../lib/config-context";
import LoadingSpinner from "../../../components/LoadingSpinner";
import Link from "next/link";
import CustomMetricsTab from "./custom-metrics";

const AreaSparkChart = dynamic(
  () => import("../../../components/charts/AreaSparkChart"),
  { ssr: false },
);

// ── Interfaces ──────────────────────────────────────────

interface KPIMetric {
  current: number;
  previous: number;
  change_pct: number | null;
}

interface DashboardSummary {
  total_pageviews: KPIMetric;
  unique_visitors: KPIMetric;
  new_visitors: KPIMetric;
  returning_visitors: KPIMetric;
  avg_active_per_session: KPIMetric;
  avg_pages_per_session: KPIMetric;
  bounce_rate: KPIMetric;
}

interface TimeseriesPoint {
  timestamp: string;
  pageviews: number;
  unique_visitors: number;
  engagement_pct: number | null;
}

interface PageviewTimeSeries {
  points: TimeseriesPoint[];
  granularity: string;
}

interface ActiveSessionData {
  session_id: string;
  user_email: string | null;
  current_page: string | null;
  device_type: string | null;
  duration_sec: number;
  presence_status: string | null;
  page_duration_sec: number | null;
  idle_duration_sec: number | null;
  last_heartbeat_ago_sec: number | null;
}

interface ActiveSessionsResponse {
  count: number;
  sessions: ActiveSessionData[];
}

interface PageEngagement {
  path: string;
  views: number;
  unique_visitors: number;
  avg_duration_ms: number | null;
  entry_count: number;
  bounce_count: number;
}

interface PagesEngagementResponse {
  pages: PageEngagement[];
}

interface SourceStats {
  sources: { source: string; medium: string | null; sessions: number }[];
}

interface DeviceStats {
  total_agents: number;
  by_device_type: {
    device_type: string;
    count: number;
    total_duration_ms: number;
  }[];
  by_browser: { browser: string; count: number; total_duration_ms: number }[];
  by_os: { os: string; count: number; total_duration_ms: number }[];
}

interface EventStats {
  total_events: number;
  by_type: { event_type: string; count: number }[];
}

interface EnrichedUser {
  user_id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  total_pageviews: number;
  total_sessions: number;
  last_active: string | null;
  avg_session_duration_sec: number | null;
  top_page: string | null;
  total_active_time_sec: number | null;
  avg_engagement_pct: number | null;
  is_live: boolean;
}

interface EnrichedUserList {
  users: EnrichedUser[];
  total_count: number;
}

// ── Helpers ─────────────────────────────────────────────

function friendlyPageName(path: string): string {
  const clean = path.replace(/^\//, "");
  if (!clean) return "Home";
  return clean
    .split("/")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" / ");
}

function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function thirtyDaysAgoLocal(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function buildFilterQS(
  dateFrom: string,
  dateTo: string,
  excludeBots: boolean,
): string {
  const qs = new URLSearchParams();
  if (dateFrom) qs.set("date_from", new Date(dateFrom).toISOString());
  if (dateTo) qs.set("date_to", new Date(dateTo).toISOString());
  qs.set("exclude_bots", String(excludeBots));
  const s = qs.toString();
  return s ? `?${s}` : "";
}

function formatDurationSec(sec: number | null | undefined): string {
  if (sec == null || sec <= 0) return "-";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) {
    const min = Math.floor(sec / 60);
    const rem = Math.round(sec % 60);
    return rem > 0 ? `${min}m ${rem}s` : `${min}m`;
  }
  if (sec < 86400) return `${(sec / 3600).toFixed(1)}h`;
  return `${(sec / 86400).toFixed(1)}d`;
}

function formatDurationMs(ms: number | null): string {
  if (ms == null) return "-";
  return formatDurationSec(ms / 1000);
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

// ── Shared Components ───────────────────────────────────

type DatePresetId = "24h" | "7d" | "30d" | "90d" | "custom";

const DATE_PRESETS: { id: DatePresetId; label: string }[] = [
  { id: "24h", label: "24h" },
  { id: "7d", label: "7 Days" },
  { id: "30d", label: "30 Days" },
  { id: "90d", label: "90 Days" },
  { id: "custom", label: "Custom" },
];

function presetLabel(id: DatePresetId): string {
  switch (id) {
    case "24h":
      return "Last 24 Hours";
    case "7d":
      return "Last 7 Days";
    case "30d":
      return "Last 30 Days";
    case "90d":
      return "Last 90 Days";
    case "custom":
      return "Custom Range";
  }
}

function formatDateRange(from: string, to: string): string {
  const f = new Date(from);
  const t = new Date(to);
  const opts: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
  };
  return `${f.toLocaleDateString([], opts)} \u2013 ${t.toLocaleDateString([], opts)}`;
}

function computePresetDates(preset: DatePresetId): {
  from: string;
  to: string;
} {
  const now = new Date();
  const to = now;
  const from = new Date(now);
  switch (preset) {
    case "24h":
      from.setHours(from.getHours() - 24);
      break;
    case "7d":
      from.setDate(from.getDate() - 7);
      break;
    case "30d":
      from.setDate(from.getDate() - 30);
      break;
    case "90d":
      from.setDate(from.getDate() - 90);
      break;
    default:
      from.setDate(from.getDate() - 30);
  }
  // Convert to local datetime-local format
  const toLocal = (d: Date) => {
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  };
  return { from: toLocal(new Date(from)), to: toLocal(new Date(to)) };
}

function FilterBar({
  dateFrom,
  dateTo,
  excludeBots,
  activePreset,
  onPresetChange,
  onDateFromChange,
  onDateToChange,
  onExcludeBotsChange,
  onApply,
  children,
}: {
  dateFrom: string;
  dateTo: string;
  excludeBots: boolean;
  activePreset: DatePresetId;
  onPresetChange: (preset: DatePresetId) => void;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onExcludeBotsChange: (v: boolean) => void;
  onApply: () => void;
  children?: React.ReactNode;
}) {
  const maxDate = nowLocal();
  return (
    <div className="glass rounded-xl p-4 mb-6 space-y-3">
      {/* Row 1: Active range headline */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-text-primary">
            {presetLabel(activePreset)}
          </h2>
          <span className="text-sm text-text-muted">
            {formatDateRange(dateFrom, dateTo)}
          </span>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={excludeBots}
            onChange={(e) => onExcludeBotsChange(e.target.checked)}
            className="rounded border-glass-border"
          />
          Exclude bots
        </label>
      </div>

      {/* Row 2: Preset pills + children */}
      <div className="flex flex-wrap items-center gap-2">
        {DATE_PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => onPresetChange(p.id)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              activePreset === p.id
                ? "bg-accent-pink/20 text-accent-pink border-accent-pink/30 font-medium"
                : "text-text-muted border-glass-border hover:text-text-secondary hover:border-text-secondary/30"
            }`}
          >
            {p.label}
          </button>
        ))}
        {children}
      </div>

      {/* Custom range inputs (only when custom is active) */}
      {activePreset === "custom" && (
        <div className="flex flex-wrap items-end gap-3 pt-1">
          <div>
            <label className="text-xs text-text-muted block mb-1">From</label>
            <input
              type="datetime-local"
              value={dateFrom}
              max={dateTo || maxDate}
              onChange={(e) => onDateFromChange(e.target.value)}
              className="bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">To</label>
            <input
              type="datetime-local"
              value={dateTo}
              max={maxDate}
              onChange={(e) => onDateToChange(e.target.value)}
              className="bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
            />
          </div>
          <button
            onClick={onApply}
            className="px-4 py-1.5 text-sm rounded-lg bg-accent-pink/20 text-accent-pink hover:bg-accent-pink/30 transition-colors"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}

function BreakdownBar({
  items,
  colorClass,
  onItemClick,
  linkPrefix,
}: {
  items: { label: string; count: number }[];
  colorClass: string;
  onItemClick?: (label: string) => void;
  linkPrefix?: string;
}) {
  const total = items.reduce((sum, i) => sum + i.count, 0);
  if (total === 0)
    return <p className="text-sm text-text-muted">No data available</p>;
  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const pct = Math.round((item.count / total) * 100);
        const interactive = !!onItemClick || !!linkPrefix;
        const content = (
          <>
            <div className="flex justify-between text-sm mb-1">
              <span
                className={`text-text-secondary ${interactive ? "group-hover:text-text-primary" : ""}`}
              >
                {item.label}
              </span>
              <span className="text-text-muted text-xs">
                {item.count} ({pct}%)
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
              <div
                className={`h-full rounded-full ${colorClass} transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </>
        );
        if (linkPrefix) {
          return (
            <Link
              key={i}
              href={`${linkPrefix}${encodeURIComponent(item.label)}`}
              className="block group hover:opacity-80 transition-opacity"
            >
              {content}
            </Link>
          );
        }
        return (
          <div
            key={i}
            className={
              interactive
                ? "group cursor-pointer hover:opacity-80 transition-opacity"
                : ""
            }
            onClick={onItemClick ? () => onItemClick(item.label) : undefined}
          >
            {content}
          </div>
        );
      })}
    </div>
  );
}

function ChangeBadge({
  metric,
  invert,
}: {
  metric: KPIMetric;
  invert?: boolean;
}) {
  const pct = metric.change_pct;
  if (pct == null) return <span className="text-xs text-text-muted">-</span>;
  const positive = invert ? pct < 0 : pct > 0;
  const negative = invert ? pct > 0 : pct < 0;
  const arrow = pct > 0 ? "\u2191" : pct < 0 ? "\u2193" : "";
  const color = positive
    ? "bg-green-500/20 text-green-400"
    : negative
      ? "bg-red-500/20 text-red-400"
      : "bg-gray-500/20 text-gray-400";
  return (
    <span
      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs font-medium ${color}`}
    >
      {arrow} {Math.abs(pct)}%
    </span>
  );
}

function KPICard({
  label,
  value,
  metric,
  format,
  invert,
  hint,
}: {
  label: string;
  value: string;
  metric: KPIMetric;
  format?: string;
  invert?: boolean;
  hint?: string;
}) {
  return (
    <div className="glass rounded-xl p-5">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <div className="flex items-end gap-2 mb-1">
        <p className="text-2xl font-bold text-text-primary">{value}</p>
        <ChangeBadge metric={metric} invert={invert} />
      </div>
      {hint && <p className="text-xs text-amber-400 mt-1">{hint}</p>}
    </div>
  );
}

// ── Tab: Overview ───────────────────────────────────────

function OverviewTab() {
  const [dateFrom, setDateFrom] = useState(thirtyDaysAgoLocal);
  const [dateTo, setDateTo] = useState(nowLocal);
  const [excludeBots, setExcludeBots] = useState(true);
  const [activePreset, setActivePreset] = useState<DatePresetId>("30d");

  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [timeseries, setTimeseries] = useState<PageviewTimeSeries | null>(null);
  const [activeSessions, setActiveSessions] =
    useState<ActiveSessionsResponse | null>(null);
  const [engagement, setEngagement] = useState<PagesEngagementResponse | null>(
    null,
  );
  const [sources, setSources] = useState<SourceStats | null>(null);
  const [devices, setDevices] = useState<DeviceStats | null>(null);
  const [events, setEvents] = useState<EventStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchKey, setFetchKey] = useState(0);
  const [granularity, setGranularity] = useState("day");
  const [deviceRange, setDeviceRange] = useState("hour");
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const buildQS = useCallback(
    () => buildFilterQS(dateFrom, dateTo, excludeBots),
    [dateFrom, dateTo, excludeBots],
  );

  // Fetch active sessions (independent of filters, polled)
  const fetchActive = useCallback(() => {
    apiFetch<ActiveSessionsResponse>(
      "/tracking/admin/analytics/active-sessions",
    )
      .then(setActiveSessions)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchActive();
    pollRef.current = setInterval(fetchActive, 30000);
    return () => clearInterval(pollRef.current);
  }, [fetchActive]);

  // Shared lookback window calculator
  const lookbackQS = useCallback((range: string, bots: boolean) => {
    const now = new Date();
    const from = new Date(now);
    switch (range) {
      case "hour":
        from.setMinutes(from.getMinutes() - 60);
        break;
      case "day":
        from.setHours(from.getHours() - 24);
        break;
      case "week":
        from.setDate(from.getDate() - 7);
        break;
      case "month":
        from.setDate(from.getDate() - 30);
        break;
      case "year":
        from.setFullYear(from.getFullYear() - 1);
        break;
    }
    return `?date_from=${from.toISOString()}&date_to=${now.toISOString()}&exclude_bots=${bots}`;
  }, []);

  // Stable fetch helpers — deps are passed as args, not captured in useCallback
  const fetchTimeseriesFor = useCallback(
    (g: string, bots: boolean) => {
      const qs = lookbackQS(g, bots) + `&granularity=${g}`;
      apiFetch<PageviewTimeSeries>(
        `/tracking/admin/analytics/pageviews/timeseries${qs}`,
      )
        .then(setTimeseries)
        .catch(() => null);
    },
    [lookbackQS],
  );

  const fetchDevicesFor = useCallback(
    (range: string, bots: boolean) => {
      const qs = lookbackQS(range, bots);
      apiFetch<DeviceStats>(`/tracking/admin/analytics/devices${qs}`)
        .then(setDevices)
        .catch(() => null);
    },
    [lookbackQS],
  );

  // Main data fetch — only re-runs on filter bar Apply/Reset
  useEffect(() => {
    setLoading(true);
    const q = buildQS();
    Promise.all([
      apiFetch<DashboardSummary>(
        `/tracking/admin/analytics/dashboard${q}`,
      ).catch(() => null),
      apiFetch<PagesEngagementResponse>(
        `/tracking/admin/analytics/pages/engagement${q}`,
      ).catch(() => null),
      apiFetch<SourceStats>(`/tracking/admin/analytics/sources${q}`).catch(
        () => null,
      ),
      apiFetch<EventStats>(`/tracking/admin/analytics/events${q}`).catch(
        () => null,
      ),
    ])
      .then(([dash, eng, src, ev]) => {
        setDashboard(dash);
        setEngagement(eng);
        setSources(src);
        setEvents(ev);
      })
      .finally(() => setLoading(false));
    fetchTimeseriesFor(granularity, excludeBots);
    fetchDevicesFor(deviceRange, excludeBots);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchKey, buildQS]);

  // Refetch only timeseries when granularity changes
  useEffect(() => {
    fetchTimeseriesFor(granularity, excludeBots);
  }, [granularity, excludeBots, fetchTimeseriesFor]);

  // Refetch only devices when device range changes
  useEffect(() => {
    fetchDevicesFor(deviceRange, excludeBots);
  }, [deviceRange, excludeBots, fetchDevicesFor]);

  const handleApply = () => setFetchKey((k) => k + 1);
  const handlePresetChange = (preset: DatePresetId) => {
    setActivePreset(preset);
    if (preset !== "custom") {
      const { from, to } = computePresetDates(preset);
      setDateFrom(from);
      setDateTo(to);
      setFetchKey((k) => k + 1);
    }
  };

  // Live tick counter — increments every second for real-time feel
  const [tickOffset, setTickOffset] = useState(0);
  const tickRef = useRef<ReturnType<typeof setInterval>>();
  const lastFetchTime = useRef(Date.now());

  // Reset tick offset when fresh data arrives
  useEffect(() => {
    lastFetchTime.current = Date.now();
    setTickOffset(0);
  }, [activeSessions]);

  // Tick every second
  useEffect(() => {
    tickRef.current = setInterval(() => {
      setTickOffset(Math.floor((Date.now() - lastFetchTime.current) / 1000));
    }, 1000);
    return () => clearInterval(tickRef.current);
  }, []);

  // Sort sessions by page_duration_sec descending, show top 5
  const sortedSessions = (activeSessions?.sessions ?? [])
    .slice()
    .sort((a, b) => (b.page_duration_sec ?? 0) - (a.page_duration_sec ?? 0));
  const displaySessions = sortedSessions.slice(0, 5);
  const extraCount = sortedSessions.length - displaySessions.length;

  return (
    <>
      <FilterBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        excludeBots={excludeBots}
        activePreset={activePreset}
        onPresetChange={handlePresetChange}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onExcludeBotsChange={setExcludeBots}
        onApply={handleApply}
      />

      {/* Row 1: Active Sessions Banner */}
      <div className="glass rounded-xl p-4 mb-6">
        {activeSessions && activeSessions.count > 0 ? (
          <>
            <div className="flex items-center gap-3 mb-3">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
              </span>
              <span className="text-text-primary font-semibold">
                {activeSessions.count} visitor
                {activeSessions.count !== 1 ? "s" : ""} on your site right now
              </span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted text-xs text-left">
                  <th className="pb-2">Visitor</th>
                  <th className="pb-2">Page</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2 text-right">On Page</th>
                  <th className="pb-2 text-right">Session</th>
                </tr>
              </thead>
              <tbody>
                {displaySessions.map((s) => {
                  const pageDur = (s.page_duration_sec ?? 0) + tickOffset;
                  const sessDur = s.duration_sec + tickOffset;
                  const idleDur =
                    s.idle_duration_sec != null
                      ? s.idle_duration_sec + tickOffset
                      : null;
                  return (
                    <tr
                      key={s.session_id}
                      className="border-t border-glass-border/30"
                    >
                      <td className="py-1.5 text-text-secondary text-xs truncate max-w-[160px]">
                        {s.user_email || "(anonymous)"}
                      </td>
                      <td
                        className="py-1.5 text-text-muted text-xs truncate max-w-[160px]"
                        title={s.current_page || ""}
                      >
                        {s.current_page
                          ? friendlyPageName(s.current_page)
                          : "-"}
                      </td>
                      <td className="py-1.5">
                        {s.presence_status === "active" ? (
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className="inline-flex rounded-full h-2 w-2 bg-green-500" />
                            <span className="text-green-400">Active</span>
                          </span>
                        ) : s.presence_status === "idle" ? (
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className="inline-flex rounded-full h-2 w-2 bg-yellow-500" />
                            <span className="text-yellow-400">
                              Idle
                              {idleDur != null
                                ? ` ${formatDurationSec(idleDur)}`
                                : ""}
                            </span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <span className="inline-flex rounded-full h-2 w-2 bg-blue-500" />
                            <span className="text-blue-400">Session Open</span>
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 text-text-primary text-xs text-right font-medium">
                        {s.page_duration_sec != null
                          ? formatDurationSec(pageDur)
                          : formatDurationSec(sessDur)}
                      </td>
                      <td className="py-1.5 text-text-muted text-xs text-right">
                        {formatDurationSec(sessDur)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {extraCount > 0 && (
              <p className="text-xs text-text-muted mt-2">
                and {extraCount} more
              </p>
            )}
          </>
        ) : (
          <div className="flex items-center gap-3">
            <span className="inline-flex rounded-full h-3 w-3 bg-gray-500" />
            <span className="text-text-muted">
              No active visitors right now
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <LoadingSpinner className="py-20" />
      ) : (
        <>
          {/* KPI Cards */}
          {dashboard && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <KPICard
                label="Total Pageviews"
                value={Math.round(
                  dashboard.total_pageviews.current,
                ).toLocaleString()}
                metric={dashboard.total_pageviews}
              />
              <KPICard
                label="Unique Visitors"
                value={Math.round(
                  dashboard.unique_visitors.current,
                ).toLocaleString()}
                metric={dashboard.unique_visitors}
              />
              <div className="glass rounded-xl p-5 group relative">
                <p className="text-xs text-text-muted mb-1">
                  New vs Returning
                  <span className="ml-1 inline-block w-3.5 h-3.5 rounded-full border border-text-muted/40 text-center text-[10px] leading-[13px] cursor-help align-middle">
                    ?
                  </span>
                </p>
                <div className="flex items-end gap-2 mb-1">
                  <p className="text-2xl font-bold text-text-primary">
                    {Math.round(dashboard.new_visitors.current)}{" "}
                    <span className="text-sm font-normal text-text-muted">
                      new
                    </span>{" "}
                    / {Math.round(dashboard.returning_visitors.current)}{" "}
                    <span className="text-sm font-normal text-text-muted">
                      ret
                    </span>
                  </p>
                  <ChangeBadge metric={dashboard.new_visitors} />
                </div>
                <div className="invisible group-hover:visible absolute left-0 right-0 top-full mt-1 z-20 glass rounded-lg p-3 text-xs text-text-secondary border border-glass-border/50 shadow-lg">
                  <p className="mb-1">
                    <span className="font-medium text-text-primary">New:</span>{" "}
                    First-ever pageview (all time) falls within the selected
                    dates
                  </p>
                  <p>
                    <span className="font-medium text-text-primary">
                      Returning:
                    </span>{" "}
                    Had at least one pageview before the selected dates, and
                    visited again during them
                  </p>
                  <p className="mt-1 text-text-muted">
                    Only authenticated users are counted. Dates are set by the
                    filter above (default: last 30 days).
                  </p>
                </div>
              </div>
              <KPICard
                label="Avg Active / Session"
                value={formatDurationSec(
                  dashboard.avg_active_per_session.current,
                )}
                metric={dashboard.avg_active_per_session}
              />
            </div>
          )}

          {/* Row 4: Traffic Over Time */}
          {timeseries && timeseries.points.length > 0 && (
            <div className="glass rounded-xl p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-text-primary">
                  Traffic Over Time
                </h2>
                <div className="flex gap-1">
                  {(["hour", "day", "week", "month", "year"] as const).map(
                    (g) => (
                      <button
                        key={g}
                        onClick={() => setGranularity(g)}
                        className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                          granularity === g
                            ? "bg-accent-pink/20 text-accent-pink"
                            : "text-text-muted hover:text-text-secondary"
                        }`}
                      >
                        {g === "hour"
                          ? "Hourly"
                          : g === "day"
                            ? "Daily"
                            : g === "week"
                              ? "Weekly"
                              : g === "month"
                                ? "Monthly"
                                : "Yearly"}
                      </button>
                    ),
                  )}
                </div>
              </div>
              <AreaSparkChart
                data={timeseries.points.map((p) => ({
                  label: p.timestamp,
                  value: p.pageviews,
                  value2: p.unique_visitors,
                  value3: p.engagement_pct,
                }))}
                color="#ec4899"
                color2="#a855f7"
                color3="#22c55e"
                height={280}
                valueLabel="Pageviews"
                valueLabel2="Unique Visitors"
                valueLabel3="Engagement %"
              />
            </div>
          )}

          {/* Row 5: Top Pages + Traffic Sources */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
            <div className="lg:col-span-3 glass rounded-xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">
                Top Pages
              </h2>
              {engagement?.pages && engagement.pages.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-text-muted text-xs text-left">
                        <th className="pb-2">Page</th>
                        <th className="pb-2 text-right">Views</th>
                        <th className="pb-2 text-right">Avg Duration</th>
                        <th className="pb-2 text-right">Bounce Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {engagement.pages.slice(0, 10).map((p, i) => {
                        const bounceRate =
                          p.entry_count > 0
                            ? Math.round((p.bounce_count / p.entry_count) * 100)
                            : 0;
                        const lowDuration =
                          p.avg_duration_ms != null && p.avg_duration_ms < 5000;
                        const highBounce = bounceRate > 60;
                        return (
                          <tr
                            key={i}
                            className="border-t border-glass-border/30"
                          >
                            <td
                              className="py-2 text-text-secondary truncate max-w-[200px]"
                              title={p.path}
                            >
                              {friendlyPageName(p.path)}
                            </td>
                            <td className="py-2 text-text-primary text-right font-medium">
                              {p.views}
                            </td>
                            <td
                              className={`py-2 text-right ${lowDuration ? "text-amber-400" : "text-text-muted"}`}
                            >
                              {formatDurationMs(p.avg_duration_ms)}
                            </td>
                            <td
                              className={`py-2 text-right ${highBounce ? "text-red-400" : "text-text-muted"}`}
                            >
                              {p.entry_count > 0 ? `${bounceRate}%` : "-"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-text-muted">No data available</p>
              )}
            </div>

            <div className="lg:col-span-2 glass rounded-xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">
                Traffic Sources
              </h2>
              <BreakdownBar
                items={(sources?.sources ?? []).slice(0, 8).map((s) => {
                  const src =
                    (s.source || "direct").charAt(0).toUpperCase() +
                    (s.source || "direct").slice(1);
                  const med =
                    s.medium && s.medium !== "none" ? ` / ${s.medium}` : "";
                  return { label: `${src}${med}`, count: s.sessions };
                })}
                colorClass="bg-accent-pink/60"
              />
            </div>
          </div>

          {/* Row 6: Device / Browser / OS — combined card */}
          <div className="glass rounded-xl p-6 mb-6">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-lg font-semibold text-text-primary">
                Device / Browser / OS{" "}
                <span className="text-sm font-normal text-text-muted">
                  (Sessions)
                </span>
              </h2>
              <div className="flex gap-1">
                {(["hour", "day", "week", "month", "year"] as const).map(
                  (r) => (
                    <button
                      key={r}
                      onClick={() => setDeviceRange(r)}
                      className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                        deviceRange === r
                          ? "bg-accent-purple/20 text-accent-purple"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      {r === "hour"
                        ? "Last Hour"
                        : r === "day"
                          ? "Last 24h"
                          : r === "week"
                            ? "7 Days"
                            : r === "month"
                              ? "30 Days"
                              : "Yearly"}
                    </button>
                  ),
                )}
              </div>
            </div>

            {devices && (
              <div className="mt-4 space-y-6">
                {/* Devices */}
                <div>
                  <p className="text-xs text-text-muted mb-2">Devices</p>
                  <div className="space-y-3">
                    {(devices.by_device_type ?? []).map((d) => {
                      const total = devices.total_agents || 1;
                      const pct = Math.round((d.count / total) * 100);
                      const barWidth = Math.max(pct, 2);
                      return (
                        <div key={d.device_type}>
                          <div className="flex items-baseline justify-between mb-1">
                            <span className="text-sm font-medium text-accent-purple">
                              {d.device_type}
                            </span>
                            <span className="text-xs text-text-muted">
                              {d.count} ({pct}%){" "}
                              <span className="font-medium text-text-secondary ml-1">
                                {formatDurationMs(d.total_duration_ms)}
                              </span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
                            <div
                              className="h-full rounded-full bg-accent-purple/60 transition-all"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Browsers */}
                <div>
                  <p className="text-xs text-text-muted mb-2">Browsers</p>
                  <div className="space-y-3">
                    {(devices.by_browser ?? []).map((d) => {
                      const total = devices.total_agents || 1;
                      const pct = Math.round((d.count / total) * 100);
                      const barWidth = Math.max(pct, 2);
                      return (
                        <div key={d.browser}>
                          <div className="flex items-baseline justify-between mb-1">
                            <span className="text-sm font-medium text-blue-400">
                              {d.browser}
                            </span>
                            <span className="text-xs text-text-muted">
                              {d.count} ({pct}%){" "}
                              <span className="font-medium text-text-secondary ml-1">
                                {formatDurationMs(d.total_duration_ms)}
                              </span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
                            <div
                              className="h-full rounded-full bg-blue-500/60 transition-all"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Operating Systems */}
                <div>
                  <p className="text-xs text-text-muted mb-2">
                    Operating Systems
                  </p>
                  <div className="space-y-3">
                    {(devices.by_os ?? []).map((d) => {
                      const total = devices.total_agents || 1;
                      const pct = Math.round((d.count / total) * 100);
                      const barWidth = Math.max(pct, 2);
                      return (
                        <div key={d.os}>
                          <div className="flex items-baseline justify-between mb-1">
                            <span className="text-sm font-medium text-emerald-400">
                              {d.os}
                            </span>
                            <span className="text-xs text-text-muted">
                              {d.count} ({pct}%){" "}
                              <span className="font-medium text-text-secondary ml-1">
                                {formatDurationMs(d.total_duration_ms)}
                              </span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
                            <div
                              className="h-full rounded-full bg-emerald-500/60 transition-all"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Events (full-width, clickable rows link to detail page) */}
          <div className="glass rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-text-primary mb-4">
              Events
              {events && events.total_events > 0 && (
                <span className="text-sm font-normal text-text-muted ml-2">
                  {events.total_events.toLocaleString()} total
                </span>
              )}
            </h2>
            {events && events.total_events > 0 ? (
              <BreakdownBar
                items={events.by_type
                  .slice(0, 12)
                  .map((e) => ({ label: e.event_type, count: e.count }))}
                colorClass="bg-accent-green/60"
                linkPrefix="/admin/analytics/events/"
              />
            ) : (
              <p className="text-sm text-text-muted">No events recorded</p>
            )}
          </div>
        </>
      )}
    </>
  );
}

// ── Tab: User Activity ──────────────────────────────────

function UserActivityTab() {
  const [dateFrom, setDateFrom] = useState(thirtyDaysAgoLocal);
  const [dateTo, setDateTo] = useState(nowLocal);
  const [excludeBots, setExcludeBots] = useState(true);
  const [activePreset, setActivePreset] = useState<DatePresetId>("30d");
  const [search, setSearch] = useState("");
  const [users, setUsers] = useState<EnrichedUser[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searched, setSearched] = useState(false);
  const [fetchKey, setFetchKey] = useState(0);
  const [segment, setSegment] = useState("all");
  const [sortBy, setSortBy] = useState("last_active");
  const [sortDir, setSortDir] = useState("desc");
  const searchTimer = useRef<ReturnType<typeof setTimeout>>();

  const fetchUsers = useCallback(
    (q: string) => {
      setLoading(true);
      const qs = buildFilterQS(dateFrom, dateTo, excludeBots);
      const sep = qs ? "&" : "?";
      const extra = `${sep}q=${encodeURIComponent(q)}&segment=${segment}&sort_by=${sortBy}&sort_dir=${sortDir}`;
      apiFetch<EnrichedUserList>(
        `/tracking/admin/analytics/users/enriched${qs}${extra}`,
      )
        .then((d) => {
          setUsers(d.users || []);
          setTotalCount(d.total_count || 0);
        })
        .catch(() => {
          setUsers([]);
          setTotalCount(0);
        })
        .finally(() => {
          setLoading(false);
          setSearched(true);
        });
    },
    [dateFrom, dateTo, excludeBots, segment, sortBy, sortDir],
  );

  useEffect(() => {
    clearTimeout(searchTimer.current);
    if (search.length < 1) {
      fetchUsers("");
      return;
    }
    searchTimer.current = setTimeout(() => fetchUsers(search), 300);
    return () => clearTimeout(searchTimer.current);
  }, [search, fetchKey, fetchUsers]);

  const handleApply = () => setFetchKey((k) => k + 1);
  const handlePresetChange = (preset: DatePresetId) => {
    setActivePreset(preset);
    if (preset !== "custom") {
      const { from, to } = computePresetDates(preset);
      setDateFrom(from);
      setDateTo(to);
      setFetchKey((k) => k + 1);
    }
  };

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
    setFetchKey((k) => k + 1);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortBy !== col)
      return <span className="text-text-muted/30 ml-1">{"\u2195"}</span>;
    return (
      <span className="text-accent-pink ml-1">
        {sortDir === "desc" ? "\u2193" : "\u2191"}
      </span>
    );
  };

  const segments = [
    { id: "all", label: "All" },
    { id: "active_today", label: "Active Today" },
    { id: "active_week", label: "Active This Week" },
    { id: "inactive", label: "Inactive (7+ days)" },
  ];

  const inactiveCount = segment === "inactive" ? users.length : 0;

  return (
    <>
      <FilterBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        excludeBots={excludeBots}
        activePreset={activePreset}
        onPresetChange={handlePresetChange}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onExcludeBotsChange={setExcludeBots}
        onApply={handleApply}
      >
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs text-text-muted block mb-1">Search</label>
          <div className="flex items-center gap-2 bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 text-text-muted shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Filter by email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none text-sm text-text-primary placeholder:text-text-muted"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-xs text-text-muted hover:text-text-secondary"
              >
                x
              </button>
            )}
          </div>
        </div>
      </FilterBar>

      {/* Segment pills */}
      <div className="flex gap-2 mb-4">
        {segments.map((s) => (
          <button
            key={s.id}
            onClick={() => {
              setSegment(s.id);
              setFetchKey((k) => k + 1);
            }}
            className={`px-3 py-1.5 text-xs rounded-full transition-colors ${
              segment === s.id
                ? "bg-accent-pink/20 text-accent-pink"
                : "bg-glass-bg text-text-muted hover:text-text-secondary"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {segment === "inactive" && users.length > 0 && (
        <div className="glass rounded-xl p-3 mb-4 border border-amber-500/20">
          <p className="text-sm text-amber-400">
            {users.length} user{users.length !== 1 ? "s" : ""} haven&apos;t
            returned in 7+ days &mdash; consider re-engagement outreach
          </p>
        </div>
      )}

      {loading ? (
        <LoadingSpinner className="py-12" />
      ) : users.length > 0 ? (
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-muted text-xs text-left border-b border-glass-border/50">
                <th className="px-4 py-3">Email</th>
                <th
                  className="px-4 py-3 cursor-pointer select-none"
                  onClick={() => toggleSort("last_active")}
                >
                  Last Active <SortIcon col="last_active" />
                </th>
                <th
                  className="px-4 py-3 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("sessions")}
                >
                  Sessions <SortIcon col="sessions" />
                </th>
                <th
                  className="px-4 py-3 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("active_time")}
                >
                  Active Time <SortIcon col="active_time" />
                </th>
                <th
                  className="px-4 py-3 text-right cursor-pointer select-none"
                  onClick={() => toggleSort("engagement")}
                >
                  Engagement % <SortIcon col="engagement" />
                </th>
                <th className="px-4 py-3">Top Page</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.user_id}
                  className="border-t border-glass-border/30 hover:bg-glass-hover/30 transition-colors"
                >
                  <td className="px-4 py-3 text-text-secondary">
                    <span className="inline-flex items-center gap-2">
                      {u.is_live && (
                        <span className="relative flex h-2.5 w-2.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
                        </span>
                      )}
                      {u.email}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-text-muted text-xs"
                    title={
                      u.last_active
                        ? new Date(u.last_active).toLocaleString()
                        : ""
                    }
                  >
                    {u.last_active ? relativeTime(u.last_active) : "-"}
                  </td>
                  <td className="px-4 py-3 text-text-primary text-right">
                    {u.total_sessions}
                  </td>
                  <td className="px-4 py-3 text-text-primary text-right font-medium">
                    {formatDurationSec(u.total_active_time_sec)}
                  </td>
                  <td className="px-4 py-3 text-right text-xs font-medium">
                    {u.avg_engagement_pct != null ? (
                      <span
                        className={
                          u.avg_engagement_pct >= 60
                            ? "text-green-400"
                            : u.avg_engagement_pct >= 30
                              ? "text-yellow-400"
                              : "text-red-400"
                        }
                      >
                        {u.avg_engagement_pct.toFixed(1)}%
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td
                    className="px-4 py-3 text-text-muted text-xs truncate max-w-[200px]"
                    title={u.top_page || ""}
                  >
                    {u.top_page ? friendlyPageName(u.top_page) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/admin/analytics/user/${u.user_id}`}
                      className="text-xs text-accent-pink hover:text-accent-pink/80 transition-colors"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : searched ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted">
            {search ? `No users found matching "${search}"` : "No users found"}
          </p>
        </div>
      ) : null}
    </>
  );
}

// ── Main Page ───────────────────────────────────────────

export default function AdminAnalyticsPage() {
  const { enable_tracking } = useConfig();
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "metrics">(
    "overview",
  );

  if (!enable_tracking) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-text-muted">
          Tracking is disabled. Enable it via{" "}
          <code className="text-accent-pink">ENABLE_TRACKING=true</code> in your
          environment configuration.
        </p>
      </div>
    );
  }

  const tabs = [
    { id: "overview" as const, label: "Overview" },
    { id: "users" as const, label: "User Activity" },
    { id: "metrics" as const, label: "Custom Metrics" },
  ];

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Analytics</span>
      </h1>

      <div className="flex gap-1 mb-6 border-b border-glass-border/50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === tab.id
                ? "text-accent-pink"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-pink rounded-full" />
            )}
          </button>
        ))}
      </div>

      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "users" && <UserActivityTab />}
      {activeTab === "metrics" && <CustomMetricsTab />}
    </div>
  );
}
