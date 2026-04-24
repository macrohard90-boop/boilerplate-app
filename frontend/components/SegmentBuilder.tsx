"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

/**
 * Filter criteria for audience segments.
 * All fields are optional — null/undefined = not filtered.
 */
export interface SegmentFilters {
  user_role?: string[];
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

/* ── Inline Chart Components ── */

function KpiCard({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format: "number" | "currency" | "decimal";
}) {
  let display: string;
  if (format === "currency") display = `$${(value / 100).toFixed(2)}`;
  else if (format === "decimal") display = value.toFixed(1);
  else display = value.toLocaleString();

  return (
    <div className="glass rounded-lg p-3">
      <div className="text-[10px] text-text-muted uppercase tracking-wider">
        {label}
      </div>
      <div className="text-lg font-semibold text-text-primary mt-1">
        {display}
      </div>
    </div>
  );
}

function RfmBars({
  data,
}: {
  data: Array<{ segment: string; count: number }>;
}) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const colors: Record<string, string> = {
    champion: "bg-accent-green",
    loyal: "bg-accent-blue",
    potential_loyalist: "bg-accent-purple",
    new: "bg-accent-cyan",
    at_risk: "bg-accent-yellow",
    hibernating: "bg-accent-orange",
    lost: "bg-accent-pink",
    unscored: "bg-glass-border",
  };
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.segment} className="flex items-center gap-2">
          <span className="text-[10px] text-text-muted w-24 text-right capitalize">
            {d.segment.replace("_", " ")}
          </span>
          <div className="flex-1 h-4 bg-glass-hover rounded overflow-hidden">
            <div
              className={`h-full rounded ${colors[d.segment] || "bg-accent-blue"}`}
              style={{ width: `${(d.count / max) * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-text-muted w-8">{d.count}</span>
        </div>
      ))}
    </div>
  );
}

function DeviceDonut({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0)
    return (
      <div className="text-xs text-text-muted text-center py-4">No data</div>
    );

  const colors = ["#60a5fa", "#34d399", "#f59e0b", "#a78bfa", "#f87171"];
  const radius = 40,
    cx = 60,
    cy = 60,
    circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 120 120" className="w-24 h-24 shrink-0">
        {entries.map(([key, val], i) => {
          const pct = val / total;
          const dash = pct * circumference;
          const gap = circumference - dash;
          const thisOffset = offset;
          offset += dash;
          return (
            <circle
              key={key}
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke={colors[i % colors.length]}
              strokeWidth="16"
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={-thisOffset}
              transform={`rotate(-90 ${cx} ${cy})`}
            />
          );
        })}
      </svg>
      <div className="space-y-1">
        {entries.map(([key, val], i) => (
          <div key={key} className="flex items-center gap-1.5 text-[10px]">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: colors[i % colors.length] }}
            />
            <span className="text-text-secondary capitalize">{key}</span>
            <span className="text-text-muted">({val})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PageBars({ data }: { data: Array<{ path: string; views: number }> }) {
  const max = Math.max(...data.map((d) => d.views), 1);
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.path} className="flex items-center gap-2">
          <span
            className="text-[10px] text-text-muted w-32 text-right truncate"
            title={d.path}
          >
            {d.path}
          </span>
          <div className="flex-1 h-4 bg-glass-hover rounded overflow-hidden">
            <div
              className="h-full rounded bg-accent-blue"
              style={{ width: `${(d.views / max) * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-text-muted w-10">{d.views}</span>
        </div>
      ))}
      {data.length === 0 && (
        <div className="text-xs text-text-muted text-center py-2">
          No page data
        </div>
      )}
    </div>
  );
}

