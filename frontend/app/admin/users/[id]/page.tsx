"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../lib/api";
import { formatDate, formatPrice, capitalize } from "../../../../lib/format";
import { useAuth } from "../../../../lib/auth-context";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import HorizontalBarChart from "../../../../components/charts/HorizontalBarChart";

// --- Types ---

interface UserProfile {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
  phone: string | null;
  whatsapp_number: string | null;
  deleted_at: string | null;
}

interface CustomerMetrics {
  order_count: number;
  total_spent: number;
  currency: string;
  rfm_segment: string | null;
  last_purchase_at: string | null;
}

interface Engagement {
  sessions_90d: number;
  pages_90d: number;
  last_visit: string | null;
}

interface RecentOrder {
  id: string;
  order_number: string;
  status: string;
  total: number;
  currency: string;
  created_at: string;
}

interface RecentSession {
  session_id: string;
  started_at: string;
  ended_at: string | null;
  page_count: number;
  browser: string | null;
  os: string | null;
  device_type: string | null;
}

interface TopPage {
  path: string;
  views: number;
}

interface EmailPreferences {
  marketing_email: boolean;
  transactional_email: boolean;
  suppressed_at: string | null;
}

interface FullProfile {
  user: UserProfile;
  customer_metrics: CustomerMetrics | null;
  engagement: Engagement;
  recent_orders: RecentOrder[];
  recent_sessions: RecentSession[];
  top_pages: TopPage[];
  email_preferences: EmailPreferences | null;
  cart_summary: { active_carts: number; total_items: number };
  wishlist_summary: { wishlists: number; total_items: number };
}

// --- Helpers ---

const AVAILABLE_ROLES = ["admin", "merchant", "customer"];

const RFM_COLORS: Record<string, string> = {
  champion: "bg-green-500/20 text-green-300 border-green-500/30",
  loyal: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  potential_loyalist: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  new: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  at_risk: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  hibernating: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  lost: "bg-red-500/20 text-red-300 border-red-500/30",
};

