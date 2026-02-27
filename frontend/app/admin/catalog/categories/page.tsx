"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../../lib/api";
import { formatDate } from "../../../../lib/format";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import { useToast } from "../../../../components/Toast";
import CategoryForm, { type CategoryFormData } from "../../../../components/admin/CategoryForm";

interface Category {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  description: string | null;
  sort_order: number;
  product_count: number;
  created_at: string;
  children: Category[];
}

/** Flatten tree into display rows with depth info */
function flattenTree(tree: Category[], depth = 0): (Category & { depth: number })[] {
  const rows: (Category & { depth: number })[] = [];
  for (const cat of tree) {
    rows.push({ ...cat, depth });
    if (cat.children?.length) {
      rows.push(...flattenTree(cat.children, depth + 1));
    }
  }
  return rows;
}

/** Flatten tree into a flat list (for parent picker) */
function flattenForPicker(tree: Category[]): { id: string; name: string; parent_id: string | null }[] {
  const result: { id: string; name: string; parent_id: string | null }[] = [];
  for (const cat of tree) {
    result.push({ id: cat.id, name: cat.name, parent_id: cat.parent_id });
    if (cat.children?.length) {
      result.push(...flattenForPicker(cat.children));
    }
  }
  return result;
}

export default function AdminCategoriesPage() {
  const { showToast } = useToast();
  const [tree, setTree] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<Category | null>(null);
  const [editing, setEditing] = useState(false);
  const [deleteItem, setDeleteItem] = useState<Category | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchCategories = useCallback(() => {
    setLoading(true);
    apiFetch<Category[]>("/ecommerce/categories")
      .then(setTree)
      .catch(() => showToast("Failed to load categories", "error"))
      .finally(() => setLoading(false));
  }, [showToast]);

  useEffect(() => { fetchCategories(); }, [fetchCategories]);

  const flatCategories = flattenForPicker(tree);
  const displayRows = flattenTree(tree);

  const handleCreate = async (formData: CategoryFormData) => {
    setCreating(true);
    try {
      await apiFetch("/ecommerce/categories", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      showToast("Category created", "success");
      setShowCreate(false);
      fetchCategories();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Failed to create category";
      showToast(msg, "error");
    }
    setCreating(false);
  };

  const handleEdit = async (formData: CategoryFormData) => {
    if (!editItem) return;
    setEditing(true);
    try {
      await apiFetch(`/ecommerce/categories/${editItem.id}`, {
        method: "PUT",
        body: JSON.stringify(formData),
      });
      showToast("Category updated", "success");
      setEditItem(null);
      fetchCategories();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Failed to update category";
      showToast(msg, "error");
    }
    setEditing(false);
  };

  const handleDelete = async () => {
    if (!deleteItem) return;
    setDeleting(true);
    try {
      await apiFetch(`/ecommerce/categories/${deleteItem.id}`, {
        method: "DELETE",
      });
      showToast("Category deleted", "success");
      setDeleteItem(null);
      fetchCategories();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Failed to delete category";
      showToast(msg, "error");
    }
    setDeleting(false);
  };

  const canDelete = deleteItem
    ? deleteItem.product_count === 0 && (!deleteItem.children || deleteItem.children.length === 0)
    : false;

  if (loading && tree.length === 0) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-text-muted text-xs">
            {displayRows.length} categor{displayRows.length === 1 ? "y" : "ies"}
          </span>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Create Category
        </button>
      </div>

      {displayRows.length === 0 ? (
        <div className="text-text-secondary glass rounded-xl p-12 text-center">
          <p className="text-lg mb-2">No categories yet</p>
          <p className="text-sm text-text-muted mb-4">Create your first category to organize products.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="btn-primary px-4 py-2 rounded-lg text-sm"
          >
            + Create Category
          </button>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-4 text-text-muted font-medium">Name</th>
                <th className="text-left p-4 text-text-muted font-medium">Slug</th>
                <th className="text-left p-4 text-text-muted font-medium">Products</th>
                <th className="text-left p-4 text-text-muted font-medium">Order</th>
                <th className="text-left p-4 text-text-muted font-medium">Created</th>
                <th className="text-right p-4 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((cat) => (
                <tr key={cat.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                  <td className="p-4 text-text-primary font-medium">
                    <span style={{ paddingLeft: `${cat.depth * 24}px` }} className="flex items-center gap-2">
                      {cat.depth > 0 && (
                        <span className="text-text-muted text-xs">└</span>
                      )}
                      {cat.name}
                    </span>
                  </td>
                  <td className="p-4 text-text-muted font-mono text-xs">{cat.slug}</td>
                  <td className="p-4 text-text-secondary">{cat.product_count}</td>
                  <td className="p-4 text-text-muted">{cat.sort_order}</td>
                  <td className="p-4 text-text-muted">{formatDate(cat.created_at)}</td>
                  <td className="p-4 text-right whitespace-nowrap">
                    <button
                      onClick={() => setEditItem(cat)}
                      className="text-xs text-accent-blue hover:text-accent-blue/80 mr-3"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteItem(cat)}
                      className="text-xs text-accent-pink hover:text-accent-pink/80"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Category Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Category" size="md">
        <CategoryForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
          loading={creating}
          submitLabel="Create"
          categories={flatCategories}
        />
      </Modal>

      {/* Edit Category Modal */}
      <Modal isOpen={!!editItem} onClose={() => setEditItem(null)} title="Edit Category" size="md">
        {editItem && (
          <CategoryForm
            initial={{
              name: editItem.name,
              parent_id: editItem.parent_id,
              description: editItem.description || "",
              sort_order: editItem.sort_order,
            }}
            onSubmit={handleEdit}
            onCancel={() => setEditItem(null)}
            loading={editing}
            submitLabel="Update"
            categories={flatCategories}
            editingId={editItem.id}
          />
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={!!deleteItem} onClose={() => setDeleteItem(null)} title="Delete Category" size="sm">
        {deleteItem && (
          <>
            {!canDelete ? (
              <div className="space-y-3 mb-4">
                {deleteItem.product_count > 0 && (
                  <p className="text-accent-pink text-sm bg-accent-pink/10 rounded-lg px-3 py-2">
                    This category has {deleteItem.product_count} assigned product{deleteItem.product_count !== 1 ? "s" : ""}. Unassign them first.
                  </p>
                )}
                {deleteItem.children?.length > 0 && (
                  <p className="text-accent-pink text-sm bg-accent-pink/10 rounded-lg px-3 py-2">
                    This category has {deleteItem.children.length} subcategor{deleteItem.children.length !== 1 ? "ies" : "y"}. Delete or reparent them first.
                  </p>
                )}
              </div>
            ) : (
              <p className="text-text-secondary text-sm mb-4">
                Are you sure you want to delete &quot;{deleteItem.name}&quot;? This action cannot be undone.
              </p>
            )}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteItem(null)}
                className="btn-secondary px-4 py-2 rounded-lg text-sm"
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors disabled:opacity-50"
                disabled={deleting || !canDelete}
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
