"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { formatPrice } from "../../../../../lib/format";
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

interface CouponStats {
  total_redemptions: number;
  total_discount_given: number;
  unique_customers: number;
  avg_order_value: number;
  total_revenue: number;
}

interface UsageProduct {
  name: string;
  image_url: string | null;
  quantity: number;
  unit_price: number;
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
  products: UsageProduct[] | null;
  device_type: string | null;
  browser: string | null;
}

interface UsageResponse {
  items: UsageItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

type TabId = "usage" | "edit";

function formatDiscount(d: Discount): string {
  if (d.type === "percentage") return `${d.value}% off`;
  if (d.type === "fixed") return `${formatPrice(d.value, d.currency)} off`;
  return "Free Shipping";
}

function formatScope(d: Discount): string {
  if (d.applies_to === "one_time") return "one-time orders";
  if (d.applies_to === "recurring") return "subscriptions";
  return "all orders";
}

function getStatusInfo(d: Discount): { label: string; className: string } {
  if (!d.active) return { label: "Inactive", className: "badge-pink" };
  if (d.valid_until && new Date(d.valid_until) < new Date())
    return { label: "Expired", className: "badge-purple" };
  if (d.max_uses !== null && d.uses_count >= d.max_uses)
    return { label: "Maxed", className: "badge-purple" };
  return { label: "Active", className: "badge-green" };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatFullDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function KPICard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="glass rounded-xl p-5">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className="text-2xl font-bold text-text-primary">{value}</p>
    </div>
  );
}

function UsageCard({ item }: { item: UsageItem }) {
  const firstProduct = item.products?.[0];
  const extraCount = (item.products?.length ?? 0) - 1;
  const statusColor =
    item.status === "completed" || item.status === "active"
      ? "bg-green-500/20 text-green-300"
      : item.status === "pending"
        ? "bg-yellow-500/20 text-yellow-300"
        : item.status === "cancelled" || item.status === "canceled"
          ? "bg-red-500/20 text-red-300"
          : "bg-white/10 text-text-muted";

  return (
    <div className="glass rounded-lg p-3 flex items-center gap-3">
      {/* Product thumbnail */}
      <div className="w-10 h-10 rounded-lg bg-white/5 flex-shrink-0 overflow-hidden">
        {firstProduct?.image_url ? (
          <img
            src={firstProduct.image_url}
            alt=""
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-text-muted/40">
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
              />
            </svg>
          </div>
        )}
      </div>

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary truncate">
            {firstProduct?.name || "Unknown product"}
            {extraCount > 0 && (
              <span className="text-text-muted font-normal">
                {" "}
                +{extraCount} more
              </span>
            )}
          </span>
          <span
            className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              item.usage_type === "order"
                ? "bg-blue-500/20 text-blue-300"
                : "bg-purple-500/20 text-purple-300"
            }`}
          >
            {item.usage_type === "order" ? "Order" : "Sub"}
          </span>
          <span
            className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusColor}`}
          >
            {item.status}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-xs text-text-muted truncate">
            {item.user_email}
          </span>
          <span className="text-xs text-text-muted font-mono">
            {item.reference_label}
          </span>
          {item.discount_amount > 0 && (
            <span className="text-xs text-green-400 font-medium">
              -{formatPrice(item.discount_amount)}
            </span>
          )}
        </div>
        {(item.device_type || item.browser) && (
          <div className="flex items-center gap-1.5 mt-1">
            {item.device_type && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-text-muted">
                {item.device_type}
              </span>
            )}
            {item.browser && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-text-muted">
                {item.browser}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Timestamp */}
      <div className="text-right shrink-0">
        <p className="text-xs text-text-muted">
          {relativeTime(item.created_at)}
        </p>
        <p className="text-[10px] text-text-muted/50">
          {formatFullDate(item.created_at)}
        </p>
      </div>
    </div>
  );
}