function roleBadge(role: string) {
  const colors: Record<string, string> = {
    admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    merchant: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    customer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors[role] ?? colors.customer}`}
    >
      {role}
    </span>
  );
}

function statusBadge(u: UserProfile) {
  if (u.deleted_at)
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/30">
        deleted
      </span>
    );
  if (!u.is_active)
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">
        inactive
      </span>
    );
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-300 border border-green-500/30">
      active
    </span>
  );
}

function orderStatusBadge(status: string) {
  const map: Record<string, string> = {
    completed: "bg-green-500/20 text-green-300",
    accepted: "bg-green-500/20 text-green-300",
    processing: "bg-blue-500/20 text-blue-300",
    pending: "bg-yellow-500/20 text-yellow-300",
    rejected: "bg-red-500/20 text-red-300",
    refunded: "bg-orange-500/20 text-orange-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {status}
    </span>
  );
}

function formatDuration(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return "active";
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  return `${(ms / 3_600_000).toFixed(1)}h`;
}

function deviceBadge(deviceType: string | null) {
  const label = deviceType ?? "unknown";
  const map: Record<string, string> = {
    desktop: "bg-blue-500/20 text-blue-300",
    mobile: "bg-green-500/20 text-green-300",
    tablet: "bg-purple-500/20 text-purple-300",
    bot: "bg-red-500/20 text-red-300",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-xs ${map[label] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {label}
    </span>
  );
}

// --- Page ---

export default function UserProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user: currentUser } = useAuth();

  const [data, setData] = useState<FullProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Admin action state
  const [actionLoading, setActionLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await apiFetch<FullProfile>(
        `/auth/admin/users/${id}/full-profile`,
      );
      setData(res);
      setError(null);
    } catch {
      setError("Failed to load user profile.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  // --- Action handlers ---

  const handleRoleChange = async (newRole: string) => {
    setActionLoading(true);
    try {
      await apiFetch(`/auth/admin/users/${id}/role`, {
        method: "PUT",
        body: JSON.stringify({ role: newRole }),
      });
      await fetchProfile();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to update role";
      alert(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStatusToggle = async (activate: boolean) => {
    setActionLoading(true);
    try {
      await apiFetch(`/auth/admin/users/${id}/status`, {
        method: "PUT",
        body: JSON.stringify({ is_active: activate }),
      });
      await fetchProfile();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to update status";
      alert(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await apiFetch(`/auth/admin/users/${id}`, { method: "DELETE" });
      router.push("/admin/users");
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to delete user";
      alert(msg);
    } finally {
      setActionLoading(false);
      setConfirmDelete(false);
    }
  };

  const handleResendVerification = async () => {
    setActionLoading(true);
    try {
      const res = await apiFetch<{ message: string }>(
        `/auth/admin/users/${id}/resend-verification`,
        { method: "POST" },
      );
      alert(res.message);
      await fetchProfile();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to resend verification";
      alert(msg);
    } finally {
      setActionLoading(false);
    }
  };

  // --- Render ---

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-20">
        <p className="text-text-muted mb-4">{error ?? "User not found."}</p>
        <Link href="/admin/users" className="text-accent hover:text-accent/80">
          Back to Users
        </Link>
      </div>
    );
  }

  const { user: u, customer_metrics: cm, engagement: eng } = data;
  const isSelf = currentUser?.id === u.id;
  const isDeleted = !!u.deleted_at;
  const displayName =
    [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/users")}
          className="p-1.5 rounded-lg hover:bg-white/5 transition-colors text-text-muted hover:text-text-primary"
        >
          <svg
            width="20"
            height="20"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <div className="flex-1">
          <h1 className="font-serif text-2xl font-bold">
            <span className="gradient-text">{displayName}</span>
          </h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-text-muted">
            <span className="font-mono text-xs">{u.email}</span>
            <span>·</span>
            {roleBadge(u.role)}
            {statusBadge(u)}
            {u.is_verified ? (
              <span className="text-green-400 text-xs" title="Email verified">
                &#10003; Verified
              </span>
            ) : (
              <span className="text-red-400 text-xs" title="Not verified">
                &#10007; Unverified
              </span>
            )}
          </div>
        </div>
        <div className="text-right text-xs text-text-muted">
          <p>Joined {formatDate(u.created_at)}</p>
          {u.phone && <p>Phone: {u.phone}</p>}
          {u.whatsapp_number && <p>WhatsApp: {u.whatsapp_number}</p>}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {/* Total Orders */}
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Total Orders</p>
          <p className="text-2xl font-bold text-text-primary tabular-nums">
            {cm?.order_count ?? 0}
          </p>
          {cm?.last_purchase_at && (
            <p className="text-xs text-text-muted mt-1">
              Last: {formatDate(cm.last_purchase_at)}
            </p>
          )}
        </div>

        {/* Total Spent */}
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Total Spent</p>
          <p className="text-2xl font-bold text-text-primary tabular-nums">
            {cm ? formatPrice(cm.total_spent, cm.currency) : "$0.00"}
          </p>
        </div>

        {/* RFM Segment */}
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">RFM Segment</p>
          {cm?.rfm_segment ? (
            <span
              className={`inline-block px-2.5 py-1 rounded-full text-sm font-medium border mt-1 ${
                RFM_COLORS[cm.rfm_segment] ??
                "bg-gray-500/20 text-gray-300 border-gray-500/30"
              }`}
            >
              {cm.rfm_segment.replace(/_/g, " ")}
            </span>
          ) : (
            <p className="text-lg text-text-muted">--</p>
          )}
        </div>

        {/* Engagement (90d) */}
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Activity (90d)</p>
          <p className="text-2xl font-bold text-text-primary tabular-nums">
            {eng.sessions_90d}
            <span className="text-sm font-normal text-text-muted ml-1">
              sessions
            </span>
          </p>
          <p className="text-xs text-text-muted mt-1">
            {eng.pages_90d} pages
            {eng.last_visit && <> · Last {formatDate(eng.last_visit)}</>}
          </p>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Recent Orders */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Recent Orders
            </h2>
            {data.recent_orders.length === 0 ? (
              <p className="text-sm text-text-muted py-4">No orders yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-text-muted text-xs border-b border-glass-border">
                      <th className="pb-2 font-medium">Order</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium text-right">Total</th>
                      <th className="pb-2 font-medium text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_orders.map((o) => (
                      <tr
                        key={o.id}
                        className="border-b border-glass-border/30"
                      >
                        <td className="py-2 font-mono text-xs text-text-primary">
                          {o.order_number}
                        </td>
                        <td className="py-2">{orderStatusBadge(o.status)}</td>
                        <td className="py-2 text-right tabular-nums text-text-primary">
                          {formatPrice(o.total, o.currency)}
                        </td>
                        <td className="py-2 text-right text-text-muted text-xs">
                          {formatDate(o.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Admin Actions */}
          {!isSelf && (
            <div className="glass rounded-xl p-5">
              <button
                onClick={() => setActionsOpen(!actionsOpen)}
                className="flex items-center justify-between w-full text-sm font-semibold text-text-primary uppercase tracking-wide"
              >
                <span>Admin Actions</span>
                <svg
                  width="16"
                  height="16"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                  className={`transition-transform ${actionsOpen ? "rotate-180" : ""}`}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {actionsOpen && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                  {/* Verification */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Verification
                    </h4>
                    {u.is_verified ? (
                      <p className="text-xs text-green-400">Email verified</p>
                    ) : isDeleted ? (
                      <p className="text-xs text-text-muted">User is deleted</p>
                    ) : (
                      <button
                        disabled={actionLoading}
                        onClick={handleResendVerification}
                        className="px-3 py-1 rounded text-xs font-medium bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 disabled:opacity-40"
                      >
                        Resend Verification
                      </button>
                    )}
                  </div>

                  {/* Role */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Role
                    </h4>
                    {isDeleted ? (
                      <p className="text-xs text-text-muted">User is deleted</p>
                    ) : (
                      <select
                        defaultValue={u.role}
                        disabled={actionLoading}
                        onChange={(e) => {
                          if (e.target.value !== u.role)
                            handleRoleChange(e.target.value);
                        }}
                        className="input-glass text-xs !py-1 !px-2 !w-auto"
                      >
                        {AVAILABLE_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {capitalize(r)}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Status */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Status
                    </h4>
                    {isDeleted ? (
                      <p className="text-xs text-text-muted">User is deleted</p>
                    ) : (
                      <button
                        disabled={actionLoading}
                        onClick={() => handleStatusToggle(!u.is_active)}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          u.is_active
                            ? "bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30"
                            : "bg-green-500/20 text-green-300 hover:bg-green-500/30"
                        } disabled:opacity-40`}
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    )}
                  </div>

                  {/* Delete */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      Delete
                    </h4>
                    {isDeleted ? (
                      <p className="text-xs text-text-muted">Already deleted</p>
                    ) : confirmDelete ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-red-400">Confirm?</span>
                        <button
                          disabled={actionLoading}
                          onClick={handleDelete}
                          className="px-3 py-1 rounded text-xs font-medium bg-red-500/20 text-red-300 hover:bg-red-500/30 disabled:opacity-40"
                        >
                          Yes, delete
                        </button>
                        <button
                          onClick={() => setConfirmDelete(false)}
                          className="px-3 py-1 rounded text-xs font-medium bg-base-100 text-text-secondary hover:bg-base-100/80"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        disabled={actionLoading}
                        onClick={() => setConfirmDelete(true)}
                        className="px-3 py-1 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-40"
                      >
                        Delete user
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Recent Sessions */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Recent Sessions
            </h2>
            {data.recent_sessions.length === 0 ? (
              <p className="text-sm text-text-muted py-4">
                No sessions recorded
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-text-muted text-xs border-b border-glass-border">
                      <th className="pb-2 font-medium">Date</th>
                      <th className="pb-2 font-medium text-right">Duration</th>
                      <th className="pb-2 font-medium text-right">Pages</th>
                      <th className="pb-2 font-medium">Device</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_sessions.map((s) => (
                      <tr
                        key={s.session_id}
                        className="border-b border-glass-border/30"
                      >
                        <td className="py-2 text-text-primary text-xs">
                          {formatDate(s.started_at)}
                        </td>
                        <td className="py-2 text-right tabular-nums text-text-secondary text-xs">
                          {formatDuration(s.started_at, s.ended_at)}
                        </td>
                        <td className="py-2 text-right tabular-nums text-text-primary text-xs">
                          {s.page_count}
                        </td>
                        <td className="py-2">
                          <div className="flex items-center gap-1">
                            {deviceBadge(s.device_type)}
                            {s.browser && (
                              <span className="text-xs text-text-muted">
                                {s.browser}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Top Pages */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Top Pages (90d)
            </h2>
            <HorizontalBarChart
              data={data.top_pages.map((p) => ({
                label: p.path,
                value: p.views,
              }))}
              color="#8b5cf6"
              formatValue={(v) => `${v} views`}
            />
          </div>
        </div>
      </div>

      {/* Full-width: Preferences & Summary */}
      <div className="glass rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-4 uppercase tracking-wide">
          Preferences & Summary
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
          {/* Email Preferences */}
          <div>
            <h4 className="text-xs font-medium text-text-muted mb-2">
              Email Preferences
            </h4>
            {data.email_preferences ? (
              <div className="space-y-1">
                <p className="text-xs">
                  <span className="text-text-muted">Marketing:</span>{" "}
                  <span
                    className={
                      data.email_preferences.marketing_email
                        ? "text-green-400"
                        : "text-red-400"
                    }
                  >
                    {data.email_preferences.marketing_email
                      ? "Opted in"
                      : "Opted out"}
                  </span>
                </p>
                <p className="text-xs">
                  <span className="text-text-muted">Transactional:</span>{" "}
                  <span
                    className={
                      data.email_preferences.transactional_email
                        ? "text-green-400"
                        : "text-red-400"
                    }
                  >
                    {data.email_preferences.transactional_email
                      ? "Enabled"
                      : "Disabled"}
                  </span>
                </p>
                {data.email_preferences.suppressed_at && (
                  <p className="text-xs text-red-400">
                    Suppressed:{" "}
                    {formatDate(data.email_preferences.suppressed_at)}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-xs text-text-muted">No preferences set</p>
            )}
          </div>

          {/* Cart Summary */}
          <div>
            <h4 className="text-xs font-medium text-text-muted mb-2">
              Active Cart
            </h4>
            <p className="text-lg font-bold text-text-primary tabular-nums">
              {data.cart_summary.total_items}
              <span className="text-xs font-normal text-text-muted ml-1">
                items
              </span>
            </p>
            <p className="text-xs text-text-muted">
              {data.cart_summary.active_carts} active{" "}
              {data.cart_summary.active_carts === 1 ? "cart" : "carts"}
            </p>
          </div>

          {/* Wishlist Summary */}
          <div>
            <h4 className="text-xs font-medium text-text-muted mb-2">
              Wishlists
            </h4>
            <p className="text-lg font-bold text-text-primary tabular-nums">
              {data.wishlist_summary.total_items}
              <span className="text-xs font-normal text-text-muted ml-1">
                items
              </span>
            </p>
            <p className="text-xs text-text-muted">
              {data.wishlist_summary.wishlists}{" "}
              {data.wishlist_summary.wishlists === 1 ? "wishlist" : "wishlists"}
            </p>
          </div>

          {/* Quick Stat */}
          <div>
            <h4 className="text-xs font-medium text-text-muted mb-2">
              Account Info
            </h4>
            <p className="text-xs">
              <span className="text-text-muted">User ID:</span>{" "}
              <span className="text-text-secondary font-mono">
                {u.id.slice(0, 8)}...
              </span>
            </p>
            {u.deleted_at && (
              <p className="text-xs text-red-400 mt-1">
                Deleted: {formatDate(u.deleted_at)}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
