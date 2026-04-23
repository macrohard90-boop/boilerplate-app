"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

/**
 * Filter criteria for audience segments.
 * All fields are optional — null/undefined = not filtered.
 */
export interface SegmentFilters {
  rfm_segment?: string[];
  order_count_min?: number | null;
  order_count_max?: number | null;
  total_spent_min?: number | null;
  total_spent_max?: number | null;
  last_purchase_days_max?: number | null;
  signup_days_min?: number | null;
  signup_days_max?: number | null;
  has_orders?: boolean;
  cart_status?: string;
  has_wishlist?: boolean;
  communication_type?: string;
  is_verified?: boolean;
  // Analytics-based filters
  device_type?: string[];
  browser?: string[];
  os?: string[];
  viewed_pages?: string[];
  min_page_views?: number | null;
  min_sessions?: number | null;
  referral_source?: string;
  // Event-based filters
  event_type?: string[];
  event_min_count?: number | null;
  event_days_lookback?: number | null;
}

const RFM_OPTIONS = [
  { value: "champion", label: "Champions", color: "text-green-400" },
  { value: "loyal", label: "Loyal", color: "text-blue-400" },
  {
    value: "potential_loyalist",
    label: "Potential Loyalist",
    color: "text-cyan-400",
  },
  { value: "at_risk", label: "At Risk", color: "text-yellow-400" },
  { value: "hibernating", label: "Hibernating", color: "text-orange-400" },
  { value: "lost", label: "Lost", color: "text-red-400" },
  { value: "new", label: "New", color: "text-purple-400" },
];

/** Shape returned by GET /marketing/admin/insights/filter-options */
interface FilterOptions {
  device_types: string[];
  browsers: Array<{ value: string; count: number }>;
  operating_systems: Array<{ value: string; count: number }>;
  top_pages: Array<{ value: string; count: number }>;
  referral_sources: Array<{ value: string; count: number }>;
  event_types: Array<{ value: string; count: number }>;
}

interface SegmentBuilderProps {
  filters: SegmentFilters;
  onChange: (filters: SegmentFilters) => void;
  /** Show a live count preview */
  showPreview?: boolean;
}

