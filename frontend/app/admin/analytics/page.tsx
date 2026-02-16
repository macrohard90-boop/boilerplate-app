"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface AnalyticsData {
  pageviews: { total: number; data?: { path: string; count: number }[] };
  sessions: { total: number };
  sources: { data?: { source: string; count: number }[] };
  utm: { data?: { campaign: string; count: number }[] };
}

export default function AdminAnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<AnalyticsData["pageviews"]>("/tracking/admin/analytics/pageviews?period=30d").catch(() => ({ total: 0 })),
      apiFetch<AnalyticsData["sessions"]>("/tracking/admin/analytics/sessions?period=30d").catch(() => ({ total: 0 })),
      apiFetch<AnalyticsData["sources"]>("/tracking/admin/analytics/sources?period=30d").catch(() => ({ data: [] })),
      apiFetch<AnalyticsData["utm"]>("/tracking/admin/analytics/utm?period=30d").catch(() => ({ data: [] })),
    ]).then(([pageviews, sessions, sources, utm]) => {
      setData({ pageviews, sessions, sources, utm });
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Analytics</span>
        <span className="text-text-muted font-normal text-sm ml-2">(Last 30 days)</span>
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Total Pageviews</p>
          <p className="text-3xl font-bold text-text-primary">{data?.pageviews.total || 0}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Total Sessions</p>
          <p className="text-3xl font-bold text-text-primary">{data?.sessions.total || 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top pages */}
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Top Pages</h2>
          {data?.pageviews.data && data.pageviews.data.length > 0 ? (
            <div className="space-y-2">
              {data.pageviews.data.slice(0, 10).map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-text-secondary truncate flex-1">{item.path}</span>
                  <span className="text-text-primary font-medium ml-2">{item.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No data available</p>
          )}
        </div>

        {/* Traffic sources */}
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Traffic Sources</h2>
          {data?.sources.data && data.sources.data.length > 0 ? (
            <div className="space-y-2">
              {data.sources.data.slice(0, 10).map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-text-secondary">{item.source || "Direct"}</span>
                  <span className="text-text-primary font-medium">{item.count}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No data available</p>
          )}
        </div>
      </div>
    </div>
  );
}
