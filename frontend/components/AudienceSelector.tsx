"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import SegmentBuilder, {
  cleanFilters,
  type SegmentFilters,
} from "./SegmentBuilder";

// ─── Types ───────────────────────────────────────────────

interface GlobalInsights {
  total_eligible: number;
  by_rfm_segment: Record<string, number>;
  avg_order_value: number;
  avg_orders_per_user: number;
  active_last_30_days: number;
  cart_abandonment_count: number;
  top_communication_types: Array<{ name: string; subscriber_count: number }>;
}

interface BehaviorInsights {
  user_count: number;
  device_breakdown: Record<string, number>;
  browser_breakdown: Record<string, number>;
  os_breakdown: Record<string, number>;
  top_pages: Array<{ path: string; view_count: number }>;
  avg_sessions_per_user: number;
  avg_page_views_per_user: number;
}

interface SegmentInsights {
  user_count: number;
  pct_of_total: number;
  avg_order_value: number;
  avg_orders_per_user: number;
  total_revenue: number;
  rfm_breakdown: Record<string, number>;
  top_products: Array<{ name: string; purchase_count: number }>;
  recent_email_stats: Record<string, number>;
}

interface SendTimeSuggestion {
  suggested_hour: number;
  suggested_day: string;
  confidence: string;
}

interface CustomerConsent {
  total_customers: number;
  opted_in: number;
  opted_out: number;
  opt_out_reasons: Array<{ type: string; count: number }>;
}

interface Segment {
  id: string;
  name: string;
  description: string | null;
  filters: SegmentFilters;
  is_system: boolean;
  user_count: number;
}

interface AudienceMetric {
  id: string;
  name: string;
  description: string;
  group_name: string | null;
  display_order: number;
  user_count: number;
  segment_id: string | null;
}

interface AudienceCard {
  id: string;
  label: string;
  category: string;
  count: number | null;
  color: string;
  detail?: string;
  filters: SegmentFilters;
}

interface ApiGroup {
  id: string;
  name: string;
  display_order: number;
  presets: ApiPreset[];
}

interface ApiPreset {
  id: string;
  group_id: string | null;
  preset_key: string;
  label: string;
  detail: string | null;
  color: string;
  filters: Record<string, unknown>;
  is_dynamic: boolean;
  display_order: number;
}

export interface SelectedAudience {
  label: string;
  filters: SegmentFilters;
  segmentId?: string;
  metricId?: string;
  userCount: number;
  avgOrderValue?: number;
  totalRevenue?: number;
}

interface AudienceSelectorProps {
  onSelect: (audience: SelectedAudience) => void;
  onBack: () => void;
}

// ─── Component ───────────────────────────────────────────

