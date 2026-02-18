"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../../lib/api";
import { formatPrice, formatDate } from "../../../lib/format";
import Pagination from "../../../components/Pagination";
import LoadingSpinner from "../../../components/LoadingSpinner";
import Modal from "../../../components/Modal";
import { useToast } from "../../../components/Toast";
import ProductForm, { type ProductFormData } from "../../../components/admin/ProductForm";
import SyncStatusBadge from "../../../components/admin/SyncStatusBadge";

interface Product {
  id: string;
  name: string;
  slug: string;
  sku: string | null;
  base_price: number;
  currency: string;
  status: string;
  type: string;
  stripe_product_id: string | null;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
  synced_provider: string | null;
  created_at: string;
}

interface ProductResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function AdminProductsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [data, setData] = useState<ProductResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const fetchProducts = useCallback(() => {
    setLoading(true);
    apiFetch<ProductResponse>(`/ecommerce/products?page=${page}&page_size=20`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const handleCreate = async (formData: ProductFormData) => {
    setCreating(true);
    try {
      await apiFetch("/ecommerce/products", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      showToast("Product created", "success");
      setShowCreate(false);
      fetchProducts();
    } catch {
      showToast("Failed to create product", "error");
    }
    setCreating(false);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await apiFetch(`/ecommerce/products/${deleteId}`, { method: "DELETE" });
      showToast("Product deleted", "success");
      setDeleteId(null);
      fetchProducts();
    } catch {
      showToast("Failed to delete product", "error");
    }
    setDeleting(false);
  };

  const handleRetrySync = async (productId: string) => {
    setSyncingId(productId);
    try {
      await apiFetch(`/ecommerce/products/${productId}/sync`, { method: "POST" });
      showToast("Sync successful", "success");
      fetchProducts();
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Products</span>
          {data && <span className="text-text-muted font-normal text-lg ml-2">({data.total})</span>}
        </h1>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Create Product
        </button>
      </div>

      {!data || data.items.length === 0 ? (
        <div className="text-text-secondary glass rounded-xl p-12 text-center">
          <p className="text-lg mb-2">No products yet</p>
          <p className="text-sm text-text-muted mb-4">Create your first product to get started.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="btn-primary px-4 py-2 rounded-lg text-sm"
          >
            + Create Product
          </button>
        </div>
      ) : (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left p-4 text-text-muted font-medium">Product</th>
                  <th className="text-left p-4 text-text-muted font-medium">SKU</th>
                  <th className="text-left p-4 text-text-muted font-medium">Price</th>
                  <th className="text-left p-4 text-text-muted font-medium">Status</th>
                  <th className="text-left p-4 text-text-muted font-medium">Sync</th>
                  <th className="text-left p-4 text-text-muted font-medium">Created</th>
                  <th className="text-right p-4 text-text-muted font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                    <td className="p-4 text-text-primary font-medium">{p.name}</td>
                    <td className="p-4 text-text-muted font-mono text-xs">{p.sku || "—"}</td>
                    <td className="p-4 text-text-primary">{formatPrice(p.base_price, p.currency)}</td>
                    <td className="p-4">
                      <span className={statusBadge(p.status)}>{p.status}</span>
                    </td>
                    <td className="p-4">
                      <SyncStatusBadge
                        status={p.stripe_sync_status}
                        error={p.stripe_sync_error}
                        provider={p.synced_provider}
                        onRetry={
                          p.stripe_sync_status === "error"
                            ? () => handleRetrySync(p.id)
                            : undefined
                        }
                      />
                      {syncingId === p.id && (
                        <span className="text-xs text-text-muted ml-1">Syncing...</span>
                      )}
                    </td>
                    <td className="p-4 text-text-muted">{formatDate(p.created_at)}</td>
                    <td className="p-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => router.push(`/admin/products/${p.id}`)}
                        className="text-xs text-accent-blue hover:text-accent-blue/80 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteId(p.id)}
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
          {data.total_pages > 1 && (
            <div className="mt-6">
              <Pagination currentPage={data.page} totalPages={data.total_pages} onPageChange={setPage} />
            </div>
          )}
        </>
      )}

      {/* Create Product Modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Product" size="lg">
        <ProductForm
          onSubmit={handleCreate}
          onCancel={() => setShowCreate(false)}
          loading={creating}
          submitLabel="Create"
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={!!deleteId} onClose={() => setDeleteId(null)} title="Delete Product" size="sm">
        <p className="text-text-secondary text-sm mb-4">
          Are you sure you want to delete this product? This action will archive it in Stripe if synced.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setDeleteId(null)}
            className="btn-secondary px-4 py-2 rounded-lg text-sm"
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors"
            disabled={deleting}
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
