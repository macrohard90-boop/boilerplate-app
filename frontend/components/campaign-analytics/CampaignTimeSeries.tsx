"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";

const AreaSparkChart = dynamic(() => import("../charts/AreaSparkChart"), {
  ssr: false,
});

interface TimeSeriesPoint {
  timestamp: string;
  delivered: number;
  opened: number;
  clicked: number;
}

interface CampaignTimeSeriesProps {
  campaignId: string;
}

export default function CampaignTimeSeries({
  campaignId,
}: CampaignTimeSeriesProps) {
  const [data, setData] = useState<TimeSeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [interval, setInterval] = useState<"hour" | "day">("hour");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<TimeSeriesPoint[]>(
        `/marketing/analytics/campaigns/${campaignId}/time-series?interval=${interval}`,
      );
      setData(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [campaignId, interval]);

  useEffect(() => {
    load();
  }, [load]);

  const chartData = data.map((p) => {
    const d = new Date(p.timestamp);
    const label =
      interval === "hour"
        ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : d.toLocaleDateString([], { month: "short", day: "numeric" });
    return {
      label,
      value: p.delivered,
      value2: p.opened,
      value3: p.clicked,
    };
  });

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Engagement Over Time</h3>
        <div className="flex gap-1">
          {(["hour", "day"] as const).map((i) => (
            <button
              key={i}
              onClick={() => setInterval(i)}
              className={`px-3 py-1 text-xs rounded transition-all ${
                interval === i
                  ? "bg-accent-pink/20 text-accent-pink"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {i === "hour" ? "Hourly" : "Daily"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner size="md" className="py-16" />
      ) : chartData.length === 0 ? (
        <div className="py-16 text-center text-text-muted text-sm">
          No time-series data available.
        </div>
      ) : (
        <AreaSparkChart
          data={chartData}
          height={250}
          color="#38bdf8"
          color2="#c084fc"
          color3="#ff6b9d"
          valueLabel="Delivered"
          valueLabel2="Opened"
          valueLabel3="Clicked"
          showGrid
        />
      )}
    </div>
  );
}
