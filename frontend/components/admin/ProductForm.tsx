"use client";

import { useState } from "react";

export interface ProductFormData {
  name: string;
  description: string;
  sku: string;
  base_price: number; // cents
  currency: string;
  status: string;
  type: string;
}

interface ProductFormProps {
  initial?: Partial<ProductFormData> | null;
  onSubmit: (data: ProductFormData) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  submitLabel?: string;
}

export default function ProductForm({
  initial,
  onSubmit,
  onCancel,
  loading,
  submitLabel = "Save",
}: ProductFormProps) {
  const [name, setName] = useState(initial?.name || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [sku, setSku] = useState(initial?.sku || "");
  const [priceDisplay, setPriceDisplay] = useState(
    initial?.base_price != null ? (initial.base_price / 100).toFixed(2) : ""
  );
  const [currency, setCurrency] = useState(initial?.currency || "USD");
  const [status, setStatus] = useState(initial?.status || "draft");
  const [type, setType] = useState(initial?.type || "physical");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Name is required";
    const cents = Math.round(parseFloat(priceDisplay) * 100);
    if (isNaN(cents) || cents < 0) errs.base_price = "Valid price required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    await onSubmit({
      name: name.trim(),
      description: description.trim(),
      sku: sku.trim(),
      base_price: Math.round(parseFloat(priceDisplay) * 100),
      currency,
      status,
      type,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Name */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Name *</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input-glass w-full"
          placeholder="Product name"
          disabled={loading}
        />
        {errors.name && <p className="text-accent-pink text-xs mt-1">{errors.name}</p>}
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="input-glass w-full h-24 resize-none"
          placeholder="Product description"
          disabled={loading}
        />
      </div>

      {/* SKU + Price row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">SKU</label>
          <input
            type="text"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            className="input-glass w-full"
            placeholder="SKU-001"
            disabled={loading}
          />
        </div>
        <div>
          <label className="block text-sm text-text-muted mb-1">Price *</label>
          <div className="flex items-center gap-2">
            <span className="text-text-muted">$</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={priceDisplay}
              onChange={(e) => setPriceDisplay(e.target.value)}
              className="input-glass w-full"
              placeholder="19.99"
              disabled={loading}
            />
          </div>
          {errors.base_price && <p className="text-accent-pink text-xs mt-1">{errors.base_price}</p>}
        </div>
      </div>

      {/* Currency + Type + Status row */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Currency</label>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="CAD">CAD</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-text-muted mb-1">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="physical">Physical</option>
            <option value="digital">Digital</option>
          </select>
        </div>
        <div>
          <label className="block text-sm text-text-muted mb-1">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>

      {status === "active" && !initial?.status && (
        <p className="text-xs text-accent-blue bg-accent-blue/10 rounded-lg px-3 py-2">
          Setting status to &quot;Active&quot; will sync this product to your payment provider (Stripe).
        </p>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="btn-secondary px-4 py-2 rounded-lg text-sm"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          type="submit"
          className="btn-primary px-4 py-2 rounded-lg text-sm"
          disabled={loading}
        >
          {loading ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
