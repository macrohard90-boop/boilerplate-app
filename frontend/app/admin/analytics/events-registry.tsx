"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";

// ── Types ────────────────────────────────────────────────

interface EventDefinition {
  id: string;
  name: string;
  description: string | null;
  category: string;
  is_system: boolean;
  is_enabled: boolean;
  created_at: string;
  fire_count_30d: number;
  last_fired: string | null;
  automation_count: number;
}

interface EventListResponse {
  definitions: EventDefinition[];
  total: number;
}

// ── Helpers ──────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  auth: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  browse: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  cart: "bg-green-500/20 text-green-300 border-green-500/30",
  checkout: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  engagement: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  discount: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  lifecycle: "bg-red-500/20 text-red-300 border-red-500/30",
};

function categoryBadge(cat: string) {
  const cls =
    CATEGORY_COLORS[cat] || "bg-gray-500/20 text-gray-300 border-gray-500/30";
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {cat}
    </span>
  );
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

// ── Component ────────────────────────────────────────────

export default function EventsRegistryTab() {
  const [definitions, setDefinitions] = useState<EventDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [search, setSearch] = useState("");
  const [toggling, setToggling] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (categoryFilter) params.set("category", categoryFilter);
      if (search) params.set("q", search);
      const data = await apiFetch<EventListResponse>(
        `/tracking/admin/events?${params.toString()}`,
      );
      setDefinitions(data.definitions);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, search]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const handleToggle = async (ev: EventDefinition) => {
    setToggling(ev.id);
    setToggleError(null);
    try {
      await apiFetch(`/tracking/admin/events/${ev.id}/toggle`, {
        method: "PATCH",
      });
      await fetchEvents();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to toggle event";
      setToggleError(msg);
    } finally {
      setToggling(null);
    }
  };

  // Derive unique categories for the filter
  const categories = Array.from(
    new Set(definitions.map((d) => d.category)),
  ).sort();

  // Group definitions by category for display
  const grouped = definitions.reduce(
    (acc, d) => {
      if (!acc[d.category]) acc[d.category] = [];
      acc[d.category].push(d);
      return acc;
    },
    {} as Record<string, EventDefinition[]>,
  );

  const sortedCategories = Object.keys(grouped).sort();

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-5">
        <input
          type="text"
          placeholder="Search events..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-glass flex-1 min-w-[200px] text-sm !py-2"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="input-glass text-sm !w-auto !py-2"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Toggle error banner */}
      {toggleError && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
          {toggleError}
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-pink" />
        </div>
      ) : definitions.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted">No events found.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {sortedCategories.map((cat) => (
            <div key={cat}>
              {/* Category header */}
              <div className="flex items-center gap-2 mb-2">
                {categoryBadge(cat)}
                <span className="text-xs text-text-muted">
                  {grouped[cat].length} event
                  {grouped[cat].length !== 1 ? "s" : ""}
                </span>
              </div>

              {/* Events table */}
              <div className="glass rounded-xl overflow-hidden">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-[22%]" />
                    <col className="w-[38%]" />
                    <col className="w-[10%]" />
                    <col className="w-[10%]" />
                    <col className="w-[10%]" />
                    <col className="w-[10%]" />
                  </colgroup>
                  <thead>
                    <tr className="text-text-muted text-xs text-left border-b border-glass-border/50">
                      <th className="px-4 py-2.5 font-medium">Event</th>
                      <th className="px-4 py-2.5 font-medium">Description</th>
                      <th className="px-4 py-2.5 font-medium text-right">
                        Fired (30d)
                      </th>
                      <th className="px-4 py-2.5 font-medium">Last Fired</th>
                      <th className="px-4 py-2.5 font-medium text-center">
                        Automations
                      </th>
                      <th className="px-4 py-2.5 font-medium text-center">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {grouped[cat].map((ev) => (
                      <tr
                        key={ev.id}
                        className="border-t border-glass-border/30 hover:bg-glass-hover/30 transition-colors"
                      >
                        <td className="px-4 py-2.5">
                          <Link
                            href={`/admin/analytics/events/${encodeURIComponent(ev.name)}`}
                            className="font-mono text-xs text-accent hover:text-accent/80 transition-colors"
                          >
                            {ev.name}
                          </Link>
                          {ev.is_system && (
                            <span className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-red-500/15 text-red-300 border border-red-500/20">
                              system
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-text-muted text-xs max-w-[300px] truncate">
                          {ev.description || "-"}
                        </td>
                        <td className="px-4 py-2.5 text-right text-text-secondary text-xs font-medium">
                          {ev.fire_count_30d.toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-text-muted text-xs">
                          {ev.last_fired ? relativeTime(ev.last_fired) : "-"}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {ev.automation_count > 0 ? (
                            <span className="px-2 py-0.5 rounded-full text-xs bg-accent-pink/20 text-accent-pink border border-accent-pink/30">
                              {ev.automation_count}
                            </span>
                          ) : (
                            <span className="text-text-muted text-xs">-</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              handleToggle(ev);
                            }}
                            disabled={toggling === ev.id}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                              ev.is_enabled
                                ? "bg-green-500/60"
                                : "bg-gray-600/60"
                            } ${toggling === ev.id ? "opacity-50" : ""}`}
                            title={
                              ev.is_enabled
                                ? "Click to disable"
                                : "Click to enable"
                            }
                          >
                            <span
                              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                                ev.is_enabled
                                  ? "translate-x-4.5"
                                  : "translate-x-1"
                              }`}
                            />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