export default function SegmentBuilder({
  filters,
  onChange,
  showPreview = true,
}: SegmentBuilderProps) {
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(
    null,
  );

  // Fetch dynamic filter options from analytics
  useEffect(() => {
    apiFetch<FilterOptions>("/marketing/admin/insights/filter-options")
      .then(setFilterOptions)
      .catch(() => {});
  }, []);

  // Debounced preview count
  useEffect(() => {
    if (!showPreview) return;
    const timer = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const clean = cleanFilters(filters);
        const res = await apiFetch<{ count: number }>(
          "/marketing/admin/segments/preview",
          {
            method: "POST",
            body: JSON.stringify({ filters: clean }),
          },
        );
        setPreviewCount(res.count);
      } catch {
        setPreviewCount(null);
      }
      setPreviewLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [filters, showPreview]);

  const toggleRfm = useCallback(
    (value: string) => {
      const current = filters.rfm_segment || [];
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      onChange({
        ...filters,
        rfm_segment: updated.length ? updated : undefined,
      });
    },
    [filters, onChange],
  );

  const setNumericFilter = useCallback(
    (key: keyof SegmentFilters, value: string) => {
      const num = value === "" ? null : parseInt(value, 10);
      onChange({ ...filters, [key]: isNaN(num as number) ? null : num });
    },
    [filters, onChange],
  );

  const toggleArrayFilter = useCallback(
    (
      key: "device_type" | "browser" | "os" | "viewed_pages" | "event_type",
      value: string,
    ) => {
      const current = (filters[key] as string[] | undefined) || [];
      const updated = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      onChange({ ...filters, [key]: updated.length ? updated : undefined });
    },
    [filters, onChange],
  );

  const pillBase = "text-xs px-2.5 py-1 rounded-full border transition-colors";
  const pillInactive =
    "border-glass-border text-text-muted hover:border-text-secondary";
  const pillActive: Record<string, string> = {
    pink: "border-accent-pink bg-accent-pink/20 text-accent-pink",
    blue: "border-accent-blue bg-accent-blue/20 text-accent-blue",
    purple: "border-accent-purple bg-accent-purple/20 text-accent-purple",
    green: "border-accent-green bg-accent-green/20 text-accent-green",
  };
  const pill = (active: boolean, color: string) =>
    `${pillBase} ${active ? pillActive[color] || pillActive.blue : pillInactive}`;

  return (
    <div className="space-y-4">
      {/* Live count */}
      {showPreview && (
        <div className="px-3 py-2 rounded-lg bg-glass-bg border border-glass-border text-sm">
          {previewLoading ? (
            <span className="text-text-muted">Counting...</span>
          ) : previewCount !== null ? (
            <span>
              <strong className="text-accent-blue">
                {previewCount.toLocaleString()}
              </strong>{" "}
              <span className="text-text-muted">users match this segment</span>
            </span>
          ) : (
            <span className="text-text-muted">
              Set filters to see audience count
            </span>
          )}
        </div>
      )}

      {/* RFM Segments */}
      <div>
        <label className="text-xs text-text-muted font-medium uppercase tracking-wider block mb-1.5">
          RFM Segments
        </label>
        <div className="flex flex-wrap gap-1.5">
          {RFM_OPTIONS.map((opt) => {
            const active = (filters.rfm_segment || []).includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleRfm(opt.value)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  active
                    ? "border-accent-blue bg-accent-blue/20 text-accent-blue"
                    : "border-glass-border text-text-muted hover:border-text-secondary"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Order Count */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Min Orders
          </label>
          <input
            type="number"
            min={0}
            value={filters.order_count_min ?? ""}
            onChange={(e) =>
              setNumericFilter("order_count_min", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Max Orders
          </label>
          <input
            type="number"
            min={0}
            value={filters.order_count_max ?? ""}
            onChange={(e) =>
              setNumericFilter("order_count_max", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
      </div>

      {/* Total Spent */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Min Spent (cents)
          </label>
          <input
            type="number"
            min={0}
            value={filters.total_spent_min ?? ""}
            onChange={(e) =>
              setNumericFilter("total_spent_min", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Max Spent (cents)
          </label>
          <input
            type="number"
            min={0}
            value={filters.total_spent_max ?? ""}
            onChange={(e) =>
              setNumericFilter("total_spent_max", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
      </div>

      {/* Recency */}
      <div>
        <label className="text-xs text-text-muted font-medium block mb-1">
          Purchased within last N days
        </label>
        <input
          type="number"
          min={1}
          value={filters.last_purchase_days_max ?? ""}
          onChange={(e) =>
            setNumericFilter("last_purchase_days_max", e.target.value)
          }
          placeholder="Any"
          className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
        />
      </div>

      {/* Account Age */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Signed up at least N days ago
          </label>
          <input
            type="number"
            min={0}
            value={filters.signup_days_min ?? ""}
            onChange={(e) =>
              setNumericFilter("signup_days_min", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
        <div>
          <label className="text-xs text-text-muted font-medium block mb-1">
            Signed up within last N days
          </label>
          <input
            type="number"
            min={0}
            value={filters.signup_days_max ?? ""}
            onChange={(e) =>
              setNumericFilter("signup_days_max", e.target.value)
            }
            placeholder="Any"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          />
        </div>
      </div>

      {/* Toggle filters */}
      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-1.5 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={!!filters.has_orders}
            onChange={(e) =>
              onChange({
                ...filters,
                has_orders: e.target.checked || undefined,
              })
            }
            className="rounded border-glass-border"
          />
          Has placed orders
        </label>
        <label className="flex items-center gap-1.5 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={!!filters.has_wishlist}
            onChange={(e) =>
              onChange({
                ...filters,
                has_wishlist: e.target.checked || undefined,
              })
            }
            className="rounded border-glass-border"
          />
          Has wishlist items
        </label>
        <label className="flex items-center gap-1.5 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={filters.is_verified === true}
            onChange={(e) =>
              onChange({
                ...filters,
                is_verified: e.target.checked || undefined,
              })
            }
            className="rounded border-glass-border"
          />
          Email verified
        </label>
      </div>

      {/* Cart status */}
      <div>
        <label className="text-xs text-text-muted font-medium block mb-1">
          Cart Status
        </label>
        <select
          value={filters.cart_status || ""}
          onChange={(e) =>
            onChange({ ...filters, cart_status: e.target.value || undefined })
          }
          className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
        >
          <option value="">Any</option>
          <option value="abandoned">Abandoned</option>
          <option value="active">Active</option>
          <option value="converted">Converted</option>
          <option value="recovered">Recovered</option>
        </select>
      </div>

      {/* ── Analytics Filters (dynamic from system data) ── */}
      {filterOptions && (
        <>
          <div className="pt-3 border-t border-glass-border">
            <label className="text-xs text-text-muted font-medium uppercase tracking-wider block mb-2">
              Analytics & Behavior
            </label>
          </div>

          {/* Device Type — only shown if system has device data */}
          {filterOptions.device_types.length > 0 && (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1.5">
                Device Type
              </label>
              <div className="flex flex-wrap gap-1.5">
                {filterOptions.device_types.map((dt) => {
                  const active = (filters.device_type || []).includes(dt);
                  return (
                    <button
                      key={dt}
                      type="button"
                      onClick={() => toggleArrayFilter("device_type", dt)}
                      className={pill(active, "pink")}
                    >
                      {dt}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Browser — only shown if system has browser data */}
          {filterOptions.browsers.length > 0 && (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1.5">
                Browser
              </label>
              <div className="flex flex-wrap gap-1.5">
                {filterOptions.browsers.map((b) => {
                  const active = (filters.browser || []).includes(b.value);
                  return (
                    <button
                      key={b.value}
                      type="button"
                      onClick={() => toggleArrayFilter("browser", b.value)}
                      className={pill(active, "blue")}
                    >
                      {b.value}
                      <span className="ml-1 opacity-60">
                        ({b.count.toLocaleString()})
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* OS — only shown if system has OS data */}
          {filterOptions.operating_systems.length > 0 && (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1.5">
                Operating System
              </label>
              <div className="flex flex-wrap gap-1.5">
                {filterOptions.operating_systems.map((o) => {
                  const active = (filters.os || []).includes(o.value);
                  return (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => toggleArrayFilter("os", o.value)}
                      className={pill(active, "purple")}
                    >
                      {o.value}
                      <span className="ml-1 opacity-60">
                        ({o.count.toLocaleString()})
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Viewed Pages — only shown if system has page data */}
          {filterOptions.top_pages.length > 0 && (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1.5">
                Viewed Pages (select paths)
              </label>
              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                {filterOptions.top_pages.map((p) => {
                  const active = (filters.viewed_pages || []).includes(p.value);
                  return (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => toggleArrayFilter("viewed_pages", p.value)}
                      className={pill(active, "green")}
                    >
                      <span className="font-mono">{p.value}</span>
                      <span className="ml-1 opacity-60">
                        ({p.count.toLocaleString()})
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Min page views & sessions */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1">
                Min Page Views (90d)
              </label>
              <input
                type="number"
                min={1}
                value={filters.min_page_views ?? ""}
                onChange={(e) =>
                  setNumericFilter("min_page_views", e.target.value)
                }
                placeholder="Any"
                className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1">
                Min Sessions (90d)
              </label>
              <input
                type="number"
                min={1}
                value={filters.min_sessions ?? ""}
                onChange={(e) =>
                  setNumericFilter("min_sessions", e.target.value)
                }
                placeholder="Any"
                className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
              />
            </div>
          </div>

          {/* Referral source — dynamic dropdown if system has data */}
          {filterOptions.referral_sources.length > 0 ? (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1">
                Referral Source
              </label>
              <select
                value={filters.referral_source || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    referral_source: e.target.value || undefined,
                  })
                }
                className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
              >
                <option value="">Any</option>
                {filterOptions.referral_sources.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.value} ({r.count.toLocaleString()})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="text-xs text-text-muted font-medium block mb-1">
                Referral Source
              </label>
              <input
                type="text"
                value={filters.referral_source || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    referral_source: e.target.value || undefined,
                  })
                }
                placeholder="e.g., google.com"
                className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
              />
            </div>
          )}

          {/* ── Event Behavior Filters ── */}
          {filterOptions.event_types.length > 0 && (
            <>
              <div className="pt-3 border-t border-glass-border">
                <label className="text-xs text-text-muted font-medium uppercase tracking-wider block mb-2">
                  Event Behavior
                </label>
              </div>

              {/* Event type pills */}
              <div>
                <label className="text-xs text-text-muted font-medium block mb-1.5">
                  Event Type
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                  {filterOptions.event_types.map((ev) => {
                    const active = (filters.event_type || []).includes(
                      ev.value,
                    );
                    return (
                      <button
                        key={ev.value}
                        type="button"
                        onClick={() =>
                          toggleArrayFilter("event_type", ev.value)
                        }
                        className={pill(active, "pink")}
                      >
                        {ev.value.replace(/_/g, " ")}
                        <span className="ml-1 opacity-60">
                          ({ev.count.toLocaleString()})
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Min count + lookback */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-text-muted font-medium block mb-1">
                    Min Event Count
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={filters.event_min_count ?? ""}
                    onChange={(e) =>
                      setNumericFilter("event_min_count", e.target.value)
                    }
                    placeholder="Any"
                    className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                  />
                </div>
                <div>
                  <label className="text-xs text-text-muted font-medium block mb-1">
                    Within Last N Days
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={filters.event_days_lookback ?? ""}
                    onChange={(e) =>
                      setNumericFilter("event_days_lookback", e.target.value)
                    }
                    placeholder="Any"
                    className="w-full px-2.5 py-1.5 text-sm rounded-md border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                  />
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

/** Remove null/undefined/empty values from filters before sending to API */
export function cleanFilters(filters: SegmentFilters): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    if (value === false && key !== "is_verified") continue;
    result[key] = value;
  }
  return result;
}