export default function AdminCouponEditPage() {
  const params = useParams();
  const router = useRouter();
  const { showToast } = useToast();
  const couponId = params.id as string;

  const [coupon, setCoupon] = useState<Discount | null>(null);
  const [stats, setStats] = useState<CouponStats | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [usagePage, setUsagePage] = useState(1);
  const [usageLoading, setUsageLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("usage");

  const fetchCoupon = useCallback(async () => {
    try {
      const data = await apiFetch<Discount>(
        `/ecommerce/admin/discounts/${couponId}`,
      );
      setCoupon(data);
      // Default tab based on usage
      setActiveTab(data.uses_count > 0 ? "usage" : "edit");
    } catch {
      showToast("Coupon not found", "error");
      router.push("/admin/catalog/coupons");
    }
    setLoading(false);
  }, [couponId, router, showToast]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiFetch<CouponStats>(
        `/ecommerce/admin/discounts/${couponId}/stats`,
      );
      setStats(data);
    } catch {
      /* non-critical */
    }
  }, [couponId]);

  const fetchUsage = useCallback(
    async (p: number) => {
      setUsageLoading(true);
      try {
        const data = await apiFetch<UsageResponse>(
          `/ecommerce/admin/discounts/${couponId}/usage?page=${p}&page_size=10`,
        );
        setUsage(data);
        setUsagePage(p);
      } catch {
        /* ignore */
      }
      setUsageLoading(false);
    },
    [couponId],
  );

  useEffect(() => {
    fetchCoupon();
    fetchStats();
  }, [fetchCoupon, fetchStats]);

  useEffect(() => {
    if (activeTab === "usage" && !usage) {
      fetchUsage(1);
    }
  }, [activeTab, usage, fetchUsage]);

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

  const status = getStatusInfo(coupon);
  const tabs: { id: TabId; label: string }[] = [
    { id: "usage", label: "Usage History" },
    { id: "edit", label: "Edit Coupon" },
  ];

  return (
    <div className="max-w-4xl">
      {/* Hero Section */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/admin/catalog/coupons")}
              className="text-text-muted hover:text-text-primary transition-colors mt-1"
            >
              <svg
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
            <div>
              <h1 className="text-3xl font-mono font-bold gradient-text">
                {coupon.code}
              </h1>
              <p className="text-lg text-text-secondary mt-1">
                {formatDiscount(coupon)}{" "}
                <span className="text-text-muted text-sm">
                  {formatScope(coupon)}
                </span>
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className={status.className}>{status.label}</span>
                <span className="text-xs text-text-muted">
                  {coupon.uses_count} / {coupon.max_uses ?? "\u221E"} used
                </span>
              </div>
            </div>
          </div>
          <div className="text-right">
            {coupon.type === "free_shipping" ? (
              <span className="text-xs text-text-muted">
                No Stripe sync (free shipping)
              </span>
            ) : (
              <SyncStatusBadge
                status={coupon.stripe_sync_status}
                error={coupon.stripe_sync_error}
              />
            )}
            {coupon.stripe_coupon_id && (
              <p className="text-[10px] text-text-muted font-mono mt-1">
                {coupon.stripe_coupon_id}
              </p>
            )}
            {coupon.stripe_promotion_code_id && (
              <p className="text-[10px] text-text-muted font-mono">
                {coupon.stripe_promotion_code_id}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        <KPICard
          label="Redemptions"
          value={stats?.total_redemptions ?? "\u2014"}
        />
        <KPICard
          label="Total Saved"
          value={stats ? formatPrice(stats.total_discount_given) : "\u2014"}
        />
        <KPICard
          label="Unique Customers"
          value={stats?.unique_customers ?? "\u2014"}
        />
        <KPICard
          label="Avg Order Value"
          value={stats ? formatPrice(stats.avg_order_value) : "\u2014"}
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mt-6 border-b border-glass-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === tab.id
                ? "text-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-pink" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "usage" && (
        <div className="mt-4">
          {usageLoading && !usage ? (
            <LoadingSpinner className="py-12" />
          ) : !usage || usage.items.length === 0 ? (
            <div className="glass rounded-xl p-10 text-center">
              <div className="text-text-muted/30 mb-3">
                <svg
                  className="w-12 h-12 mx-auto"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1}
                    d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z"
                  />
                </svg>
              </div>
              <p className="text-text-secondary text-sm">
                No one has used this coupon yet
              </p>
              <p className="text-text-muted text-xs mt-1">
                Share the code with customers to start tracking redemptions.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {usage.items.map((item) => (
                  <UsageCard
                    key={`${item.usage_type}-${item.reference_id}`}
                    item={item}
                  />
                ))}
              </div>
              {usageLoading && (
                <div className="text-center py-2">
                  <span className="text-xs text-text-muted">Loading...</span>
                </div>
              )}
              {usage.total_pages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/10">
                  <span className="text-xs text-text-muted">
                    Page {usage.page} of {usage.total_pages} ({usage.total}{" "}
                    total)
                  </span>
                  <div className="flex gap-2">
                    <button
                      disabled={usagePage <= 1 || usageLoading}
                      onClick={() => fetchUsage(usagePage - 1)}
                      className="px-3 py-1 text-xs rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-text-secondary transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      disabled={usagePage >= usage.total_pages || usageLoading}
                      onClick={() => fetchUsage(usagePage + 1)}
                      className="px-3 py-1 text-xs rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed text-text-secondary transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === "edit" && (
        <div className="glass rounded-xl p-6 mt-4">
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
      )}
    </div>
  );
}
