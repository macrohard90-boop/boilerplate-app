"use client";

import { useState } from "react";

export interface ProductFormData {
  name: string;
  description: string;
  sku: string;
  base_price: number; // cents
  currency: string;
  status: string;
  pricing_type: string;
  recurring_interval: string | null;
  recurring_interval_count: number;
  trial_period_days: number | null;
  category_ids: string[];
}

export interface CategoryOption {
  id: string;
  name: string;
  parent_id: string | null;
  children?: CategoryOption[];
}

interface ProductFormProps {
  initial?: Partial<ProductFormData> | null;
  onSubmit: (data: ProductFormData) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  submitLabel?: string;
  allowRecurring?: boolean;
  categories?: CategoryOption[];
  initialCategoryIds?: string[];
}

export default function ProductForm({
  initial,
  onSubmit,
  onCancel,
  loading,
  submitLabel = "Save",
  allowRecurring = true,
  categories = [],
  initialCategoryIds = [],
}: ProductFormProps) {
  const [name, setName] = useState(initial?.name || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [sku, setSku] = useState(initial?.sku || "");
  const [priceDisplay, setPriceDisplay] = useState(
    initial?.base_price != null ? (initial.base_price / 100).toFixed(2) : "",
  );
  const [currency, setCurrency] = useState(initial?.currency || "USD");
  const [status, setStatus] = useState(initial?.status || "draft");
  const [pricingType, setPricingType] = useState(
    initial?.pricing_type || "one_time",
  );
  const [recurringInterval, setRecurringInterval] = useState(
    initial?.recurring_interval || "month",
  );
  const [recurringIntervalCount, setRecurringIntervalCount] = useState(
    initial?.recurring_interval_count ?? 1,
  );
  const [trialDays, setTrialDays] = useState(
    initial?.trial_period_days != null ? String(initial.trial_period_days) : "",
  );
  const [selectedCategoryIds, setSelectedCategoryIds] =
    useState<string[]>(initialCategoryIds);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const toggleCategory = (id: string, parentId?: string | null) => {
    setSelectedCategoryIds((prev) => {
      if (prev.includes(id)) {
        // Deselecting: remove this id. If it's a parent, also remove its children.
        const childIds =
          categories.find((c) => c.id === id)?.children?.map((ch) => ch.id) ||
          [];
        return prev.filter((c) => c !== id && !childIds.includes(c));
      } else {
        // Selecting: add this id. If it's a child, also select the parent.
        const next = [...prev, id];
        if (parentId && !next.includes(parentId)) {
          next.push(parentId);
        }
        return next;
      }
    });
  };

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
      pricing_type: pricingType,
      recurring_interval:
        pricingType === "recurring" ? recurringInterval : null,
      recurring_interval_count:
        pricingType === "recurring" ? recurringIntervalCount : 1,
      trial_period_days:
        pricingType === "recurring" && trialDays
          ? parseInt(trialDays, 10)
          : null,
      category_ids: selectedCategoryIds,
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
        {errors.name && (
          <p className="text-accent-pink text-xs mt-1">{errors.name}</p>
        )}
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm text-text-muted mb-1">
          Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="input-glass w-full h-24 resize-none"
          placeholder="Product description"
          disabled={loading}
        />
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div>
          <label className="block text-sm text-text-muted mb-2">
            Categories
          </label>
          <div className="space-y-3">
            {categories.map((cat) => (
              <div key={cat.id}>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    disabled={loading}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                      selectedCategoryIds.includes(cat.id)
                        ? "bg-accent-purple/20 text-accent-purple border border-accent-purple/30"
                        : "text-text-muted hover:text-text-primary border border-glass-border hover:border-text-muted"
                    }`}
                  >
                    {cat.name}
                  </button>
                  {cat.children?.map((child) => (
                    <button
                      key={child.id}
                      type="button"
                      onClick={() => toggleCategory(child.id, cat.id)}
                      disabled={loading}
                      className={`px-3 py-1.5 rounded-full text-xs transition-colors ${
                        selectedCategoryIds.includes(child.id)
                          ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
                          : "text-text-muted hover:text-text-primary border border-glass-border/50 hover:border-text-muted"
                      }`}
                    >
                      {child.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
          {errors.base_price && (
            <p className="text-accent-pink text-xs mt-1">{errors.base_price}</p>
          )}
        </div>
      </div>

      {/* Pricing Type + Currency row */}
      <div className="grid grid-cols-2 gap-4">
        {allowRecurring && (
          <div>
            <label className="block text-sm text-text-muted mb-1">
              Pricing
            </label>
            <select
              value={pricingType}
              onChange={(e) => setPricingType(e.target.value)}
              className="input-glass w-full"
              disabled={loading}
            >
              <option value="one_time">One-time</option>
              <option value="recurring">Recurring</option>
            </select>
          </div>
        )}
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
      </div>

      {/* Recurring options */}
      {pricingType === "recurring" && (
        <div className="glass rounded-lg p-4 space-y-3">
          <p className="text-xs text-accent-blue font-medium">
            Recurring Billing
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-text-muted mb-1">
                Interval
              </label>
              <select
                value={recurringInterval}
                onChange={(e) => setRecurringInterval(e.target.value)}
                className="input-glass w-full"
                disabled={loading}
              >
                <option value="month">Monthly</option>
                <option value="year">Yearly</option>
                <option value="week">Weekly</option>
                <option value="day">Daily</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1">
                Every X intervals
              </label>
              <input
                type="number"
                min="1"
                max="365"
                value={recurringIntervalCount}
                onChange={(e) =>
                  setRecurringIntervalCount(parseInt(e.target.value, 10) || 1)
                }
                className="input-glass w-full"
                disabled={loading}
              />
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1">
                Trial days
              </label>
              <input
                type="number"
                min="0"
                value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)}
                className="input-glass w-full"
                placeholder="0"
                disabled={loading}
              />
            </div>
          </div>
        </div>
      )}

      {/* Status */}
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
          {initial?.status && <option value="archived">Archived</option>}
        </select>
      </div>

      {status === "active" && !initial?.status && (
        <p className="text-xs text-accent-blue bg-accent-blue/10 rounded-lg px-3 py-2">
          Setting status to &quot;Active&quot; will sync this product to your
          payment provider (Stripe).
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
