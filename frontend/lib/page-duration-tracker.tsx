"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { getAccessToken, getSessionId, refreshTokens } from "./api";

const MIN_DURATION_MS = 500;
// If no interaction for this long, assume the user walked away
const IDLE_TIMEOUT_MS = 2 * 60 * 1000; // 2 minutes
const HEARTBEAT_INTERVAL_MS = 30 * 1000; // 30 seconds
const HEARTBEAT_DEBOUNCE_MS = 5 * 1000; // min 5s between heartbeats
const INTERACTION_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
] as const;

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const sid = getSessionId();
  if (sid) {
    headers["X-Session-ID"] = sid;
  }
  return headers;
}

/** Fire-and-forget POST with silent 401 retry (no redirect on failure). */
async function trackingPost(path: string, body: object) {
  const opts: RequestInit = {
    method: "POST",
    headers: getAuthHeaders(),
    credentials: "include",
    body: JSON.stringify(body),
    keepalive: true,
  };
  try {
    const res = await fetch(path, opts);
    if (res.status === 401) {
      const refreshed = await refreshTokens();
      if (refreshed) {
        await fetch(path, { ...opts, headers: getAuthHeaders() });
      }
    }
  } catch {
    // Silent — tracking should never disrupt the user
  }
}

type Trigger = "navigated" | "tab_switch" | "idle" | "closed";

// Track whether we've sent the initial referrer for this page load
let initialReferrerSent = false;

function sendPageview(path: string, durationMs: number, trigger: Trigger) {
  if (durationMs < MIN_DURATION_MS) return;
  const body: Record<string, unknown> = {
    path,
    duration_ms: Math.round(durationMs),
    trigger,
  };
  // Send document.referrer on the very first pageview of the session
  // so the backend can classify the traffic source (direct, google, etc.)
  if (!initialReferrerSent) {
    body.referrer = document.referrer || "";
    initialReferrerSent = true;
  }
  trackingPost("/api/tracking/pageview", body);
}

function sendHeartbeat(path: string, status: "active" | "idle") {
  trackingPost("/api/tracking/heartbeat", { path, status });
}

export default function PageDurationTracker() {
  const pathname = usePathname();
  const lastPath = useRef(pathname);

  // Accumulated active (visible + not idle) time in ms
  const activeAccum = useRef(0);
  // Timestamp when the current active segment started, or 0 if paused
  const activeSince = useRef(
    document.visibilityState === "visible" ? Date.now() : 0,
  );
  // Whether the user is currently idle (no interaction for IDLE_TIMEOUT_MS)
  const isIdle = useRef(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Heartbeat state
  const heartbeatInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastHeartbeatTime = useRef(0);

  /** Send a heartbeat if not debounced. */
  function maybeHeartbeat(status: "active" | "idle") {
    const now = Date.now();
    if (now - lastHeartbeatTime.current < HEARTBEAT_DEBOUNCE_MS) return;
    lastHeartbeatTime.current = now;
    sendHeartbeat(lastPath.current, status);
  }

  /** Bank the current active segment into the accumulator. */
  function bankActive() {
    if (activeSince.current > 0) {
      activeAccum.current += Date.now() - activeSince.current;
      activeSince.current = 0;
    }
  }

  /** Start a new active segment (only if tab is visible and not idle). */
  function startActive() {
    if (
      document.visibilityState === "visible" &&
      !isIdle.current &&
      activeSince.current === 0
    ) {
      activeSince.current = Date.now();
    }
  }

  /** Flush accumulated active time for the current page. */
  function flushDuration(trigger: Trigger) {
    bankActive();
    sendPageview(lastPath.current, activeAccum.current, trigger);
  }

  /** Reset everything for a new page. */
  function resetTimer() {
    activeAccum.current = 0;
    isIdle.current = false;
    activeSince.current =
      document.visibilityState === "visible" ? Date.now() : 0;
    resetIdleTimer();
  }

  /** Reset the idle countdown — called on every interaction. */
  function resetIdleTimer() {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => {
      // No interaction for IDLE_TIMEOUT_MS — flush active segment, go idle
      bankActive();
      sendPageview(lastPath.current, activeAccum.current, "idle");
      activeAccum.current = 0;
      isIdle.current = true;
      // Send idle heartbeat immediately
      maybeHeartbeat("idle");
    }, IDLE_TIMEOUT_MS);
  }

  /** Handle any user interaction — wake from idle if needed. */
  function onInteraction() {
    if (isIdle.current) {
      // User is back — resume counting
      isIdle.current = false;
      startActive();
      // Send active heartbeat immediately on wake
      maybeHeartbeat("active");
    }
    resetIdleTimer();
  }

  // Route change — flush previous page, start fresh
  useEffect(() => {
    if (lastPath.current !== pathname) {
      flushDuration("navigated");
      lastPath.current = pathname;
      resetTimer();
      // Only the visible tab should claim the new path
      if (document.visibilityState === "visible") {
        maybeHeartbeat("active");
      }
    }
  }, [pathname]);

  // Visibility + interaction + heartbeat listeners
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        bankActive();
        // Flush active segment with tab_switch trigger
        sendPageview(lastPath.current, activeAccum.current, "tab_switch");
        activeAccum.current = 0;
        if (idleTimer.current) clearTimeout(idleTimer.current);
        // Send idle heartbeat when tab goes hidden
        maybeHeartbeat("idle");
      } else {
        // Tab visible again — resume counting
        isIdle.current = false;
        startActive();
        resetIdleTimer();
        // Send active heartbeat when tab becomes visible
        maybeHeartbeat("active");
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    for (const evt of INTERACTION_EVENTS) {
      document.addEventListener(evt, onInteraction, { passive: true });
    }

    // Start the idle countdown
    resetIdleTimer();

    // Start heartbeat interval (30s regular pulse)
    heartbeatInterval.current = setInterval(() => {
      if (document.visibilityState === "visible") {
        maybeHeartbeat(isIdle.current ? "idle" : "active");
      }
    }, HEARTBEAT_INTERVAL_MS);

    // Send initial heartbeat only if this tab is the one the user is looking at
    if (document.visibilityState === "visible") {
      maybeHeartbeat("active");
    }

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      for (const evt of INTERACTION_EVENTS) {
        document.removeEventListener(evt, onInteraction);
      }
      if (idleTimer.current) clearTimeout(idleTimer.current);
      if (heartbeatInterval.current) clearInterval(heartbeatInterval.current);
      // Component unmount — flush final duration
      flushDuration("closed");
    };
  }, []);

  return null;
}
