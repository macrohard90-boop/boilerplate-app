"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { useToast } from "../../../../../components/Toast";
import LoadingSpinner from "../../../../../components/LoadingSpinner";
import ProductForm, { type ProductFormData } from "../../../../../components/admin/ProductForm";
import SyncStatusBadge from "../../../../../components/admin/SyncStatusBadge";
import ImageUploader from "../../../../../components/admin/ImageUploader";

interface Plan {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  sku: string | null;
  base_price: number;
  currency: string;
  status: string;
  pricing_type: string;
  recurring_interval: string | null;
  recurring_interval_count: number;
  trial_period_days: number | null;
  stripe_product_id: string | null;
  stripe_price_id: string | null;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
  synced_provider: string | null;
}

export default function EditPlanPage() {
  const params = useParams();
  const router = useRouter();
  const { showToast } = useToast();
  const planId = params.id as string;

  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchPlan = useCallback(async () => {
    try {
      const allData = await apiFetch<{ items: Plan[] }>(
        `/ecommerce/products?pricing_type=recurring&page=1&page_size=100`
      );
      const found = allData.items.find((p) => p.id === planId);
      if (found) {
        setPlan(found);
      } else {
        showToast("Plan not found", "error");
        router.push("/admin/subscriptions/plans");
      }
    } catch {
      showToast("Failed to load plan", "error");
      router.push("/admin/subscriptions/plans");
    }
    setLoading(false);
  }, [planId, router, showToast]);

  useEffect(() => { fetchPlan(); }, [fetchPlan]);

  const handleUpdate = async (formData: ProductFormData) => {
    setSaving(true);
    try {
      await apiFetch(`/ecommerce/products/${planId}`, {
        method: "PUT",
        body: JSON.stringify(formData),
      });
      showToast("Plan updated", "success");
      fetchPlan();
    } catch {
      showToast("Failed to update plan", "error");
    }
    setSaving(false);
  };

  const handleRetrySync = async () => {
    setSyncing(true);
    try {
      await apiFetch(`/ecommerce/products/${planId}/sync`, { method: "POST" });
      showToast("Sync successful", "success");
      fetchPlan();
    } catch {
      showToast("Sync failed", "error");
    }
    setSyncing(false);
  };

  if (loading) return <LoadingSpinner className="py-20" />;
  if (!plan) return null;

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/subscriptions/plans")}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Edit Plan</span>
        </h1>
      </div>

      {/* Sync Status Banner */}
      <div className="glass rounded-xl p-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-xs text-text-muted block">Catalog Sync</span>
            <SyncStatusBadge
              status={plan.stripe_sync_status}
              error={plan.stripe_sync_error}
              provider={plan.synced_provider}
              onRetry={plan.stripe_sync_status === "error" ? handleRetrySync : undefined}
            />
          </div>
          {plan.stripe_product_id && (
            <div>
              <span className="text-xs text-text-muted block">Stripe Product</span>
              <span className="text-xs text-text-secondary font-mono">{plan.stripe_product_id}</span>
            </div>
          )}
          {plan.stripe_price_id && (
            <div>
              <span className="text-xs text-text-muted block">Stripe Price</span>
              <span className="text-xs text-text-secondary font-mono">{plan.stripe_price_id}</span>
            </div>
          )}
        </div>
        {plan.stripe_sync_status !== "synced" && plan.status === "active" && (
          <button
            onClick={handleRetrySync}
            className="btn-primary px-3 py-1.5 rounded-lg text-sm"
            disabled={syncing}
          >
            {syncing ? "Syncing..." : "Sync Now"}
          </button>
        )}
      </div>

      {/* Plan Form */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Plan Details</h2>
        <ProductForm
          initial={{
            name: plan.name,
            description: plan.description || "",
            sku: plan.sku || "",
            base_price: plan.base_price,
            currency: plan.currency,
            status: plan.status,
            pricing_type: "recurring",
            recurring_interval: plan.recurring_interval,
            recurring_interval_count: plan.recurring_interval_count || 1,
            trial_period_days: plan.trial_period_days,
          }}
          onSubmit={handleUpdate}
          onCancel={() => router.push("/admin/subscriptions/plans")}
          loading={saving}
          submitLabel="Update Plan"
          allowRecurring={false}
        />
      </div>

      {/* Plan Images */}
      <div className="glass rounded-xl p-6 mt-6">
        <ImageUploader productId={planId} />
      </div>
    </div>
  );
}
