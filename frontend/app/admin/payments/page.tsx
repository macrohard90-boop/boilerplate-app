"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";

interface MethodInfo {
  key: string;
  label: string;
  description: string;
}

const PAYMENT_METHODS: MethodInfo[] = [
  { key: "card", label: "Cards", description: "Credit and debit cards (Visa, Mastercard, Amex)" },
  { key: "link", label: "Link", description: "Stripe Link — one-click checkout with saved details" },
  { key: "apple_pay", label: "Apple Pay", description: "Pay with Apple Pay on supported devices" },
  { key: "google_pay", label: "Google Pay", description: "Pay with Google Pay on supported devices" },
  { key: "klarna", label: "Klarna", description: "Buy now, pay later in installments" },
  { key: "afterpay_clearpay", label: "Afterpay", description: "Buy now, pay in 4 interest-free installments" },
  { key: "paypal", label: "PayPal", description: "Pay with PayPal account" },
];

function defaultMethods(): Record<string, boolean> {
  const m: Record<string, boolean> = {};
  PAYMENT_METHODS.forEach((pm) => (m[pm.key] = true));
  return m;
}

export default function AdminPaymentsPage() {
  const [methods, setMethods] = useState<Record<string, boolean>>(defaultMethods);
  const [customized, setCustomized] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    apiFetch<{ methods: Record<string, boolean>; customized: boolean }>(
      "/payments/settings/payment-methods"
    )
      .then((data) => {
        setMethods(data.methods);
        setCustomized(data.customized);
      })
      .catch(() => {
        setMessage({ type: "error", text: "Failed to load payment settings." });
      })
      .finally(() => setLoading(false));
  }, []);

  function toggleMethod(key: string) {
    setMethods((prev) => ({ ...prev, [key]: !prev[key] }));
    setDirty(true);
    setMessage(null);
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const data = await apiFetch<{ methods: Record<string, boolean>; customized: boolean }>(
        "/payments/settings/payment-methods",
        {
          method: "PUT",
          body: JSON.stringify({ methods }),
        }
      );
      setMethods(data.methods);
      setCustomized(data.customized);
      setDirty(false);
      setMessage({ type: "success", text: "Payment methods updated successfully." });
    } catch {
      setMessage({ type: "error", text: "Failed to save payment settings." });
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    setMessage(null);
    try {
      const data = await apiFetch<{ methods: Record<string, boolean>; customized: boolean }>(
        "/payments/settings/payment-methods",
        { method: "DELETE" }
      );
      setMethods(data.methods);
      setCustomized(data.customized);
      setDirty(false);
      setMessage({ type: "success", text: "Reset to automatic mode." });
    } catch {
      setMessage({ type: "error", text: "Failed to reset payment settings." });
    } finally {
      setSaving(false);
    }
  }

  const enabledCount = Object.values(methods).filter(Boolean).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl font-bold">
            <span className="gradient-text">Payment Methods</span>
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Toggle which payment methods are accepted at checkout.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {customized && (
            <button
              onClick={handleReset}
              className="btn-secondary px-3 py-1.5 rounded-lg text-xs"
              disabled={saving}
            >
              Reset to Auto
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="btn-primary px-4 py-1.5 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="glass rounded-xl p-4 mb-6">
        <p className="text-xs text-text-muted">
          Payment methods must also be enabled in your{" "}
          <span className="text-accent-blue">Stripe Dashboard</span> (Settings &rarr; Payment methods).
          Toggling a method here controls what gets sent to Stripe&apos;s API — if a method isn&apos;t
          enabled in Stripe, it won&apos;t appear even if toggled on here.
        </p>
        {!customized && !dirty && (
          <p className="text-xs text-accent-blue mt-2">
            Currently using automatic mode — Stripe decides which methods to show based on
            currency, location, and amount. Toggle any method to switch to manual control.
          </p>
        )}
      </div>

      {message && (
        <div
          className={`mb-6 p-3 rounded-lg text-sm ${
            message.type === "success"
              ? "bg-green-500/10 border border-green-500/20 text-green-400"
              : "bg-red-500/10 border border-red-500/20 text-red-400"
          }`}
        >
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="text-center py-20 text-text-muted">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {PAYMENT_METHODS.map((method) => {
              const enabled = !!methods[method.key];
              return (
                <div
                  key={method.key}
                  className={`glass rounded-xl p-5 cursor-pointer transition-all ${
                    enabled
                      ? "border border-accent-pink/30 bg-accent-pink/5"
                      : "border border-transparent opacity-60"
                  }`}
                  onClick={() => toggleMethod(method.key)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-text-primary">{method.label}</h3>
                    <div
                      className={`w-10 h-5 rounded-full transition-colors flex items-center px-0.5 ${
                        enabled ? "bg-accent-pink" : "bg-base-100"
                      }`}
                    >
                      <div
                        className={`w-4 h-4 rounded-full bg-white transition-transform ${
                          enabled ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </div>
                  </div>
                  <p className="text-xs text-text-muted">{method.description}</p>
                </div>
              );
            })}
          </div>

          <div className="glass rounded-xl p-4">
            <p className="text-xs text-text-muted">
              <span className="text-text-secondary font-medium">{enabledCount}</span> of{" "}
              {PAYMENT_METHODS.length} methods enabled
              {enabledCount === 0 && (
                <span className="text-red-400 ml-2">
                  — At least one method must be enabled. Automatic mode will be used as fallback.
                </span>
              )}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
