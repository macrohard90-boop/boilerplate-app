"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const CATALOG_TABS = [
  { href: "/admin/catalog/products", label: "All Products" },
  { href: "/admin/catalog/coupons", label: "Coupons" },
  { href: "/admin/catalog/shipping", label: "Shipping Rates" },
  { href: "/admin/catalog/tax", label: "Tax Rates" },
];

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-1 border-b border-glass-border">
          {CATALOG_TABS.map((tab) => {
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
