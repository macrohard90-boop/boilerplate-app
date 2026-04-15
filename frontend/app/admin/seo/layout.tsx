"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConfig } from "../../../lib/config-context";

const SEO_TABS = [
  { href: "/admin/seo/overview", label: "Overview" },
  { href: "/admin/seo/meta", label: "Meta Editor" },
  {
    href: "/admin/seo/crawler",
    label: "Crawler",
    feature: "seo_crawler" as const,
  },
  {
    href: "/admin/seo/audit",
    label: "Audit & Scores",
    feature: "seo_scoring" as const,
  },
];

export default function SeoLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { enable_seo_scoring, enable_seo_crawler } = useConfig();

  const visibleTabs = SEO_TABS.filter((tab) => {
    if (tab.feature === "seo_crawler") return enable_seo_crawler;
    if (tab.feature === "seo_scoring") return enable_seo_scoring;
    return true;
  });

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-1 border-b border-glass-border">
          {visibleTabs.map((tab) => {
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
      {children}
    </div>
  );
}
