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
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="glass rounded-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="font-serif text-3xl font-bold gradient-text mb-2">
              Forgot Password
            </h1>
            <p className="text-text-secondary text-sm">
              We&apos;ll send you a reset link
            </p>
          </div>

          {sent ? (
            <div className="p-4 rounded-lg bg-accent-green/10 border border-accent-green/20 text-accent-green text-sm">
              <p>
                If an account exists with that email, a reset link has been
                sent.
              </p>
              <Link
                href="/auth/login"
                className="inline-block mt-4 text-accent-purple hover:text-accent-blue transition-colors"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm text-text-secondary mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="input-glass"
                  placeholder="you@example.com"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Sending..." : "Send Reset Link"}
              </button>

              <div className="text-center text-sm">
                <Link
                  href="/auth/login"
                  className="text-text-muted hover:text-accent-purple transition-colors"
                >
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
