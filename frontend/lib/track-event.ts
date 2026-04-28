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
 * Fire-and-forget event tracking. Never throws — tracking must never disrupt
 * the user experience. The backend gates on ENABLE_TRACKING and GDPR consent.
 */
export function trackEvent(
  eventType: string,
  eventData?: Record<string, unknown>,
): void {
  trackEventAsync(eventType, eventData).catch(() => {});
}

/**
 * Awaitable version of trackEvent. Use when the event MUST be delivered
 * before navigating away (e.g. logout). Resolves once the POST completes
 * or after a 3-second timeout — whichever comes first.
 */
export async function trackEventAsync(
  eventType: string,
  eventData?: Record<string, unknown>,
): Promise<void> {
  const body = { event_type: eventType, event_data: eventData ?? {} };
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
