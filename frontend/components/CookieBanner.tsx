"use client";

import { useEffect, useState } from "react";

const COOKIE_KEY = "cookie_consent";

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);
  const [prefs, setPrefs] = useState({
    necessary: true,
    analytics: false,
    marketing: false,
    preferences: false,
  });

  useEffect(() => {
    const saved = localStorage.getItem(COOKIE_KEY);
    if (!saved) {
      setVisible(true);
    }
  }, []);

  function savePrefs(all: boolean) {
    const consent = all
      ? { necessary: true, analytics: true, marketing: true, preferences: true }
      : prefs;

    localStorage.setItem(COOKIE_KEY, JSON.stringify(consent));
    setVisible(false);

    // Sync with backend (best effort)
    fetch("/api/gdpr/cookies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(consent),
    }).catch(() => {});
  }

  function rejectNonEssential() {
    const consent = { necessary: true, analytics: false, marketing: false, preferences: false };
    localStorage.setItem(COOKIE_KEY, JSON.stringify(consent));
    setVisible(false);

    fetch("/api/gdpr/cookies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(consent),
    }).catch(() => {});
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-[150] p-4">
      <div className="max-w-3xl mx-auto glass rounded-2xl p-6 shadow-2xl">
        {!showCustomize ? (
          <>
            <div className="flex items-start gap-4">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-text-primary mb-1">Cookie Preferences</h3>
                <p className="text-xs text-text-secondary">
                  We use cookies to enhance your experience. Some are necessary for the site to work, others help us improve it.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 mt-4">
              <button onClick={() => savePrefs(true)} className="btn-primary text-xs !px-4 !py-2">
                Accept All
              </button>
              <button onClick={rejectNonEssential} className="btn-secondary text-xs !px-4 !py-2">
                Reject Non-Essential
              </button>
              <button onClick={() => setShowCustomize(true)} className="text-xs text-text-muted hover:text-text-secondary transition-colors px-4 py-2">
                Customize
              </button>
            </div>
          </>
        ) : (
          <>
            <h3 className="text-sm font-semibold text-text-primary mb-4">Customize Cookies</h3>
            <div className="space-y-3">
              {Object.entries(prefs).map(([key, val]) => {
                const isNecessary = key === "necessary";
                return (
                  <label key={key} className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary capitalize">{key}</span>
                    <button
                      onClick={() => !isNecessary && setPrefs((p) => ({ ...p, [key]: !val }))}
                      disabled={isNecessary}
                      className={`relative w-10 h-5 rounded-full transition-colors ${val ? "bg-accent-green/30" : "bg-glass-bg"} ${isNecessary ? "opacity-50" : "cursor-pointer"}`}
                    >
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${val ? "left-5 bg-accent-green" : "left-0.5 bg-text-muted"}`} />
                    </button>
                  </label>
                );
              })}
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => savePrefs(false)} className="btn-primary text-xs !px-4 !py-2">
                Save Preferences
              </button>
              <button onClick={() => setShowCustomize(false)} className="text-xs text-text-muted hover:text-text-secondary transition-colors px-4 py-2">
                Back
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
