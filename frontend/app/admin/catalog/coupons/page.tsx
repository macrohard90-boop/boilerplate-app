"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../../../lib/api";
import { formatPrice, formatDate } from "../../../../lib/format";
import Pagination from "../../../../components/Pagination";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import { useToast } from "../../../../components/Toast";
import SyncStatusBadge from "../../../../components/admin/SyncStatusBadge";

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

interface DiscountListResponse {
  items: Discount[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
];

function formatValue(d: Discount): string {
  if (d.type === "percentage") return `${d.value}%`;
  if (d.type === "fixed") return formatPrice(d.value, d.currency);
  return "Free Shipping";
}

function getStatusInfo(d: Discount): { label: string; className: string } {
  if (!d.active) return { label: "Inactive", className: "badge-pink" };
  if (d.valid_until && new Date(d.valid_until) < new Date())
    return { label: "Expired", className: "badge-purple" };
  if (d.max_uses !== null && d.uses_count >= d.max_uses)
    return { label: "Maxed", className: "badge-purple" };
  return { label: "Active", className: "badge-green" };
}

interface ProductInfo {
  id: string;
  name: string;
}

export default function AdminCouponsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [data, setData] = useState<DiscountListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [deactivateId, setDeactivateId] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState(false);
  const [productMap, setProductMap] = useState<Record<string, string>>({});

  const fetchCoupons = useCallback(() => {
    setLoading(true);
    const statusParam = statusFilter !== "all" ? `&status=${statusFilter}` : "";
    apiFetch<DiscountListResponse>(
      `/ecommerce/admin/discounts?page=${page}&page_size=20${statusParam}`,
    )
      .then(setData)
      .catch(() => showToast("Failed to load coupons", "error"))
      .finally(() => setLoading(false));
  }, [page, statusFilter, showToast]);

  useEffect(() => {
    fetchCoupons();
  }, [fetchCoupons]);

