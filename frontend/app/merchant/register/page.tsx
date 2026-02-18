"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../../lib/auth-context";
import { apiFetch } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";

export default function MerchantRegisterPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Become a Merchant</h1>
        <p className="text-text-secondary mb-6">Sign in to your account first, then upgrade to a merchant account.</p>
        <Link href="/auth/login?redirect=/merchant/register" className="btn-primary text-sm">
          Sign In
        </Link>
      </div>
    );
  }

  if (user?.role === "merchant") {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Already a Merchant</h1>
        <p className="text-text-secondary mb-6">Your account is already a merchant account. Continue to onboarding or your dashboard.</p>
        <div className="flex gap-4 justify-center">
          <Link href="/merchant/onboard" className="btn-primary text-sm">Start Onboarding</Link>
          <Link href="/merchant/dashboard" className="btn-secondary text-sm">Dashboard</Link>
        </div>
      </div>
    );
  }

  if (user?.role === "admin") {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold text-red-400 mb-4">Not Available</h1>
        <p className="text-text-secondary mb-6">Admin accounts cannot be converted to merchant accounts.</p>
        <Link href="/dashboard" className="btn-primary text-sm">Back to Dashboard</Link>
      </div>
    );
  }

  async function handleUpgrade() {
    setUpgrading(true);
    setError(null);
    try {
      await apiFetch("/auth/upgrade-to-merchant", { method: "POST" });

      // Refresh the session to get new role in JWT
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        const { setAccessToken, setCsrfToken } = await import("../../../lib/api");
        setAccessToken(data.access_token);
        if (data.csrf_token) setCsrfToken(data.csrf_token);
      }

      // Redirect to onboarding
      router.push("/merchant/onboard");
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || "Failed to upgrade account. Please try again.");
    }
    setUpgrading(false);
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="glass rounded-2xl p-8">
        <h1 className="font-serif text-3xl font-bold gradient-text mb-2">Become a Merchant</h1>
        <p className="text-text-secondary mb-8">
          Upgrade your account to start selling on our platform. You&apos;ll be guided through
          Stripe Connect setup to receive payments directly.
        </p>

        <div className="space-y-4 mb-8">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent-purple/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-accent-purple text-sm font-bold">1</span>
            </div>
            <div>
              <p className="text-text-primary font-medium">Upgrade your account</p>
              <p className="text-sm text-text-muted">Your customer account will be converted to a merchant account.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-accent-blue text-sm font-bold">2</span>
            </div>
            <div>
              <p className="text-text-primary font-medium">Connect with Stripe</p>
              <p className="text-sm text-text-muted">Set up your Stripe Express account to receive payments securely.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent-green/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-accent-green text-sm font-bold">3</span>
            </div>
            <div>
              <p className="text-text-primary font-medium">Start selling</p>
              <p className="text-sm text-text-muted">Once verified, you can list products and receive payments.</p>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}

        <button
          onClick={handleUpgrade}
          disabled={upgrading}
          className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {upgrading ? "Upgrading..." : "Upgrade to Merchant Account"}
        </button>

        <p className="text-xs text-text-muted text-center mt-4">
          You can still shop as a customer after upgrading.
        </p>
      </div>
    </div>
  );
}
