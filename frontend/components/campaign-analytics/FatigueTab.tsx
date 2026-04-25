"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";

const AreaSparkChart = dynamic(() => import("../charts/AreaSparkChart"), {
  ssr: false,
});

interface FatigueMetrics {
  period_days: number;
  unsubscribe_trend: { week: string; unsubscribes: number }[];
  over_messaged_users: number;
  complaint_rate: number;
}

const DAY_OPTIONS = [7, 14, 30, 60, 90];

function formatPercent(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

export default function FatigueTab() {
  const [data, setData] = useState<FatigueMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<FatigueMetrics>(
        `/marketing/analytics/effectiveness/fatigue?days=${days}`,
      );
      setData(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;
  if (!data)
    return (
      <div className="glass rounded-xl p-12 text-center text-text-secondary">
        No fatigue data available.
      </div>
    );

  const complaintSeverity =
    data.complaint_rate > 0.003
      ? "critical"
      : data.complaint_rate > 0.001
        ? "warning"
        : "ok";

  const chartData = data.unsubscribe_trend.map((d) => ({
    label: new Date(d.week).toLocaleDateString([], {
      month: "short",
      day: "numeric",
    }),
    value: d.unsubscribes,
  }));

  return (
    <div className="space-y-6">
      {/* Controls */}
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

      {/* Warning cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div
          className={`glass rounded-xl p-5 border ${
            complaintSeverity === "critical"
              ? "border-accent-pink/40"
              : complaintSeverity === "warning"
                ? "border-yellow-500/30"
                : "border-accent-green/20"
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {complaintSeverity === "critical" && (
              <span className="text-accent-pink text-lg">!</span>
            )}
            <span className="text-sm text-text-secondary">Complaint Rate</span>
          </div>
          <p
            className={`text-2xl font-bold ${
              complaintSeverity === "critical"
                ? "text-accent-pink"
                : complaintSeverity === "warning"
                  ? "text-yellow-400"
                  : "text-accent-green"
            }`}
          >
            {formatPercent(data.complaint_rate)}
          </p>
          <p className="text-xs text-text-muted mt-1">
            {complaintSeverity === "critical"
              ? "Above 0.3% — risk of provider penalties"
              : complaintSeverity === "warning"
                ? "Above 0.1% — monitor closely"
                : "Healthy range"}
          </p>
        </div>

        <div className="glass rounded-xl p-5">
          <span className="text-sm text-text-secondary">
            Over-Messaged Users
          </span>
          <p
            className={`text-2xl font-bold mt-2 ${
              data.over_messaged_users > 100
                ? "text-accent-pink"
                : data.over_messaged_users > 20
                  ? "text-yellow-400"
                  : "text-text-primary"
            }`}
          >
            {data.over_messaged_users.toLocaleString()}
          </p>
          <p className="text-xs text-text-muted mt-1">
            Users receiving 5+ campaigns in {data.period_days} days
          </p>
        </div>

        <div className="glass rounded-xl p-5">
          <span className="text-sm text-text-secondary">
            Total Unsubscribes
          </span>
          <p className="text-2xl font-bold mt-2 text-text-primary">
            {data.unsubscribe_trend
              .reduce((s, d) => s + d.unsubscribes, 0)
              .toLocaleString()}
          </p>
          <p className="text-xs text-text-muted mt-1">
            Over {data.period_days} day period
          </p>
        </div>
      </div>

      {/* Unsubscribe trend chart */}
      {chartData.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-text-secondary mb-4">
            Unsubscribe Trend (Weekly)
          </h3>
          <AreaSparkChart
            data={chartData}
            height={200}
            color="#ff6b9d"
            valueLabel="Unsubscribes"
            showGrid
          />
        </div>
      )}
    </div>
  );
}