  // Fetch product names for any coupons that have product_ids
  useEffect(() => {
    if (!data) return;
    const allProductIds = new Set<string>();
    data.items.forEach((d) =>
      d.product_ids?.forEach((pid) => {
        if (!productMap[pid]) allProductIds.add(pid);
      }),
    );
    if (allProductIds.size === 0) return;
    // Fetch products to build id→name map
    apiFetch<{ items: ProductInfo[] }>(
      "/ecommerce/products?status=active&page_size=200",
    )
      .then((res) => {
        const map: Record<string, string> = { ...productMap };
        (res.items || []).forEach((p) => {
          map[p.id] = p.name;
        });
        setProductMap(map);
      })
      .catch(() => {});
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleDeactivate = async () => {
    if (!deactivateId) return;
    setDeactivating(true);
    try {
      await apiFetch(`/ecommerce/admin/discounts/${deactivateId}`, {
        method: "DELETE",
      });
      showToast("Coupon deactivated", "success");
      setDeactivateId(null);
      fetchCoupons();
    } catch {
      showToast("Failed to deactivate coupon", "error");
    }
    setDeactivating(false);
  };

  if (loading && !data) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => handleStatusFilterChange(f.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                statusFilter === f.value
                  ? "bg-accent-pink/10 text-accent-pink border border-accent-pink/30"
                  : "text-text-muted hover:text-text-primary border border-transparent"
              }`}
            >
              {f.label}
            </button>
          ))}
          {data && (
            <span className="text-text-muted text-xs ml-2">({data.total})</span>
          )}
        </div>
        <button
          onClick={() => router.push("/admin/catalog/coupons/new")}
          className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Create Coupon
        </button>
      </div>

      {!data || data.items.length === 0 ? (
        <div className="text-text-secondary glass rounded-xl p-12 text-center">
          <p className="text-lg mb-2">No coupons yet</p>
          <p className="text-sm text-text-muted mb-4">
            Create your first coupon to offer discounts.
          </p>
          <button
            onClick={() => router.push("/admin/catalog/coupons/new")}
            className="btn-primary px-4 py-2 rounded-lg text-sm"
          >
            + Create Coupon
          </button>
        </div>
      ) : (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left p-4 text-text-muted font-medium">
                    Code
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Type
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Value
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Min Order
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Applies To
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Restrictions
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Usage
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Valid Until
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Status
                  </th>
                  <th className="text-left p-4 text-text-muted font-medium">
                    Stripe
                  </th>
                  <th className="text-right p-4 text-text-muted font-medium">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((d) => {
                  const status = getStatusInfo(d);
                  return (
                    <tr
                      key={d.id}
                      className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                    >
                      <td className="p-4 text-text-primary font-mono font-medium">
                        {d.code}
                      </td>
                      <td className="p-4 text-text-secondary capitalize">
                        {d.type.replace("_", " ")}
                      </td>
                      <td className="p-4 text-text-primary">
                        {formatValue(d)}
                      </td>
                      <td className="p-4 text-text-muted">
                        {d.min_order_amount > 0
                          ? formatPrice(d.min_order_amount, d.currency)
                          : "\u2014"}
                      </td>
                      <td className="p-4 text-text-secondary capitalize">
                        {d.applies_to === "one_time"
                          ? "One-time"
                          : d.applies_to === "recurring"
                            ? "Recurring"
                            : "All"}
                      </td>
                      <td className="p-4">
                        <div className="flex flex-col gap-1">
                          {d.product_ids?.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {d.product_ids.map((pid) => (
                                <span
                                  key={pid}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-accent-blue/10 text-accent-blue"
                                  title={pid}
                                >
                                  {productMap[pid] || pid.slice(0, 8)}
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="flex flex-wrap gap-1">
                            {d.restricted_to_customer_id && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-purple/10 text-accent-purple">
                                Customer
                              </span>
                            )}
                            {d.first_time_transaction_only && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-green/10 text-accent-green">
                                First-time
                              </span>
                            )}
                            {d.max_uses_per_customer != null && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-400">
                                {d.max_uses_per_customer}/customer
                              </span>
                            )}
                          </div>
                          {!d.product_ids?.length &&
                            !d.restricted_to_customer_id &&
                            !d.first_time_transaction_only &&
                            d.max_uses_per_customer == null && (
                              <span className="text-text-muted text-xs">
                                Global
                              </span>
                            )}
                        </div>
                      </td>
                      <td className="p-4 text-text-secondary">
                        {d.uses_count} / {d.max_uses ?? "unlimited"}
                      </td>
                      <td className="p-4 text-text-muted">
                        {d.valid_until ? formatDate(d.valid_until) : "\u2014"}
                      </td>
                      <td className="p-4">
                        <span className={status.className}>{status.label}</span>
                      </td>
                      <td className="p-4">
                        {d.type === "free_shipping" ? (
                          <span className="text-xs text-text-muted">N/A</span>
                        ) : (
                          <SyncStatusBadge
                            status={d.stripe_sync_status}
                            error={d.stripe_sync_error}
                          />
                        )}
                      </td>
                      <td className="p-4 text-right whitespace-nowrap">
                        <button
                          onClick={() =>
                            router.push(`/admin/catalog/coupons/${d.id}`)
                          }
                          className="text-xs text-accent-blue hover:text-accent-blue/80 mr-3"
                        >
                          Edit
                        </button>
                        {d.active && (
                          <button
                            onClick={() => setDeactivateId(d.id)}
                            className="text-xs text-accent-pink hover:text-accent-pink/80"
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {data.total_pages > 1 && (
            <div className="mt-6">
              <Pagination
                currentPage={data.page}
                totalPages={data.total_pages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}

      {/* Deactivate Confirmation Modal */}
      <Modal
        isOpen={!!deactivateId}
        onClose={() => setDeactivateId(null)}
        title="Deactivate Coupon"
        size="sm"
      >
        <p className="text-text-secondary text-sm mb-4">
          Are you sure you want to deactivate this coupon? It will no longer be
          usable at checkout.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setDeactivateId(null)}
            className="btn-secondary px-4 py-2 rounded-lg text-sm"
            disabled={deactivating}
          >
            Cancel
          </button>
          <button
            onClick={handleDeactivate}
            className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors"
            disabled={deactivating}
          >
            {deactivating ? "Deactivating..." : "Deactivate"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
