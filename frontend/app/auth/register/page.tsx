"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../../lib/auth-context";

function passwordStrength(pw: string): { label: string; color: string } {
  if (pw.length < 8) return { label: "Too short", color: "#dc2626" };
  const hasUpper = /[A-Z]/.test(pw);
  const hasLower = /[a-z]/.test(pw);
  const hasDigit = /\d/.test(pw);
  if (!hasUpper || !hasLower || !hasDigit) return { label: "Weak", color: "#f59e0b" };
  if (pw.length >= 12) return { label: "Strong", color: "#16a34a" };
  return { label: "Good", color: "#2563eb" };
}

export default function RegisterPage() {
  const router = useRouter();
  const { register, error, clearError, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    router.push("/protected");
    return null;
  }

  const strength = passwordStrength(password);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    clearError();
    try {
      await register(email, password, firstName, lastName);
      router.push("/protected");
    } catch {
      // error is set in auth context
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: 24 }}>Create Account</h1>

      {error && (
        <div style={{ background: "#fee2e2", color: "#dc2626", padding: 12, borderRadius: 4, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>First name</label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>Last name</label>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
            />
          </div>
        </div>

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
            minLength={8}
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
          />
          {password && (
            <div style={{ fontSize: 12, marginTop: 4, color: strength.color, fontWeight: 500 }}>
              {strength.label} (min 8 chars, uppercase, lowercase, digit)
            </div>
          )}
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
          {loading ? "Creating account..." : "Create Account"}
        </button>
      </form>

      <div style={{ marginTop: 24, textAlign: "center", fontSize: 14 }}>
        Already have an account?{" "}
        <Link href="/auth/login" style={{ color: "#2563eb" }}>
          Login
        </Link>
      </div>
    </div>
  );
}
