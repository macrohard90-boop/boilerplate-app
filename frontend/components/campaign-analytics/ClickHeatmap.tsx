"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";

interface HeatmapZone {
  zone: string;
  total_clicks: number;
  unique_clickers: number;
  distinct_urls: number;
  click_rate: number;
}

interface TopUrl {
  url: string;
  zone: string;
  clicks: number;
  unique_clicks: number;
}

interface HeatmapData {
  campaign_id: string;
  total_recipients: number;
  zones: HeatmapZone[];
  top_urls: TopUrl[];
}

interface ClickHeatmapProps {
  campaignId: string;
}

function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

export default function ClickHeatmap({ campaignId }: ClickHeatmapProps) {
  const [data, setData] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<HeatmapData>(
        `/marketing/analytics/campaigns/${campaignId}/heatmap`,
      );
      setData(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSpinner size="md" className="py-16" />;

  if (!data || data.zones.length === 0) {
    return (
      <div className="glass rounded-xl p-6 text-center text-text-muted text-sm">
        No click data available for this campaign.
      </div>
    );
  }

  const maxClicks = Math.max(...data.zones.map((z) => z.total_clicks), 1);

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-glass-border">
        <h3 className="text-lg font-semibold">Click Heatmap</h3>
        <p className="text-xs text-text-muted mt-1">
          {data.total_recipients.toLocaleString()} total recipients
        </p>
      </div>

      {/* Zone bars */}
      <div className="p-4 space-y-3">
        {data.zones.map((zone) => {
          const widthPct = (zone.total_clicks / maxClicks) * 100;
          return (
            <div key={zone.zone} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary font-mono">
                  {zone.zone}
                </span>
                <span className="text-text-muted">
                  {zone.total_clicks} clicks ({zone.unique_clickers} unique) -{" "}
                  {formatPercent(zone.click_rate)}
                </span>
              </div>
              <div className="h-5 bg-glass-bg rounded overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent-blue to-accent-purple rounded transition-all duration-500"
                  style={{ width: `${Math.max(widthPct, 2)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Top URLs */}
      {data.top_urls.length > 0 && (
        <div className="border-t border-glass-border">
          <div className="p-4">
            <h4 className="text-sm font-semibold text-text-secondary mb-3">
              Top Clicked URLs
            </h4>
            <div className="space-y-2">
              {data.top_urls.slice(0, 10).map((url, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 text-xs hover:bg-glass-hover rounded px-2 py-1.5"
                >
                  <span className="text-text-muted w-4 text-right">
                    {i + 1}
                  </span>
                  <span className="flex-1 font-mono text-accent-blue truncate">
                    {url.url}
                  </span>
                  <span className="badge badge-purple text-xs">{url.zone}</span>
                  <span className="text-text-secondary font-mono">
                    {url.clicks}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
