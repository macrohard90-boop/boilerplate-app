"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth-context";

export default function AuthNav() {
  const { user, isAuthenticated, logout, isLoading } = useAuth();

  if (isLoading) return null;

  return (
    <nav
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "12px 24px",
        borderBottom: "1px solid #e0e0e0",
        fontFamily: "system-ui, sans-serif",
        fontSize: "14px",
        background: "#fafafa",
      }}
    >
      <Link
        href="/"
        style={{ fontWeight: 700, textDecoration: "none", color: "#111" }}
      >
        Boilerplate App
      </Link>

      <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
        {isAuthenticated ? (
          <>
            <Link
              href="/protected"
              style={{ textDecoration: "none", color: "#333" }}
            >
              Dashboard
            </Link>
            <span style={{ color: "#666" }}>{user?.email}</span>
            <span
              style={{
                background:
                  user?.role === "admin"
                    ? "#dc2626"
                    : user?.role === "merchant"
                      ? "#2563eb"
                      : "#16a34a",
                color: "white",
                padding: "2px 8px",
                borderRadius: "4px",
                fontSize: "12px",
              }}
            >
              {user?.role}
            </span>
            <button
              onClick={() => logout()}
              style={{
                background: "none",
                border: "1px solid #ccc",
                padding: "4px 12px",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <Link
              href="/auth/login"
              style={{ textDecoration: "none", color: "#333" }}
            >
              Login
            </Link>
            <Link
              href="/auth/register"
              style={{
                textDecoration: "none",
                background: "#111",
                color: "white",
                padding: "6px 16px",
                borderRadius: "4px",
              }}
            >
              Register
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
