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

// ── Helpers ─────────────────────────────────────────────

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

  const [dateFrom, setDateFrom] = useState(thirtyDaysAgoLocal);
  const [dateTo, setDateTo] = useState(nowLocal);
  const [excludeBots, setExcludeBots] = useState(true);
  const [activePreset, setActivePreset] = useState<DatePresetId>("30d");

  const [data, setData] = useState<EventDetailList | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [fetchKey, setFetchKey] = useState(0);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

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

  return (
    <div>
      {/* Header with back link */}
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
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Events:</span>{" "}
          <span className="text-text-primary">{eventType}</span>
          {data && (
            <span className="text-sm font-normal text-text-muted ml-3">
              {data.total.toLocaleString()} total
            </span>
          )}
        </h1>
      </div>

      {/* Filter bar */}
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