function ActivityChart({
  data,
}: {
  data: Array<{ date: string; views: number }>;
}) {
  if (data.length === 0)
    return (
      <div className="text-xs text-text-muted text-center py-4">
        No activity data
      </div>
    );

  const width = 320,
    height = 120,
    padX = 30,
    padY = 20;
  const maxViews = Math.max(...data.map((d) => d.views), 1);
  const plotW = width - 2 * padX,
    plotH = height - 2 * padY;

  const points = data
    .map((d, i) => {
      const x =
        padX + (data.length > 1 ? (i / (data.length - 1)) * plotW : plotW / 2);
      const y = padY + plotH - (d.views / maxViews) * plotH;
      return `${x},${y}`;
    })
    .join(" ");

  // Fill area
  const areaPoints = `${padX},${padY + plotH} ${points} ${padX + (data.length > 1 ? plotW : plotW / 2)},${padY + plotH}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <line
          key={f}
          x1={padX}
          x2={width - padX}
          y1={padY + plotH * (1 - f)}
          y2={padY + plotH * (1 - f)}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="0.5"
        />
      ))}
      {/* Area fill */}
      <polygon points={areaPoints} fill="rgba(96,165,250,0.1)" />
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="#60a5fa"
        strokeWidth="1.5"
      />
      {/* Y-axis labels */}
      <text
        x={padX - 4}
        y={padY + 4}
        textAnchor="end"
        className="fill-text-muted"
        fontSize="8"
      >
        {maxViews}
      </text>
      <text
        x={padX - 4}
        y={padY + plotH + 3}
        textAnchor="end"
        className="fill-text-muted"
        fontSize="8"
      >
        0
      </text>
      {/* X-axis labels (first and last) */}
      {data.length > 0 && (
        <>
          <text
            x={padX}
            y={height - 2}
            textAnchor="start"
            className="fill-text-muted"
            fontSize="7"
          >
            {data[0].date.slice(5)}
          </text>
          <text
            x={width - padX}
            y={height - 2}
            textAnchor="end"
            className="fill-text-muted"
            fontSize="7"
          >
            {data[data.length - 1].date.slice(5)}
          </text>
        </>
      )}
    </svg>
  );
}

/** Shape returned by GET /marketing/admin/insights/filter-options */
interface FilterOptions {
  device_types: string[];
  browsers: Array<{ value: string; count: number }>;
  operating_systems: Array<{ value: string; count: number }>;
  top_pages: Array<{ value: string; count: number }>;
  referral_sources: Array<{ value: string; count: number }>;
  event_types: Array<{ value: string; count: number }>;
}

interface DashboardData {
  kpis: {
    total_users: number;
    avg_order_value: number;
    total_revenue: number;
    avg_sessions: number;
  };
  rfm_distribution: Array<{ segment: string; count: number }>;
  device_breakdown: Record<string, number>;
  top_pages: Array<{ path: string; views: number }>;
  activity_timeline: Array<{ date: string; views: number }>;
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
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);

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

  // Debounced dashboard fetch
  useEffect(() => {
    if (!showPreview) {
      setDashboard(null);
      return;
    }
    const clean = cleanFilters(filters);
    if (Object.keys(clean).length === 0) {
      setDashboard(null);
      return;
    }
    setDashboardLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await apiFetch<DashboardData>(
          "/marketing/admin/segments/dashboard",
          {
            method: "POST",
            body: JSON.stringify({ filters: clean }),
          },
        );
        setDashboard(res);
      } catch {
        setDashboard(null);
      }
      setDashboardLoading(false);
    }, 600);
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
      key:
        | "user_role"
        | "device_type"
        | "browser"
        | "os"
        | "viewed_pages"
        | "event_type",
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

      {/* User Role */}
      <div>
        <label className="text-xs text-text-muted font-medium uppercase tracking-wider block mb-1.5">
          User Role
        </label>
        <div className="flex flex-wrap gap-1.5">
          {["customer", "merchant", "admin"].map((role) => {
            const active = (filters.user_role || []).includes(role);
            return (
              <button
                key={role}
                type="button"
                onClick={() => toggleArrayFilter("user_role", role)}
                className={pill(active, "purple")}
              >
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </button>
            );
          })}
        </div>
      </div>

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

      {/* Audience Dashboard */}
      {dashboardLoading && !dashboard && (
        <div className="mt-6 flex items-center justify-center py-8">
          <div className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
          <span className="ml-2 text-xs text-text-muted">
            Loading dashboard...
          </span>
        </div>
      )}
      {dashboard && (
        <div className="mt-6 space-y-4">
          <h3 className="text-xs text-text-muted font-medium uppercase tracking-wider">
            Audience Dashboard
          </h3>

          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard
              label="Total Users"
              value={dashboard.kpis.total_users}
              format="number"
            />
            <KpiCard
              label="Avg Order Value"
              value={dashboard.kpis.avg_order_value}
              format="currency"
            />
            <KpiCard
              label="Total Revenue"
              value={dashboard.kpis.total_revenue}
              format="currency"
            />
            <KpiCard
              label="Avg Sessions"
              value={dashboard.kpis.avg_sessions}
              format="decimal"
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* RFM Distribution - horizontal bars */}
            <div className="glass rounded-xl p-4">
              <h4 className="text-xs text-text-muted font-medium mb-3">
                RFM Distribution
              </h4>
              <RfmBars data={dashboard.rfm_distribution} />
            </div>

            {/* Device Breakdown - donut chart */}
            <div className="glass rounded-xl p-4">
              <h4 className="text-xs text-text-muted font-medium mb-3">
                Device Breakdown
              </h4>
              <DeviceDonut data={dashboard.device_breakdown} />
            </div>

            {/* Top Pages - horizontal bars */}
            <div className="glass rounded-xl p-4">
              <h4 className="text-xs text-text-muted font-medium mb-3">
                Top Pages (90d)
              </h4>
              <PageBars data={dashboard.top_pages} />
            </div>

            {/* Activity Timeline - line chart */}
            <div className="glass rounded-xl p-4">
              <h4 className="text-xs text-text-muted font-medium mb-3">
                Activity (30d)
              </h4>
              <ActivityChart data={dashboard.activity_timeline} />
            </div>
          </div>
        </div>
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
