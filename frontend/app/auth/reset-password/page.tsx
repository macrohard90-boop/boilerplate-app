"use client";

import { Suspense, useState, FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch, type ApiError } from "../../../lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
        <h1>Reset Password</h1>
        <div style={{ background: "#fee2e2", color: "#dc2626", padding: 12, borderRadius: 4, marginTop: 16 }}>
          Invalid or missing reset token. Please request a new reset link.
        </div>
        <div style={{ marginTop: 16 }}>
          <Link href="/auth/forgot-password" style={{ color: "#2563eb" }}>
            Request new reset link
          </Link>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setSuccess(true);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message || "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
        <h1>Password Reset</h1>
        <div style={{ background: "#dcfce7", color: "#16a34a", padding: 16, borderRadius: 4, marginTop: 16 }}>
          Your password has been reset successfully.
          <div style={{ marginTop: 16 }}>
            <Link href="/auth/login" style={{ color: "#2563eb" }}>
              Login with new password
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 400, margin: "60px auto", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ marginBottom: 24 }}>Set New Password</h1>

      {error && (
        <div style={{ background: "#fee2e2", color: "#dc2626", padding: 12, borderRadius: 4, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>New Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box" }}
          />
          <div style={{ fontSize: 12, marginTop: 4, color: "#666" }}>
            Min 8 chars, uppercase, lowercase, digit
          </div>
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
          {loading ? "Resetting..." : "Reset Password"}
        </button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center" }}>Loading...</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
