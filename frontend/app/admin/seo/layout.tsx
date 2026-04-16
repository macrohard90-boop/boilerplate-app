"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConfig } from "../../../lib/config-context";

/* ── Top-level section tabs (SEO vs GEO) ──────────────────────── */

const MAIN_TABS = [
  { id: "seo", label: "SEO", href: "/admin/seo/discover", feature: null },
  { id: "geo", label: "GEO", href: "/admin/seo/geo", feature: "geo_scoring" as const },
];

/* ── SEO sub-tabs (stage-based) ────────────────────────────────── */

const SEO_SUB_TABS = [
  { href: "/admin/seo/discover", label: "Discover", feature: null },
  {
    href: "/admin/seo/optimize",
    label: "Optimize",
    feature: "seo_scoring" as const,
  },
  {
    href: "/admin/seo/verify",
    label: "Verify",
    feature: "seo_crawler" as const,
  },
];

export default function SeoLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const {
    enable_seo_scoring,
    enable_seo_crawler,
    enable_seo_keywords,
    enable_geo_scoring,
  } = useConfig();

  const isGeo = pathname.startsWith("/admin/seo/geo");
  const activeMainTab = isGeo ? "geo" : "seo";

  const visibleMainTabs = MAIN_TABS.filter((tab) => {
    if (tab.feature === "geo_scoring") return enable_geo_scoring;
    return true;
  });

  const visibleSubTabs = SEO_SUB_TABS.filter((tab) => {
    if (tab.feature === "seo_scoring") return enable_seo_scoring;
    if (tab.feature === "seo_crawler") return enable_seo_crawler;
    return true;
  });

  return (
    <div>
      {/* Top row: SEO | GEO */}
      <div className="mb-2">
        <div className="flex items-center gap-1">
          {visibleMainTabs.map((tab) => {
            const active = activeMainTab === tab.id;
            return (
              <Link
                key={tab.id}
                href={tab.href}
                className={`px-5 py-2 text-sm font-semibold transition-colors relative rounded-t-lg ${
                  active
                    ? "text-text-primary bg-glass-bg"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {tab.label}
                {active && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-accent-purple rounded-full" />
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Sub-tabs row (only when SEO section is active) */}
      {!isGeo && (
        <div className="mb-6">
          <div className="flex items-center gap-1 border-b border-glass-border">
            {visibleSubTabs.map((tab) => {
              const active =
                pathname === tab.href || pathname.startsWith(tab.href + "/");
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
                    active
                      ? "text-accent-pink"
                      : "text-text-muted hover:text-text-primary"
                  }`}
                >
                  {tab.label}
                  {active && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-pink rounded-full" />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {children}
    </div>
  );
}
