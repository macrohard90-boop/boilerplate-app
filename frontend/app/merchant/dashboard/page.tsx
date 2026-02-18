"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth-context";
import { apiFetch } from "../../../lib/api";
import Link from "next/link";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface MerchantStatus {
  account_id: string;
  status: string;
  charges_enabled: boolean;
  payouts_enabled: boolean;
  business_name: string | null;
}

export default function MerchantDashboardPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [status, setStatus] = useState<MerchantStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardUrl, setDashboardUrl] = useState<string | null>(null);
  const [loadingDashboard, setLoadingDashboard] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== "merchant") return;

    async function load() {
      try {
        const data = await apiFetch<MerchantStatus>("/payments/merchants/status");
        setStatus(data);
      } catch {
        setError("not_found");
      }
      setLoading(false);
    }
    load();
  }, [isAuthenticated, user?.role]);

  if (isLoading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Merchant Dashboard</h1>
        <p className="text-text-secondary mb-6">Please sign in to access your merchant dashboard.</p>
        <Link href="/auth/login?redirect=/merchant/dashboard" className="btn-primary text-sm">Sign In</Link>
      </div>
    );
  }

  if (user?.role !== "merchant") {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Merchant Dashboard</h1>
        <p className="text-text-secondary mb-6">You need a merchant account to access this page.</p>
        <Link href="/merchant/register" className="btn-primary text-sm">Become a Merchant</Link>
      </div>
    );
  }

  if (loading) return <LoadingSpinner size="lg" className="py-40" />;

  // No Stripe account yet — prompt onboarding
  if (error === "not_found" || !status) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Complete Setup</h1>
        <p className="text-text-secondary mb-6">
          Your merchant account is ready, but you haven&apos;t connected Stripe yet.
          Complete onboarding to start receiving payments.
        </p>
        <Link href="/merchant/onboard" className="btn-primary text-sm">Start Stripe Onboarding</Link>
      </div>
    );
  }

  async function openStripeDashboard() {
    setLoadingDashboard(true);
    try {
      const data = await apiFetch<{ dashboard_url: string }>("/payments/merchants/dashboard-link");
      setDashboardUrl(data.dashboard_url);
      window.open(data.dashboard_url, "_blank");
    } catch {
      // Fallback — show error
    }
    setLoadingDashboard(false);
  }

  const isActive = status.charges_enabled && status.payouts_enabled;
  const isPending = status.status === "onboarding" || (!status.charges_enabled && status.status !== "rejected");

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="font-serif text-2xl font-bold gradient-text mb-6">Merchant Dashboard</h1>

      {/* Status card */}
      <div className="glass rounded-2xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">Stripe Account</h2>
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${
            isActive ? "bg-accent-green/10 text-accent-green" :
            isPending ? "bg-yellow-500/10 text-yellow-400" :
            "bg-red-500/10 text-red-400"
          }`}>
            {isActive ? "Active" : isPending ? "Pending Verification" : status.status}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-xs text-text-muted mb-1">Account ID</p>
            <p className="text-sm text-text-secondary font-mono">{status.account_id}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Business Name</p>
            <p className="text-sm text-text-secondary">{status.business_name || "Not set"}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Charges</p>
            <p className={`text-sm font-medium ${status.charges_enabled ? "text-accent-green" : "text-text-muted"}`}>
              {status.charges_enabled ? "Enabled" : "Disabled"}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-muted mb-1">Payouts</p>
            <p className={`text-sm font-medium ${status.payouts_enabled ? "text-accent-green" : "text-text-muted"}`}>
              {status.payouts_enabled ? "Enabled" : "Disabled"}
            </p>
          </div>
        </div>

        {isPending && (
          <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-sm text-yellow-400 mb-4">
            Your account is being verified by Stripe. This usually takes a few minutes.
            If verification is incomplete, click below to continue onboarding.
          </div>
        )}

        <div className="flex gap-3">
          {isActive && (
            <button
              onClick={openStripeDashboard}
              disabled={loadingDashboard}
              className="btn-primary text-sm disabled:opacity-50"
            >
              {loadingDashboard ? "Opening..." : "Open Stripe Dashboard"}
            </button>
          )}
          {isPending && (
            <Link href="/merchant/onboard" className="btn-primary text-sm">
              Continue Onboarding
            </Link>
          )}
          <button
            onClick={() => window.location.reload()}
            className="btn-secondary text-sm"
          >
            Refresh Status
          </button>
        </div>

        {dashboardUrl && (
          <p className="text-xs text-text-muted mt-3">
            Dashboard opened in a new tab.{" "}
            <a href={dashboardUrl} target="_blank" rel="noopener noreferrer" className="text-accent-purple hover:text-accent-blue">
              Open again
            </a>
          </p>
        )}
      </div>

      <div className="text-center">
        <Link href="/dashboard" className="text-sm text-text-muted hover:text-text-secondary">
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
