"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../../lib/api";
import { useConfig } from "../../../../../lib/config-context";
import LoadingSpinner from "../../../../../components/LoadingSpinner";
import Pagination from "../../../../../components/Pagination";

// ── Interfaces ──────────────────────────────────────────

interface EventDetailItem {
  id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
  session_id: string;
  user_email: string | null;
  page_path: string | null;
}

interface EventDetailList {
  items: EventDetailItem[];
  total: number;
  page: number;
  page_size: number;
}

interface PayloadField {
  field: string;
  type: string;
  description: string;
}

interface SourceLocation {
  file: string;
  line: number;
  snippet: string;
}

interface AutomationRef {
  id: string;
  name: string;
  status: string;
}

interface EventDefinition {
  id: string;
  name: string;
  description: string | null;
  category: string;
  payload_schema: PayloadField[];
  source_locations: SourceLocation[];
  is_system: boolean;
  is_enabled: boolean;
  created_at: string;
  fire_count_total: number;
  fire_count_30d: number;
  unique_users_30d: number;
  automation_count: number;
  automations: AutomationRef[];
}

// ── Helpers ─────────────────────────────────────────────

type DatePresetId = "24h" | "7d" | "30d" | "90d" | "custom";

const DATE_PRESETS: { id: DatePresetId; label: string }[] = [
  { id: "24h", label: "24h" },
  { id: "7d", label: "7 Days" },
  { id: "30d", label: "30 Days" },
  { id: "90d", label: "90 Days" },
  { id: "custom", label: "Custom" },
];

const CATEGORY_COLORS: Record<string, string> = {
  auth: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  browse: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  cart: "bg-green-500/20 text-green-300 border-green-500/30",
  checkout: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  engagement: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  discount: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  lifecycle: "bg-red-500/20 text-red-300 border-red-500/30",
};

const FLOW_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-300 border-green-500/30",
  paused: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  draft: "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

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
  const toLocal = (d: Date) => {
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  };
  return { from: toLocal(new Date(from)), to: toLocal(new Date(to)) };
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

function friendlyPageName(path: string): string {
  const clean = path.replace(/^\//, "");
  if (!clean) return "Home";
  return clean
    .split("/")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" / ");
}

function compactJson(data: Record<string, unknown>): string {
  const entries = Object.entries(data);
  if (entries.length === 0) return "{}";
  return entries
    .slice(0, 4)
    .map(([k, v]) => {
      const val =
        typeof v === "string"
          ? v.length > 30
            ? v.slice(0, 30) + "..."
            : v
          : JSON.stringify(v);
      return `${k}: ${val}`;
    })
    .join(", ");
}

// ── Page Component ──────────────────────────────────────

const PAGE_SIZE = 25;

