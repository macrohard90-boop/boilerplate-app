"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../lib/api";
import { useToast } from "../../../components/Toast";
import { useConfig } from "../../../lib/config-context";
import LoadingSpinner from "../../../components/LoadingSpinner";
import {
  CONSENT_TYPES,
  CATEGORY_LABELS,
  CONSENT_TO_COOKIE_MAP,
} from "../../../lib/consent-types";

interface ConsentItem {
  consent_type: string;
  granted: boolean;
  updated_at: string;
}

interface MarketingPref {
  communication_type_id: string;
  communication_type_name: string;
  description: string | null;
  allowed: boolean;
}

export default function PrivacyPage() {
  const { showToast } = useToast();
  const { enable_marketing } = useConfig();
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Marketing preferences state
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [marketingPrefs, setMarketingPrefs] = useState<MarketingPref[]>([]);
  const [marketingLoading, setMarketingLoading] = useState(false);

  async function fetchConsents() {
    try {
      const data = await apiFetch<{ consents: ConsentItem[] }>("/gdpr/consent");
      setConsents(Array.isArray(data.consents) ? data.consents : []);
    } catch {
      setConsents([]);
    }
    setLoading(false);
  }

  const fetchMarketingPrefs = useCallback(async () => {
    if (!enable_marketing) return;
    setMarketingLoading(true);
    try {
      const data = await apiFetch<{
        marketing_email_consent: boolean;
        preferences: MarketingPref[];
      }>("/marketing/preferences");
      setMarketingConsent(data.marketing_email_consent);
      setMarketingPrefs(data.preferences);
    } catch {
      setMarketingPrefs([]);
    }
    setMarketingLoading(false);
  }, [enable_marketing]);

  useEffect(() => { fetchConsents(); }, []);
  useEffect(() => { fetchMarketingPrefs(); }, [fetchMarketingPrefs]);

  async function toggleConsent(type: string, granted: boolean) {
    const ct = CONSENT_TYPES.find((c) => c.key === type);
    if (ct?.required) return;

    try {
      await apiFetch("/gdpr/consent", {
        method: "POST",
        body: JSON.stringify({ consent_type: type, granted }),
      });
      setConsents((prev) => {
        const exists = prev.find((c) => c.consent_type === type);
        if (exists) {
          return prev.map((c) =>
            c.consent_type === type ? { ...c, granted } : c
          );
        }
        return [...prev, { consent_type: type, granted, updated_at: new Date().toISOString() }];
      });
      showToast(`${ct?.label ?? type} consent ${granted ? "granted" : "revoked"}`, "info");

      // Sync cookie preferences if this is a cookie-related consent
      if (type in CONSENT_TO_COOKIE_MAP) {
        syncCookiePreferences(type, granted);
      }

      // Re-fetch marketing preferences when marketing_email consent changes
      if (type === "marketing_email" && enable_marketing) {
        fetchMarketingPrefs();
      }
    } catch {
      showToast("Failed to update consent", "error");
    }
  }

  async function syncCookiePreferences(changedType: string, granted: boolean) {
    const cookiePrefs: Record<string, boolean> = { necessary: true };
    for (const [consentKey, cookieKey] of Object.entries(CONSENT_TO_COOKIE_MAP)) {
      if (consentKey === changedType) {
        cookiePrefs[cookieKey] = granted;
      } else {
        const existing = consents.find((c) => c.consent_type === consentKey);
        cookiePrefs[cookieKey] = existing?.granted ?? false;
      }
    }
    try {
      await apiFetch("/gdpr/cookies", {
        method: "POST",
        body: JSON.stringify(cookiePrefs),
      });
      localStorage.setItem("cookie_consent", JSON.stringify(cookiePrefs));
    } catch {
      // Best effort sync
    }
  }

  async function toggleMarketingPref(typeId: string, allowed: boolean) {
    try {
      await apiFetch("/marketing/preferences", {
        method: "PUT",
        body: JSON.stringify({ preferences: [{ communication_type_id: typeId, allowed }] }),
      });
      setMarketingPrefs((prev) =>
        prev.map((p) => (p.communication_type_id === typeId ? { ...p, allowed } : p))
      );
      const pref = marketingPrefs.find((p) => p.communication_type_id === typeId);
      showToast(
        `${pref?.communication_type_name ?? "Preference"} ${allowed ? "enabled" : "disabled"}`,
        "info"
      );
    } catch {
      showToast("Failed to update marketing preference", "error");
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      await apiFetch("/gdpr/export", { method: "POST" });
      showToast("Data export requested. You'll receive it soon.", "success");
    } catch (e) {
      const err = e as ApiError;
      showToast(err.message || "Export request failed", "error");
    }
    setExporting(false);
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await apiFetch("/gdpr/delete", { method: "POST" });
      showToast("Deletion request submitted. 30-day grace period applies.", "success");
      setDeleteConfirm(false);
    } catch (e) {
      const err = e as ApiError;
      showToast(err.message || "Deletion request failed", "error");
    }
    setDeleting(false);
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  // Group consent types by category
  const categories = Array.from(new Set(CONSENT_TYPES.map((ct) => ct.category)));

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Privacy & GDPR</span>
      </h1>

      {/* Consent Management */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Consent Preferences</h2>
        <div className="space-y-6">
          {categories.map((category) => (
            <div key={category}>
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">
                {CATEGORY_LABELS[category] ?? category}
              </h3>
              <div className="space-y-3">
                {CONSENT_TYPES.filter((ct) => ct.category === category).map((ct) => {
                  const consent = consents.find((c) => c.consent_type === ct.key);
                  const isGranted = ct.required ? true : (consent?.granted ?? ct.defaultValue);
                  return (
                    <div key={ct.key} className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {ct.label}
                          {ct.required && (
                            <span className="ml-2 text-xs text-text-muted">(Required)</span>
                          )}
                        </p>
                        <p className="text-xs text-text-muted">{ct.description}</p>
                      </div>
                      <button
                        onClick={() => toggleConsent(ct.key, !isGranted)}
                        disabled={ct.required}
                        className={`relative w-12 h-6 rounded-full transition-colors shrink-0 ${
                          isGranted
                            ? "bg-accent-green/30"
                            : "bg-glass-bg"
                        } ${ct.required ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                      >
                        <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
                          isGranted
                            ? "left-6 bg-accent-green"
                            : "left-0.5 bg-text-muted"
                        }`} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Marketing Preferences */}
      {enable_marketing && (
        <div className="glass rounded-xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-text-primary mb-1">Marketing Preferences</h2>
          <p className="text-sm text-text-secondary mb-4">
            Choose which types of marketing communications you&apos;d like to receive.
          </p>

          {marketingLoading ? (
            <LoadingSpinner size="sm" className="py-4" />
          ) : !marketingConsent ? (
            <div className="p-4 rounded-lg bg-accent-blue/10 border border-accent-blue/20">
              <p className="text-sm text-accent-blue">
                Marketing emails are turned off. Enable the{" "}
                <strong>Marketing Email</strong> consent above to manage
                your communication preferences.
              </p>
            </div>
          ) : marketingPrefs.length === 0 ? (
            <p className="text-sm text-text-muted">No communication types available.</p>
          ) : (
            <div className="space-y-3">
              {marketingPrefs.map((pref) => (
                <div key={pref.communication_type_id} className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-sm font-medium text-text-primary capitalize">
                      {pref.communication_type_name}
                    </p>
                    {pref.description && (
                      <p className="text-xs text-text-muted">{pref.description}</p>
                    )}
                  </div>
                  <button
                    onClick={() => toggleMarketingPref(pref.communication_type_id, !pref.allowed)}
                    className={`relative w-12 h-6 rounded-full transition-colors shrink-0 cursor-pointer ${
                      pref.allowed ? "bg-accent-green/30" : "bg-glass-bg"
                    }`}
                  >
                    <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
                      pref.allowed
                        ? "left-6 bg-accent-green"
                        : "left-0.5 bg-text-muted"
                    }`} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Data Export */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-2">Data Export</h2>
        <p className="text-sm text-text-secondary mb-4">
          Request a copy of all your personal data (Right of Access, GDPR Art. 15).
        </p>
        <button onClick={handleExport} disabled={exporting} className="btn-secondary text-sm disabled:opacity-50">
          {exporting ? "Requesting..." : "Request Data Export"}
        </button>
      </div>

      {/* Account Deletion */}
      <div className="glass rounded-xl p-6 border-accent-pink/20">
        <h2 className="text-lg font-semibold text-accent-pink mb-2">Delete Account</h2>
        <p className="text-sm text-text-secondary mb-4">
          Permanently delete your account and all associated data (Right to Erasure, GDPR Art. 17). There is a 30-day grace period during which you can cancel.
        </p>
        {deleteConfirm ? (
          <div className="p-4 rounded-lg bg-accent-pink/10 border border-accent-pink/20">
            <p className="text-sm text-accent-pink mb-3">Are you sure? This cannot be undone after 30 days.</p>
            <div className="flex gap-3">
              <button onClick={handleDelete} disabled={deleting} className="px-4 py-2 rounded-lg bg-accent-pink text-white text-sm font-medium disabled:opacity-50">
                {deleting ? "Deleting..." : "Yes, Delete My Account"}
              </button>
              <button onClick={() => setDeleteConfirm(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </div>
        ) : (
          <button onClick={() => setDeleteConfirm(true)} className="px-4 py-2 rounded-lg border border-accent-pink/30 text-accent-pink text-sm hover:bg-accent-pink/10 transition-colors">
            Request Account Deletion
          </button>
        )}
      </div>
    </div>
  );
}
