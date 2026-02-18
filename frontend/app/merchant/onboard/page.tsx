"use client";

import { useState } from "react";
import { useAuth } from "../../../lib/auth-context";
import { apiFetch } from "../../../lib/api";
import Link from "next/link";
import LoadingSpinner from "../../../components/LoadingSpinner";

export default function MerchantOnboardPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("individual");
  const [country, setCountry] = useState("US");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Merchant Onboarding</h1>
        <p className="text-text-secondary mb-6">Please sign in to continue.</p>
        <Link href="/auth/login?redirect=/merchant/onboard" className="btn-primary text-sm">Sign In</Link>
      </div>
    );
  }

  if (user?.role !== "merchant") {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Upgrade Required</h1>
        <p className="text-text-secondary mb-6">You need a merchant account to access onboarding.</p>
        <Link href="/merchant/register" className="btn-primary text-sm">Become a Merchant</Link>
      </div>
    );
  }

  async function handleOnboard() {
    setSubmitting(true);
    setError(null);
    try {
      const data = await apiFetch<{ onboarding_url: string }>("/payments/merchants/onboard", {
        method: "POST",
        body: JSON.stringify({
          business_name: businessName || null,
          business_type: businessType,
          country,
        }),
      });
      // Redirect to Stripe Connect onboarding
      window.location.href = data.onboarding_url;
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || "Failed to start onboarding. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="glass rounded-2xl p-8">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-2">Stripe Connect Setup</h1>
        <p className="text-text-secondary text-sm mb-8">
          Complete your Stripe Express account to start receiving payments. You&apos;ll be redirected
          to Stripe to verify your identity and business details.
        </p>

        <div className="space-y-4 mb-6">
          <div>
            <label htmlFor="businessName" className="block text-sm text-text-secondary mb-1">
              Business Name <span className="text-text-muted">(optional)</span>
            </label>
            <input
              id="businessName"
              type="text"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              className="input-field w-full"
              placeholder="Your business name"
            />
          </div>

          <div>
            <label htmlFor="businessType" className="block text-sm text-text-secondary mb-1">
              Business Type
            </label>
            <select
              id="businessType"
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              className="input-field w-full"
            >
              <option value="individual">Individual / Sole Proprietor</option>
              <option value="company">Company</option>
              <option value="non_profit">Non-profit</option>
            </select>
          </div>

          <div>
            <label htmlFor="country" className="block text-sm text-text-secondary mb-1">
              Country
            </label>
            <select
              id="country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="input-field w-full"
            >
              <option value="US">United States</option>
              <option value="CA">Canada</option>
              <option value="GB">United Kingdom</option>
              <option value="AU">Australia</option>
              <option value="DE">Germany</option>
              <option value="FR">France</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}

        <button
          onClick={handleOnboard}
          disabled={submitting}
          className="btn-primary w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Redirecting to Stripe..." : "Continue to Stripe"}
        </button>

        <p className="text-xs text-text-muted text-center mt-4">
          You&apos;ll be redirected to Stripe&apos;s secure onboarding page.
        </p>
      </div>

      <div className="text-center mt-6">
        <Link href="/merchant/dashboard" className="text-sm text-text-muted hover:text-text-secondary">
          Already onboarded? Go to dashboard
        </Link>
      </div>
    </div>
  );
}