export default function EventDetailPage() {
  const params = useParams();
  const eventType = decodeURIComponent(params.type as string);
  const { enable_tracking } = useConfig();

  // Registry data
  const [definition, setDefinition] = useState<EventDefinition | null>(null);
  const [defLoading, setDefLoading] = useState(true);
  const [toggling, setToggling] = useState(false);

  // Fire history data
  const [dateFrom, setDateFrom] = useState(thirtyDaysAgoLocal);
  const [dateTo, setDateTo] = useState(nowLocal);
  const [excludeBots, setExcludeBots] = useState(true);
  const [activePreset, setActivePreset] = useState<DatePresetId>("30d");

  const [data, setData] = useState<EventDetailList | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [fetchKey, setFetchKey] = useState(0);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Fetch event definition
  useEffect(() => {
    setDefLoading(true);
    apiFetch<EventDefinition>(
      `/tracking/admin/events/by-name/${encodeURIComponent(eventType)}`,
    )
      .then(setDefinition)
      .catch(() => setDefinition(null))
      .finally(() => setDefLoading(false));
  }, [eventType]);

  // Fetch fire history
  const fetchEvents = useCallback(() => {
    setLoading(true);
    const qs = new URLSearchParams();
    qs.set("event_type", eventType);
    if (dateFrom) qs.set("date_from", new Date(dateFrom).toISOString());
    if (dateTo) qs.set("date_to", new Date(dateTo).toISOString());
    qs.set("exclude_bots", String(excludeBots));
    qs.set("page", String(page));
    qs.set("page_size", String(PAGE_SIZE));

    apiFetch<EventDetailList>(
      `/tracking/admin/analytics/events/detail?${qs.toString()}`,
    )
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [eventType, dateFrom, dateTo, excludeBots, page, fetchKey]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handlePresetChange = (preset: DatePresetId) => {
    setActivePreset(preset);
    if (preset !== "custom") {
      const { from, to } = computePresetDates(preset);
      setDateFrom(from);
      setDateTo(to);
      setPage(1);
      setFetchKey((k) => k + 1);
    }
  };

  const handleApply = () => {
    setPage(1);
    setFetchKey((k) => k + 1);
  };

  const handlePageChange = (p: number) => {
    setPage(p);
    setFetchKey((k) => k + 1);
  };

  const handleToggle = async () => {
    if (!definition) return;
    setToggling(true);
    try {
      await apiFetch(`/tracking/admin/events/${definition.id}/toggle`, {
        method: "PATCH",
      });
      // Refetch definition
      const updated = await apiFetch<EventDefinition>(
        `/tracking/admin/events/by-name/${encodeURIComponent(eventType)}`,
      );
      setDefinition(updated);
    } catch {
      // silent
    } finally {
      setToggling(false);
    }
  };

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

  const maxDate = nowLocal();
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const catCls =
    CATEGORY_COLORS[definition?.category || ""] ||
    "bg-gray-500/20 text-gray-300 border-gray-500/30";

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/admin/analytics"
          className="text-text-muted hover:text-text-secondary transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-serif text-2xl font-bold">
              <span className="gradient-text">Event:</span>{" "}
              <span className="text-text-primary font-mono">{eventType}</span>
            </h1>
            {definition && (
              <>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium border ${catCls}`}
                >
                  {definition.category}
                </span>
                {definition.is_system && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/15 text-red-300 border border-red-500/20">
                    system
                  </span>
                )}
                <button
                  onClick={handleToggle}
                  disabled={toggling}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    definition.is_enabled ? "bg-green-500/60" : "bg-gray-600/60"
                  } ${toggling ? "opacity-50" : ""}`}
                  title={
                    definition.is_enabled
                      ? "Enabled (click to disable)"
                      : "Disabled (click to enable)"
                  }
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                      definition.is_enabled
                        ? "translate-x-4.5"
                        : "translate-x-1"
                    }`}
                  />
                </button>
              </>
            )}
          </div>
          {definition?.description && (
            <p className="text-sm text-text-muted mt-1">
              {definition.description}
            </p>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      {defLoading ? (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      ) : definition ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[
              {
                label: "Total Fires",
                value: definition.fire_count_total.toLocaleString(),
              },
              {
                label: "Fires (30d)",
                value: definition.fire_count_30d.toLocaleString(),
              },
              {
                label: "Unique Users (30d)",
                value: definition.unique_users_30d.toLocaleString(),
              },
              {
                label: "Automations",
                value: String(definition.automation_count),
              },
            ].map((kpi) => (
              <div key={kpi.label} className="glass rounded-xl p-4">
                <p className="text-xs text-text-muted mb-1">{kpi.label}</p>
                <p className="text-xl font-bold text-text-primary">
                  {kpi.value}
                </p>
              </div>
            ))}
          </div>

          {/* Source Code + Payload Schema */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            {/* Source Code */}
            <div className="glass rounded-xl p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">
                Source Code
              </h3>
              {definition.source_locations.length > 0 ? (
                <div className="space-y-3">
                  {definition.source_locations.map((loc, i) => (
                    <div
                      key={i}
                      className="rounded-lg bg-base-100/50 border border-glass-border/30 p-3"
                    >
                      <p className="text-xs text-text-muted mb-1.5 font-mono">
                        {loc.file}:{loc.line}
                      </p>
                      <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap leading-relaxed">
                        {loc.snippet}
                      </pre>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">
                  No source locations recorded.
                </p>
              )}
            </div>

            {/* Payload Schema */}
            <div className="glass rounded-xl p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">
                Payload Schema
              </h3>
              {definition.payload_schema.length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-text-muted text-left border-b border-glass-border/30">
                      <th className="pb-2 pr-3 font-medium">Field</th>
                      <th className="pb-2 pr-3 font-medium">Type</th>
                      <th className="pb-2 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {definition.payload_schema.map((field) => (
                      <tr
                        key={field.field}
                        className="border-t border-glass-border/20"
                      >
                        <td className="py-2 pr-3 font-mono text-accent">
                          {field.field}
                        </td>
                        <td className="py-2 pr-3 text-text-muted">
                          {field.type}
                        </td>
                        <td className="py-2 text-text-secondary">
                          {field.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-text-muted">
                  No payload (event carries no data).
                </p>
              )}
            </div>
          </div>

          {/* Automations */}
          {definition.automations.length > 0 && (
            <div className="glass rounded-xl p-5 mb-6">
              <h3 className="text-sm font-semibold text-text-primary mb-3">
                Linked Automations
              </h3>
              <div className="space-y-2">
                {definition.automations.map((flow) => {
                  const flowCls =
                    FLOW_STATUS_COLORS[flow.status] ||
                    "bg-gray-500/20 text-gray-300 border-gray-500/30";
                  return (
                    <div
                      key={flow.id}
                      className="flex items-center justify-between py-2 px-3 rounded-lg bg-base-100/30"
                    >
                      <span className="text-sm text-text-secondary">
                        {flow.name}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${flowCls}`}
                      >
                        {flow.status}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      ) : null}

      {/* Fire History */}
      <div className="glass rounded-xl p-4 mb-6 space-y-3">
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
              onChange={(e) => {
                setExcludeBots(e.target.checked);
                setPage(1);
                setFetchKey((k) => k + 1);
              }}
              className="rounded border-glass-border"
            />
            Exclude bots
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {DATE_PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => handlePresetChange(p.id)}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                activePreset === p.id
                  ? "bg-accent-pink/20 text-accent-pink border-accent-pink/30 font-medium"
                  : "text-text-muted border-glass-border hover:text-text-secondary hover:border-text-secondary/30"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {activePreset === "custom" && (
          <div className="flex flex-wrap items-end gap-3 pt-1">
            <div>
              <label className="text-xs text-text-muted block mb-1">From</label>
              <input
                type="datetime-local"
                value={dateFrom}
                max={dateTo || maxDate}
                onChange={(e) => setDateFrom(e.target.value)}
                className="bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">To</label>
              <input
                type="datetime-local"
                value={dateTo}
                max={maxDate}
                onChange={(e) => setDateTo(e.target.value)}
                className="bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
              />
            </div>
            <button
              onClick={handleApply}
              className="px-4 py-1.5 text-sm rounded-lg bg-accent-pink/20 text-accent-pink hover:bg-accent-pink/30 transition-colors"
            >
              Apply
            </button>
          </div>
        )}
      </div>

      {/* Event list */}
      {loading ? (
        <LoadingSpinner className="py-20" />
      ) : data && data.items.length > 0 ? (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted text-xs text-left border-b border-glass-border/50">
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Page</th>
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Session</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => {
                  const isExpanded = expandedRow === item.id;
                  const hasData = Object.keys(item.event_data || {}).length > 0;
                  return (
                    <tr
                      key={item.id}
                      className="border-t border-glass-border/30 hover:bg-glass-hover/30 transition-colors"
                    >
                      <td
                        className="px-4 py-3 text-text-secondary text-xs whitespace-nowrap"
                        title={new Date(item.created_at).toLocaleString()}
                      >
                        {relativeTime(item.created_at)}
                      </td>
                      <td className="px-4 py-3 text-text-secondary text-xs truncate max-w-[180px]">
                        {item.user_email || (
                          <span className="text-text-muted">(anonymous)</span>
                        )}
                      </td>
                      <td
                        className="px-4 py-3 text-text-muted text-xs truncate max-w-[180px]"
                        title={item.page_path || ""}
                      >
                        {item.page_path
                          ? friendlyPageName(item.page_path)
                          : "-"}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {hasData ? (
                          <button
                            onClick={() =>
                              setExpandedRow(isExpanded ? null : item.id)
                            }
                            className="text-left text-text-muted hover:text-text-secondary transition-colors"
                          >
                            {isExpanded ? (
                              <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary max-w-[300px]">
                                {JSON.stringify(item.event_data, null, 2)}
                              </pre>
                            ) : (
                              <span className="truncate block max-w-[250px]">
                                {compactJson(item.event_data)}
                              </span>
                            )}
                          </button>
                        ) : (
                          <span className="text-text-muted">{"{}"}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-text-muted text-xs font-mono truncate max-w-[100px]">
                        {item.session_id.slice(0, 8)}...
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-6">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={handlePageChange}
              />
            </div>
          )}
        </>
      ) : (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted">
            No {eventType} events found in this date range.
          </p>
        </div>
      )}
    </div>
  );
}
