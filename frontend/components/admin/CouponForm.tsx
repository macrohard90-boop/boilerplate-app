"use client";

import { useState } from "react";

export interface CouponFormData {
  code: string;
  type: string;
  value: number; // percentage integer (0-100) or cents for fixed
  currency: string;
  min_order_amount: number; // cents
  max_uses: number | null;
  valid_from: string | null;
  valid_until: string | null;
  applies_to: string;
  stripe_duration: string;
  stripe_duration_in_months: number | null;
}

interface CouponFormProps {
  initial?: Partial<CouponFormData & { active: boolean; stripe_coupon_id?: string }> | null;
  onSubmit: (data: CouponFormData) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  submitLabel?: string;
}

export default function CouponForm({
  initial,
  onSubmit,
  onCancel,
  loading,
  submitLabel = "Save",
}: CouponFormProps) {
  const [code, setCode] = useState(initial?.code || "");
  const [type, setType] = useState(initial?.type || "percentage");
  const [valueDisplay, setValueDisplay] = useState(() => {
    if (initial?.value == null) return "";
    if (initial.type === "fixed") return (initial.value / 100).toFixed(2);
    return String(initial.value);
  });
  const [currency, setCurrency] = useState(initial?.currency || "USD");
  const [minOrderDisplay, setMinOrderDisplay] = useState(
    initial?.min_order_amount != null ? (initial.min_order_amount / 100).toFixed(2) : ""
  );
  const [maxUses, setMaxUses] = useState(
    initial?.max_uses != null ? String(initial.max_uses) : ""
  );
  const [validFrom, setValidFrom] = useState(
    initial?.valid_from ? initial.valid_from.slice(0, 16) : ""
  );
  const [validUntil, setValidUntil] = useState(
    initial?.valid_until ? initial.valid_until.slice(0, 16) : ""
  );
  const [appliesTo, setAppliesTo] = useState(initial?.applies_to || "all");
  const [stripeDuration, setStripeDuration] = useState(initial?.stripe_duration || "once");
  const [durationInMonths, setDurationInMonths] = useState(
    initial?.stripe_duration_in_months != null ? String(initial.stripe_duration_in_months) : ""
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!code.trim()) errs.code = "Code is required";
    const numValue = parseFloat(valueDisplay);
    if (type === "free_shipping") {
      // no value needed
    } else if (isNaN(numValue) || numValue < 0) {
      errs.value = "Valid value required";
    } else if (type === "percentage" && (numValue < 1 || numValue > 100)) {
      errs.value = "Percentage must be 1-100";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    let value = 0;
    if (type === "percentage") {
      value = Math.round(parseFloat(valueDisplay));
    } else if (type === "fixed") {
      value = Math.round(parseFloat(valueDisplay) * 100);
    }

    await onSubmit({
      code: code.trim().toUpperCase(),
      type,
      value,
      currency,
      min_order_amount: minOrderDisplay ? Math.round(parseFloat(minOrderDisplay) * 100) : 0,
      max_uses: maxUses ? parseInt(maxUses, 10) : null,
      valid_from: validFrom || null,
      valid_until: validUntil || null,
      applies_to: appliesTo,
      stripe_duration: stripeDuration,
      stripe_duration_in_months:
        stripeDuration === "repeating" && durationInMonths
          ? parseInt(durationInMonths, 10)
          : null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Code */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Coupon Code *</label>
        <input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          className="input-glass w-full font-mono"
          placeholder="SAVE10"
          disabled={loading}
        />
        {errors.code && <p className="text-accent-pink text-xs mt-1">{errors.code}</p>}
      </div>

      {/* Type + Value row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Type</label>
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setValueDisplay("");
            }}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="percentage">Percentage Off</option>
            <option value="fixed">Fixed Amount Off</option>
            <option value="free_shipping">Free Shipping</option>
          </select>
        </div>
        {type !== "free_shipping" && (
          <div>
            <label className="block text-sm text-text-muted mb-1">
              Value * {type === "percentage" ? "(%)" : "($)"}
            </label>
            <div className="flex items-center gap-2">
              {type === "fixed" && <span className="text-text-muted">$</span>}
              <input
                type="number"
                step={type === "percentage" ? "1" : "0.01"}
                min="0"
                max={type === "percentage" ? "100" : undefined}
                value={valueDisplay}
                onChange={(e) => setValueDisplay(e.target.value)}
                className="input-glass w-full"
                placeholder={type === "percentage" ? "10" : "5.00"}
                disabled={loading}
              />
              {type === "percentage" && <span className="text-text-muted">%</span>}
            </div>
            {errors.value && <p className="text-accent-pink text-xs mt-1">{errors.value}</p>}
          </div>
        )}
      </div>

      {/* Currency + Min Order */}
      <div className="grid grid-cols-2 gap-4">
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
          <label className="block text-sm text-text-muted mb-1">Min Order Amount</label>
          <div className="flex items-center gap-2">
            <span className="text-text-muted">$</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={minOrderDisplay}
              onChange={(e) => setMinOrderDisplay(e.target.value)}
              className="input-glass w-full"
              placeholder="0.00"
              disabled={loading}
            />
          </div>
        </div>
      </div>

      {/* Max Uses */}
      <div>
        <label className="block text-sm text-text-muted mb-1">Max Uses (leave empty for unlimited)</label>
        <input
          type="number"
          min="1"
          value={maxUses}
          onChange={(e) => setMaxUses(e.target.value)}
          className="input-glass w-full"
          placeholder="Unlimited"
          disabled={loading}
        />
      </div>

      {/* Applies To + Stripe Duration */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Applies To</label>
          <select
            value={appliesTo}
            onChange={(e) => setAppliesTo(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          >
            <option value="all">All Payments</option>
            <option value="one_time">One-time Only</option>
            <option value="recurring">Recurring Only</option>
          </select>
        </div>
        {appliesTo !== "one_time" && (
          <div>
            <label className="block text-sm text-text-muted mb-1">Stripe Duration</label>
            <select
              value={stripeDuration}
              onChange={(e) => setStripeDuration(e.target.value)}
              className="input-glass w-full"
              disabled={loading}
            >
              <option value="once">Once</option>
              <option value="repeating">Repeating</option>
              <option value="forever">Forever</option>
            </select>
          </div>
        )}
      </div>

      {stripeDuration === "repeating" && appliesTo !== "one_time" && (
        <div>
          <label className="block text-sm text-text-muted mb-1">Duration (months)</label>
          <input
            type="number"
            min="1"
            max="36"
            value={durationInMonths}
            onChange={(e) => setDurationInMonths(e.target.value)}
            className="input-glass w-full"
            placeholder="3"
            disabled={loading}
          />
          <p className="text-xs text-text-muted mt-1">
            Number of months the discount applies to recurring payments
          </p>
        </div>
      )}

      {/* Validity period */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Valid From</label>
          <input
            type="datetime-local"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          />
        </div>
        <div>
          <label className="block text-sm text-text-muted mb-1">Valid Until (optional)</label>
          <input
            type="datetime-local"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="input-glass w-full"
            disabled={loading}
          />
        </div>
      </div>

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
