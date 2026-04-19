"use client";

import { Suspense, useState, FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch, type ApiError } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <h1 className="font-serif text-3xl font-bold gradient-text mb-4">
          Invalid Link
        </h1>
        <div className="p-4 rounded-lg bg-accent-pink/10 border border-accent-pink/20 text-accent-pink text-sm mb-4">
          Invalid or missing reset token. Please request a new reset link.
        </div>
        <Link
          href="/auth/forgot-password"
          className="text-accent-purple hover:text-accent-blue transition-colors text-sm"
        >
          Request new reset link
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <h1 className="font-serif text-3xl font-bold gradient-text mb-4">
          Password Reset
        </h1>
        <div className="p-4 rounded-lg bg-accent-green/10 border border-accent-green/20 text-accent-green text-sm mb-4">
          Your password has been reset successfully.
        </div>
        <Link href="/auth/login" className="btn-primary text-sm">
          Sign in with new password
        </Link>
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

  return (
    <div className="glass rounded-2xl p-8">
      <div className="text-center mb-8">
        <h1 className="font-serif text-3xl font-bold gradient-text mb-2">
          Set New Password
        </h1>
        <p className="text-text-secondary text-sm">Choose a strong password</p>
      </div>

      {error && (
        <div className="mb-6 p-3 rounded-lg bg-accent-pink/10 border border-accent-pink/20 text-accent-pink text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm text-text-secondary mb-1.5">
            New Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="input-glass"
            placeholder="Min 8 characters"
          />
          <p className="text-xs text-text-muted mt-1">
            Requires uppercase, lowercase, and digit
          </p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Resetting..." : "Reset Password"}
        </button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <Suspense fallback={<LoadingSpinner size="lg" className="py-20" />}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
