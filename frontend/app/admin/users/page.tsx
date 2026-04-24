"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { apiFetch } from "../../../lib/api";
import { formatDate } from "../../../lib/format";
import { useAuth } from "../../../lib/auth-context";
import LoadingSpinner from "../../../components/LoadingSpinner";

// --- Types ---

interface UserItem {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_verified: boolean;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
}

interface UserDetail extends UserItem {
  is_merchant: boolean;
}

interface UserListResponse {
  items: UserItem[];
  total: number;
  page: number;
  page_size: number;
}

// --- Helpers ---

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

function statusBadge(item: UserItem) {
  if (item.deleted_at) {
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-300 border border-red-500/30">
        deleted
      </span>
    );
  }
  if (!item.is_active) {
    return (
      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-300 border border-yellow-500/30">
        inactive
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-300 border border-green-500/30">
      active
    </span>
  );
}

// --- Available roles (fetched dynamically in future; static for now) ---
const AVAILABLE_ROLES = ["admin", "merchant", "customer"];

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();

  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  // Expanded row detail
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Action state
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Debounce search
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current);
    };
  }, [search]);

  // Fetch users
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      if (debouncedSearch) params.set("search", debouncedSearch);
      if (roleFilter) params.set("role", roleFilter);
      if (statusFilter) params.set("status", statusFilter);

      const data = await apiFetch<UserListResponse>(
        `/auth/admin/users?${params.toString()}`,
      );
      setUsers(data.items);
      setTotal(data.total);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, roleFilter, statusFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Fetch detail on expand
  useEffect(() => {
    if (!expandedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    apiFetch<UserDetail>(`/auth/admin/users/${expandedId}`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [expandedId]);

  // --- Actions ---

  const handleRoleChange = async (userId: string, newRole: string) => {
    setActionLoading(userId);
    try {
      await apiFetch(`/auth/admin/users/${userId}/role`, {
        method: "PUT",
        body: JSON.stringify({ role: newRole }),
      });
      await fetchUsers();
      if (expandedId === userId) setExpandedId(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to update role";
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStatusToggle = async (userId: string, activate: boolean) => {
    setActionLoading(userId);
    try {
      await apiFetch(`/auth/admin/users/${userId}/status`, {
        method: "PUT",
        body: JSON.stringify({ is_active: activate }),
      });
      await fetchUsers();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to update status";
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (userId: string) => {
    setActionLoading(userId);
    try {
      await apiFetch(`/auth/admin/users/${userId}`, { method: "DELETE" });
      setConfirmDelete(null);
      await fetchUsers();
      if (expandedId === userId) setExpandedId(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to delete user";
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResendVerification = async (userId: string) => {
    setActionLoading(userId);
    try {
      const res = await apiFetch<{ message: string }>(
        `/auth/admin/users/${userId}/resend-verification`,
        { method: "POST" },
      );
      alert(res.message);
      await fetchUsers();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message: string }).message
          : "Failed to resend verification";
      alert(msg);
    } finally {
      setActionLoading(null);
    }
  };

  const totalPages = Math.ceil(total / pageSize);
  const isSelf = (userId: string) => currentUser?.id === userId;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Users</span>
        <span className="text-text-muted text-sm font-normal ml-3">
          {total} total
        </span>
      </h1>

      {/* Search & Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder="Search by email or name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-glass flex-1 min-w-[200px] text-sm !py-2"
        />
        <select
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(1);
          }}
          className="input-glass text-sm !w-auto !py-2"
        >
          <option value="">All Roles</option>
          {AVAILABLE_ROLES.map((r) => (
            <option key={r} value={r}>
              {r.charAt(0).toUpperCase() + r.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="input-glass text-sm !w-auto !py-2"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="deleted">Deleted</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : users.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-secondary">No users found.</p>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border text-left text-text-muted">
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Verified</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <>
                    <tr
                      key={u.id}
                      className={`border-b border-glass-border/50 hover:bg-base-100/50 transition-colors ${
                        expandedId === u.id ? "bg-base-100/30" : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-text-primary font-mono text-xs">
                        {u.email}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {u.first_name} {u.last_name}
                      </td>
                      <td className="px-4 py-3">{roleBadge(u.role)}</td>
                      <td className="px-4 py-3">{statusBadge(u)}</td>
                      <td className="px-4 py-3 text-center">
                        {u.is_verified ? (
                          <span className="text-green-400" title="Verified">
                            &#10003;
                          </span>
                        ) : (
                          <span className="text-red-400" title="Not verified">
                            &#10007;
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-text-muted text-xs">
                        {formatDate(u.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        {isSelf(u.id) ? (
                          <span className="text-text-muted text-xs italic">
                            you
                          </span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() =>
                                setExpandedId(expandedId === u.id ? null : u.id)
                              }
                              className="text-xs text-accent hover:text-accent/80"
                            >
                              {expandedId === u.id ? "Close" : "Details"}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {expandedId === u.id && (
                      <tr key={`${u.id}-detail`}>
                        <td colSpan={7} className="px-4 py-4 bg-base-100/20">
                          {detailLoading ? (
                            <div className="flex justify-center py-4">
                              <LoadingSpinner />
                            </div>
                          ) : detail ? (
                            <UserActions
                              user={u}
                              detail={detail}
                              actionLoading={actionLoading}
                              confirmDelete={confirmDelete}
                              onRoleChange={handleRoleChange}
                              onStatusToggle={handleStatusToggle}
                              onDelete={handleDelete}
                              onConfirmDelete={setConfirmDelete}
                              onResendVerification={handleResendVerification}
                            />
                          ) : (
                            <p className="text-text-muted text-sm">
                              Failed to load details.
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-glass-border">
              <p className="text-xs text-text-muted">
                Page {page} of {totalPages} ({total} users)
              </p>
              <div className="flex gap-1">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1 text-xs rounded bg-base-100 text-text-secondary hover:bg-base-100/80 disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1 text-xs rounded bg-base-100 text-text-secondary hover:bg-base-100/80 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Inline action panel for expanded row ---

function UserActions({
  user,
  detail,
  actionLoading,
  confirmDelete,
  onRoleChange,
  onStatusToggle,
  onDelete,
  onConfirmDelete,
  onResendVerification,
}: {
  user: UserItem;
  detail: UserDetail;
  actionLoading: string | null;
  confirmDelete: string | null;
  onRoleChange: (userId: string, role: string) => void;
  onStatusToggle: (userId: string, activate: boolean) => void;
  onDelete: (userId: string) => void;
  onConfirmDelete: (userId: string | null) => void;
  onResendVerification: (userId: string) => void;
}) {
  const isLoading = actionLoading === user.id;
  const isDeleted = !!user.deleted_at;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Verification */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
          Verification
        </h4>
        {user.is_verified ? (
          <p className="text-xs text-green-400">Email verified</p>
        ) : isDeleted ? (
          <p className="text-xs text-text-muted">User is deleted</p>
        ) : (
          <button
            disabled={isLoading}
            onClick={() => onResendVerification(user.id)}
            className="px-3 py-1 rounded text-xs font-medium bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 disabled:opacity-40"
          >
            Resend Verification
          </button>
        )}
      </div>

      {/* Role management */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
          Role
        </h4>
        {detail.is_merchant ? (
          <p className="text-xs text-yellow-400">
            Merchant account — role cannot be changed
          </p>
        ) : isDeleted ? (
          <p className="text-xs text-text-muted">User is deleted</p>
        ) : (
          <div className="flex items-center gap-2">
            <select
              defaultValue={user.role}
              disabled={isLoading}
              onChange={(e) => {
                if (e.target.value !== user.role) {
                  onRoleChange(user.id, e.target.value);
                }
              }}
              className="input-glass text-xs !py-1 !px-2 !w-auto"
            >
              {AVAILABLE_ROLES.filter((r) => r !== "merchant").map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
            {isLoading && (
              <span className="text-xs text-text-muted">Saving...</span>
            )}
          </div>
        )}
      </div>

      {/* Status toggle */}
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-text-muted uppercase tracking-wide">
          Status
        </h4>
        {isDeleted ? (
          <p className="text-xs text-text-muted">User is deleted</p>
        ) : (
          <button
            disabled={isLoading}
            onClick={() => onStatusToggle(user.id, !user.is_active)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              user.is_active
                ? "bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30"
                : "bg-green-500/20 text-green-300 hover:bg-green-500/30"
            } disabled:opacity-40`}
          >
            {user.is_active ? "Deactivate" : "Activate"}
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
        ) : confirmDelete === user.id ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-red-400">Confirm?</span>
            <button
              disabled={isLoading}
              onClick={() => onDelete(user.id)}
              className="px-3 py-1 rounded text-xs font-medium bg-red-500/20 text-red-300 hover:bg-red-500/30 disabled:opacity-40"
            >
              Yes, delete
            </button>
            <button
              onClick={() => onConfirmDelete(null)}
              className="px-3 py-1 rounded text-xs font-medium bg-base-100 text-text-secondary hover:bg-base-100/80"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            disabled={isLoading}
            onClick={() => onConfirmDelete(user.id)}
            className="px-3 py-1 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 disabled:opacity-40"
          >
            Delete user
          </button>
        )}
      </div>
    </div>
  );
}
