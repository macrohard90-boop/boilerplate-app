"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../lib/api";
import { useToast } from "../../../components/Toast";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface ConsentItem {
  consent_type: string;
  granted: boolean;
  updated_at: string;
}

const CONSENT_LABELS: Record<string, { label: string; description: string }> = {
  necessary: { label: "Necessary", description: "Required for the site to function" },
  analytics: { label: "Analytics", description: "Help us understand how you use the site" },
  marketing: { label: "Marketing", description: "Personalized ads and promotions" },
  preferences: { label: "Preferences", description: "Remember your settings and choices" },
  functional: { label: "Functional", description: "Enhanced features and personalization" },
  third_party: { label: "Third Party", description: "Third-party integrations" },
};

export default function PrivacyPage() {
  const { showToast } = useToast();
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  async function fetchConsents() {
    try {
      const data = await apiFetch<ConsentItem[]>("/gdpr/consents");
      setConsents(Array.isArray(data) ? data : []);
    } catch {
      setConsents([]);
    }
    setLoading(false);
  }

  useEffect(() => { fetchConsents(); }, []);

  async function toggleConsent(type: string, granted: boolean) {
    try {
      await apiFetch("/gdpr/consents", {
        method: "POST",
        body: JSON.stringify({ consent_type: type, granted }),
      });
      setConsents((prev) =>
        prev.map((c) => c.consent_type === type ? { ...c, granted } : c)
      );
      showToast(`${type} consent ${granted ? "granted" : "revoked"}`, "info");
    } catch {
      showToast("Failed to update consent", "error");
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

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Privacy & GDPR</span>
      </h1>

      {/* Consent Management */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Consent Preferences</h2>
        <div className="space-y-4">
          {Object.entries(CONSENT_LABELS).map(([type, info]) => {
            const consent = consents.find((c) => c.consent_type === type);
            const isNecessary = type === "necessary";
            return (
              <div key={type} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-text-primary">{info.label}</p>
                  <p className="text-xs text-text-muted">{info.description}</p>
                </div>
                <button
                  onClick={() => !isNecessary && toggleConsent(type, !consent?.granted)}
                  disabled={isNecessary}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    consent?.granted || isNecessary
                      ? "bg-accent-green/30"
                      : "bg-glass-bg"
                  } ${isNecessary ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <div className={`absolute top-0.5 w-5 h-5 rounded-full transition-all ${
                    consent?.granted || isNecessary
                      ? "left-6 bg-accent-green"
                      : "left-0.5 bg-text-muted"
                  }`} />
                </button>
              </div>
            );
          })}
        </div>
      </div>

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
