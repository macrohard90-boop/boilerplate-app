"use client";

import { useState } from "react";
import Modal from "./Modal";
import { apiFetch } from "../lib/api";
import { useToast } from "./Toast";
import {
  CONSENT_TYPES,
  CATEGORY_LABELS,
  CONSENT_TO_COOKIE_MAP,
} from "../lib/consent-types";

interface ConsentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ConsentModal({ isOpen, onClose }: ConsentModalProps) {
  const { showToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const ct of CONSENT_TYPES) {
      initial[ct.key] = ct.defaultValue;
    }
    return initial;
  });

  function handleToggle(key: string) {
    const ct = CONSENT_TYPES.find((c) => c.key === key);
    if (ct?.required) return;
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      // Save each consent type
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

      // Sync cookie preferences with backend
      const cookiePrefs: Record<string, boolean> = { necessary: true };
      for (const [consentKey, cookieKey] of Object.entries(
        CONSENT_TO_COOKIE_MAP,
      )) {
        cookiePrefs[cookieKey] = toggles[consentKey] ?? false;
      }
      await apiFetch("/gdpr/cookies", {
        method: "POST",
        body: JSON.stringify(cookiePrefs),
      }).catch(() => {});

      // Set localStorage to suppress cookie banner and modal
      localStorage.setItem("cookie_consent", JSON.stringify(cookiePrefs));
      localStorage.setItem("consent_modal_completed", "true");

      showToast("Consent preferences saved", "success");
      onClose();
    } catch {
      showToast("Failed to save preferences", "error");
    }
    setSaving(false);
  }

  function handleDismiss() {
    localStorage.setItem("consent_modal_dismissed", "true");
    onClose();
  }

  // Group consent types by category
  const categories = Array.from(
    new Set(CONSENT_TYPES.map((ct) => ct.category)),
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleDismiss}
      title="Your Privacy Preferences"
      size="lg"
    >
      <p className="text-sm text-text-secondary mb-6">
        Choose how we use your data. You can change these anytime in Dashboard
        &gt; Privacy.
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
                        toggles[ct.key] ? "bg-accent-green/30" : "bg-glass-bg"
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

      <div className="flex gap-3 mt-6 pt-4 border-t border-glass-border">
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary text-sm disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Preferences"}
        </button>
        <button onClick={handleDismiss} className="btn-secondary text-sm">
          Skip for now
        </button>
      </div>
    </Modal>
  );
}
