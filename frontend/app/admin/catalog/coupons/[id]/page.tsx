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

interface UsageItem {
  usage_type: "order" | "subscription";
  reference_id: string;
  reference_label: string;
  user_id: string;
  user_email: string;
  discount_amount: number;
  status: string;
  created_at: string;
}

interface UsageResponse {
  items: UsageItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function UsageHistory({ couponId }: { couponId: string }) {
  const [open, setOpen] = useState(false);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const fetchUsage = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const data = await apiFetch<UsageResponse>(
          `/ecommerce/admin/discounts/${couponId}/usage?page=${p}&page_size=10`,
        );
        setUsage(data);
        setPage(p);
      } catch {
        /* ignore */
      }
      setLoading(false);
    },
    [couponId],
  );

  useEffect(() => {
    if (open && !usage) {
      fetchUsage(1);
    }
  }, [open, usage, fetchUsage]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatCents = (cents: number) => {
    if (cents === 0) return "-";
    return `$${(cents / 100).toFixed(2)}`;
  };

  return (
    <div className="glass rounded-xl mt-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-4 flex items-center justify-between text-left"
      >
        <h2 className="font-semibold text-text-primary">
          Usage History
          {usage && (
            <span className="ml-2 text-xs text-text-muted font-normal">
              ({usage.total} redemption{usage.total !== 1 ? "s" : ""})
            </span>
          )}
        </h2>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`h-5 w-5 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4">
          {loading && !usage ? (
            <LoadingSpinner className="py-8" />
          ) : !usage || usage.items.length === 0 ? (
            <p className="text-text-muted text-sm py-6 text-center">
              No redemptions yet
            </p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-text-muted text-xs">
                      <th className="text-left py-2 pr-3 font-medium">
                        Customer
                      </th>
                      <th className="text-left py-2 pr-3 font-medium">Type</th>
                      <th className="text-left py-2 pr-3 font-medium">
                        Reference
                      </th>
                      <th className="text-left py-2 pr-3 font-medium">Date</th>
                      <th className="text-right py-2 pr-3 font-medium">
                        Discount
                      </th>
                      <th className="text-left py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.items.map((item) => (
                      <tr
                        key={`${item.usage_type}-${item.reference_id}`}
                        className="border-b border-white/5"
                      >
                        <td className="py-2 pr-3 text-text-secondary">
                          {item.user_email}
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              item.usage_type === "order"
                                ? "bg-blue-500/20 text-blue-300"
                                : "bg-purple-500/20 text-purple-300"
                            }`}
                          >
                            {item.usage_type === "order"
                              ? "Order"
                              : "Subscription"}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-text-secondary font-mono text-xs">
                          {item.reference_label}
                        </td>
                        <td className="py-2 pr-3 text-text-muted text-xs">
                          {formatDate(item.created_at)}
                        </td>
                        <td className="py-2 pr-3 text-right text-text-secondary">
                          {formatCents(item.discount_amount)}
                        </td>
                        <td className="py-2">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              item.status === "completed" ||
                              item.status === "active"
                                ? "bg-green-500/20 text-green-300"
                                : item.status === "pending"
                                  ? "bg-yellow-500/20 text-yellow-300"
                                  : item.status === "cancelled" ||
                                      item.status === "canceled"
                                    ? "bg-red-500/20 text-red-300"
                                    : "bg-white/10 text-text-muted"
                            }`}
                          >
                            {item.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {usage.total_pages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/10">
                  <span className="text-xs text-text-muted">
                    Page {usage.page} of {usage.total_pages}
                  </span>
                  <div className="flex gap-2">
                    <button
                      disabled={page <= 1 || loading}
                      onClick={() => fetchUsage(page - 1)}
                      className="px-3 py-1 text-xs rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-text-secondary transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      disabled={page >= usage.total_pages || loading}
                      onClick={() => fetchUsage(page + 1)}
                      className="px-3 py-1 text-xs rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-text-secondary transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
          {loading && usage && (
            <div className="text-center py-2">
              <span className="text-xs text-text-muted">Loading...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
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

      {/* Usage History */}
      <UsageHistory couponId={couponId} />
    </div>
  );
}
