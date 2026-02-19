"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../../lib/api";
import { formatDate } from "../../../../lib/format";
import Pagination from "../../../../components/Pagination";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import { useToast } from "../../../../components/Toast";

interface Subscription {
  id: string;
  user_id: string;
  user_email: string;
  product_id: string;
  product_name: string;
  stripe_subscription_id: string | null;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  trial_start: string | null;
  trial_end: string | null;
  created_at: string;
}

interface SubscriptionListResponse {
  items: Subscription[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-500/10 text-green-400 border border-green-500/20",
  trialing: "bg-accent-blue/10 text-accent-blue border border-accent-blue/20",
  past_due: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
  canceled: "bg-accent-pink/10 text-accent-pink border border-accent-pink/20",
  unpaid: "bg-red-500/10 text-red-400 border border-red-500/20",
  incomplete: "bg-gray-500/10 text-gray-400 border border-gray-500/20",
  paused: "bg-purple-500/10 text-purple-400 border border-purple-500/20",
};

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "trialing", label: "Trialing" },
  { value: "past_due", label: "Past Due" },
  { value: "canceled", label: "Canceled" },
];

export default function AdminSubscribersPage() {
  const { showToast } = useToast();
  const [data, setData] = useState<SubscriptionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [cancelId, setCancelId] = useState<string | null>(null);
  const [canceling, setCanceling] = useState(false);

  const fetchSubscriptions = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await apiFetch(`/ecommerce/admin/subscriptions?${params}`) as SubscriptionListResponse;
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleCancel = async () => {
    if (!cancelId) return;
    setCanceling(true);
    try {
      await apiFetch(`/ecommerce/admin/subscriptions/${cancelId}/cancel`, { method: "POST" });
      showToast("Subscription canceled at period end", "success");
      setCancelId(null);
      fetchSubscriptions();
    } catch {
      showToast("Failed to cancel subscription", "error");
    }
    setCanceling(false);
  };

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
      </div>

      {loading ? (
        <LoadingSpinner size="lg" className="py-20" />
      ) : !data || data.items.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center">
          <p className="text-text-muted">No subscriptions found</p>
          <p className="text-xs text-text-muted mt-1">
            Subscriptions appear here when customers subscribe to recurring products
          </p>
        </div>
      ) : (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left p-4 text-text-muted font-medium">Customer</th>
                  <th className="text-left p-4 text-text-muted font-medium">Product</th>
                  <th className="text-left p-4 text-text-muted font-medium">Status</th>
                  <th className="text-left p-4 text-text-muted font-medium">Current Period</th>
                  <th className="text-left p-4 text-text-muted font-medium">Created</th>
                  <th className="text-right p-4 text-text-muted font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((sub) => (
                  <tr key={sub.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                    <td className="p-4 text-text-primary">{sub.user_email}</td>
                    <td className="p-4 text-text-secondary">{sub.product_name}</td>
                    <td className="p-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          STATUS_STYLES[sub.status] || "bg-gray-500/10 text-gray-400"
                        }`}
                      >
                        {sub.status}
                        {sub.cancel_at_period_end && sub.status === "active" ? " (canceling)" : ""}
                      </span>
                    </td>
                    <td className="p-4 text-text-muted text-xs">
                      {sub.current_period_start && sub.current_period_end ? (
                        <>
                          {formatDate(sub.current_period_start)} &mdash; {formatDate(sub.current_period_end)}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="p-4 text-text-muted">{formatDate(sub.created_at)}</td>
                    <td className="p-4 text-right whitespace-nowrap">
                      {sub.stripe_subscription_id && (
                        <span className="text-xs font-mono text-text-muted mr-3">
                          {sub.stripe_subscription_id.slice(0, 16)}...
                        </span>
                      )}
                      {(sub.status === "active" || sub.status === "trialing") && !sub.cancel_at_period_end && (
                        <button
                          onClick={() => setCancelId(sub.id)}
                          className="text-xs text-accent-pink hover:text-accent-pink/80"
                        >
                          Cancel
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

      {/* Cancel Confirmation Modal */}
      <Modal isOpen={!!cancelId} onClose={() => setCancelId(null)} title="Cancel Subscription" size="sm">
        <p className="text-text-secondary text-sm mb-4">
          Are you sure you want to cancel this subscription? It will remain active until the end of the current billing period.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setCancelId(null)}
            className="btn-secondary px-4 py-2 rounded-lg text-sm"
            disabled={canceling}
          >
            Keep Active
          </button>
          <button
            onClick={handleCancel}
            className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors"
            disabled={canceling}
          >
            {canceling ? "Canceling..." : "Cancel Subscription"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
