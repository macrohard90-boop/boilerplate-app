"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PAYMENT_TABS = [
  { href: "/admin/payments", label: "Methods" },
  { href: "/admin/payments/fees", label: "Fee Tiers" },
];

export default function PaymentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-1 border-b border-glass-border">
          {PAYMENT_TABS.map((tab) => {
            const active =
              tab.href === "/admin/payments"
                ? pathname === "/admin/payments"
                : pathname === tab.href || pathname.startsWith(tab.href + "/");
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
