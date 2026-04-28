"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth-context";
import { apiFetch } from "../../lib/api";
import { trackEvent } from "../../lib/track-event";
import { useToast } from "../../components/Toast";
import LoadingSpinner from "../../components/LoadingSpinner";
import {
  CONSENT_TYPES,
  CATEGORY_LABELS,
  CONSENT_TO_COOKIE_MAP,
} from "../../lib/consent-types";

const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  },
  {
    href: "/dashboard/orders",
    label: "Orders",
    icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
  },
  {
    href: "/dashboard/profile",
    label: "Profile",
    icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  },
  {
    href: "/dashboard/privacy",
    label: "Privacy",
    icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  },
];

/**
 * Save consent preferences to backend + localStorage.
 * Shared by "Save Preferences" and "Accept All" flows.
 */
async function persistConsent(
  toggles: Record<string, boolean>,
  userId: string,
) {
  await Promise.all(
    CONSENT_TYPES.map((ct) =>
      apiFetch("/gdpr/consent", {
        method: "POST",
        body: JSON.stringify({
          consent_type: ct.key,
          granted: toggles[ct.key],
        }),
      }),
    ),
  );

  const cookiePrefs: Record<string, boolean> = { necessary: true };
  for (const [consentKey, cookieKey] of Object.entries(CONSENT_TO_COOKIE_MAP)) {
    cookiePrefs[cookieKey] = toggles[consentKey] ?? false;
  }
  await apiFetch("/gdpr/cookies", {
    method: "POST",
    body: JSON.stringify(cookiePrefs),
  }).catch(() => {});

  localStorage.setItem("cookie_consent", JSON.stringify(cookiePrefs));
  localStorage.setItem(`consent_completed_${userId}`, "true");

  return cookiePrefs;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const { showToast } = useToast();
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [consentState, setConsentState] = useState<
    "loading" | "needed" | "done"
  >("loading");
  const [saving, setSaving] = useState(false);
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const ct of CONSENT_TYPES) {
      initial[ct.key] = ct.defaultValue;
    }
    return initial;
  });

  useEffect(() => {
    if (!isAuthenticated || isLoading || !user) return;

    // User-specific localStorage key — prevents stale consent from a different account
    const consentKey = `consent_completed_${user.id}`;
    const completed = localStorage.getItem(consentKey);
    if (completed) {
      setConsentState("done");
      return;
    }

    // Check backend for existing consent records (returning user, different session)
    (async () => {
      try {
        const data = await apiFetch<{
          consents: Array<{
            consent_type: string;
            granted: boolean;
            updated_at: string | null;
          }>;
        }>("/gdpr/consent");
        const hasRecords = data.consents?.some((c) => c.updated_at !== null);
        if (hasRecords) {
          // Returning user — sync localStorage from DB records and skip consent screen
          localStorage.setItem(consentKey, "true");
          const cookiePrefs: Record<string, boolean> = { necessary: true };
          for (const [ctKey, ckKey] of Object.entries(CONSENT_TO_COOKIE_MAP)) {
            const record = data.consents.find((c) => c.consent_type === ctKey);
            cookiePrefs[ckKey] = record?.granted ?? false;
          }
          localStorage.setItem("cookie_consent", JSON.stringify(cookiePrefs));
          setConsentState("done");
        } else {
          setConsentState("needed");
        }
      } catch {
        // If API fails, require consent to be safe
        setConsentState("needed");
      }
    })();
  }, [isAuthenticated, isLoading, user]);

  function handleToggle(key: string) {
    const ct = CONSENT_TYPES.find((c) => c.key === key);
    if (ct?.required) return;
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const cookiePrefs = await persistConsent(toggles, user!.id);
      trackEvent("cookie_consent_given", {
        analytics: cookiePrefs.analytics ?? false,
        marketing: cookiePrefs.marketing ?? false,
        method: "customized",
      });
      showToast("Consent preferences saved", "success");
      setConsentState("done");
    } catch {
      showToast("Failed to save preferences", "error");
    }
    setSaving(false);
  }

  async function handleAcceptAll() {
    setSaving(true);
    try {
      const allAccepted: Record<string, boolean> = {};
      for (const ct of CONSENT_TYPES) {
        allAccepted[ct.key] = true;
      }
      const cookiePrefs = await persistConsent(allAccepted, user!.id);
      trackEvent("cookie_consent_given", {
        analytics: cookiePrefs.analytics ?? false,
        marketing: cookiePrefs.marketing ?? false,
        method: "accept_all",
      });
      setConsentState("done");
    } catch {
      showToast("Failed to save preferences", "error");
    }
    setSaving(false);
  }

  if (isLoading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!isAuthenticated) {
    router.push("/auth/login");
    return null;
  }

  if (consentState === "loading") {
    return <LoadingSpinner size="lg" className="py-40" />;
  }

  // ── Consent screen (blocks dashboard until user consents) ──
  if (consentState === "needed") {
    const categories = Array.from(
      new Set(CONSENT_TYPES.map((ct) => ct.category)),
    );

    return (
      <div className="max-w-2xl mx-auto px-4 py-16">
        <div className="glass rounded-xl p-8">
          <h1 className="font-serif text-2xl font-bold mb-2">
            <span className="gradient-text">Your Privacy Preferences</span>
          </h1>
          <p className="text-sm text-text-secondary mb-6">
            Choose how we use your data. You can change these anytime in
            Dashboard &gt; Privacy.
          </p>

          <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-1">
            {categories.map((category) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-text-primary mb-3">
                  {CATEGORY_LABELS[category] ?? category}
                </h3>
                <div className="space-y-3">
                  {CONSENT_TYPES.filter((ct) => ct.category === category).map(
                    (ct) => (
                      <div
                        key={ct.key}
                        className="flex items-center justify-between py-2"
                      >
                        <div className="pr-4">
                          <p className="text-sm font-medium text-text-primary">
                            {ct.label}
                            {ct.required && (
                              <span className="ml-2 text-xs text-text-muted">
                                (Required)
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-text-muted">
                            {ct.description}
                          </p>
                        </div>
                        <button
                          onClick={() => handleToggle(ct.key)}
                          disabled={ct.required}
                          className={`relative w-12 h-6 rounded-full transition-colors shrink-0 ${
                            toggles[ct.key]
                              ? "bg-accent-green/30"
                              : "bg-glass-bg"
                          } ${ct.required ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                        >
                          <div
                            className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
                              toggles[ct.key]
                                ? "left-6 bg-accent-green"
                                : "left-0.5 bg-text-muted"
                            }`}
                          />
                        </button>
                      </div>
                    ),
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col-reverse sm:flex-row gap-3 mt-6 pt-4 border-t border-glass-border">
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full sm:w-auto btn-primary text-sm disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Preferences"}
            </button>
            <button
              onClick={handleAcceptAll}
              disabled={saving}
              className="w-full sm:w-auto btn-secondary text-sm disabled:opacity-50"
            >
              {saving ? "..." : "Accept All & Continue"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Normal dashboard layout ──
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex gap-8">
        {/* Mobile toggle */}
        <button
          className="lg:hidden fixed bottom-4 left-4 z-50 btn-primary !p-3 !rounded-full shadow-lg"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>

        {/* Sidebar */}
        <aside
          className={`w-56 shrink-0 ${sidebarOpen ? "fixed inset-0 z-40 bg-black/50 lg:relative lg:bg-transparent" : "hidden lg:block"}`}
        >
          {sidebarOpen && (
            <div
              className="fixed inset-0 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}
          <nav
            className={`glass rounded-xl p-4 space-y-1 sticky top-24 ${sidebarOpen ? "relative z-50 m-4 lg:m-0" : ""}`}
          >
            {NAV_ITEMS.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                    active
                      ? "bg-accent-purple/10 text-accent-purple"
                      : "text-text-secondary hover:text-text-primary hover:bg-glass-hover"
                  }`}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-5 w-5 shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d={item.icon}
                    />
                  </svg>
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
