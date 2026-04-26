"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-sql";
import { apiFetch } from "../../../lib/api";
import { useConfig } from "../../../lib/config-context";
import LoadingSpinner from "../../../components/LoadingSpinner";

const AreaSparkChart = dynamic(
  () => import("../../../components/charts/AreaSparkChart"),
  { ssr: false },
);
const HorizontalBarChart = dynamic(
  () => import("../../../components/charts/HorizontalBarChart"),
  { ssr: false },
);

// ── Types ────────────────────────────────────────────────

interface SavedMetric {
  id: string;
  name: string;
  description: string;
  sql_query: string;
  visualization_type: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  group_name: string | null;
  display_order: number;
  is_audience: boolean;
}

interface QueryResult {
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  cached: boolean;
}

// ── Schema reference ─────────────────────────────────────

const ANALYTICS_SCHEMA = [
  {
    table: "core.users",
    columns: [
      "id",
      "email",
      "first_name",
      "last_name",
      "is_verified",
      "is_active",
      "created_at",
      "updated_at",
    ],
  },
  {
    table: "analytics.page_views",
    columns: [
      "id",
      "user_id",
      "session_id",
      "path",
      "referrer",
      "duration_ms",
      "trigger",
      "created_at",
    ],
  },
  {
    table: "analytics.analytics_sessions",
    columns: [
      "id",
      "user_id",
      "session_id",
      "started_at",
      "ended_at",
      "page_count",
    ],
  },
  {
    table: "analytics.events",
    columns: [
      "id",
      "user_id",
      "session_id",
      "event_type",
      "event_data",
      "created_at",
    ],
  },
  {
    table: "analytics.user_agents",
    columns: [
      "id",
      "session_id",
      "raw",
      "browser",
      "browser_version",
      "os",
      "device_type",
    ],
  },
  {
    table: "analytics.referral_sources",
    columns: ["id", "session_id", "source", "medium", "campaign"],
  },
  {
    table: "analytics.utm_tracking",
    columns: [
      "id",
      "session_id",
      "utm_source",
      "utm_medium",
      "utm_campaign",
      "utm_content",
      "utm_term",
    ],
  },
];

// ── Audience metric type (from /audience-metrics endpoint) ──

interface AudienceMetric {
  id: string;
  name: string;
  description: string;
  group_name: string | null;
  display_order: number;
  user_count: number;
  segment_id: string | null;
  audience_filters: Record<string, unknown> | null;
  preset_key: string | null;
}

// ── Audience dashboard type ───────────────────────────────

interface AudienceDashboard {
  metric_name: string;
  metric_description: string;
  kpis: {
    total_users: number;
    avg_order_value: number;
    total_revenue: number;
    avg_sessions: number;
  };
  rfm_distribution: { segment: string; count: number }[];
  device_breakdown: Record<string, number>;
  browser_breakdown: Record<string, number>;
  os_breakdown: Record<string, number>;
  top_pages: { path: string; views: number }[];
  top_products: { name: string; purchase_count: number }[];
  activity_timeline: { day: string; views: number }[];
  avg_sessions_per_user: number;
  avg_page_views_per_user: number;
  pct_of_total: number;
}

// ── Starter templates ────────────────────────────────────

const STARTER_QUERIES = [
  {
    name: "Pageviews by Day (30d)",
    sql: `SELECT DATE(created_at) AS day, COUNT(*) AS pageviews
FROM analytics.page_views
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day`,
    visualization: "line_chart",
  },
  {
    name: "Top 10 Pages",
    sql: `SELECT path, COUNT(*) AS views
FROM analytics.page_views
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY path
ORDER BY views DESC
LIMIT 10`,
    visualization: "bar_chart",
  },
  {
    name: "Unique Visitors (30d)",
    sql: `SELECT COUNT(DISTINCT COALESCE(CAST(user_id AS text), session_id)) AS unique_visitors
FROM analytics.page_views
WHERE created_at >= NOW() - INTERVAL '30 days'`,
    visualization: "number",
  },
  {
    name: "Events by Type",
    sql: `SELECT event_type, COUNT(*) AS count
FROM analytics.events
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY event_type
ORDER BY count DESC`,
    visualization: "bar_chart",
  },
];

// ── Viz icon helper ──────────────────────────────────────

function VizIcon({ type }: { type: string }) {
  switch (type) {
    case "line_chart":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case "bar_chart":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <rect x="3" y="12" width="4" height="8" rx="1" />
          <rect x="10" y="8" width="4" height="12" rx="1" />
          <rect x="17" y="4" width="4" height="16" rx="1" />
        </svg>
      );
    case "number":
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M4 17h16M4 7h16M7 3l-3 18M17 3l-3 18" />
        </svg>
      );
    default:
      return (
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M9 3v18" />
        </svg>
      );
  }
}

