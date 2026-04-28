"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import {
  apiFetch,
  refreshTokens,
  setAccessToken,
  getAccessToken,
  setCsrfToken,
  onSessionExpired,
  type ApiError,
} from "./api";

interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_verified: boolean;
  permissions: string[];
  created_at: string;
}

interface Session {
  session_id: string;
  device: string | null;
  ip_address: string | null;
  created_at: string;
}

interface UserContext {
  user: User;
  session: Session | null;
  active_sessions_count: number;
  auth_type: string;
}

interface AuthState {
  user: User | null;
  session: Session | null;
  activeSessionsCount: number;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    firstName: string,
    lastName: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  error: string | null;
  clearError: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [activeSessionsCount, setActiveSessionsCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    try {
      const data = await apiFetch<UserContext>("/auth/me");
      setUser(data.user);
      setSession(data.session);
      setActiveSessionsCount(data.active_sessions_count);
    } catch {
      setUser(null);
      setSession(null);
      setAccessToken(null);
    }
  }, []);

  // Listen for session-expired events from apiFetch (replaces nuclear redirect)
  useEffect(() => {
    return onSessionExpired(() => {
      setUser(null);
      setSession(null);
    });
  }, []);

  // Try to restore session on mount (via sessionStorage + refresh token cookie)
  useEffect(() => {
    async function init() {
      // Check URL for token from OAuth callback
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        const token = params.get("token");
        if (token) {
          setAccessToken(token);
          window.history.replaceState({}, "", window.location.pathname);
        }
      }

      if (!getAccessToken()) {
        // Try refresh via httpOnly cookie
        await refreshTokens();
      }

      if (getAccessToken()) {
        await fetchMe();
      }
      setIsLoading(false);
    }
    init();
  }, [fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const data = await apiFetch<{
          access_token: string;
          csrf_token?: string;
          expires_in?: number;
        }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        setAccessToken(data.access_token);
        if (data.csrf_token) setCsrfToken(data.csrf_token);
        await fetchMe();
      } catch (e) {
        const err = e as ApiError;
        setError(err.message || "Login failed");
        throw e;
      }
    },
    [fetchMe],
  );

  const register = useCallback(
    async (
      email: string,
      password: string,
      firstName: string,
      lastName: string,
    ) => {
      setError(null);
      try {
        const data = await apiFetch<{
          access_token: string;
          csrf_token?: string;
          expires_in?: number;
        }>("/auth/register", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            first_name: firstName,
            last_name: lastName,
          }),
        });
        setAccessToken(data.access_token);
        if (data.csrf_token) setCsrfToken(data.csrf_token);
        await fetchMe();
      } catch (e) {
        const err = e as ApiError;
        setError(err.message || "Registration failed");
        throw e;
      }
    },
    [fetchMe],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Ignore errors on logout
    }
    setAccessToken(null);
    setCsrfToken(null);
    setUser(null);
    setSession(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        activeSessionsCount,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        error,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
