"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch } from "../../lib/api";

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
  product_ids: string[];
  restricted_to_customer_id: string | null;
  first_time_transaction_only: boolean;
  max_uses_per_customer: number | null;
}

interface ProductOption {
  id: string;
  name: string;
}

interface UserOption {
  id: string;
  email: string;
  full_name: string | null;
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

  // --- New restriction fields ---
  const [restrictProducts, setRestrictProducts] = useState(
    (initial?.product_ids?.length ?? 0) > 0
  );
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>(
    initial?.product_ids || []
  );
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);

  const [restrictCustomer, setRestrictCustomer] = useState(
    !!initial?.restricted_to_customer_id
  );
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerResults, setCustomerResults] = useState<UserOption[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<UserOption | null>(null);
  const [customerSearchLoading, setCustomerSearchLoading] = useState(false);
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const customerRef = useRef<HTMLDivElement>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [firstTimeOnly, setFirstTimeOnly] = useState(
    initial?.first_time_transaction_only || false
  );
  const [maxUsesPerCustomer, setMaxUsesPerCustomer] = useState(
    initial?.max_uses_per_customer != null ? String(initial.max_uses_per_customer) : ""
  );

  // Load products when restriction is toggled on
  useEffect(() => {
    if (restrictProducts && products.length === 0) {
      setProductsLoading(true);
      apiFetch<{ items: ProductOption[] }>("/ecommerce/products?status=active&page_size=100")
        .then((data) => setProducts(data.items || []))
        .catch(() => {})
        .finally(() => setProductsLoading(false));
    }
  }, [restrictProducts, products.length]);

  // Load initial customer if editing (only on mount)
  const initialCustomerLoaded = useRef(false);
  useEffect(() => {
    if (initial?.restricted_to_customer_id && !initialCustomerLoaded.current) {
      initialCustomerLoaded.current = true;
      apiFetch<{ id: string; email: string; first_name: string | null; last_name: string | null }>(`/auth/admin/users/${initial.restricted_to_customer_id}`)
        .then((u) => setSelectedCustomer({ id: u.id, email: u.email, full_name: [u.first_name, u.last_name].filter(Boolean).join(" ") || null }))
        .catch(() => {});
    }
  }, [initial?.restricted_to_customer_id]);

  // Customer search debounce
  useEffect(() => {
    if (!restrictCustomer || customerSearch.length < 2) {
      setCustomerResults([]);
      return;
    }
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      setCustomerSearchLoading(true);
      try {
        const data = await apiFetch<{ items: { id: string; email: string; first_name: string | null; last_name: string | null }[] }>(
          `/auth/admin/users?search=${encodeURIComponent(customerSearch)}&page_size=5`
        );
        setCustomerResults((data.items || []).map((u) => ({
          id: u.id,
          email: u.email,
          full_name: [u.first_name, u.last_name].filter(Boolean).join(" ") || null,
        })));
        setShowCustomerDropdown(true);
      } catch {
        setCustomerResults([]);
      }
      setCustomerSearchLoading(false);
    }, 300);
    return () => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current);
    };
  }, [customerSearch, restrictCustomer]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (customerRef.current && !customerRef.current.contains(e.target as Node)) {
        setShowCustomerDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

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
      product_ids: restrictProducts ? selectedProductIds : [],
      restricted_to_customer_id: restrictCustomer && selectedCustomer ? selectedCustomer.id : null,
      first_time_transaction_only: firstTimeOnly,
      max_uses_per_customer: maxUsesPerCustomer ? parseInt(maxUsesPerCustomer, 10) : null,
    });
  };

  const toggleProduct = (pid: string) => {
    setSelectedProductIds((prev) =>
      prev.includes(pid) ? prev.filter((p) => p !== pid) : [...prev, pid]
    );
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
      <div className={`grid gap-4 ${type === "fixed" ? "grid-cols-2" : ""}`}>
        {type === "fixed" && (
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
        )}
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

      {/* Max Uses row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Max Uses (total)</label>
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
        <div>
          <label className="block text-sm text-text-muted mb-1">Max Uses Per Customer</label>
          <input
            type="number"
            min="1"
            value={maxUsesPerCustomer}
            onChange={(e) => setMaxUsesPerCustomer(e.target.value)}
            className="input-glass w-full"
            placeholder="Unlimited"
            disabled={loading}
          />
        </div>
      </div>

      {/* Applies To + Stripe Duration */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-text-muted mb-1">Applies To</label>
          <select
            value={appliesTo}
            onChange={(e) => {
              setAppliesTo(e.target.value);
              if (e.target.value === "one_time") {
                setStripeDuration("once");
                setDurationInMonths("");
              }
            }}
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
            <label className="block text-sm text-text-muted mb-1">Subscription Duration</label>
            <select
              value={stripeDuration}
              onChange={(e) => setStripeDuration(e.target.value)}
              className="input-glass w-full"
              disabled={loading}
            >
              <option value="once">First invoice only</option>
              <option value="repeating">Multiple months</option>
              <option value="forever">Every invoice forever</option>
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

      {/* --- Restrictions Section --- */}
      <div className="border-t border-glass-border pt-4 mt-4">
        <p className="text-sm font-medium text-text-primary mb-3">Restrictions</p>

        {/* First-time only */}
        <label className="flex items-center gap-2 mb-3 cursor-pointer">
          <input
            type="checkbox"
            checked={firstTimeOnly}
            onChange={(e) => setFirstTimeOnly(e.target.checked)}
            className="accent-accent-blue"
            disabled={loading}
          />
          <span className="text-sm text-text-secondary">First-time purchases only</span>
        </label>

        {/* Product restriction */}
        <label className="flex items-center gap-2 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={restrictProducts}
            onChange={(e) => {
              setRestrictProducts(e.target.checked);
              if (!e.target.checked) setSelectedProductIds([]);
            }}
            className="accent-accent-blue"
            disabled={loading}
          />
          <span className="text-sm text-text-secondary">Restrict to specific products</span>
        </label>
        {restrictProducts && (
          <div className="ml-6 mb-3">
            {productsLoading ? (
              <p className="text-xs text-text-muted">Loading products...</p>
            ) : (
              <div className="max-h-40 overflow-y-auto border border-glass-border rounded-lg p-2 space-y-1">
                {products.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedProductIds.includes(p.id)}
                      onChange={() => toggleProduct(p.id)}
                      className="accent-accent-blue"
                      disabled={loading}
                    />
                    <span className="text-text-secondary">{p.name}</span>
                  </label>
                ))}
                {products.length === 0 && (
                  <p className="text-xs text-text-muted">No active products found</p>
                )}
              </div>
            )}
            {selectedProductIds.length > 0 && (
              <p className="text-xs text-text-muted mt-1">
                {selectedProductIds.length} product{selectedProductIds.length !== 1 ? "s" : ""} selected
              </p>
            )}
          </div>
        )}

        {/* Customer restriction */}
        <label className="flex items-center gap-2 mb-2 cursor-pointer">
          <input
            type="checkbox"
            checked={restrictCustomer}
            onChange={(e) => {
              setRestrictCustomer(e.target.checked);
              setSelectedCustomer(null);
              setCustomerSearch("");
            }}
            className="accent-accent-blue"
            disabled={loading}
          />
          <span className="text-sm text-text-secondary">Restrict to specific customer</span>
        </label>
        {restrictCustomer && (
          <div className="ml-6 mb-3 relative" ref={customerRef}>
            {selectedCustomer ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-text-primary">{selectedCustomer.email}</span>
                {selectedCustomer.full_name && (
                  <span className="text-text-muted">({selectedCustomer.full_name})</span>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setSelectedCustomer(null);
                    setCustomerSearch("");
                  }}
                  className="text-accent-pink text-xs hover:text-accent-pink/80"
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <input
                  type="text"
                  value={customerSearch}
                  onChange={(e) => setCustomerSearch(e.target.value)}
                  className="input-glass w-full text-sm"
                  placeholder="Search by email or name..."
                  disabled={loading}
                />
                {customerSearchLoading && (
                  <p className="text-xs text-text-muted mt-1">Searching...</p>
                )}
                {showCustomerDropdown && customerResults.length > 0 && (
                  <div className="absolute z-10 top-full mt-1 w-full bg-bg-secondary border border-glass-border rounded-lg shadow-lg max-h-40 overflow-y-auto">
                    {customerResults.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => {
                          setSelectedCustomer(u);
                          setCustomerSearch("");
                          setShowCustomerDropdown(false);
                        }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-glass-hover transition-colors"
                      >
                        <span className="text-text-primary">{u.email}</span>
                        {u.full_name && (
                          <span className="text-text-muted ml-2">({u.full_name})</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
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
