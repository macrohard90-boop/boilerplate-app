"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../../lib/auth-context";

const OAUTH_PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "github", label: "GitHub" },
  { id: "microsoft", label: "Microsoft" },
  { id: "apple", label: "Apple" },
];

export default function LoginPage() {
  const router = useRouter();
  const { login, error, clearError, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) {
    router.push("/dashboard");
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    clearError();
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch {
      // error is set in auth context
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="glass rounded-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="font-serif text-3xl font-bold gradient-text mb-2">Welcome back</h1>
            <p className="text-text-secondary text-sm">Sign in to your account</p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-accent-pink/10 border border-accent-pink/20 text-accent-pink text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm text-text-secondary mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input-glass"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm text-text-secondary mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input-glass"
                placeholder="Enter your password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="my-6 flex items-center gap-3">
            <div className="flex-1 h-px bg-glass-border" />
            <span className="text-xs text-text-muted">or continue with</span>
            <div className="flex-1 h-px bg-glass-border" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            {OAUTH_PROVIDERS.map((p) => (
              <a
                key={p.id}
                href={`/api/auth/oauth/${p.id}`}
                className="btn-secondary text-center text-sm !py-2.5"
              >
                {p.label}
              </a>
            ))}
          </div>

          <div className="mt-6 text-center text-sm space-x-3">
            <Link href="/auth/forgot-password" className="text-text-muted hover:text-accent-purple transition-colors">
              Forgot password?
            </Link>
            <span className="text-text-muted">|</span>
            <Link href="/auth/register" className="text-text-muted hover:text-accent-purple transition-colors">
              Create account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
