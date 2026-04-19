"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { useToast } from "../../../../../components/Toast";
import LoadingSpinner from "../../../../../components/LoadingSpinner";
import SyncStatusBadge from "../../../../../components/admin/SyncStatusBadge";
import CouponForm, {
  type CouponFormData,
} from "../../../../../components/admin/CouponForm";

interface Discount {
  id: string;
  code: string;
  type: string;
  value: number;
  currency: string;
  min_order_amount: number;
  max_uses: number | null;
  uses_count: number;
  valid_from: string;
  valid_until: string | null;
  active: boolean;
  created_at: string;
  applies_to: string;
  stripe_duration: string;
  stripe_duration_in_months: number | null;
  stripe_coupon_id: string | null;
  stripe_promotion_code_id: string | null;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
  product_ids: string[];
  restricted_to_customer_id: string | null;
  first_time_transaction_only: boolean;
  max_uses_per_customer: number | null;
}

export default function AdminCouponEditPage() {
  const params = useParams();
  const router = useRouter();
  const { showToast } = useToast();
  const couponId = params.id as string;

  const [coupon, setCoupon] = useState<Discount | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchCoupon = useCallback(async () => {
    try {
      const data = await apiFetch<Discount>(
        `/ecommerce/admin/discounts/${couponId}`,
      );
      setCoupon(data);
    } catch {
      showToast("Coupon not found", "error");
      router.push("/admin/catalog/coupons");
    }
    setLoading(false);
  }, [couponId, router, showToast]);

  useEffect(() => {
    fetchCoupon();
  }, [fetchCoupon]);

  const handleUpdate = async (formData: CouponFormData) => {
    setSaving(true);
    try {
      const updated = await apiFetch<Discount>(
        `/ecommerce/admin/discounts/${couponId}`,
        { method: "PUT", body: JSON.stringify(formData) },
      );
      setCoupon(updated);
      if (updated.stripe_sync_status === "error") {
        showToast(
          `Saved, but Stripe sync failed: ${updated.stripe_sync_error}`,
          "error",
        );
      } else {
        showToast("Coupon updated", "success");
      }
    } catch {
      showToast("Failed to update coupon", "error");
    }
    setSaving(false);
  };

  if (loading) return <LoadingSpinner className="py-20" />;
  if (!coupon) return null;

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/catalog/coupons")}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Edit Coupon</span>
        </h1>
        <span className="font-mono text-text-muted text-sm">{coupon.code}</span>
      </div>

      {/* Stripe Sync Banner */}
      <div className="glass rounded-xl p-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div>
            <span className="text-xs text-text-muted block">Stripe Sync</span>
            {coupon.type === "free_shipping" ? (
              <span className="text-xs text-text-muted">
                N/A (free shipping)
              </span>
            ) : (
              <SyncStatusBadge
                status={coupon.stripe_sync_status}
                error={coupon.stripe_sync_error}
              />
            )}
          </div>
          {coupon.stripe_coupon_id && (
            <div>
              <span className="text-xs text-text-muted block">Coupon ID</span>
              <span className="text-xs text-text-secondary font-mono">
                {coupon.stripe_coupon_id}
              </span>
            </div>
          )}
          {coupon.stripe_promotion_code_id && (
            <div>
              <span className="text-xs text-text-muted block">
                Promo Code ID
              </span>
              <span className="text-xs text-text-secondary font-mono">
                {coupon.stripe_promotion_code_id}
              </span>
            </div>
          )}
          <div>
            <span className="text-xs text-text-muted block">Usage</span>
            <span className="text-xs text-text-secondary">
              {coupon.uses_count} / {coupon.max_uses ?? "unlimited"}
            </span>
          </div>
        </div>
        {coupon.stripe_sync_status === "error" && (
          <span className="text-xs text-text-muted">Save to retry sync</span>
        )}
      </div>

      {/* Coupon Form */}
      <div className="glass rounded-xl p-6">
        <CouponForm
          initial={{
            code: coupon.code,
            type: coupon.type,
            value: coupon.value,
            currency: coupon.currency,
            min_order_amount: coupon.min_order_amount,
            max_uses: coupon.max_uses,
            valid_from: coupon.valid_from,
            valid_until: coupon.valid_until,
            active: coupon.active,
            applies_to: coupon.applies_to,
            stripe_duration: coupon.stripe_duration,
            stripe_duration_in_months: coupon.stripe_duration_in_months,
            stripe_coupon_id: coupon.stripe_coupon_id ?? undefined,
            product_ids: coupon.product_ids || [],
            restricted_to_customer_id: coupon.restricted_to_customer_id,
            first_time_transaction_only: coupon.first_time_transaction_only,
            max_uses_per_customer: coupon.max_uses_per_customer,
          }}
          onSubmit={handleUpdate}
          onCancel={() => router.push("/admin/catalog/coupons")}
          loading={saving}
          submitLabel="Update Coupon"
        />
      </div>
    </div>
  );
}
