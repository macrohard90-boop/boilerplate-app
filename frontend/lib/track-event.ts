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
  const body = { event_type: eventType, event_data: eventData ?? {} };
  const opts: RequestInit = {
    method: "POST",
    headers: getAuthHeaders(),
    credentials: "include",
    body: JSON.stringify(body),
    keepalive: true,
  };

  fetch("/api/tracking/events", opts)
    .then(async (res) => {
      if (res.status === 401) {
        const refreshed = await refreshTokens();
        if (refreshed) {
          fetch("/api/tracking/events", { ...opts, headers: getAuthHeaders() });
        }
      }
    })
    .catch(() => {
      // Silent — tracking should never disrupt the user
    });
}
