"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await apiFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
    } catch {
      // Always show success (prevent email enumeration)
    }
    setSent(true);
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: 24 }}>Forgot Password</h1>

      {sent ? (
        <div style={{ background: "#dcfce7", color: "#16a34a", padding: 16, borderRadius: 4 }}>
          If an account exists with that email, a reset link has been sent.
          <div style={{ marginTop: 16 }}>
            <Link href="/auth/login" style={{ color: "#2563eb" }}>
              Back to login
            </Link>
          </div>
        </div>
      ) : (
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
            {loading ? "Sending..." : "Send Reset Link"}
          </button>

          <div style={{ marginTop: 16, textAlign: "center", fontSize: 14 }}>
            <Link href="/auth/login" style={{ color: "#2563eb" }}>
              Back to login
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
