"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

interface Stats {
  pageviews: number;
  sessions: number;
  pendingDeletions: number;
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<Stats>({ pageviews: 0, sessions: 0, pendingDeletions: 0 });

  useEffect(() => {
    apiFetch<{ total_views: number }>("/tracking/admin/analytics/pageviews")
      .then((d) => setStats((s) => ({ ...s, pageviews: d.total_views || 0 })))
      .catch(() => {});
    apiFetch<{ total_sessions: number }>("/tracking/admin/analytics/sessions")
      .then((d) => setStats((s) => ({ ...s, sessions: d.total_sessions || 0 })))
      .catch(() => {});
    apiFetch<{ total: number }>("/gdpr/admin/deletions?status=grace_period")
      .then((d) => setStats((s) => ({ ...s, pendingDeletions: d.total || 0 })))
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Admin Dashboard</span>
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Pageviews (30d)</p>
          <p className="text-2xl font-bold text-text-primary">{stats.pageviews}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Sessions (30d)</p>
          <p className="text-2xl font-bold text-text-primary">{stats.sessions}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Pending Deletions</p>
          <p className={`text-2xl font-bold ${stats.pendingDeletions > 0 ? "text-accent-pink" : "text-text-primary"}`}>
            {stats.pendingDeletions}
          </p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Status</p>
          <p className="text-sm"><span className="badge-green">All systems operational</span></p>
        </div>
      </div>

      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Quick Links</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { href: "/admin/products", label: "Manage Products" },
            { href: "/admin/orders", label: "Manage Orders" },
            { href: "/admin/users", label: "View Users" },
            { href: "/admin/analytics", label: "Analytics" },
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
