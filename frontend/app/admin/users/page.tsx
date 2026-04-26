"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
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
                  <tr
                    key={u.id}
                    className="border-b border-glass-border/50 hover:bg-base-100/50 transition-colors"
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
                        <Link
                          href={`/admin/users/${u.id}`}
                          className="text-xs text-accent hover:text-accent/80"
                        >
                          Details
                        </Link>
                      )}
                    </td>
                  </tr>
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
