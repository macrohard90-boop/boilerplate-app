"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { useConfig } from "../../lib/config-context";

interface Stats {
  pageviews: number;
  sessions: number;
  pendingDeletions: number;
}

interface ServiceHealth {
  name: string;
  status: "ok" | "error" | "checking";
}

const SERVICE_LABELS: Record<string, string> = {
  api: "API",
  db: "Database",
  redis: "Cache",
};

export default function AdminDashboardPage() {
  const { enable_tracking } = useConfig();
  const [stats, setStats] = useState<Stats>({ pageviews: 0, sessions: 0, pendingDeletions: 0 });
  const [services, setServices] = useState<ServiceHealth[]>([
    { name: "api", status: "checking" },
    { name: "db", status: "checking" },
    { name: "redis", status: "checking" },
  ]);
  const [statusExpanded, setStatusExpanded] = useState(false);

  useEffect(() => {
    if (enable_tracking) {
      apiFetch<{ total_views: number }>("/tracking/admin/analytics/pageviews")
        .then((d) => setStats((s) => ({ ...s, pageviews: d.total_views || 0 })))
        .catch(() => {});
      apiFetch<{ total_sessions: number }>("/tracking/admin/analytics/sessions")
        .then((d) => setStats((s) => ({ ...s, sessions: d.total_sessions || 0 })))
        .catch(() => {});
    }
    apiFetch<{ total: number }>("/gdpr/admin/deletions?status=grace_period")
      .then((d) => setStats((s) => ({ ...s, pendingDeletions: d.total || 0 })))
      .catch(() => {});

    // Health check — /api/health is unauthenticated
    fetch("/api/health")
      .then((r) => r.json())
      .then((data: { status: string; services: Record<string, string> }) => {
        const result: ServiceHealth[] = [
          { name: "api", status: "ok" },
          { name: "db", status: data.services?.db === "ok" ? "ok" : "error" },
          { name: "redis", status: data.services?.redis === "ok" ? "ok" : "error" },
        ];
        setServices(result);
      })
      .catch(() => {
        setServices([
          { name: "api", status: "error" },
          { name: "db", status: "error" },
          { name: "redis", status: "error" },
        ]);
      });
  }, []);

  const healthyCount = services.filter((s) => s.status === "ok").length;
  const allHealthy = healthyCount === services.length;
  const checking = services.some((s) => s.status === "checking");

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Admin Dashboard</span>
      </h1>

      <div className={`grid grid-cols-1 sm:grid-cols-2 ${enable_tracking ? "lg:grid-cols-4" : "lg:grid-cols-2"} gap-4 mb-8`}>
        {enable_tracking && (
          <>
            <div className="glass rounded-xl p-5">
              <p className="text-xs text-text-muted mb-1">Pageviews (30d)</p>
              <p className="text-2xl font-bold text-text-primary">{stats.pageviews}</p>
            </div>
            <div className="glass rounded-xl p-5">
              <p className="text-xs text-text-muted mb-1">Sessions (30d)</p>
              <p className="text-2xl font-bold text-text-primary">{stats.sessions}</p>
            </div>
          </>
        )}
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Pending Deletions</p>
          <p className={`text-2xl font-bold ${stats.pendingDeletions > 0 ? "text-accent-pink" : "text-text-primary"}`}>
            {stats.pendingDeletions}
          </p>
        </div>
        <div
          className="glass rounded-xl p-5 cursor-pointer hover:bg-base-100/30 transition-colors"
          onClick={() => setStatusExpanded(!statusExpanded)}
        >
          <p className="text-xs text-text-muted mb-1">Status</p>
          {checking ? (
            <p className="text-sm text-text-muted">Checking...</p>
          ) : allHealthy ? (
            <p className="text-sm">
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-300 border border-green-500/30">
                All systems operational
              </span>
            </p>
          ) : (
            <p className="text-sm">
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/30">
                {services.length - healthyCount} service{services.length - healthyCount !== 1 ? "s" : ""} degraded
              </span>
            </p>
          )}
          {statusExpanded && (
            <div className="mt-3 space-y-1.5 border-t border-glass-border/50 pt-3">
              {services.map((s) => (
                <div key={s.name} className="flex items-center justify-between text-xs">
                  <span className="text-text-secondary">{SERVICE_LABELS[s.name] ?? s.name}</span>
                  {s.status === "checking" ? (
                    <span className="text-text-muted">...</span>
                  ) : s.status === "ok" ? (
                    <span className="text-green-400">Operational</span>
                  ) : (
                    <span className="text-red-400">Down</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Quick Links</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { href: "/admin/products", label: "Manage Products" },
            { href: "/admin/orders", label: "Manage Orders" },
            { href: "/admin/users", label: "View Users" },
            ...(enable_tracking ? [{ href: "/admin/analytics", label: "Analytics" }] : []),
            { href: "/admin/gdpr", label: "GDPR Management" },
            { href: "/admin/seo", label: "SEO Settings" },
          ].map((link) => (
            <a key={link.href} href={link.href} className="glass rounded-lg p-3 text-sm text-text-secondary hover:text-accent-pink hover:border-accent-pink/20 transition-all text-center">
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
