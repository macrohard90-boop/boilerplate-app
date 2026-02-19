"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../../lib/api";
import { formatPrice, formatDate } from "../../../../lib/format";
import Pagination from "../../../../components/Pagination";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import { useToast } from "../../../../components/Toast";
import CouponForm, { type CouponFormData } from "../../../../components/admin/CouponForm";

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

export default function AdminCouponsPage() {
  const { showToast } = useToast();
  const [data, setData] = useState<DiscountListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<Discount | null>(null);
  const [editing, setEditing] = useState(false);
  const [deactivateId, setDeactivateId] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  const fetchCoupons = useCallback(() => {
    setLoading(true);
    const statusParam = statusFilter !== "all" ? `&status=${statusFilter}` : "";
    apiFetch<DiscountListResponse>(
      `/ecommerce/admin/discounts?page=${page}&page_size=20${statusParam}`
    )
      .then(setData)
      .catch(() => showToast("Failed to load coupons", "error"))
      .finally(() => setLoading(false));
  }, [page, statusFilter, showToast]);

  useEffect(() => { fetchCoupons(); }, [fetchCoupons]);

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleCreate = async (formData: CouponFormData) => {
    setCreating(true);
    try {
      await apiFetch("/ecommerce/admin/discounts", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      showToast("Coupon created", "success");
      setShowCreate(false);
      fetchCoupons();
    } catch {
      showToast("Failed to create coupon", "error");
    }
    setCreating(false);
  };

  const handleEdit = async (formData: CouponFormData) => {
    if (!editItem) return;
    setEditing(true);
    try {
      await apiFetch(`/ecommerce/admin/discounts/${editItem.id}`, {
        method: "PUT",
        body: JSON.stringify(formData),
      });
      showToast("Coupon updated", "success");
      setEditItem(null);
      fetchCoupons();
    } catch {
      showToast("Failed to update coupon", "error");
    }
    setEditing(false);
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
          {data && <span className="text-text-muted text-xs ml-2">({data.total})</span>}
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Create Coupon
        </button>
      </div>

      {!data || data.items.length === 0 ? (
        <div className="text-text-secondary glass rounded-xl p-12 text-center">
          <p className="text-lg mb-2">No coupons yet</p>
          <p className="text-sm text-text-muted mb-4">Create your first coupon to offer discounts.</p>
          <button
            onClick={() => setShowCreate(true)}
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
                  <th className="text-left p-4 text-text-muted font-medium">Code</th>
                  <th className="text-left p-4 text-text-muted font-medium">Type</th>
                  <th className="text-left p-4 text-text-muted font-medium">Value</th>
                  <th className="text-left p-4 text-text-muted font-medium">Min Order</th>
                  <th className="text-left p-4 text-text-muted font-medium">Applies To</th>
                  <th className="text-left p-4 text-text-muted font-medium">Usage</th>
                  <th className="text-left p-4 text-text-muted font-medium">Valid Until</th>
                  <th className="text-left p-4 text-text-muted font-medium">Status</th>
                  <th className="text-right p-4 text-text-muted font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((d) => {
                  const status = getStatusInfo(d);
                  return (
                    <tr key={d.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                      <td className="p-4 text-text-primary font-mono font-medium">{d.code}</td>
                      <td className="p-4 text-text-secondary capitalize">{d.type.replace("_", " ")}</td>
                      <td className="p-4 text-text-primary">{formatValue(d)}</td>
                      <td className="p-4 text-text-muted">
                        {d.min_order_amount > 0 ? formatPrice(d.min_order_amount, d.currency) : "—"}
                      </td>
                      <td className="p-4 text-text-secondary capitalize">
                        {d.applies_to === "one_time" ? "One-time" : d.applies_to === "recurring" ? "Recurring" : "All"}
                      </td>
                      <td className="p-4 text-text-secondary">
                        {d.uses_count} / {d.max_uses ?? "unlimited"}
                      </td>
                      <td className="p-4 text-text-muted">
                        {d.valid_until ? formatDate(d.valid_until) : "—"}
                      </td>
                      <td className="p-4">
                        <span className={status.className}>{status.label}</span>
                      </td>
                      <td className="p-4 text-right whitespace-nowrap">
                        <button
                          onClick={() => setEditItem(d)}
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
              <Pagination currentPage={data.page} totalPages={data.total_pages} onPageChange={setPage} />
            </div>
          )}
        </>
      )}

      {/* Create Coupon Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Coupon" size="lg">
        <CouponForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
          loading={creating}
          submitLabel="Create"
        />
      </Modal>

      {/* Edit Coupon Modal */}
      <Modal isOpen={!!editItem} onClose={() => setEditItem(null)} title="Edit Coupon" size="lg">
        {editItem && (
          <CouponForm
            initial={{
              code: editItem.code,
              type: editItem.type,
              value: editItem.value,
              currency: editItem.currency,
              min_order_amount: editItem.min_order_amount,
              max_uses: editItem.max_uses,
              valid_from: editItem.valid_from,
              valid_until: editItem.valid_until,
              active: editItem.active,
              applies_to: editItem.applies_to,
              stripe_duration: editItem.stripe_duration,
              stripe_duration_in_months: editItem.stripe_duration_in_months,
              stripe_coupon_id: editItem.stripe_coupon_id ?? undefined,
            }}
            onSubmit={handleEdit}
            onCancel={() => setEditItem(null)}
            loading={editing}
            submitLabel="Update"
          />
        )}
      </Modal>

      {/* Deactivate Confirmation Modal */}
      <Modal isOpen={!!deactivateId} onClose={() => setDeactivateId(null)} title="Deactivate Coupon" size="sm">
        <p className="text-text-secondary text-sm mb-4">
          Are you sure you want to deactivate this coupon? It will no longer be usable at checkout.
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
