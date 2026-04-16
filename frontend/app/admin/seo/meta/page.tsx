"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useToast } from "../../../../components/Toast";
import Modal from "../../../../components/Modal";
import Pagination from "../../../../components/Pagination";
import SerpPreview from "../../../../components/SerpPreview";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface MetaOverride {
  id: string;
  path: string;
  title: string | null;
  description: string | null;
  robots_index: boolean;
  robots_follow: boolean;
  canonical_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface MetaListResponse {
  items: MetaOverride[];
  total: number;
  page: number;
  page_size: number;
}

const EMPTY_FORM = {
  path: "",
  title: "",
  description: "",
  robots_index: true,
  robots_follow: true,
  canonical_url: "",
};

export default function SeoMetaEditorPage() {
  const { showToast } = useToast();
  const [data, setData] = useState<MetaListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [editingPath, setEditingPath] = useState<string | null>(null);

  async function fetchData(pg: number = page) {
    try {
      const res = await apiFetch<MetaListResponse>(
        `/seo/admin/seo/meta?page=${pg}&page_size=20`
      );
      setData(res);
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingPath(null);
    setModalOpen(true);
  }

  function openEdit(override: MetaOverride) {
    setForm({
      path: override.path,
      title: override.title || "",
      description: override.description || "",
      robots_index: override.robots_index,
      robots_follow: override.robots_follow,
      canonical_url: override.canonical_url || "",
    });
    setEditingPath(override.path);
    setModalOpen(true);
  }

  async function handleSave() {
    const path = editingPath || form.path;
    if (!path) {
      showToast("Path is required", "error");
      return;
    }
    setSaving(true);
    try {
      await apiFetch(`/seo/admin/seo/meta/${path}`, {
        method: "PUT",
        body: JSON.stringify({
          title: form.title || null,
          description: form.description || null,
          robots_index: form.robots_index,
          robots_follow: form.robots_follow,
          canonical_url: form.canonical_url || null,
        }),
      });
      showToast("Override saved", "success");
      setModalOpen(false);
      fetchData();
    } catch (e) {
      showToast((e as ApiError).message || "Save failed", "error");
    }
    setSaving(false);
  }

  async function handleDelete(path: string) {
    try {
      await apiFetch(`/seo/admin/seo/meta/${path}`, { method: "DELETE" });
      showToast("Override removed", "success");
      fetchData();
    } catch {
      showToast("Failed to remove", "error");
    }
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  const totalPages = data ? Math.ceil(data.total / 20) : 1;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Meta Tag Overrides</span>
        </h1>
        <button onClick={openCreate} className="btn-primary text-sm">
          + Add Override
        </button>
      </div>

      <p className="text-sm text-text-secondary mb-6">
        Your pages already have auto-generated SEO metadata from product and category
        data. Add custom overrides here to fine-tune the title, description, and other
        SEO fields for specific pages.
      </p>

      {/* Table */}
      <div className="glass rounded-xl overflow-hidden">
        {!data || data.items.length === 0 ? (
          <p className="p-6 text-sm text-text-muted">
            No custom overrides yet. Your pages use auto-generated SEO metadata from
            their product and category data. Add an override to optimize a specific
            page&apos;s search appearance.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Path
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Title
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Description
                  </th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((o) => (
                  <tr
                    key={o.id}
                    className="border-b border-glass-border/50 hover:bg-glass-hover"
                  >
                    <td className="py-3 px-4 font-mono text-accent-blue text-xs">
                      /{o.path}
                    </td>
                    <td className="py-3 px-4 text-text-primary max-w-[200px] truncate">
                      {o.title || "—"}
                    </td>
                    <td className="py-3 px-4 text-text-secondary max-w-[300px] truncate">
                      {o.description || "—"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => openEdit(o)}
                        className="text-accent-blue hover:text-accent-purple text-xs mr-3 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(o.path)}
                        className="text-text-muted hover:text-accent-pink text-xs transition-colors"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {totalPages > 1 && (
        <div className="mt-6">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </div>
      )}

      {/* Create/Edit Modal */}
      {modalOpen && (
        <Modal
          isOpen={modalOpen}
          title={editingPath ? "Edit Meta Override" : "Add Meta Override"}
          onClose={() => setModalOpen(false)}
        >
          <div className="space-y-4">
            {/* Path */}
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Page Path
              </label>
              <input
                type="text"
                value={form.path}
                onChange={(e) => setForm({ ...form, path: e.target.value })}
                disabled={!!editingPath}
                placeholder="products/my-product"
                className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary disabled:opacity-50"
              />
            </div>

            {/* Title */}
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Title{" "}
                <span
                  className={`text-xs ${
                    form.title.length > 60
                      ? "text-red-400"
                      : form.title.length >= 30
                        ? "text-green-400"
                        : "text-text-muted"
                  }`}
                >
                  ({form.title.length}/60)
                </span>
              </label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                maxLength={60}
                placeholder="Page title for search engines"
                className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Description{" "}
                <span
                  className={`text-xs ${
                    form.description.length > 160
                      ? "text-red-400"
                      : form.description.length >= 120
                        ? "text-green-400"
                        : "text-text-muted"
                  }`}
                >
                  ({form.description.length}/160)
                </span>
              </label>
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                maxLength={160}
                rows={3}
                placeholder="Page description for search engines"
                className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary resize-none"
              />
            </div>

            {/* Robots */}
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={form.robots_index}
                  onChange={(e) =>
                    setForm({ ...form, robots_index: e.target.checked })
                  }
                  className="rounded"
                />
                Index
              </label>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={form.robots_follow}
                  onChange={(e) =>
                    setForm({ ...form, robots_follow: e.target.checked })
                  }
                  className="rounded"
                />
                Follow
              </label>
            </div>

            {/* Canonical */}
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Canonical URL (optional)
              </label>
              <input
                type="text"
                value={form.canonical_url}
                onChange={(e) =>
                  setForm({ ...form, canonical_url: e.target.value })
                }
                placeholder="https://example.com/page"
                className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
              />
            </div>

            {/* SERP Preview */}
            {(form.title || form.description) && (
              <SerpPreview
                title={form.title}
                url={`https://example.com/${form.path || editingPath || ""}`}
                description={form.description}
              />
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setModalOpen(false)}
                className="btn-secondary text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Override"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
