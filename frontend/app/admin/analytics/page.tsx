"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface PageViewStats {
  total_views: number;
  unique_visitors: number;
  top_pages: { path: string; views: number; unique_visitors: number }[];
}

interface SessionStats {
  total_sessions: number;
  avg_page_count: number;
}

interface SourceStats {
  sources: { source: string; medium: string | null; sessions: number }[];
}

interface UTMStats {
  campaigns: { utm_source: string | null; utm_medium: string | null; utm_campaign: string | null; sessions: number }[];
}

interface DeviceStats {
  total_agents: number;
  by_device_type: { device_type: string; count: number }[];
  by_browser: { browser: string; count: number }[];
  by_os: { os: string; count: number }[];
}

function BreakdownBar({ items, colorClass }: { items: { label: string; count: number }[]; colorClass: string }) {
  const total = items.reduce((sum, i) => sum + i.count, 0);
  if (total === 0) return <p className="text-sm text-text-muted">No data available</p>;

  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const pct = Math.round((item.count / total) * 100);
        return (
          <div key={i}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-text-secondary">{item.label}</span>
              <span className="text-text-muted text-xs">{item.count} ({pct}%)</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-glass-bg overflow-hidden">
              <div
                className={`h-full rounded-full ${colorClass} transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [pageviews, setPageviews] = useState<PageViewStats | null>(null);
  const [sessions, setSessions] = useState<SessionStats | null>(null);
  const [sources, setSources] = useState<SourceStats | null>(null);
  const [utm, setUtm] = useState<UTMStats | null>(null);
  const [devices, setDevices] = useState<DeviceStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<PageViewStats>("/tracking/admin/analytics/pageviews").catch(() => null),
      apiFetch<SessionStats>("/tracking/admin/analytics/sessions").catch(() => null),
      apiFetch<SourceStats>("/tracking/admin/analytics/sources").catch(() => null),
      apiFetch<UTMStats>("/tracking/admin/analytics/utm").catch(() => null),
      apiFetch<DeviceStats>("/tracking/admin/analytics/devices").catch(() => null),
    ]).then(([pv, sess, src, u, dev]) => {
      setPageviews(pv);
      setSessions(sess);
      setSources(src);
      setUtm(u);
      setDevices(dev);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Analytics</span>
        <span className="text-text-muted font-normal text-sm ml-2">(Last 30 days)</span>
      </h1>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Total Pageviews</p>
          <p className="text-3xl font-bold text-text-primary">{pageviews?.total_views ?? 0}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Unique Visitors</p>
          <p className="text-3xl font-bold text-text-primary">{pageviews?.unique_visitors ?? 0}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Total Sessions</p>
          <p className="text-3xl font-bold text-text-primary">{sessions?.total_sessions ?? 0}</p>
        </div>
      </div>

      {/* Device / Browser / OS breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Device Types</h2>
          <BreakdownBar
            items={(devices?.by_device_type ?? []).map((d) => ({ label: d.device_type, count: d.count }))}
            colorClass="bg-accent-purple/60"
          />
        </div>
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Browsers</h2>
          <BreakdownBar
            items={(devices?.by_browser ?? []).map((d) => ({ label: d.browser, count: d.count }))}
            colorClass="bg-accent-blue/60"
          />
        </div>
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Operating Systems</h2>
          <BreakdownBar
            items={(devices?.by_os ?? []).map((d) => ({ label: d.os, count: d.count }))}
            colorClass="bg-accent-green/60"
          />
        </div>
      </div>

      {/* Top Pages + Traffic Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Top Pages</h2>
          {pageviews?.top_pages && pageviews.top_pages.length > 0 ? (
            <div className="space-y-2">
              {pageviews.top_pages.slice(0, 10).map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-text-secondary truncate flex-1 font-mono text-xs">{item.path}</span>
                  <span className="text-text-primary font-medium ml-2">{item.views}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No data available</p>
          )}
        </div>

        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Traffic Sources</h2>
          {sources?.sources && sources.sources.length > 0 ? (
            <div className="space-y-2">
              {sources.sources.slice(0, 10).map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-text-secondary">
                    {item.source || "Direct"}
                    {item.medium && <span className="text-text-muted"> / {item.medium}</span>}
                  </span>
                  <span className="text-text-primary font-medium">{item.sessions}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No data available</p>
          )}
        </div>
      </div>

      {/* UTM Campaigns */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">UTM Campaigns</h2>
        {utm?.campaigns && utm.campaigns.length > 0 ? (
          <div className="space-y-2">
            {utm.campaigns.slice(0, 10).map((item, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-text-secondary">
                  {item.utm_campaign || item.utm_source || "Unknown"}
                  {item.utm_medium && <span className="text-text-muted"> ({item.utm_medium})</span>}
                </span>
                <span className="text-text-primary font-medium">{item.sessions}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No UTM campaign data</p>
        )}
      </div>
    </div>
  );
}
