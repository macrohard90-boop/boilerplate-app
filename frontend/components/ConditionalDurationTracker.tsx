"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth-context";
import { apiFetch } from "../lib/api";
import { useConfig } from "../lib/config-context";
import PageDurationTracker from "../lib/page-duration-tracker";

const COOKIE_KEY = "cookie_consent";

export default function ConditionalDurationTracker() {
  const { enable_tracking } = useConfig();
  const { isAuthenticated, isLoading } = useAuth();
  const [hasConsent, setHasConsent] = useState(false);
  const serverChecked = useRef(false);

  // Check localStorage for consent
  const checkLocalConsent = useCallback((): boolean => {
    try {
      const raw = localStorage.getItem(COOKIE_KEY);
      if (raw) {
        const consent = JSON.parse(raw);
        if (consent?.analytics === true) {
          setHasConsent(true);
          return true;
        }
      }
    } catch {
      // parse error
    }
    return false;
  }, []);

  // On mount + when auth state settles, determine consent
  useEffect(() => {
    if (!enable_tracking || isLoading) return;

    // Fast path: localStorage already has consent
    if (checkLocalConsent()) return;

    // For authenticated users: check server-side consent
    // (handles incognito, new devices, cleared localStorage)
    if (isAuthenticated && !serverChecked.current) {
      serverChecked.current = true;
      apiFetch<{ analytics: boolean }>("/gdpr/cookies")
        .then((prefs) => {
          if (prefs?.analytics) {
            setHasConsent(true);
            // Sync to localStorage so CookieBanner hides + future loads are instant
            try {
              const existing = localStorage.getItem(COOKIE_KEY);
              const consent = existing
                ? JSON.parse(existing)
                : { necessary: true, analytics: false, marketing: false, preferences: false };
              consent.analytics = true;
              localStorage.setItem(COOKIE_KEY, JSON.stringify(consent));
            } catch {
              // localStorage write failed — state-based consent still works
            }
          }
        })
        .catch((err) => {
          // Log but don't crash — will retry on next auth state change
          console.warn("[ConditionalDurationTracker] Failed to check server consent:", err);
          serverChecked.current = false;
        });
    }
  }, [isAuthenticated, isLoading, enable_tracking, checkLocalConsent]);

  // Also listen for localStorage changes (CookieBanner acceptance in same/other tab)
  useEffect(() => {
    if (hasConsent) return; // already consented, no need to poll

    const onStorage = (e: StorageEvent) => {
      if (e.key === COOKIE_KEY) checkLocalConsent();
    };
    window.addEventListener("storage", onStorage);

    // Poll for same-tab writes (storage event only fires cross-tab)
    const interval = setInterval(checkLocalConsent, 3000);

    return () => {
      window.removeEventListener("storage", onStorage);
      clearInterval(interval);
    };
  }, [hasConsent, checkLocalConsent]);

  if (!enable_tracking || !hasConsent) return null;
  return <PageDurationTracker />;
}
