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

interface Segment {
  id: string;
  name: string;
  description: string | null;
  filters: SegmentFilters;
  is_system: boolean;
  user_count: number;
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

export interface SelectedAudience {
  label: string;
  filters: SegmentFilters;
  segmentId?: string;
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
  const [loading, setLoading] = useState(true);

  // Detail view state
  const [detailCard, setDetailCard] = useState<AudienceCard | null>(null);
  const [detailInsights, setDetailInsights] =
    useState<SegmentInsights | null>(null);
  const [detailBehavior, setDetailBehavior] =
    useState<BehaviorInsights | null>(null);
  const [detailSendTime, setDetailSendTime] =
    useState<SendTimeSuggestion | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Custom builder
  const [showCustom, setShowCustom] = useState(false);
  const [customFilters, setCustomFilters] = useState<SegmentFilters>({});
  const [customCount, setCustomCount] = useState<number | null>(null);

  // ─── Fetch global data on mount ────────────────────────

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      const [gi, bi, segs] = await Promise.allSettled([
        apiFetch<GlobalInsights>("/marketing/admin/insights/global"),
        apiFetch<BehaviorInsights>(
          "/marketing/admin/insights/segment/behavior",
          {
            method: "POST",
            body: JSON.stringify({ filters: {} }),
          },
        ),
        apiFetch<{ segments: Segment[] }>("/marketing/admin/segments"),
      ]);
      if (gi.status === "fulfilled") setGlobalInsights(gi.value);
      if (bi.status === "fulfilled") setBehaviorInsights(bi.value);
      if (segs.status === "fulfilled") setSegments(segs.value.segments);
      setLoading(false);
    }
    fetchData();
  }, []);

  // ─── Build cards from fetched data ─────────────────────

  const cards: AudienceCard[] = [];

  if (globalInsights) {
    // Purchase Behavior
    const rfm = globalInsights.by_rfm_segment;
    cards.push({
      id: "all",
      label: "All Subscribers",
      category: "Audience Overview",
      count: globalInsights.total_eligible,
      color: "text-accent-blue",
      detail: `AOV $${globalInsights.avg_order_value}`,
      filters: {},
    });
    cards.push({
      id: "champions",
      label: "Champions",
      category: "Purchase Behavior",
      count: rfm?.champion ?? null,
      color: "text-green-400",
      detail: "High-value repeat buyers",
      filters: { rfm_segment: ["champion"] },
    });
    cards.push({
      id: "at_risk",
      label: "At-Risk",
      category: "Purchase Behavior",
      count: (rfm?.at_risk ?? 0) + (rfm?.hibernating ?? 0),
      color: "text-yellow-400",
      detail: "Fading engagement",
      filters: { rfm_segment: ["at_risk", "hibernating"] },
    });
    cards.push({
      id: "cart_abandon",
      label: "Cart Abandoners",
      category: "Purchase Behavior",
      count: globalInsights.cart_abandonment_count,
      color: "text-orange-400",
      detail: "Left items in cart",
      filters: { cart_status: "abandoned" },
    });
    cards.push({
      id: "new_customers",
      label: "New Customers",
      category: "Purchase Behavior",
      count: rfm?.new ?? null,
      color: "text-purple-400",
      detail: "Recently acquired",
      filters: { rfm_segment: ["new"] },
    });
    cards.push({
      id: "active_30d",
      label: "Active (30d)",
      category: "Engagement",
      count: globalInsights.active_last_30_days,
      color: "text-cyan-400",
      detail: "Recent site activity",
      filters: { last_purchase_days_max: 30 },
    });
  }

  if (behaviorInsights) {
    // Dynamically create a card for each device type the system has recorded
    const deviceColors: Record<string, string> = {
      mobile: "text-accent-pink",
      desktop: "text-accent-blue",
      tablet: "text-accent-purple",
      bot: "text-text-muted",
      unknown: "text-text-muted",
    };
    for (const [deviceType, count] of Object.entries(
      behaviorInsights.device_breakdown,
    )) {
      if (deviceType === "bot" || deviceType === "unknown" || count === 0)
        continue;
      cards.push({
        id: `device-${deviceType}`,
        label: `${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)} Users`,
        category: "Device & Platform",
        count,
        color: deviceColors[deviceType] || "text-accent-blue",
        filters: { device_type: [deviceType] },
      });
    }

    // Top browsers as cards (top 3 only to avoid clutter)
    const browserEntries = Object.entries(behaviorInsights.browser_breakdown)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 3);
    for (const [browser, count] of browserEntries) {
      if (count === 0) continue;
      cards.push({
        id: `browser-${browser}`,
        label: `${browser} Users`,
        category: "Device & Platform",
        count,
        color: "text-cyan-400",
        filters: { browser: [browser] },
      });
    }

    // High engagers
    if (behaviorInsights.avg_sessions_per_user > 0) {
      cards.push({
        id: "high_engagers",
        label: "High Engagers",
        category: "Engagement",
        count: null, // will be fetched on detail
        color: "text-accent-green",
        detail: "10+ sessions (90d)",
        filters: { min_sessions: 10 },
      });
    }
  }

  // Group cards by category
  const categories = [
    "Audience Overview",
    "Purchase Behavior",
    "Device & Platform",
    "Engagement",
  ];
  const grouped = categories
    .map((cat) => ({
      label: cat,
      items: cards.filter((c) => c.category === cat),
    }))
    .filter((g) => g.items.length > 0);

  // Saved segments (non-system custom ones)
  const savedSegments = segments.filter((s) => !s.is_system);

  // ─── Detail view data fetching ─────────────────────────

  const openDetail = useCallback(async (card: AudienceCard) => {
    setDetailCard(card);
    setDetailInsights(null);
    setDetailBehavior(null);
    setDetailSendTime(null);
    setDetailLoading(true);

    const body = JSON.stringify({ filters: cleanFilters(card.filters) });
    const [si, bi, st] = await Promise.allSettled([
      apiFetch<SegmentInsights>("/marketing/admin/insights/segment", {
        method: "POST",
        body,
      }),
      apiFetch<BehaviorInsights>(
        "/marketing/admin/insights/segment/behavior",
        { method: "POST", body },
      ),
      apiFetch<SendTimeSuggestion>("/marketing/admin/insights/send-time", {
        method: "POST",
        body,
      }),
    ]);

    if (si.status === "fulfilled") setDetailInsights(si.value);
    if (bi.status === "fulfilled") setDetailBehavior(bi.value);
    if (st.status === "fulfilled") setDetailSendTime(st.value);
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
                  {Object.keys(detailBehavior.browser_breakdown).length >
                    0 && (
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

      {loading ? (
        <div className="glass rounded-xl p-12 text-center">
          <div className="animate-spin h-6 w-6 border-2 border-accent-blue border-t-transparent rounded-full mx-auto mb-2" />
          <span className="text-text-muted text-sm">
            Loading audience data...
          </span>
        </div>
      ) : (
        <>
          {/* Categorized cards */}
          {grouped.map((group) => (
            <div key={group.label}>
              <h3 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
                {group.label}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
                {group.items.map((card) => (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => openDetail(card)}
                    className="glass rounded-xl p-4 text-left hover:border-accent-blue/50 border border-transparent transition-all group"
                  >
                    <p className="text-xs text-text-muted font-medium mb-1">
                      {card.label}
                    </p>
                    <p className={`text-2xl font-bold ${card.color}`}>
                      {card.count !== null
                        ? card.count.toLocaleString()
                        : "..."}
                    </p>
                    {card.detail && (
                      <p className="text-xs text-text-muted mt-1 truncate">
                        {card.detail}
                      </p>
                    )}
                    <span className="text-xs text-accent-blue opacity-0 group-hover:opacity-100 transition-opacity mt-2 block">
                      View Details &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}

          {/* Saved Segments */}
          {savedSegments.length > 0 && (
            <div>
              <h3 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
                Saved Segments
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
                {savedSegments.map((seg) => (
                  <button
                    key={seg.id}
                    type="button"
                    onClick={() => openSegmentDetail(seg)}
                    className="glass rounded-xl p-4 text-left hover:border-accent-purple/50 border border-transparent transition-all group"
                  >
                    <p className="text-xs text-text-muted font-medium mb-1">
                      {seg.name}
                    </p>
                    <p className="text-2xl font-bold text-accent-purple">
                      {seg.user_count.toLocaleString()}
                    </p>
                    {seg.description && (
                      <p className="text-xs text-text-muted mt-1 truncate">
                        {seg.description}
                      </p>
                    )}
                    <span className="text-xs text-accent-purple opacity-0 group-hover:opacity-100 transition-opacity mt-2 block">
                      View Details &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

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
                  disabled={
                    Object.keys(cleanFilters(customFilters)).length === 0
                  }
                  className="w-full py-2.5 rounded-lg bg-accent-blue text-white font-medium hover:bg-accent-blue/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Use Custom Audience & Continue
                </button>
              </div>
            )}
          </div>
        </>
      )}
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
