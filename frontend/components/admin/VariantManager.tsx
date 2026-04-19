"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../lib/api";
import { formatPrice } from "../../lib/format";
import SyncStatusBadge from "./SyncStatusBadge";
import Modal from "../Modal";

interface Variant {
  id: string;
  product_id: string;
  name: string;
  sku: string | null;
  price_override: number | null;
  stock_quantity: number;
  effective_price: number;
  attributes: Record<string, string>;
  stripe_price_id: string | null;
  stripe_sync_status: string;
  created_at: string;
}

interface VariantManagerProps {
  productId: string;
  productBasePrice: number;
  currency: string;
  onVariantsChange?: (variants: { id: string; name: string }[]) => void;
  refreshKey?: number;
}

export default function VariantManager({
  productId,
  productBasePrice,
  currency,
  onVariantsChange,
  refreshKey,
}: VariantManagerProps) {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formSku, setFormSku] = useState("");
  const [formPriceOverride, setFormPriceOverride] = useState("");
  const [formStock, setFormStock] = useState("0");
  const [formSaving, setFormSaving] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchVariants = useCallback(async () => {
    try {
      const data = await apiFetch<Variant[]>(
        `/ecommerce/products/${productId}/variants`,
      );
      setVariants(data);
      onVariantsChange?.(data.map((v) => ({ id: v.id, name: v.name })));
    } catch {
      /* ignore */
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, onVariantsChange, refreshKey]);

  useEffect(() => {
    fetchVariants();
  }, [fetchVariants]);

  const resetForm = () => {
    setFormName("");
    setFormSku("");
    setFormPriceOverride("");
    setFormStock("0");
    setShowForm(false);
    setEditingId(null);
  };

  const startEdit = (v: Variant) => {
    setEditingId(v.id);
    setFormName(v.name);
    setFormSku(v.sku || "");
    setFormPriceOverride(
      v.price_override != null ? (v.price_override / 100).toFixed(2) : "",
    );
    setFormStock(String(v.stock_quantity));
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) return;
    setFormSaving(true);

    const body: Record<string, unknown> = {
      name: formName.trim(),
      sku: formSku.trim() || null,
      stock_quantity: parseInt(formStock) || 0,
    };

    if (formPriceOverride.trim()) {
      body.price_override = Math.round(parseFloat(formPriceOverride) * 100);
    } else {
      body.price_override = null;
    }

    try {
      if (editingId) {
        await apiFetch(
          `/ecommerce/products/${productId}/variants/${editingId}`,
          {
            method: "PUT",
            body: JSON.stringify(body),
          },
        );
      } else {
        await apiFetch(`/ecommerce/products/${productId}/variants`, {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchVariants();
    } catch {
      /* ignore */
    }
    setFormSaving(false);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setDeleteLoading(true);
    try {
      await apiFetch(`/ecommerce/products/${productId}/variants/${deleteId}`, {
        method: "DELETE",
      });
      setDeleteId(null);
      fetchVariants();
    } catch {
      /* ignore */
    }
    setDeleteLoading(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text-primary">Variants</h3>
        {!showForm && (
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="btn-primary px-3 py-1.5 rounded-lg text-sm"
          >
            + Add Variant
          </button>
        )}
      </div>

      {/* Inline form */}
      {showForm && (
        <div className="glass rounded-xl p-4 mb-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">
                Name *
              </label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="input-glass w-full text-sm"
                placeholder="e.g. Small / Red"
                disabled={formSaving}
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">SKU</label>
              <input
                type="text"
                value={formSku}
                onChange={(e) => setFormSku(e.target.value)}
                className="input-glass w-full text-sm"
                placeholder="SKU-001-S"
                disabled={formSaving}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">
                Price Override{" "}
                <span className="opacity-60">
                  (blank = base {formatPrice(productBasePrice, currency)})
                </span>
              </label>
              <div className="flex items-center gap-1">
                <span className="text-text-muted text-sm">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formPriceOverride}
                  onChange={(e) => setFormPriceOverride(e.target.value)}
                  className="input-glass w-full text-sm"
                  placeholder="Leave blank for base price"
                  disabled={formSaving}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">
                Stock Quantity
              </label>
              <input
                type="number"
                min="0"
                value={formStock}
                onChange={(e) => setFormStock(e.target.value)}
                className="input-glass w-full text-sm"
                disabled={formSaving}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={resetForm}
              className="btn-secondary px-3 py-1.5 rounded-lg text-sm"
              disabled={formSaving}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="btn-primary px-3 py-1.5 rounded-lg text-sm"
              disabled={formSaving || !formName.trim()}
            >
              {formSaving ? "Saving..." : editingId ? "Update" : "Add"}
            </button>
          </div>
        </div>
      )}

      {/* Info note for auto-created default variant */}
      {!loading && variants.length === 1 && variants[0].name === "Default" && (
        <p className="text-text-secondary text-sm glass rounded-xl p-4 mb-4">
          A default variant was created automatically. You can rename it, adjust
          stock, or add more variants (e.g., sizes, colors).
        </p>
      )}

      {/* Variants table */}
      {loading ? (
        <p className="text-text-muted text-sm">Loading variants...</p>
      ) : variants.length === 0 ? (
        <p className="text-text-secondary text-sm glass rounded-xl p-4 text-center">
          No variants yet. Add at least one variant with stock to make this
          product purchasable.
        </p>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">
                  Name
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  SKU
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Price
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Stock
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Sync
                </th>
                <th className="text-right p-3 text-text-muted font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {variants.map((v) => (
                <tr
                  key={v.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3 text-text-primary font-medium">
                    {v.name}
                  </td>
                  <td className="p-3 text-text-muted font-mono text-xs">
                    {v.sku || "—"}
                  </td>
                  <td className="p-3 text-text-primary">
                    {v.price_override != null ? (
                      formatPrice(v.price_override, currency)
                    ) : (
                      <span className="text-text-muted">
                        {formatPrice(productBasePrice, currency)} (base)
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    <span
                      className={
                        v.stock_quantity <= 0
                          ? "text-accent-pink"
                          : "text-text-primary"
                      }
                    >
                      {v.stock_quantity}
                    </span>
                  </td>
                  <td className="p-3">
                    <SyncStatusBadge status={v.stripe_sync_status} />
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => startEdit(v)}
                      className="text-xs text-accent-blue hover:text-accent-blue/80 mr-3"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteId(v.id)}
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

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Delete Variant"
        size="sm"
      >
        <p className="text-text-secondary text-sm mb-4">
          This will permanently delete this variant and any images assigned to
          it. This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setDeleteId(null)}
            className="btn-secondary px-4 py-2 rounded-lg text-sm"
            disabled={deleteLoading}
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            className="bg-accent-pink/20 text-accent-pink border border-accent-pink/30 px-4 py-2 rounded-lg text-sm hover:bg-accent-pink/30 transition-colors"
            disabled={deleteLoading}
          >
            {deleteLoading ? "Deleting..." : "Delete"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
