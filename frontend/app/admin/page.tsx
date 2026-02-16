"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

interface Stats {
  pageviews?: number;
  sessions?: number;
  events?: number;
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<Stats>({});

  useEffect(() => {
    apiFetch<{ total?: number }>("/tracking/admin/analytics/pageviews?period=7d")
      .then((d) => setStats((s) => ({ ...s, pageviews: d.total || 0 })))
      .catch(() => {});
    apiFetch<{ total?: number }>("/tracking/admin/analytics/sessions?period=7d")
      .then((d) => setStats((s) => ({ ...s, sessions: d.total || 0 })))
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Admin Dashboard</span>
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Pageviews (7d)</p>
          <p className="text-2xl font-bold text-text-primary">{stats.pageviews ?? "—"}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Sessions (7d)</p>
          <p className="text-2xl font-bold text-text-primary">{stats.sessions ?? "—"}</p>
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
            { href: "/admin/gdpr", label: "GDPR Requests" },
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
