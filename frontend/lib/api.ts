/**
 * Centralized API client with token handling and 401 refresh interceptor.
 *
 * Tokens are persisted in sessionStorage so they survive page reloads
 * within the same tab.  A background timer proactively refreshes the
 * access token before it expires.
 */

const API_BASE = "/api";

// ── Token storage (sessionStorage-backed) ──

function _read(key: string): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(key);
}

function _write(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (value) sessionStorage.setItem(key, value);
  else sessionStorage.removeItem(key);
}

let _accessToken: string | null = null;
let _csrfToken: string | null = null;
let _expiresIn: number = 3600; // seconds, updated on each token response
let _refreshTimer: ReturnType<typeof setTimeout> | null = null;

// Hydrate from sessionStorage on module load
if (typeof window !== "undefined") {
  _accessToken = sessionStorage.getItem("access_token");
  _csrfToken = sessionStorage.getItem("csrf_token");
}

export function setAccessToken(token: string | null) {
  _accessToken = token;
  _write("access_token", token);
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setCsrfToken(token: string | null) {
  _csrfToken = token;
  _write("csrf_token", token);
}

export function getCsrfToken(): string | null {
  return _csrfToken;
}

/** Generate a UUID v4 without requiring a secure context. */
function uuidv4(): string {
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++)
      bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const h = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Guest session ID — persisted in localStorage so consent and tracking work for anonymous users. */
export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem("guest_session_id");
  if (!sid) {
    sid = uuidv4();
    localStorage.setItem("guest_session_id", sid);
  }
  return sid;
}

// ── Proactive refresh timer ──

function scheduleRefresh() {
  if (_refreshTimer) clearTimeout(_refreshTimer);
  if (typeof window === "undefined") return;
  // Refresh at 80% of the token lifetime
  const delayMs = Math.max(_expiresIn * 0.8 * 1000, 30_000);
  _refreshTimer = setTimeout(() => {
    refreshTokens().catch(() => {});
  }, delayMs);
}

function cancelRefresh() {
  if (_refreshTimer) {
    clearTimeout(_refreshTimer);
    _refreshTimer = null;
  }
}

// ── Token refresh ──

let refreshPromise: Promise<boolean> | null = null;

export async function refreshTokens(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include", // send httpOnly cookie
    });
    if (!res.ok) {
      cancelRefresh();
      return false;
    }
    const data = await res.json();
    setAccessToken(data.access_token);
    if (data.csrf_token) setCsrfToken(data.csrf_token);
    if (data.expires_in) _expiresIn = data.expires_in;
    scheduleRefresh();
    return true;
  } catch {
    cancelRefresh();
    return false;
  }
}

// ── Fetch helpers ──

export interface ApiError {
  error: string;
  message: string;
  details?: unknown;
}

/** Event emitted when the session is truly dead (refresh failed). */
type SessionExpiredListener = () => void;
const _sessionExpiredListeners: SessionExpiredListener[] = [];

export function onSessionExpired(fn: SessionExpiredListener) {
  _sessionExpiredListeners.push(fn);
  return () => {
    const idx = _sessionExpiredListeners.indexOf(fn);
    if (idx >= 0) _sessionExpiredListeners.splice(idx, 1);
  };
}

function _notifySessionExpired() {
  setAccessToken(null);
  setCsrfToken(null);
  cancelRefresh();
  for (const fn of _sessionExpiredListeners) {
    try {
      fn();
    } catch {
      /* ignore */
    }
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  // Attach guest session ID for consent/tracking when not authenticated
  const sid = getSessionId();
  if (sid) {
    headers["X-Session-ID"] = sid;
  }

  // Attach CSRF token on state-changing requests
  const method = (options.method || "GET").toUpperCase();
  if (_csrfToken && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
    headers["X-CSRF-Token"] = _csrfToken;
  }

  let res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // On 401, try to refresh tokens once
  if (res.status === 401 && _accessToken) {
    if (!refreshPromise) {
      refreshPromise = refreshTokens();
    }
    const refreshed = await refreshPromise;
    refreshPromise = null;

    if (refreshed) {
      headers["Authorization"] = `Bearer ${_accessToken}`;
      if (_csrfToken && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
        headers["X-CSRF-Token"] = _csrfToken;
      }
      res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    } else {
      _notifySessionExpired();
      throw new Error("Session expired");
    }
  }

  // On 403 with CSRF error, try to refresh tokens to get a new CSRF token
  if (
    res.status === 403 &&
    ["POST", "PUT", "DELETE", "PATCH"].includes(method)
  ) {
    try {
      const body = await res.clone().json();
      const msg = body?.detail?.message || body?.message || "";
      if (msg.toLowerCase().includes("csrf")) {
        const refreshed = await refreshTokens();
        if (refreshed && _csrfToken) {
          headers["X-CSRF-Token"] = _csrfToken;
          if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;
          res = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
            credentials: "include",
          });
        }
      }
    } catch {
      // Fall through to normal error handling
    }
  }

  if (!res.ok) {
    let err: ApiError;
    try {
      const body = await res.json();
      err = body.detail || body;
    } catch {
      err = { error: "unknown", message: res.statusText };
    }
    throw err;
  }

  // 204 No Content — nothing to parse
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

/**
 * Upload a file via FormData. Does NOT set Content-Type (browser sets multipart boundary).
 */
export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData,
): Promise<T> {
  const headers: Record<string, string> = {};

  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }
  if (_csrfToken) {
    headers["X-CSRF-Token"] = _csrfToken;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
    credentials: "include",
  });

  if (!res.ok) {
    let err: ApiError;
    try {
      const body = await res.json();
      err = body.detail || body;
    } catch {
      err = { error: "unknown", message: res.statusText };
    }
    throw err;
  }

  return res.json();
}
