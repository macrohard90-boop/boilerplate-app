import { getAccessToken, getSessionId, refreshTokens } from "./api";

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

/**
 * Build a JSON body with auth fields embedded for sendBeacon delivery.
 * The backend reads _access_token and _session_id from the body when
 * the Authorization header is absent (sendBeacon can't set headers).
 */
function buildBeaconBody(
  eventType: string,
  eventData: Record<string, unknown>,
): string {
  return JSON.stringify({
    event_type: eventType,
    event_data: eventData,
    _access_token: getAccessToken() || undefined,
    _session_id: getSessionId() || undefined,
  });
}

/**
 * Fire-and-forget event tracking via navigator.sendBeacon.
 * sendBeacon is designed for analytics — it survives page navigations,
 * tab closes, and SPA route changes. Falls back to fetch if unavailable.
 *
 * Never throws — tracking must never disrupt the user experience.
 */
export function trackEvent(
  eventType: string,
  eventData?: Record<string, unknown>,
): void {
  const data = eventData ?? {};
  try {
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const body = buildBeaconBody(eventType, data);
      const blob = new Blob([body], { type: "application/json" });
      const sent = navigator.sendBeacon("/api/tracking/events", blob);
      if (sent) return;
    }
  } catch {
    // sendBeacon failed — fall through to fetch
  }
  // Fallback: fire-and-forget fetch
  trackEventAsync(eventType, data).catch(() => {});
}

/**
 * Awaitable version of trackEvent using fetch. Use when the event MUST be
 * delivered before the next action (e.g. logout). Resolves once the POST
 * completes or after a 3-second timeout — whichever comes first.
 */
export async function trackEventAsync(
  eventType: string,
  eventData?: Record<string, unknown>,
): Promise<void> {
  const body = {
    event_type: eventType,
    event_data: eventData ?? {},
    _access_token: getAccessToken() || undefined,
    _session_id: getSessionId() || undefined,
  };
  const opts: RequestInit = {
    method: "POST",
    headers: getAuthHeaders(),
    credentials: "include",
    body: JSON.stringify(body),
    keepalive: true,
  };

  const timeout = new Promise<void>((resolve) => setTimeout(resolve, 3000));
  const send = fetch("/api/tracking/events", opts)
    .then(async (res) => {
      if (res.status === 401) {
        const refreshed = await refreshTokens();
        if (refreshed) {
          await fetch("/api/tracking/events", {
            ...opts,
            headers: getAuthHeaders(),
          });
        }
      }
    })
    .catch(() => {});

  await Promise.race([send, timeout]);
}