export default function AudienceSelector({
  onSelect,
  onBack,
}: AudienceSelectorProps) {
  const [globalInsights, setGlobalInsights] = useState<GlobalInsights | null>(
    null,
  );
  const [behaviorInsights, setBehaviorInsights] =
    useState<BehaviorInsights | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [audienceMetrics, setAudienceMetrics] = useState<AudienceMetric[]>([]);
  const [loading, setLoading] = useState(true);

  // API-driven groups
  const [apiGroups, setApiGroups] = useState<ApiGroup[]>([]);
  const [managingGroups, setManagingGroups] = useState(false);
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editingGroupName, setEditingGroupName] = useState("");

  // Detail view state
  const [detailCard, setDetailCard] = useState<AudienceCard | null>(null);
  const [detailInsights, setDetailInsights] = useState<SegmentInsights | null>(
    null,
  );
  const [detailBehavior, setDetailBehavior] = useState<BehaviorInsights | null>(
    null,
  );
  const [detailSendTime, setDetailSendTime] =
    useState<SendTimeSuggestion | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailConsent, setDetailConsent] = useState<CustomerConsent | null>(
    null,
  );
  const [detailSql, setDetailSql] = useState<string | null>(null);
  const [showSql, setShowSql] = useState(false);

  // Custom builder
  const [showCustom, setShowCustom] = useState(false);
  const [customFilters, setCustomFilters] = useState<SegmentFilters>({});
  const [customCount, setCustomCount] = useState<number | null>(null);

  // ─── Fetch API groups ───────────────────────────────────

  const fetchGroups = useCallback(async () => {
    try {
      const res = await apiFetch<{ groups: ApiGroup[] }>(
        "/marketing/admin/audience-groups",
      );
      setApiGroups(res.groups);
    } catch {
      // If endpoint unavailable, apiGroups stays empty
    }
  }, []);

  // ─── Fetch global data on mount ────────────────────────

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      const [gi, bi, segs, am] = await Promise.allSettled([
        apiFetch<GlobalInsights>("/marketing/admin/insights/global"),
        apiFetch<BehaviorInsights>(
          "/marketing/admin/insights/segment/behavior",
          {
            method: "POST",
            body: JSON.stringify({ filters: {} }),
          },
        ),
        apiFetch<{ segments: Segment[] }>("/marketing/admin/segments"),
        apiFetch<{ metrics: AudienceMetric[] }>(
          "/tracking/admin/metrics/audience-metrics",
        ),
      ]);
      if (gi.status === "fulfilled") setGlobalInsights(gi.value);
      if (bi.status === "fulfilled") setBehaviorInsights(bi.value);
      if (segs.status === "fulfilled") setSegments(segs.value.segments);
      if (am.status === "fulfilled") setAudienceMetrics(am.value.metrics);
      setLoading(false);
    }
    fetchData();
    fetchGroups();
  }, [fetchGroups]);

  // ─── Helper: map preset_key to a count from globalInsights ──

  function getPresetCount(
    presetKey: string,
    filters: Record<string, unknown>,
  ): number | null {
    if (!globalInsights) return null;
    switch (presetKey) {
      case "all":
        return globalInsights.total_eligible;
      case "all_customers": {
        // Look for has_orders filter — count not directly available
        if (filters.has_orders) return null;
        return null;
      }
      case "champions":
        return globalInsights.by_rfm_segment?.champion ?? null;
      case "at_risk":
        return (
          (globalInsights.by_rfm_segment?.at_risk ?? 0) +
          (globalInsights.by_rfm_segment?.hibernating ?? 0)
        );
      case "new_customers":
        return globalInsights.by_rfm_segment?.new ?? null;
      case "cart_abandon":
      case "cart_abandoners":
        return globalInsights.cart_abandonment_count ?? null;
      case "active_30d":
        return globalInsights.active_last_30_days ?? null;
      default:
        // Event-based presets — computed on demand
        return null;
    }
  }

  // ─── Build preset cards from API groups ─────────────────

  const presetCards: AudienceCard[] = (apiGroups ?? []).flatMap((g) =>
    (g.presets ?? [])
      .filter((p) => !p.is_dynamic)
      .map((p) => ({
        id: p.preset_key,
        label: p.label,
        category: g.name,
        count: getPresetCount(p.preset_key, p.filters),
        color: p.color,
        detail: p.detail || "",
        filters: p.filters as Record<string, unknown>,
      })),
  );

  // Dynamic cards from behavior insights (device, browser) — appended when data loads
  const dynamicCards: AudienceCard[] = [];
  if (behaviorInsights) {
    const deviceColors: Record<string, string> = {
      mobile: "text-accent-pink",
      desktop: "text-accent-blue",
      tablet: "text-accent-purple",
    };
    for (const [deviceType, count] of Object.entries(
      behaviorInsights.device_breakdown,
    )) {
      if (deviceType === "bot" || deviceType === "unknown" || count === 0)
        continue;
      dynamicCards.push({
        id: `device-${deviceType}`,
        label: `${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)} Users`,
        category: "Device & Platform",
        count,
        color: deviceColors[deviceType] || "text-accent-blue",
        filters: { device_type: [deviceType] },
      });
    }
    const browserEntries = Object.entries(behaviorInsights.browser_breakdown)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 3);
    for (const [browser, count] of browserEntries) {
      if (count === 0) continue;
      dynamicCards.push({
        id: `browser-${browser}`,
        label: `${browser} Users`,
        category: "Device & Platform",
        count,
        color: "text-cyan-400",
        filters: { browser: [browser] },
      });
    }
  }

  const cards = [...presetCards, ...dynamicCards];

  // Derive categories from API groups, preserving display_order
  const categories = (apiGroups ?? []).map((g) => g.name);
  // Ensure "Device & Platform" is included if dynamic cards exist but no API group has that name
  if (dynamicCards.length > 0 && !categories.includes("Device & Platform")) {
    categories.push("Device & Platform");
  }

  const grouped = categories
    .map((cat) => ({
      label: cat,
      groupId: (apiGroups ?? []).find((g) => g.name === cat)?.id || null,
      items: cards.filter((c) => c.category === cat),
    }))
    .filter((g) => g.items.length > 0);

  // Saved segments (non-system custom ones)
  const savedSegments = segments.filter((s) => !s.is_system);

  // ─── Group management API calls ─────────────────────────

  async function renameGroup(groupId: string, newName: string) {
    try {
      await apiFetch(`/marketing/admin/audience-groups/${groupId}`, {
        method: "PUT",
        body: JSON.stringify({ name: newName }),
      });
      await fetchGroups();
    } catch {
      // Rename failed — keep old name
    }
    setEditingGroupId(null);
    setEditingGroupName("");
  }

  async function reorderGroups(groupIds: string[]) {
    try {
      await apiFetch("/marketing/admin/audience-groups/reorder", {
        method: "POST",
        body: JSON.stringify({ group_ids: groupIds }),
      });
      await fetchGroups();
    } catch {
      // Reorder failed
    }
  }

  async function movePreset(presetId: string, targetGroupId: string) {
    try {
      await apiFetch(`/marketing/admin/audience-presets/${presetId}/move`, {
        method: "PUT",
        body: JSON.stringify({ target_group_id: targetGroupId }),
      });
      await fetchGroups();
    } catch {
      // Move failed
    }
  }

  function swapGroups(index: number, direction: "up" | "down") {
    const swapIdx = direction === "up" ? index - 1 : index + 1;
    if (swapIdx < 0 || swapIdx >= apiGroups.length) return;
    const reordered = [...apiGroups];
    [reordered[index], reordered[swapIdx]] = [
      reordered[swapIdx],
      reordered[index],
    ];
    const ids = reordered.map((g) => g.id);
    reorderGroups(ids);
  }

  // Find preset ID from preset_key by searching apiGroups
  function findPresetId(presetKey: string): string | null {
    for (const g of apiGroups) {
      for (const p of g.presets) {
        if (p.preset_key === presetKey) return p.id;
      }
    }
    return null;
  }

  // ─── Detail view data fetching ─────────────────────────

  const openDetail = useCallback(async (card: AudienceCard) => {
    setDetailCard(card);
    setDetailInsights(null);
    setDetailBehavior(null);
    setDetailSendTime(null);
    setDetailConsent(null);
    setDetailSql(null);
    setShowSql(false);
    setDetailLoading(true);

    const body = JSON.stringify({ filters: cleanFilters(card.filters) });
    const fetches: Promise<unknown>[] = [
      apiFetch<SegmentInsights>("/marketing/admin/insights/segment", {
        method: "POST",
        body,
      }),
      apiFetch<BehaviorInsights>("/marketing/admin/insights/segment/behavior", {
        method: "POST",
        body,
      }),
      apiFetch<SendTimeSuggestion>("/marketing/admin/insights/send-time", {
        method: "POST",
        body,
      }),
      apiFetch<{ sql: string }>("/marketing/admin/insights/explain-query", {
        method: "POST",
        body,
      }),
    ];
    // Fetch consent breakdown for "All Customers"
    if (card.id === "all_customers") {
      fetches.push(
        apiFetch<CustomerConsent>("/marketing/admin/insights/customer-consent"),
      );
    }

    const results = await Promise.allSettled(fetches);

    if (results[0].status === "fulfilled")
      setDetailInsights(results[0].value as SegmentInsights);
    if (results[1].status === "fulfilled")
      setDetailBehavior(results[1].value as BehaviorInsights);
    if (results[2].status === "fulfilled")
      setDetailSendTime(results[2].value as SendTimeSuggestion);
    if (results[3].status === "fulfilled")
      setDetailSql((results[3].value as { sql: string }).sql);
    if (card.id === "all_customers" && results[4]?.status === "fulfilled")
      setDetailConsent(results[4].value as CustomerConsent);

    setDetailLoading(false);
  }, []);

  const openSegmentDetail = useCallback(
    async (seg: Segment) => {
      const card: AudienceCard = {
        id: `seg-${seg.id}`,
        label: seg.name,
        category: "Saved Segments",
        count: seg.user_count,
        color: "text-accent-blue",
        detail: seg.description || undefined,
        filters: seg.filters,
      };
      await openDetail(card);
    },
    [openDetail],
  );

  // ─── Custom audience count ─────────────────────────────

  useEffect(() => {
    if (!showCustom) return;
    const timer = setTimeout(async () => {
      try {
        const clean = cleanFilters(customFilters);
        if (Object.keys(clean).length === 0) {
          setCustomCount(null);
          return;
        }
        const res = await apiFetch<{ count: number }>(
          "/marketing/admin/segments/preview",
          { method: "POST", body: JSON.stringify({ filters: clean }) },
        );
        setCustomCount(res.count);
      } catch {
        setCustomCount(null);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [customFilters, showCustom]);

  // ─── Handle selection ──────────────────────────────────

  function selectDetailAudience() {
    if (!detailCard) return;
    onSelect({
      label: detailCard.label,
      filters: detailCard.filters,
      userCount: detailInsights?.user_count ?? detailCard.count ?? 0,
      avgOrderValue: detailInsights?.avg_order_value,
      totalRevenue: detailInsights?.total_revenue,
    });
  }

  function selectCustomAudience() {
    const clean = cleanFilters(customFilters);
    onSelect({
      label: "Custom Audience",
      filters: clean as SegmentFilters,
      userCount: customCount ?? 0,
    });
  }

  function selectAudienceMetric(m: AudienceMetric) {
    onSelect({
      label: m.name,
      filters: {},
      metricId: m.id,
      segmentId: m.segment_id || undefined,
      userCount: m.user_count,
    });
  }

  // Group audience metrics by group_name
  const audienceMetricGroups = (() => {
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
      .map(([name, items]) => ({ name, items }));
  })();

  // ─── Render: Detail View ───────────────────────────────

  if (detailCard) {
    return (
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setDetailCard(null)}
            className="text-sm text-text-muted hover:text-text-primary transition-colors"
          >
            &larr; Back to Audiences
          </button>
          <span className="text-text-muted/30">|</span>
          <h2 className="text-lg font-semibold text-text-primary">
            <span className={detailCard.color}>{detailCard.label}</span>
            {detailInsights && (
              <span className="text-sm text-text-muted font-normal ml-2">
                {detailInsights.user_count.toLocaleString()} users (
                {detailInsights.pct_of_total}%)
              </span>
            )}
          </h2>
        </div>

        {detailLoading ? (
          <div className="glass rounded-xl p-12 text-center">
            <div className="animate-spin h-6 w-6 border-2 border-accent-blue border-t-transparent rounded-full mx-auto mb-2" />
            <span className="text-text-muted text-sm">
              Loading analytics...
            </span>
          </div>
        ) : (
          <>
            {/* Key Metrics Row */}
            {detailInsights && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {(
                  [
                    [
                      "Users",
                      detailInsights.user_count.toLocaleString(),
                      "text-accent-blue",
                    ],
                    [
                      "AOV",
                      `$${detailInsights.avg_order_value.toFixed(2)}`,
                      "text-accent-green",
                    ],
                    [
                      "Revenue",
                      `$${(detailInsights.total_revenue / 100).toLocaleString()}`,
                      "text-accent-purple",
                    ],
                    [
                      "Avg Orders",
                      `${detailInsights.avg_orders_per_user}/user`,
                      "text-accent-pink",
                    ],
                    [
                      "% of Total",
                      `${detailInsights.pct_of_total}%`,
                      "text-cyan-400",
                    ],
                  ] as [string, string, string][]
                ).map(([label, val, color]) => (
                  <div key={label} className="glass rounded-lg p-3">
                    <p className="text-xs text-text-muted mb-0.5">{label}</p>
                    <p className={`text-xl font-bold ${color}`}>{val}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Two-column: Purchase + Device/Browser */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Purchase Insights */}
              {detailInsights && (
                <div className="glass rounded-xl p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Purchase Insights
                  </h3>
                  {/* RFM Breakdown */}
                  {Object.keys(detailInsights.rfm_breakdown).length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">
                        RFM Breakdown
                      </p>
                      <div className="space-y-1.5">
                        {Object.entries(detailInsights.rfm_breakdown)
                          .sort(([, a], [, b]) => b - a)
                          .map(([seg, cnt]) => {
                            const total = Object.values(
                              detailInsights.rfm_breakdown,
                            ).reduce((s, v) => s + v, 0);
                            const pct = total > 0 ? (cnt / total) * 100 : 0;
                            return (
                              <div
                                key={seg}
                                className="flex items-center gap-2"
                              >
                                <span className="text-xs text-text-secondary w-28 truncate">
                                  {seg}
                                </span>
                                <div className="flex-1 bg-glass-border rounded-full h-2 overflow-hidden">
                                  <div
                                    className="h-full bg-accent-blue rounded-full"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="text-xs text-text-muted w-10 text-right">
                                  {cnt}
                                </span>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}
                  {/* Top Products */}
                  {detailInsights.top_products.length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">
                        Top Products
                      </p>
                      <div className="space-y-1">
                        {detailInsights.top_products.map((p, i) => (
                          <div
                            key={p.name}
                            className="flex items-center justify-between text-xs"
                          >
                            <span className="text-text-secondary">
                              {i + 1}. {p.name}
                            </span>
                            <span className="text-text-muted">
                              ({p.purchase_count})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Device & Browser */}
              {detailBehavior && (
                <div className="glass rounded-xl p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Device & Platform
                  </h3>
                  {/* Device breakdown */}
                  {Object.keys(detailBehavior.device_breakdown).length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">
                        Device Type
                      </p>
                      <BreakdownBars
                        data={detailBehavior.device_breakdown}
                        color="bg-accent-pink"
                      />
                    </div>
                  )}
                  {/* Browser breakdown */}
                  {Object.keys(detailBehavior.browser_breakdown).length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">
                        Top Browsers
                      </p>
                      <BreakdownBars
                        data={detailBehavior.browser_breakdown}
                        color="bg-accent-blue"
                      />
                    </div>
                  )}
                  {/* OS breakdown */}
                  {Object.keys(detailBehavior.os_breakdown).length > 0 && (
                    <div>
                      <p className="text-xs text-text-muted mb-2">
                        Operating System
                      </p>
                      <BreakdownBars
                        data={detailBehavior.os_breakdown}
                        color="bg-accent-purple"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Email Health + Top Pages + Send Time */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Email Health */}
              {detailInsights && (
                <div className="glass rounded-xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Email Health (90d)
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {(
                      [
                        [
                          "Sent",
                          detailInsights.recent_email_stats.sent,
                          "text-accent-blue",
                        ],
                        [
                          "Delivered",
                          detailInsights.recent_email_stats.delivered,
                          "text-accent-green",
                        ],
                        [
                          "Skipped",
                          detailInsights.recent_email_stats.skipped,
                          "text-yellow-400",
                        ],
                        [
                          "Bounced",
                          detailInsights.recent_email_stats.bounced,
                          "text-accent-pink",
                        ],
                      ] as [string, number, string][]
                    ).map(([label, val, color]) => (
                      <div key={label}>
                        <p className="text-xs text-text-muted">{label}</p>
                        <p className={`text-lg font-semibold ${color}`}>
                          {val?.toLocaleString() ?? 0}
                        </p>
                        {detailInsights.recent_email_stats.sent > 0 &&
                          label !== "Sent" && (
                            <p className="text-xs text-text-muted">
                              {(
                                ((val ?? 0) /
                                  detailInsights.recent_email_stats.sent) *
                                100
                              ).toFixed(1)}
                              %
                            </p>
                          )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Top Pages */}
              {detailBehavior && detailBehavior.top_pages.length > 0 && (
                <div className="glass rounded-xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Top Pages Viewed
                  </h3>
                  <div className="space-y-1.5">
                    {detailBehavior.top_pages.slice(0, 8).map((p) => (
                      <div
                        key={p.path}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="text-text-secondary font-mono truncate max-w-[200px]">
                          {p.path}
                        </span>
                        <span className="text-text-muted ml-2">
                          {p.view_count.toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                  {detailBehavior.avg_page_views_per_user > 0 && (
                    <p className="text-xs text-text-muted pt-2 border-t border-glass-border">
                      Avg{" "}
                      <strong className="text-text-secondary">
                        {detailBehavior.avg_page_views_per_user}
                      </strong>{" "}
                      page views,{" "}
                      <strong className="text-text-secondary">
                        {detailBehavior.avg_sessions_per_user}
                      </strong>{" "}
                      sessions per user (90d)
                    </p>
                  )}
                </div>
              )}

              {/* Send Time Suggestion */}
              {detailSendTime && (
                <div className="glass rounded-xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Suggested Send Time
                  </h3>
                  <p className="text-2xl font-bold text-accent-blue">
                    {detailSendTime.suggested_day} at{" "}
                    {detailSendTime.suggested_hour}:00
                  </p>
                  <p className="text-xs text-text-muted">
                    {detailSendTime.confidence} confidence — based on audience
                    activity patterns
                  </p>
                </div>
              )}
            </div>

            {/* Customer Consent Breakdown (All Customers only) */}
            {detailConsent && (
              <div className="glass rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-semibold text-text-primary">
                  Marketing Consent
                </h3>
                <div className="flex items-center gap-6">
                  {/* Donut chart */}
                  <div className="relative w-28 h-28 shrink-0">
                    <svg viewBox="0 0 36 36" className="w-full h-full">
                      <circle
                        cx="18"
                        cy="18"
                        r="15.9"
                        fill="none"
                        stroke="rgba(255,255,255,0.05)"
                        strokeWidth="3"
                      />
                      {detailConsent.total_customers > 0 && (
                        <>
                          <circle
                            cx="18"
                            cy="18"
                            r="15.9"
                            fill="none"
                            stroke="#22c55e"
                            strokeWidth="3"
                            strokeDasharray={`${(detailConsent.opted_in / detailConsent.total_customers) * 100} ${100 - (detailConsent.opted_in / detailConsent.total_customers) * 100}`}
                            strokeDashoffset="25"
                            strokeLinecap="round"
                          />
                          <circle
                            cx="18"
                            cy="18"
                            r="15.9"
                            fill="none"
                            stroke="#ef4444"
                            strokeWidth="3"
                            strokeDasharray={`${(detailConsent.opted_out / detailConsent.total_customers) * 100} ${100 - (detailConsent.opted_out / detailConsent.total_customers) * 100}`}
                            strokeDashoffset={`${25 - (detailConsent.opted_in / detailConsent.total_customers) * 100}`}
                            strokeLinecap="round"
                          />
                        </>
                      )}
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-bold text-text-primary">
                        {detailConsent.total_customers}
                      </span>
                    </div>
                  </div>
                  {/* Legend */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-green-500 shrink-0" />
                      <span className="text-sm text-text-secondary">
                        Opted In:{" "}
                        <strong className="text-accent-green">
                          {detailConsent.opted_in}
                        </strong>
                        {detailConsent.total_customers > 0 && (
                          <span className="text-text-muted ml-1">
                            (
                            {Math.round(
                              (detailConsent.opted_in /
                                detailConsent.total_customers) *
                                100,
                            )}
                            %)
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full bg-red-500 shrink-0" />
                      <span className="text-sm text-text-secondary">
                        Opted Out:{" "}
                        <strong className="text-accent-pink">
                          {detailConsent.opted_out}
                        </strong>
                        {detailConsent.total_customers > 0 && (
                          <span className="text-text-muted ml-1">
                            (
                            {Math.round(
                              (detailConsent.opted_out /
                                detailConsent.total_customers) *
                                100,
                            )}
                            %)
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                  {/* Opt-out reasons */}
                  {detailConsent.opt_out_reasons.length > 0 && (
                    <div className="border-l border-glass-border pl-4 space-y-1.5">
                      <p className="text-xs text-text-muted font-medium">
                        Not Opted In By Type
                      </p>
                      {detailConsent.opt_out_reasons.map((r) => (
                        <div
                          key={r.type}
                          className="flex items-center justify-between gap-4 text-xs"
                        >
                          <span className="text-text-secondary capitalize">
                            {r.type}
                          </span>
                          <span className="text-text-muted tabular-nums">
                            {r.count}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* View Query (collapsible SQL) */}
            {detailSql && (
              <div className="glass rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowSql(!showSql)}
                  className="w-full px-5 py-3 flex items-center justify-between text-sm text-text-muted hover:text-text-primary transition-colors"
                >
                  <span className="font-medium">View Query</span>
                  <span>{showSql ? "\u25B2" : "\u25BC"}</span>
                </button>
                {showSql && (
                  <div className="px-5 pb-4 border-t border-glass-border">
                    <pre className="mt-3 p-3 bg-glass-bg/50 rounded-lg text-xs font-mono text-text-secondary overflow-x-auto whitespace-pre-wrap">
                      {detailSql}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* Select button */}
            <button
              type="button"
              onClick={selectDetailAudience}
              className="w-full py-3 rounded-xl bg-accent-green text-white font-medium hover:bg-accent-green/90 transition-colors"
            >
              Select This Audience & Continue
            </button>
          </>
        )}
      </div>
    );
  }

  // ─── Render: Card Grid ─────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          &larr; Back to Campaigns
        </button>
        <span className="text-text-muted/30">|</span>
        <h2 className="text-lg font-semibold text-text-primary">
          Create Campaign &mdash; Choose Audience
        </h2>
      </div>

      <>
        {/* Categorized cards — compact table-style rows */}
        {grouped.map((group, groupIndex) => {
          const apiGroupIndex = apiGroups.findIndex(
            (g) => g.id === group.groupId,
          );
          return (
            <div key={group.label} className="glass rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 border-b border-glass-border/50 flex items-center gap-2">
                {/* Group header: inline rename or label */}
                {managingGroups && editingGroupId === group.groupId ? (
                  <form
                    className="flex items-center gap-2 flex-1"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (group.groupId && editingGroupName.trim()) {
                        renameGroup(group.groupId, editingGroupName.trim());
                      }
                    }}
                  >
                    <input
                      type="text"
                      value={editingGroupName}
                      onChange={(e) => setEditingGroupName(e.target.value)}
                      className="bg-glass-bg border border-glass-border rounded px-2 py-0.5 text-xs text-text-primary font-medium uppercase tracking-wider focus:outline-none focus:border-accent-blue"
                      autoFocus
                      onBlur={() => {
                        if (group.groupId && editingGroupName.trim()) {
                          renameGroup(group.groupId, editingGroupName.trim());
                        } else {
                          setEditingGroupId(null);
                          setEditingGroupName("");
                        }
                      }}
                    />
                    <button
                      type="submit"
                      className="text-xs text-accent-green hover:text-accent-green/80"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingGroupId(null);
                        setEditingGroupName("");
                      }}
                      className="text-xs text-text-muted hover:text-text-primary"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <h3
                    className={`text-xs text-text-muted font-medium uppercase tracking-wider flex-1 ${
                      managingGroups && group.groupId
                        ? "cursor-pointer hover:text-text-primary"
                        : ""
                    }`}
                    onClick={() => {
                      if (managingGroups && group.groupId) {
                        setEditingGroupId(group.groupId);
                        setEditingGroupName(group.label);
                      }
                    }}
                    title={
                      managingGroups && group.groupId
                        ? "Click to rename"
                        : undefined
                    }
                  >
                    {group.label}
                  </h3>
                )}

                {/* Manage mode: reorder arrows */}
                {managingGroups && group.groupId && apiGroupIndex >= 0 && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={apiGroupIndex === 0}
                      onClick={() => swapGroups(apiGroupIndex, "up")}
                      className="text-xs text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed px-1 py-0.5"
                      title="Move group up"
                    >
                      &#9650;
                    </button>
                    <button
                      type="button"
                      disabled={apiGroupIndex === apiGroups.length - 1}
                      onClick={() => swapGroups(apiGroupIndex, "down")}
                      className="text-xs text-text-muted hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed px-1 py-0.5"
                      title="Move group down"
                    >
                      &#9660;
                    </button>
                  </div>
                )}

                {/* Gear icon to toggle manage mode (shown on first group) */}
                {groupIndex === 0 && apiGroups.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setManagingGroups(!managingGroups);
                      setEditingGroupId(null);
                      setEditingGroupName("");
                    }}
                    className={`text-sm transition-colors px-1.5 py-0.5 rounded ${
                      managingGroups
                        ? "text-accent-blue bg-accent-blue/10"
                        : "text-text-muted hover:text-text-primary"
                    }`}
                    title={managingGroups ? "Done managing" : "Manage groups"}
                  >
                    &#9881;
                  </button>
                )}
              </div>
              <div className="divide-y divide-glass-border/30">
                {group.items.map((card) => (
                  <div key={card.id} className="relative group/card">
                    <button
                      type="button"
                      onClick={() => openDetail(card)}
                      className="w-full px-4 py-3 flex items-center gap-4 hover:bg-glass-hover/50 transition-colors group text-left"
                    >
                      <p
                        className={`text-xl font-bold tabular-nums w-20 shrink-0 ${card.color}`}
                      >
                        {card.count !== null ? (
                          card.count.toLocaleString()
                        ) : loading ? (
                          <span className="inline-block w-12 h-5 bg-glass-border/50 rounded animate-pulse" />
                        ) : (
                          "\u2014"
                        )}
                      </p>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-text-primary font-medium">
                          {card.label}
                        </p>
                        {card.detail && (
                          <p className="text-xs text-text-muted truncate">
                            {card.detail}
                          </p>
                        )}
                      </div>
                      <span className="text-xs text-accent-blue opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        View &rarr;
                      </span>
                    </button>
                    {/* Move preset dropdown (visible in manage mode on hover) */}
                    {managingGroups &&
                      !card.id.startsWith("device-") &&
                      !card.id.startsWith("browser-") && (
                        <div className="absolute top-1 right-20 opacity-0 group-hover/card:opacity-100 transition-opacity z-10">
                          <select
                            className="text-[10px] bg-glass-bg border border-glass-border rounded px-1.5 py-0.5 text-text-muted cursor-pointer focus:outline-none focus:border-accent-blue appearance-none"
                            value=""
                            onChange={(e) => {
                              const targetGroupId = e.target.value;
                              if (!targetGroupId) return;
                              const presetId = findPresetId(card.id);
                              if (presetId) {
                                movePreset(presetId, targetGroupId);
                              }
                            }}
                          >
                            <option value="">Move to...</option>
                            {apiGroups
                              .filter((g) => g.name !== card.category)
                              .map((g) => (
                                <option key={g.id} value={g.id}>
                                  {g.name}
                                </option>
                              ))}
                          </select>
                        </div>
                      )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* Saved Segments */}
        {savedSegments.length > 0 && (
          <div className="glass rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-glass-border/50">
              <h3 className="text-xs text-text-muted font-medium uppercase tracking-wider">
                Saved Segments
              </h3>
            </div>
            <div className="divide-y divide-glass-border/30">
              {savedSegments.map((seg) => (
                <button
                  key={seg.id}
                  type="button"
                  onClick={() => openSegmentDetail(seg)}
                  className="w-full px-4 py-3 flex items-center gap-4 hover:bg-glass-hover/50 transition-colors group text-left"
                >
                  <p className="text-xl font-bold tabular-nums w-20 shrink-0 text-accent-purple">
                    {seg.user_count.toLocaleString()}
                  </p>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary font-medium">
                      {seg.name}
                    </p>
                    {seg.description && (
                      <p className="text-xs text-text-muted truncate">
                        {seg.description}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-accent-purple opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    View &rarr;
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Audience Metrics (from SQL editor) */}
        {audienceMetricGroups.length > 0 &&
          audienceMetricGroups.map((group) => (
            <div key={group.name} className="glass rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 border-b border-glass-border/50 flex items-center gap-2">
                <h3 className="text-xs text-text-muted font-medium uppercase tracking-wider">
                  {group.name}
                </h3>
                <span className="text-[10px] text-accent-purple/70 font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-accent-purple/10">
                  SQL
                </span>
              </div>
              <div className="divide-y divide-glass-border/30">
                {group.items.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => selectAudienceMetric(m)}
                    className="w-full px-4 py-3 flex items-center gap-4 hover:bg-glass-hover/50 transition-colors group text-left"
                  >
                    <p className="text-xl font-bold tabular-nums w-20 shrink-0 text-accent-purple">
                      {m.user_count > 0 ? (
                        m.user_count.toLocaleString()
                      ) : (
                        <span className="text-text-muted">&mdash;</span>
                      )}
                    </p>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary font-medium">
                        {m.name}
                      </p>
                      {m.description && (
                        <p className="text-xs text-text-muted truncate">
                          {m.description}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-accent-purple opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      Select &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}

        {/* Build Custom Audience */}
        <div className="glass rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => setShowCustom(!showCustom)}
            className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-text-primary hover:bg-glass-hover transition-colors"
          >
            <span>Build Custom Audience</span>
            <span className="text-text-muted">
              {showCustom ? "\u25B2" : "\u25BC"}
            </span>
          </button>
          {showCustom && (
            <div className="px-5 pb-5 space-y-4 border-t border-glass-border">
              <div className="pt-4">
                <SegmentBuilder
                  filters={customFilters}
                  onChange={setCustomFilters}
                  showPreview={false}
                />
              </div>
              {customCount !== null && (
                <p className="text-sm text-text-muted">
                  <strong className="text-accent-blue">
                    {customCount.toLocaleString()}
                  </strong>{" "}
                  users match
                </p>
              )}
              <button
                type="button"
                onClick={selectCustomAudience}
                disabled={Object.keys(cleanFilters(customFilters)).length === 0}
                className="w-full py-2.5 rounded-lg bg-accent-blue text-white font-medium hover:bg-accent-blue/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Use Custom Audience & Continue
              </button>
            </div>
          )}
        </div>
      </>
    </div>
  );
}

// ─── Reusable bar chart ──────────────────────────────────

function BreakdownBars({
  data,
  color,
}: {
  data: Record<string, number>;
  color: string;
}) {
  const total = Object.values(data).reduce((s, v) => s + v, 0);
  if (total === 0) return null;

  return (
    <div className="space-y-1.5">
      {Object.entries(data)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 6)
        .map(([label, cnt]) => {
          const pct = (cnt / total) * 100;
          return (
            <div key={label} className="flex items-center gap-2">
              <span className="text-xs text-text-secondary w-20 truncate">
                {label}
              </span>
              <div className="flex-1 bg-glass-border rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full ${color} rounded-full`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-xs text-text-muted w-16 text-right">
                {Math.round(pct)}% ({cnt})
              </span>
            </div>
          );
        })}
    </div>
  );
}
