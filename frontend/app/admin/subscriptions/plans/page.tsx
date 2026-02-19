"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../../lib/api";
import { formatPrice, formatDate } from "../../../../lib/format";
import Pagination from "../../../../components/Pagination";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import { useToast } from "../../../../components/Toast";
import ProductForm, { type ProductFormData } from "../../../../components/admin/ProductForm";
import SyncStatusBadge from "../../../../components/admin/SyncStatusBadge";

interface Plan {
  id: string;
  name: string;
  slug: string;
  base_price: number;
  currency: string;
  status: string;
  pricing_type: string;
  recurring_interval: string | null;
  recurring_interval_count: number;
  trial_period_days: number | null;
  stripe_product_id: string | null;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
  synced_provider: string | null;
  subscriber_count: number;
  created_at: string;
}

interface PlanListResponse {
  items: Plan[];
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

function formatInterval(interval: string | null, count: number): string {
  if (!interval) return "—";
  const labels: Record<string, [string, string]> = {
    day: ["Daily", "days"],
    week: ["Weekly", "weeks"],
    month: ["Monthly", "months"],
    year: ["Yearly", "years"],
  };
  const [single, plural] = labels[interval] || [interval, interval];
  if (count === 1) return single;
  return `Every ${count} ${plural}`;
}

export default function SubscriptionPlansPage() {
  const { showToast } = useToast();
  const [data, setData] = useState<PlanListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<Plan | null>(null);
  const [saving, setSaving] = useState(false);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const fetchPlans = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({
      page: String(page),
      page_size: "20",
      pricing_type: "recurring",
    });
    if (statusFilter !== "all") params.set("status", statusFilter);
    apiFetch<PlanListResponse>(`/ecommerce/products?${params}`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleCreate = async (formData: ProductFormData) => {
    setCreating(true);
    try {
      await apiFetch("/ecommerce/products", {
        method: "POST",
        body: JSON.stringify({
          ...formData,
          pricing_type: "recurring",
          type: "subscription",
        }),
      });
      showToast("Plan created", "success");
      setShowCreate(false);
      fetchPlans();
    } catch {
      showToast("Failed to create plan", "error");
    }
    setCreating(false);
  };

  const handleEdit = async (formData: ProductFormData) => {
    if (!editItem) return;
    setSaving(true);
    try {
      await apiFetch(`/ecommerce/products/${editItem.id}`, {
        method: "PUT",
        body: JSON.stringify(formData),
      });
      showToast("Plan updated", "success");
      setEditItem(null);
      fetchPlans();
    } catch {
      showToast("Failed to update plan", "error");
    }
    setSaving(false);
  };

  const handleArchive = async () => {
    if (!archiveId) return;
    setArchiving(true);
    try {
      await apiFetch(`/ecommerce/products/${archiveId}`, {
        method: "PUT",
        body: JSON.stringify({ status: "archived" }),
      });
      showToast("Plan archived", "success");
      setArchiveId(null);
      fetchPlans();
    } catch {
      showToast("Failed to archive plan", "error");
    }
    setArchiving(false);
  };

  const handleRetrySync = async (planId: string) => {
    setSyncingId(planId);
    try {
      await apiFetch(`/ecommerce/products/${planId}/sync`, { method: "POST" });
      showToast("Sync successful", "success");
      fetchPlans();
    } catch {
      showToast("Sync failed", "error");
    }
    setSyncingId(null);
  };

  const statusBadge = (status: string) => {
    if (status === "active") return "badge-green";
    if (status === "archived") return "badge-pink";
    return "badge-purple";
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
          + Create Plan
        </button>
      </div>

      {!data || data.items.length === 0 ? (
        <div className="text-text-secondary glass rounded-xl p-12 text-center">
          <p className="text-lg mb-2">No subscription plans yet</p>
          <p className="text-sm text-text-muted mb-4">
            Create your first subscription plan to offer recurring billing.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="btn-primary px-4 py-2 rounded-lg text-sm"
          >
            + Create Plan
          </button>
        </div>
      ) : (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left p-4 text-text-muted font-medium">Name</th>
                  <th className="text-left p-4 text-text-muted font-medium">Price</th>
                  <th className="text-left p-4 text-text-muted font-medium">Interval</th>
                  <th className="text-left p-4 text-text-muted font-medium">Trial</th>
                  <th className="text-left p-4 text-text-muted font-medium">Subscribers</th>
                  <th className="text-left p-4 text-text-muted font-medium">Status</th>
                  <th className="text-left p-4 text-text-muted font-medium">Sync</th>
                  <th className="text-right p-4 text-text-muted font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((plan) => (
                  <tr key={plan.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                    <td className="p-4 text-text-primary font-medium">{plan.name}</td>
                    <td className="p-4 text-text-primary">{formatPrice(plan.base_price, plan.currency)}</td>
                    <td className="p-4 text-text-secondary">
                      {formatInterval(plan.recurring_interval, plan.recurring_interval_count)}
                    </td>
                    <td className="p-4 text-text-muted">
                      {plan.trial_period_days ? `${plan.trial_period_days} days` : "—"}
                    </td>
                    <td className="p-4">
                      <span className="text-text-primary font-medium">{plan.subscriber_count}</span>
                    </td>
                    <td className="p-4">
                      <span className={statusBadge(plan.status)}>{plan.status}</span>
                    </td>
                    <td className="p-4">
                      <SyncStatusBadge
                        status={plan.stripe_sync_status}
                        error={plan.stripe_sync_error}
                        provider={plan.synced_provider}
                        onRetry={
                          plan.stripe_sync_status === "error"
                            ? () => handleRetrySync(plan.id)
                            : undefined
                        }
                      />
                      {syncingId === plan.id && (
                        <span className="text-xs text-text-muted ml-1">Syncing...</span>
                      )}
                    </td>
                    <td className="p-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => setEditItem(plan)}
                        className="text-xs text-accent-blue hover:text-accent-blue/80 mr-3"
                      >
                        Edit
                      </button>
                      {plan.status !== "archived" && (
                        <button
                          onClick={() => setArchiveId(plan.id)}
                          className="text-xs text-accent-pink hover:text-accent-pink/80"
                        >
                          Archive
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
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

      {/* Create Plan Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Subscription Plan" size="lg">
        <ProductForm
          initial={{
            pricing_type: "recurring",
            type: "subscription",
            recurring_interval: "month",
            recurring_interval_count: 1,
          }}
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
          loading={creating}
          submitLabel="Create Plan"
        />
      </Modal>

      {/* Edit Plan Modal */}
      <Modal isOpen={!!editItem} onClose={() => setEditItem(null)} title="Edit Subscription Plan" size="lg">
        {editItem && (
          <ProductForm
            initial={{
              name: editItem.name,
              base_price: editItem.base_price,
              currency: editItem.currency,
              status: editItem.status,
              type: "subscription",
              pricing_type: "recurring",
              recurring_interval: editItem.recurring_interval,
              recurring_interval_count: editItem.recurring_interval_count,
              trial_period_days: editItem.trial_period_days,
            }}
            onSubmit={handleEdit}
            onCancel={() => setEditItem(null)}
            loading={saving}
            submitLabel="Update Plan"
          />
        )}
      </Modal>

      {/* Archive Confirmation Modal */}
      <Modal isOpen={!!archiveId} onClose={() => setArchiveId(null)} title="Archive Plan" size="sm">
        <p className="text-text-secondary text-sm mb-4">
          Are you sure you want to archive this subscription plan? Existing subscribers will not be affected,
          but no new subscriptions can be created for this plan.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setArchiveId(null)}
            className="btn-secondary px-4 py-2 rounded-lg text-sm"
            disabled={archiving}
          >
            Cancel
          </button>
          <button
            onClick={handleArchive}
            className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors"
            disabled={archiving}
          >
            {archiving ? "Archiving..." : "Archive"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
