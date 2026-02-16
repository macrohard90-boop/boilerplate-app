"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../../lib/auth-context";

const OAUTH_PROVIDERS = ["google", "github", "microsoft", "apple"];

export default function LoginPage() {
  const router = useRouter();
  const { login, error, clearError, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    router.push("/protected");
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    clearError();
    try {
      await login(email, password);
      router.push("/protected");
    } catch {
      // error is set in auth context
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: 24 }}>Login</h1>

      {error && (
        <div style={{ background: "#fee2e2", color: "#dc2626", padding: 12, borderRadius: 4, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: 10,
            background: "#111",
            color: "white",
            border: "none",
            borderRadius: 4,
            cursor: loading ? "wait" : "pointer",
            fontSize: 14,
          }}
        >
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>

      <div style={{ margin: "24px 0", textAlign: "center", color: "#999" }}>or continue with</div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {OAUTH_PROVIDERS.map((p) => (
          <a
            key={p}
            href={`/api/auth/oauth/${p}`}
            style={{
              flex: 1,
              padding: "8px 12px",
              border: "1px solid #ccc",
              borderRadius: 4,
              textAlign: "center",
              textDecoration: "none",
              color: "#333",
              textTransform: "capitalize",
              fontSize: 13,
            }}
          >
            {p}
          </a>
        ))}
      </div>

      <div style={{ marginTop: 24, textAlign: "center", fontSize: 14 }}>
        <Link href="/auth/forgot-password" style={{ color: "#2563eb" }}>
          Forgot password?
        </Link>
        {" | "}
        <Link href="/auth/register" style={{ color: "#2563eb" }}>
          Create account
        </Link>
      </div>
    </div>
  );
}
