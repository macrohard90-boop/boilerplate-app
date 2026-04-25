"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";

const AreaSparkChart = dynamic(() => import("../charts/AreaSparkChart"), {
  ssr: false,
});

interface EngagementTrend {
  period: string;
  campaigns: number;
  avg_open_rate: number;
  avg_click_rate: number;
  avg_conversion_rate: number;
  total_sent: number;
  bounce_rate: number;
}

const DAY_OPTIONS = [7, 14, 30, 60, 90];

function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

export default function TrendsTab() {
  const [data, setData] = useState<EngagementTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [interval, setInterval] = useState<"day" | "week">("day");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<EngagementTrend[]>(
        `/marketing/analytics/effectiveness/trends?days=${days}&interval=${interval}`,
      );
      setData(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [days, interval]);

  useEffect(() => {
    load();
  }, [load]);

  // Summary calculations
  const totalCampaigns = data.reduce((sum, d) => sum + d.campaigns, 0);
  const totalSent = data.reduce((sum, d) => sum + d.total_sent, 0);
  const avgOpen =
    data.length > 0
      ? data.reduce((sum, d) => sum + d.avg_open_rate, 0) / data.length
      : 0;
  const avgClick =
    data.length > 0
      ? data.reduce((sum, d) => sum + d.avg_click_rate, 0) / data.length
      : 0;

  const chartData = data.map((d) => {
    const date = new Date(d.period);
    return {
      label:
        interval === "day"
          ? date.toLocaleDateString([], { month: "short", day: "numeric" })
          : `W${Math.ceil(date.getDate() / 7)}`,
      value: d.avg_open_rate * 100,
      value2: d.avg_click_rate * 100,
      value3: d.avg_conversion_rate * 100,
    };
  });

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-2 py-1 text-xs rounded transition-all ${
                days === d
                  ? "bg-accent-pink/20 text-accent-pink"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(["day", "week"] as const).map((i) => (
            <button
              key={i}
              onClick={() => setInterval(i)}
              className={`px-3 py-1 text-xs rounded transition-all ${
                interval === i
                  ? "bg-accent-purple/20 text-accent-purple"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {i === "day" ? "Daily" : "Weekly"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner size="lg" className="py-20" />
      ) : data.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center text-text-secondary">
          No trend data for this period.
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass rounded-lg p-3 text-center">
              <span className="text-xs text-text-muted">Campaigns</span>
              <p className="text-lg font-bold text-text-primary mt-1">
                {totalCampaigns}
              </p>
            </div>
            <div className="glass rounded-lg p-3 text-center">
              <span className="text-xs text-text-muted">Total Sent</span>
              <p className="text-lg font-bold text-text-primary mt-1">
                {totalSent.toLocaleString()}
              </p>
            </div>
            <div className="glass rounded-lg p-3 text-center">
              <span className="text-xs text-text-muted">Avg Open Rate</span>
              <p className="text-lg font-bold text-accent-blue mt-1">
                {formatPercent(avgOpen)}
              </p>
            </div>
            <div className="glass rounded-lg p-3 text-center">
              <span className="text-xs text-text-muted">Avg Click Rate</span>
              <p className="text-lg font-bold text-accent-purple mt-1">
                {formatPercent(avgClick)}
              </p>
            </div>
          </div>

          {/* Chart */}
          <div className="glass rounded-xl p-6">
            <h3 className="text-sm font-semibold text-text-secondary mb-4">
              Engagement Rate Trends (%)
            </h3>
            <AreaSparkChart
              data={chartData}
              height={280}
              color="#38bdf8"
              color2="#c084fc"
              color3="#34d399"
              valueLabel="Open %"
              valueLabel2="Click %"
              valueLabel3="Conv %"
              showGrid
            />
          </div>
        </>
      )}
    </div>
  );
}
