"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../../lib/auth-context";
import { trackEvent } from "../../../lib/track-event";

function passwordStrength(pw: string): {
  label: string;
  color: string;
  width: string;
} {
  if (pw.length < 8)
    return { label: "Too short", color: "text-accent-pink", width: "w-1/4" };
  const hasUpper = /[A-Z]/.test(pw);
  const hasLower = /[a-z]/.test(pw);
  const hasDigit = /\d/.test(pw);
  if (!hasUpper || !hasLower || !hasDigit)
    return { label: "Weak", color: "text-amber-400", width: "w-1/2" };
  if (pw.length >= 12)
    return { label: "Strong", color: "text-accent-green", width: "w-full" };
  return { label: "Good", color: "text-accent-blue", width: "w-3/4" };
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
    router.push("/dashboard");
    return null;
  }

  const strength = passwordStrength(password);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    clearError();
    try {
      await register(email, password, firstName, lastName);
      trackEvent("signup_completed", { method: "email" });
      router.push("/dashboard");
    } catch {
      trackEvent("signup_failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="glass rounded-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="font-serif text-3xl font-bold gradient-text mb-2">
              Create Account
            </h1>
            <p className="text-text-secondary text-sm">
              Join us and start shopping
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-accent-pink/10 border border-accent-pink/20 text-accent-pink text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-text-secondary mb-1.5">
                  First name
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                  className="input-glass"
                  placeholder="John"
                />
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1.5">
                  Last name
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                  className="input-glass"
                  placeholder="Doe"
                />
              </div>
            </div>

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

            <div>
              <label className="block text-sm text-text-secondary mb-1.5">
                Password
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
              {password && (
                <div className="mt-2">
                  <div className="h-1 rounded-full bg-glass-bg overflow-hidden">
                    <div
                      className={`h-full ${strength.width} rounded-full transition-all duration-300`}
                      style={{
                        background:
                          strength.color === "text-accent-pink"
                            ? "#ff6b9d"
                            : strength.color === "text-amber-400"
                              ? "#fbbf24"
                              : strength.color === "text-accent-blue"
                                ? "#38bdf8"
                                : "#34d399",
                      }}
                    />
                  </div>
                  <p className={`text-xs mt-1 ${strength.color}`}>
                    {strength.label} — requires uppercase, lowercase, and digit
                  </p>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-text-muted">Already have an account? </span>
            <Link
              href="/auth/login"
              className="text-accent-purple hover:text-accent-blue transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
