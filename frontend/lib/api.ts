/**
 * Centralized API client with token handling and 401 refresh interceptor.
 */

const API_BASE = "/api";

let accessToken: string | null = null;
let csrfToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

/** Generate a UUID v4 without requiring a secure context. */
function uuidv4(): string {
  const bytes = new Uint8Array(16);
  (crypto.getRandomValues || function (b: Uint8Array) {
    for (let i = 0; i < b.length; i++) b[i] = Math.floor(Math.random() * 256);
  })(bytes);
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

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export async function refreshTokens(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include", // send httpOnly cookie
    });
    if (!res.ok) return false;
    const data = await res.json();
    accessToken = data.access_token;
    if (data.csrf_token) csrfToken = data.csrf_token;
    return true;
  } catch {
    return false;
  }
}

export interface ApiError {
  error: string;
  message: string;
  details?: unknown;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  // Attach guest session ID for consent/tracking when not authenticated
  const sid = getSessionId();
  if (sid) {
    headers["X-Session-ID"] = sid;
  }

  // Attach CSRF token on state-changing requests
  const method = (options.method || "GET").toUpperCase();
  if (csrfToken && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  let res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // On 401, try to refresh tokens once
  if (res.status === 401 && accessToken) {
    if (!refreshPromise) {
      refreshPromise = refreshTokens();
    }
    const refreshed = await refreshPromise;
    refreshPromise = null;

    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      if (csrfToken && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
        headers["X-CSRF-Token"] = csrfToken;
      }
      res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
    } else {
      accessToken = null;
      if (typeof window !== "undefined") {
        window.location.href = "/auth/login";
      }
      throw new Error("Session expired");
    }
  }

  // On 403 with CSRF error, try to refresh tokens to get a new CSRF token
  if (res.status === 403 && ["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
    try {
      const body = await res.clone().json();
      const msg = body?.detail?.message || body?.message || "";
      if (msg.toLowerCase().includes("csrf")) {
        const refreshed = await refreshTokens();
        if (refreshed && csrfToken) {
          headers["X-CSRF-Token"] = csrfToken;
          if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
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

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
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
