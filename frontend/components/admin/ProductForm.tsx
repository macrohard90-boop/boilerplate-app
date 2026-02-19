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
  pricing_type: string;
  recurring_interval: string | null;
  recurring_interval_count: number;
  trial_period_days: number | null;
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
  const [pricingType, setPricingType] = useState(initial?.pricing_type || "one_time");
  const [recurringInterval, setRecurringInterval] = useState(initial?.recurring_interval || "month");
  const [recurringIntervalCount, setRecurringIntervalCount] = useState(
    initial?.recurring_interval_count ?? 1
  );
  const [trialDays, setTrialDays] = useState(
    initial?.trial_period_days != null ? String(initial.trial_period_days) : ""
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Name is required";
    const cents = Math.round(parseFloat(priceDisplay) * 100);
    if (isNaN(cents) || cents < 0) errs.base_price = "Valid price required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handlePricingTypeChange = (value: string) => {
    setPricingType(value);
    if (value === "recurring") {
      setType("subscription");
    } else if (type === "subscription") {
      setType("physical");
    }
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
      type: pricingType === "recurring" ? "subscription" : type,
      pricing_type: pricingType,
      recurring_interval: pricingType === "recurring" ? recurringInterval : null,
      recurring_interval_count: pricingType === "recurring" ? recurringIntervalCount : 1,
      trial_period_days: pricingType === "recurring" && trialDays ? parseInt(trialDays, 10) : null,
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

      {/* Pricing Type + Currency row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Pricing</label>
          <select
            value={pricingType}
            onChange={(e) => handlePricingTypeChange(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="one_time">One-time</option>
            <option value="recurring">Recurring</option>
          </select>
        </div>
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
          <p className="text-xs text-accent-blue font-medium">Recurring Billing</p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-text-muted mb-1">Interval</label>
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
              <label className="block text-sm text-text-muted mb-1">Every X intervals</label>
              <input
                type="number"
                min="1"
                max="365"
                value={recurringIntervalCount}
                onChange={(e) => setRecurringIntervalCount(parseInt(e.target.value, 10) || 1)}
                className="input-glass w-full"
                disabled={loading}
              />
            </div>
            <div>
              <label className="block text-sm text-text-muted mb-1">Trial days</label>
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

      {/* Type + Status row */}
      <div className="grid grid-cols-2 gap-4">
        {pricingType !== "recurring" && (
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
        )}
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