// ── Results renderer ─────────────────────────────────────

function ResultsView({
  result,
  vizType,
}: {
  result: QueryResult;
  vizType: string;
}) {
  if (result.row_count === 0) {
    return (
      <p className="text-text-muted text-sm py-6 text-center">
        Query returned no results.
      </p>
    );
  }

  // Number: single KPI
  if (vizType === "number") {
    const val = result.rows[0]?.[0];
    return (
      <div className="text-center py-8">
        <p className="text-5xl font-bold gradient-text tabular-nums">
          {typeof val === "number" ? val.toLocaleString() : String(val ?? "—")}
        </p>
        {result.columns[0] && (
          <p className="text-text-muted text-sm mt-2">{result.columns[0]}</p>
        )}
      </div>
    );
  }

  // Line chart: first column = label, second = value
  if (vizType === "line_chart" && result.columns.length >= 2) {
    const data = result.rows.map((row) => ({
      label: String(row[0] ?? ""),
      value: Number(row[1]) || 0,
      ...(result.columns.length >= 3 ? { value2: Number(row[2]) || 0 } : {}),
    }));
    return (
      <AreaSparkChart
        data={data}
        color="#ec4899"
        color2={result.columns.length >= 3 ? "#a855f7" : undefined}
        height={300}
        valueLabel={result.columns[1]}
        valueLabel2={result.columns.length >= 3 ? result.columns[2] : undefined}
      />
    );
  }

  // Bar chart: first column = label, second = value
  if (vizType === "bar_chart" && result.columns.length >= 2) {
    const data = result.rows.map((row) => ({
      label: String(row[0] ?? ""),
      value: Number(row[1]) || 0,
    }));
    return (
      <HorizontalBarChart
        data={data}
        color="#a855f7"
        formatValue={(v) => v.toLocaleString()}
      />
    );
  }

  // Default: table
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-glass-border/50">
            {result.columns.map((col) => (
              <th
                key={col}
                className="text-left text-text-muted font-medium py-2 px-3"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-glass-border/20 hover:bg-glass-bg/30"
            >
              {row.map((cell, j) => (
                <td key={j} className="py-2 px-3 text-text-secondary">
                  {cell === null ? (
                    <span className="text-text-muted italic">null</span>
                  ) : typeof cell === "object" ? (
                    <code className="text-xs bg-glass-bg/50 rounded px-1 py-0.5">
                      {JSON.stringify(cell)}
                    </code>
                  ) : (
                    String(cell)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {result.truncated && (
        <p className="text-text-muted text-xs mt-2 text-center">
          Results truncated to 1,000 rows.
        </p>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────

export default function CustomMetricsTab() {
  const { enable_marketing } = useConfig();

  // Audience metrics state (unified with campaign wizard)
  const [audienceMetrics, setAudienceMetrics] = useState<AudienceMetric[]>([]);
  const [seeding, setSeeding] = useState(false);

  // List view state
  const [metrics, setMetrics] = useState<SavedMetric[]>([]);
  const [loading, setLoading] = useState(true);

  // Editor view state
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [sql, setSql] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [vizType, setVizType] = useState("table");
  const [showSchema, setShowSchema] = useState(false);

  const [groupName, setGroupName] = useState("");
  const [isAudience, setIsAudience] = useState(false);

  // Execution state
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Inline run state for saved metrics list
  const [runningMetricId, setRunningMetricId] = useState<string | null>(null);
  const [metricResults, setMetricResults] = useState<
    Record<string, QueryResult>
  >({});

  // Grouping and drag-and-drop state
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    new Set(),
  );
  const [dragItem, setDragItem] = useState<string | null>(null);
  const [dragOverItem, setDragOverItem] = useState<string | null>(null);

  // Audience dashboard view state
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [dashboardData, setDashboardData] = useState<AudienceDashboard | null>(
    null,
  );
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardMetricId, setDashboardMetricId] = useState<string | null>(
    null,
  );

  // ── Fetch saved metrics ──────────────────────────────

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await apiFetch<{ metrics: SavedMetric[]; total: number }>(
        "/tracking/admin/metrics",
      );
      setMetrics(data.metrics || []);
    } catch {
      // Silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // ── Fetch audience metrics (shared CRUD with campaign wizard) ──

  const fetchAudienceMetrics = useCallback(async () => {
    if (!enable_marketing) return;
    try {
      const data = await apiFetch<{
        metrics: AudienceMetric[];
        total: number;
      }>("/tracking/admin/metrics/audience-metrics");
      setAudienceMetrics(data.metrics ?? []);
    } catch {
      // Silent
    }
  }, [enable_marketing]);

  useEffect(() => {
    fetchAudienceMetrics();
  }, [fetchAudienceMetrics]);

  const seedPresets = async () => {
    setSeeding(true);
    try {
      await apiFetch("/tracking/admin/metrics/seed-audience-presets", {
        method: "POST",
      });
      await fetchAudienceMetrics();
      await fetchMetrics();
    } catch {
      // Silent
    } finally {
      setSeeding(false);
    }
  };

  // Group audience metrics by group_name
  const audienceGroups = useMemo(() => {
    if (audienceMetrics.length === 0) return [];
    const groups = new Map<string, AudienceMetric[]>();
    for (const m of audienceMetrics) {
      const key = m.group_name || "Ungrouped";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(m);
    }
    return Array.from(groups.entries())
      .sort(([a], [b]) => {
        if (a === "Ungrouped") return 1;
        if (b === "Ungrouped") return -1;
        return a.localeCompare(b);
      })
      .map(([name, items]) => ({
        name,
        items: items.sort((a, b) => a.display_order - b.display_order),
      }));
  }, [audienceMetrics]);

  // ── Grouped metrics ────────────────────────────────

  const existingGroups = useMemo(
    () =>
      Array.from(
        new Set(metrics.map((m) => m.group_name).filter(Boolean) as string[]),
      ),
    [metrics],
  );

  // When marketing is enabled, audience metrics are shown in the dedicated
  // Audience Segments section above — filter them out here to avoid duplication.
  const displayMetrics = useMemo(
    () => (enable_marketing ? metrics.filter((m) => !m.is_audience) : metrics),
    [metrics, enable_marketing],
  );

  const groupedMetrics = useMemo(() => {
    const groups = new Map<string, SavedMetric[]>();
    for (const m of displayMetrics) {
      const key = m.group_name || "__ungrouped__";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(m);
    }
    Array.from(groups.values()).forEach((items) => {
      items.sort((a, b) => a.display_order - b.display_order);
    });
    const sortedKeys = Array.from(groups.keys()).sort((a, b) => {
      if (a === "__ungrouped__") return 1;
      if (b === "__ungrouped__") return -1;
      return a.localeCompare(b);
    });
    return sortedKeys.map((key) => ({
      key,
      displayName: key === "__ungrouped__" ? "Ungrouped" : key,
      metrics: groups.get(key)!,
    }));
  }, [displayMetrics]);

  // ── Drag-and-drop handlers ─────────────────────────

  const handleDragStart = (e: React.DragEvent, metricId: string) => {
    setDragItem(metricId);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", metricId);
  };

  const handleDragOver = (e: React.DragEvent, metricId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverItem(metricId);
  };

  const handleDragOverGroup = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverItem(null);
  };

  const handleDrop = async (
    e: React.DragEvent,
    targetMetricId: string | null,
    targetGroupKey: string,
  ) => {
    e.preventDefault();
    if (!dragItem) return;
    const targetGroup =
      targetGroupKey === "__ungrouped__" ? null : targetGroupKey;
    const dragged = metrics.find((m) => m.id === dragItem);
    if (!dragged) return;

    const without = metrics.filter((m) => m.id !== dragItem);
    const updatedDragged = { ...dragged, group_name: targetGroup };

    if (targetMetricId) {
      const idx = without.findIndex((m) => m.id === targetMetricId);
      without.splice(idx, 0, updatedDragged);
    } else {
      const groupItems = without.filter(
        (m) => (m.group_name || null) === targetGroup,
      );
      const last = groupItems[groupItems.length - 1];
      const insertIdx = last ? without.indexOf(last) + 1 : without.length;
      without.splice(insertIdx, 0, updatedDragged);
    }

    // Recalculate display_order per group
    const counters = new Map<string | null, number>();
    const reordered = without.map((m) => {
      const gk = m.group_name || null;
      const order = counters.get(gk) || 0;
      counters.set(gk, order + 1);
      return { ...m, display_order: order };
    });

    setMetrics(reordered);
    setDragItem(null);
    setDragOverItem(null);

    // Persist
    try {
      await apiFetch("/tracking/admin/metrics/reorder", {
        method: "PUT",
        body: JSON.stringify({
          items: reordered.map((m) => ({
            id: m.id,
            group_name: m.group_name,
            display_order: m.display_order,
          })),
        }),
      });
    } catch {
      fetchMetrics();
    }
  };

  const handleDragEnd = () => {
    setDragItem(null);
    setDragOverItem(null);
  };

  // ── Execute query ────────────────────────────────────

  const runQuery = async (query?: string) => {
    const q = query || sql;
    if (!q.trim()) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const data = await apiFetch<QueryResult>(
        "/tracking/admin/metrics/execute",
        {
          method: "POST",
          body: JSON.stringify({ sql_query: q }),
        },
      );
      setResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Query execution failed";
      setError(msg);
    } finally {
      setRunning(false);
    }
  };

  // ── Run saved metric inline ──────────────────────────

  const runMetricInline = async (metric: SavedMetric) => {
    setRunningMetricId(metric.id);
    try {
      const data = await apiFetch<QueryResult>(
        `/tracking/admin/metrics/${metric.id}/run`,
        { method: "POST" },
      );
      setMetricResults((prev) => ({ ...prev, [metric.id]: data }));
    } catch {
      // Silent
    } finally {
      setRunningMetricId(null);
    }
  };

  // ── Save metric ──────────────────────────────────────

  const saveMetric = async () => {
    if (!name.trim() || !sql.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        await apiFetch(`/tracking/admin/metrics/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            name,
            description,
            sql_query: sql,
            visualization_type: vizType,
            group_name: groupName || "",
            is_audience: isAudience,
          }),
        });
      } else {
        await apiFetch("/tracking/admin/metrics", {
          method: "POST",
          body: JSON.stringify({
            name,
            description,
            sql_query: sql,
            visualization_type: vizType,
            group_name: groupName || null,
            is_audience: isAudience,
          }),
        });
      }
      setEditorOpen(false);
      resetEditor();
      fetchMetrics();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save metric";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  // ── Delete metric ────────────────────────────────────

  const deleteMetric = async (id: string) => {
    try {
      await apiFetch(`/tracking/admin/metrics/${id}`, { method: "DELETE" });
      setMetrics((prev) => prev.filter((m) => m.id !== id));
      setMetricResults((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch {
      // Silent
    }
  };

  // ── Editor helpers ───────────────────────────────────

  const resetEditor = () => {
    setSql("");
    setName("");
    setDescription("");
    setVizType("table");
    setGroupName("");
    setIsAudience(false);
    setEditingId(null);
    setResult(null);
    setError("");
  };

  const openNew = () => {
    resetEditor();
    setEditorOpen(true);
  };

  const openEdit = (m: SavedMetric) => {
    setSql(m.sql_query);
    setName(m.name);
    setDescription(m.description);
    setVizType(m.visualization_type);
    setGroupName(m.group_name || "");
    setIsAudience(m.is_audience || false);
    setEditingId(m.id);
    setResult(null);
    setError("");
    setEditorOpen(true);
  };

  const loadStarter = (starter: (typeof STARTER_QUERIES)[0]) => {
    setSql(starter.sql);
    setName(starter.name);
    setVizType(starter.visualization);
    setDescription("");
    setEditingId(null);
    setResult(null);
    setError("");
    setEditorOpen(true);
  };

  // ── Audience dashboard ─────────────────────────────────

  const openDashboard = async (metricId: string) => {
    setDashboardOpen(true);
    setDashboardLoading(true);
    setDashboardData(null);
    setDashboardMetricId(metricId);
    try {
      const data = await apiFetch<AudienceDashboard>(
        `/tracking/admin/metrics/${metricId}/audience-dashboard`,
      );
      setDashboardData(data);
    } catch {
      setDashboardData(null);
    } finally {
      setDashboardLoading(false);
    }
  };

  const closeDashboard = () => {
    setDashboardOpen(false);
    setDashboardData(null);
    setDashboardMetricId(null);
  };

  // ── Highlight function for PrismJS ───────────────────

  const highlight = (code: string) =>
    Prism.highlight(code, Prism.languages.sql, "sql");

  // ── Render: Audience Dashboard View ─────────────────

  if (dashboardOpen) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={closeDashboard}
              className="text-text-muted hover:text-text-secondary text-sm flex items-center gap-1"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polyline points="15 18 9 12 15 6" />
              </svg>
              Back
            </button>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                {dashboardData?.metric_name ?? "Loading..."}
              </h2>
              {dashboardData?.metric_description && (
                <p className="text-xs text-text-muted mt-0.5">
                  {dashboardData.metric_description}
                </p>
              )}
            </div>
          </div>
          {dashboardMetricId && (
            <button
              onClick={() => {
                const metric = metrics.find(
                  (mm) => mm.id === dashboardMetricId,
                );
                if (metric) {
                  closeDashboard();
                  openEdit(metric);
                }
              }}
              className="btn-secondary text-xs"
            >
              Edit SQL
            </button>
          )}
        </div>

        {dashboardLoading && (
          <div className="flex items-center justify-center py-16">
            <LoadingSpinner />
          </div>
        )}

        {!dashboardLoading && !dashboardData && (
          <div className="glass rounded-xl p-8 text-center">
            <p className="text-text-muted text-sm">
              Failed to load dashboard data.
            </p>
          </div>
        )}

        {dashboardData && dashboardData.kpis.total_users === 0 && (
          <div className="glass rounded-xl p-8 text-center">
            <p className="text-text-muted text-sm">
              No users match this audience segment.
            </p>
          </div>
        )}

        {dashboardData && dashboardData.kpis.total_users > 0 && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="glass rounded-xl p-4">
                <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  Total Users
                </p>
                <p className="text-2xl font-bold text-text-primary tabular-nums mt-1">
                  {dashboardData.kpis.total_users.toLocaleString()}
                </p>
                <p className="text-xs text-accent-purple mt-1">
                  {dashboardData.pct_of_total}% of total
                </p>
              </div>
              <div className="glass rounded-xl p-4">
                <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  Avg Order Value
                </p>
                <p className="text-2xl font-bold text-text-primary tabular-nums mt-1">
                  $
                  {dashboardData.kpis.avg_order_value.toLocaleString(
                    undefined,
                    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
                  )}
                </p>
              </div>
              <div className="glass rounded-xl p-4">
                <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  Total Revenue
                </p>
                <p className="text-2xl font-bold text-text-primary tabular-nums mt-1">
                  $
                  {(dashboardData.kpis.total_revenue / 100).toLocaleString(
                    undefined,
                    { minimumFractionDigits: 2, maximumFractionDigits: 2 },
                  )}
                </p>
              </div>
              <div className="glass rounded-xl p-4">
                <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  Avg Sessions
                </p>
                <p className="text-2xl font-bold text-text-primary tabular-nums mt-1">
                  {dashboardData.kpis.avg_sessions}
                </p>
                <p className="text-xs text-text-muted mt-1">
                  {dashboardData.avg_page_views_per_user} avg page views
                </p>
              </div>
            </div>

            {/* RFM Distribution + Device Breakdown */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  RFM Distribution
                </h3>
                {dashboardData.rfm_distribution.length > 0 ? (
                  <HorizontalBarChart
                    data={dashboardData.rfm_distribution.map((r) => ({
                      label: r.segment,
                      value: r.count,
                    }))}
                    color="#a855f7"
                    formatValue={(v) => v.toLocaleString()}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  Device Breakdown
                </h3>
                {Object.keys(dashboardData.device_breakdown).length > 0 ? (
                  <HorizontalBarChart
                    data={Object.entries(dashboardData.device_breakdown).map(
                      ([label, value]) => ({ label, value }),
                    )}
                    color="#ec4899"
                    formatValue={(v) => v.toLocaleString()}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
            </div>

            {/* Top Pages + Top Products */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  Top Pages
                </h3>
                {dashboardData.top_pages.length > 0 ? (
                  <HorizontalBarChart
                    data={dashboardData.top_pages.map((p) => ({
                      label: p.path,
                      value: p.views,
                    }))}
                    color="#3b82f6"
                    formatValue={(v) => v.toLocaleString() + " views"}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  Top Products
                </h3>
                {dashboardData.top_products.length > 0 ? (
                  <HorizontalBarChart
                    data={dashboardData.top_products.map((p) => ({
                      label: p.name,
                      value: p.purchase_count,
                    }))}
                    color="#10b981"
                    formatValue={(v) => v.toLocaleString() + " purchases"}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
            </div>

            {/* Activity Timeline */}
            {dashboardData.activity_timeline.length > 0 && (
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  Activity Timeline (30 days)
                </h3>
                <AreaSparkChart
                  data={dashboardData.activity_timeline.map((t) => ({
                    label: t.day,
                    value: t.views,
                  }))}
                  color="#ec4899"
                  height={200}
                  valueLabel="Page Views"
                />
              </div>
            )}

            {/* Browser + OS Breakdown */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  Browser Breakdown
                </h3>
                {Object.keys(dashboardData.browser_breakdown).length > 0 ? (
                  <HorizontalBarChart
                    data={Object.entries(dashboardData.browser_breakdown).map(
                      ([label, value]) => ({ label, value }),
                    )}
                    color="#f59e0b"
                    formatValue={(v) => v.toLocaleString()}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  OS Breakdown
                </h3>
                {Object.keys(dashboardData.os_breakdown).length > 0 ? (
                  <HorizontalBarChart
                    data={Object.entries(dashboardData.os_breakdown).map(
                      ([label, value]) => ({ label, value }),
                    )}
                    color="#8b5cf6"
                    formatValue={(v) => v.toLocaleString()}
                  />
                ) : (
                  <p className="text-sm text-text-muted py-4">No data</p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    );
  }

  // ── Render: Editor View ──────────────────────────────

  if (editorOpen) {
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">
            {editingId ? "Edit Metric" : "New Custom Metric"}
          </h2>
          <button
            onClick={() => {
              setEditorOpen(false);
              resetEditor();
            }}
            className="text-text-muted hover:text-text-secondary text-sm"
          >
            Cancel
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* SQL Editor (2/3 width) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-glass-border/50">
                <span className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  SQL Query
                </span>
                <button
                  onClick={() => setShowSchema(!showSchema)}
                  className="text-xs text-accent-purple hover:text-accent-pink transition-colors lg:hidden"
                >
                  {showSchema ? "Hide" : "Show"} Schema
                </button>
              </div>
              <div className="min-h-[200px] max-h-[400px] overflow-auto">
                <Editor
                  value={sql}
                  onValueChange={setSql}
                  highlight={highlight}
                  padding={16}
                  className="font-mono text-sm"
                  style={{
                    minHeight: "200px",
                    background: "transparent",
                    color: "rgba(255,255,255,0.85)",
                  }}
                  placeholder="SELECT ... FROM analytics.page_views"
                />
              </div>
            </div>

            {/* Controls row */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => runQuery()}
                disabled={running || !sql.trim()}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {running ? "Running..." : "Run Query"}
              </button>

              <select
                value={vizType}
                onChange={(e) => setVizType(e.target.value)}
                className="input-glass text-sm !py-2 !w-auto"
              >
                <option value="table">Table</option>
                <option value="line_chart">Line Chart</option>
                <option value="bar_chart">Bar Chart</option>
                <option value="number">Number</option>
              </select>

              <div className="flex-1" />

              <button
                onClick={saveMetric}
                disabled={saving || !name.trim() || !sql.trim()}
                className="btn-secondary text-sm disabled:opacity-50"
              >
                {saving ? "Saving..." : editingId ? "Update" : "Save Metric"}
              </button>
            </div>

            {/* Name / description / group inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Metric name"
                className="input-glass text-sm"
              />
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description (optional)"
                className="input-glass text-sm"
              />
              <div className="relative">
                <input
                  type="text"
                  list="metric-groups"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="Group (optional)"
                  className="input-glass text-sm w-full"
                />
                <datalist id="metric-groups">
                  {existingGroups.map((g) => (
                    <option key={g} value={g} />
                  ))}
                </datalist>
              </div>
            </div>

            {/* Audience toggle */}
            <label className="flex items-center gap-3 cursor-pointer">
              <span
                role="switch"
                aria-checked={isAudience}
                tabIndex={0}
                onClick={() => setIsAudience(!isAudience)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setIsAudience(!isAudience);
                  }
                }}
                className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors ${
                  isAudience ? "bg-accent-purple" : "bg-glass-border"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform mt-0.5 ${
                    isAudience ? "translate-x-4 ml-0.5" : "translate-x-0.5"
                  }`}
                />
              </span>
              <span className="text-sm text-text-secondary">
                Audience Query
              </span>
              {isAudience && (
                <span className="text-xs text-text-muted">
                  Query must return a{" "}
                  <code className="text-accent-purple font-mono">user_id</code>{" "}
                  column
                </span>
              )}
            </label>

            {/* Error */}
            {error && (
              <div className="p-3 rounded-lg bg-accent-pink/10 border border-accent-pink/20 text-accent-pink text-sm">
                {error}
              </div>
            )}

            {/* Results */}
            {result && (
              <div className="glass rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-text-muted">
                    {result.row_count} row{result.row_count !== 1 ? "s" : ""} in{" "}
                    {result.execution_time_ms}ms
                    {result.cached && (
                      <span className="ml-2 text-accent-purple">(cached)</span>
                    )}
                  </span>
                </div>
                <ResultsView result={result} vizType={vizType} />
              </div>
            )}

            {running && (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner />
              </div>
            )}
          </div>

          {/* Schema Reference Panel (1/3 width) */}
          <div className={`${showSchema ? "" : "hidden lg:block"}`}>
            <div className="glass rounded-xl p-4 sticky top-4">
              <h3 className="text-sm font-semibold text-text-primary mb-3">
                Schema Reference
              </h3>
              <div className="space-y-3">
                {ANALYTICS_SCHEMA.map((tbl) => (
                  <div key={tbl.table}>
                    <button
                      onClick={() =>
                        setSql(
                          (prev) =>
                            prev +
                            (prev && !prev.endsWith(" ") ? " " : "") +
                            tbl.table,
                        )
                      }
                      className="text-xs font-mono text-accent-purple hover:text-accent-pink transition-colors cursor-pointer"
                      title="Click to insert table name"
                    >
                      {tbl.table}
                    </button>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {tbl.columns.map((col) => (
                        <button
                          key={col}
                          onClick={() =>
                            setSql(
                              (prev) =>
                                prev +
                                (prev && !prev.endsWith(" ") ? " " : "") +
                                col,
                            )
                          }
                          className="text-xs font-mono text-text-muted hover:text-text-secondary bg-glass-bg/50 rounded px-1.5 py-0.5 cursor-pointer transition-colors"
                          title="Click to insert column name"
                        >
                          {col}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render: List View ────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-text-muted text-sm">
          Write SQL queries against your analytics data and save them as
          reusable metrics.
        </p>
        <button onClick={openNew} className="btn-primary text-sm">
          New Metric
        </button>
      </div>

      {/* Audience Segments (unified with Campaign Wizard) */}
      {enable_marketing && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-text-primary">
                Audience Segments
              </h3>
              <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple">
                Shared with Campaigns
              </span>
            </div>
            {audienceMetrics.length === 0 && (
              <button
                onClick={seedPresets}
                disabled={seeding}
                className="btn-secondary text-xs disabled:opacity-50"
              >
                {seeding ? "Seeding..." : "Seed Preset Audiences"}
              </button>
            )}
          </div>
          {audienceGroups.length > 0 ? (
            audienceGroups.map((group) => (
              <div key={group.name} className="glass rounded-xl p-4">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
                  {group.name}
                </h4>
                <div className="space-y-1">
                  {group.items.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => openDashboard(m.id)}
                      className="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-glass-bg/30 transition-colors group cursor-pointer"
                    >
                      {/* Count badge */}
                      <span
                        className={`w-14 text-center text-sm font-bold tabular-nums ${
                          m.user_count > 0
                            ? "text-accent-purple"
                            : "text-text-muted"
                        }`}
                      >
                        {m.user_count > 0
                          ? m.user_count.toLocaleString()
                          : "\u2014"}
                      </span>

                      {/* Label + detail */}
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-text-primary">
                          {m.name}
                        </span>
                        {m.description && (
                          <span className="text-xs text-text-muted ml-2">
                            {m.description}
                          </span>
                        )}
                      </div>

                      {/* Badges */}
                      {m.preset_key && (
                        <span className="text-[10px] text-text-muted/60 font-medium uppercase tracking-wider">
                          Preset
                        </span>
                      )}

                      {/* Actions */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const metric = metrics.find((mm) => mm.id === m.id);
                          if (metric) openEdit(metric);
                        }}
                        className="text-xs text-text-muted hover:text-accent-purple transition-colors opacity-0 group-hover:opacity-100"
                      >
                        Edit
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <div className="glass rounded-xl p-6 text-center">
              <p className="text-sm text-text-muted mb-3">
                No audience segments yet. Seed the preset audiences to get
                started, or create a new metric with the &quot;Audience
                Query&quot; toggle enabled.
              </p>
              <button
                onClick={seedPresets}
                disabled={seeding}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {seeding ? "Seeding..." : "Seed Preset Audiences"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Starter templates */}
      {displayMetrics.length === 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-text-primary mb-4">
            Get Started
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {STARTER_QUERIES.map((sq) => (
              <button
                key={sq.name}
                onClick={() => loadStarter(sq)}
                className="glass rounded-lg p-4 text-left hover:bg-glass-bg/50 transition-colors group"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-text-muted group-hover:text-accent-purple transition-colors">
                    <VizIcon type={sq.visualization} />
                  </span>
                  <span className="text-sm font-medium text-text-primary">
                    {sq.name}
                  </span>
                </div>
                <p className="text-xs text-text-muted font-mono line-clamp-2">
                  {sq.sql.split("\n")[0]}...
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Always show starter templates link when there are saved metrics */}
      {displayMetrics.length > 0 && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">
              Quick Start Templates
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {STARTER_QUERIES.map((sq) => (
              <button
                key={sq.name}
                onClick={() => loadStarter(sq)}
                className="inline-flex items-center gap-1.5 text-xs bg-glass-bg/50 rounded-full px-3 py-1.5 text-text-muted hover:text-accent-purple hover:bg-glass-bg transition-colors"
              >
                <VizIcon type={sq.visualization} />
                {sq.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Saved metrics — grouped with drag-and-drop */}
      {displayMetrics.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-primary">
            {enable_marketing ? "Analytics Metrics" : "Saved Metrics"} (
            {displayMetrics.length})
          </h3>
          {groupedMetrics.map((group) => {
            const isCollapsed = collapsedGroups.has(group.key);
            return (
              <div
                key={group.key}
                className="space-y-2"
                onDragOver={(e) => handleDragOverGroup(e)}
                onDrop={(e) => handleDrop(e, null, group.key)}
              >
                {/* Group header */}
                <button
                  onClick={() =>
                    setCollapsedGroups((prev) => {
                      const next = new Set(prev);
                      next.has(group.key)
                        ? next.delete(group.key)
                        : next.add(group.key);
                      return next;
                    })
                  }
                  className="w-full flex items-center gap-2 py-1.5 text-left group"
                >
                  <span className="text-text-muted text-xs">
                    {isCollapsed ? "\u25B6" : "\u25BC"}
                  </span>
                  <span className="text-sm font-semibold text-text-primary">
                    {group.displayName}
                  </span>
                  <span className="text-xs text-text-muted">
                    ({group.metrics.length})
                  </span>
                </button>

                {/* Metrics in group */}
                {!isCollapsed &&
                  group.metrics.map((m) => (
                    <div
                      key={m.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, m.id)}
                      onDragOver={(e) => handleDragOver(e, m.id)}
                      onDrop={(e) => {
                        e.stopPropagation();
                        handleDrop(e, m.id, group.key);
                      }}
                      onDragEnd={handleDragEnd}
                      className={`glass rounded-xl overflow-hidden transition-all ${
                        dragItem === m.id ? "opacity-40" : ""
                      } ${
                        dragOverItem === m.id
                          ? "ring-2 ring-accent-blue ring-offset-1 ring-offset-transparent"
                          : ""
                      }`}
                    >
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-4">
                          {/* Drag handle */}
                          <div className="flex items-center shrink-0 pt-0.5 cursor-grab active:cursor-grabbing text-text-muted/40 hover:text-text-muted">
                            <svg
                              width="12"
                              height="16"
                              viewBox="0 0 12 16"
                              fill="currentColor"
                            >
                              <circle cx="3" cy="2" r="1.3" />
                              <circle cx="9" cy="2" r="1.3" />
                              <circle cx="3" cy="8" r="1.3" />
                              <circle cx="9" cy="8" r="1.3" />
                              <circle cx="3" cy="14" r="1.3" />
                              <circle cx="9" cy="14" r="1.3" />
                            </svg>
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-text-muted">
                                <VizIcon type={m.visualization_type} />
                              </span>
                              <h4 className="text-sm font-medium text-text-primary truncate">
                                {m.name}
                              </h4>
                              {m.is_audience && (
                                <span className="shrink-0 text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple">
                                  Audience
                                </span>
                              )}
                            </div>
                            {m.description && (
                              <p className="text-xs text-text-muted mt-1 line-clamp-1">
                                {m.description}
                              </p>
                            )}
                            <p className="text-xs text-text-muted mt-1 font-mono line-clamp-1 opacity-60">
                              {m.sql_query}
                            </p>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              onClick={() => runMetricInline(m)}
                              disabled={runningMetricId === m.id}
                              className="text-xs text-accent-purple hover:text-accent-pink transition-colors disabled:opacity-50"
                            >
                              {runningMetricId === m.id ? "Running..." : "Run"}
                            </button>
                            <button
                              onClick={() => openEdit(m)}
                              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteMetric(m.id)}
                              className="text-xs text-text-muted hover:text-accent-pink transition-colors"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Inline results */}
                      {metricResults[m.id] && (
                        <div className="px-4 pb-4 border-t border-glass-border/30 pt-3">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-text-muted">
                              {metricResults[m.id].row_count} row
                              {metricResults[m.id].row_count !== 1
                                ? "s"
                                : ""}{" "}
                              in {metricResults[m.id].execution_time_ms}ms
                              {metricResults[m.id].cached && (
                                <span className="ml-1 text-accent-purple">
                                  (cached)
                                </span>
                              )}
                            </span>
                            <button
                              onClick={() =>
                                setMetricResults((prev) => {
                                  const next = { ...prev };
                                  delete next[m.id];
                                  return next;
                                })
                              }
                              className="text-xs text-text-muted hover:text-text-secondary"
                            >
                              Close
                            </button>
                          </div>
                          <ResultsView
                            result={metricResults[m.id]}
                            vizType={m.visualization_type}
                          />
                        </div>
                      )}
                    </div>
                  ))}

                {/* Empty group drop zone */}
                {!isCollapsed && group.metrics.length === 0 && (
                  <div className="glass rounded-xl p-4 text-center text-text-muted text-xs border-2 border-dashed border-glass-border">
                    Drop metrics here
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {displayMetrics.length === 0 && (
        <p className="text-text-muted text-sm text-center py-4">
          No saved metrics yet. Create one using the editor above or click a
          starter template.
        </p>
      )}
    </div>
  );
}
