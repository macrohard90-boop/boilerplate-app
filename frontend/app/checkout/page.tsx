"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { useCart, cartItemKey } from "../../lib/cart-context";
import { useAuth } from "../../lib/auth-context";
import { apiFetch } from "../../lib/api";
import { formatPrice } from "../../lib/format";
import { getStripe } from "../../lib/stripe";
import { useToast } from "../../components/Toast";
import LoadingSpinner from "../../components/LoadingSpinner";

interface AddressForm {
  first_name: string;
  last_name: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}

interface CheckoutResponse {
  order_id: string;
  order_number: string;
  client_secret: string | null;
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  total: number;
  currency: string;
}

const emptyAddress: AddressForm = {
  first_name: "",
  last_name: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "US",
};

/* ── Stripe Payment Form (rendered inside <Elements>) ── */
function PaymentForm({ orderId }: { orderId: string }) {
  const stripe = useStripe();
  const elements = useElements();
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;

    setPaying(true);
    setError(null);

    const { error: stripeError } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/orders/${orderId}/confirmation`,
      },
    });

    // Only reaches here if there's an immediate error (redirect didn't happen)
    if (stripeError) {
      setError(stripeError.message || "Payment failed. Please try again.");
    }
    setPaying(false);
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement options={{ layout: "tabs" }} />
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={!stripe || paying}
        className="btn-primary w-full mt-6 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {paying ? "Processing..." : "Pay Now"}
      </button>
    </form>
  );
}

/* ── Address Form Fields ── */
function AddressFields({ data, onChange }: { data: AddressForm; onChange: (field: keyof AddressForm, value: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm text-text-secondary mb-1">First name</label>
          <input value={data.first_name} onChange={(e) => onChange("first_name", e.target.value)} required className="input-glass text-sm" />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">Last name</label>
          <input value={data.last_name} onChange={(e) => onChange("last_name", e.target.value)} required className="input-glass text-sm" />
        </div>
      </div>
      <div>
        <label className="block text-sm text-text-secondary mb-1">Address</label>
        <input value={data.address_line1} onChange={(e) => onChange("address_line1", e.target.value)} required className="input-glass text-sm" placeholder="Street address" />
      </div>
      <input value={data.address_line2} onChange={(e) => onChange("address_line2", e.target.value)} className="input-glass text-sm" placeholder="Apt, suite, etc. (optional)" />
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-sm text-text-secondary mb-1">City</label>
          <input value={data.city} onChange={(e) => onChange("city", e.target.value)} required className="input-glass text-sm" />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">State</label>
          <input value={data.state} onChange={(e) => onChange("state", e.target.value)} required className="input-glass text-sm" />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1">ZIP</label>
          <input value={data.postal_code} onChange={(e) => onChange("postal_code", e.target.value)} required className="input-glass text-sm" />
        </div>
      </div>
    </div>
  );
}

/* ── Main Checkout Page ── */
export default function CheckoutPage() {
  const router = useRouter();
  const { cart, isLoading, clearCart } = useCart();
  const { isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const [step, setStep] = useState(1);
  const [shipping, setShipping] = useState<AddressForm>({ ...emptyAddress });
  const [billing, setBilling] = useState<AddressForm>({ ...emptyAddress });
  const [sameAsShipping, setSameAsShipping] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [stripePromise] = useState(() => getStripe());

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Sign in Required</h1>
        <p className="text-text-secondary mb-6">Please sign in to complete your purchase.</p>
        <Link href="/auth/login" className="btn-primary text-sm">Sign In</Link>
      </div>
    );
  }

  if (isLoading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!clientSecret && cart.items.length === 0) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Cart is Empty</h1>
        <p className="text-text-secondary mb-6">Add some products before checkout.</p>
        <Link href="/products" className="btn-primary text-sm">Browse Products</Link>
      </div>
    );
  }

  // Cart type detection — subscriptions don't need shipping
  const hasSubscription = cart.items.some(item => item.pricing_type === "recurring");
  const hasOneTime = cart.items.some(item => item.pricing_type !== "recurring");
  const subscriptionOnly = hasSubscription && !hasOneTime;

  function updateField(setter: (v: AddressForm) => void, state: AddressForm, field: keyof AddressForm, value: string) {
    setter({ ...state, [field]: value });
  }

  function mapAddress(addr: AddressForm) {
    return {
      line1: addr.address_line1,
      line2: addr.address_line2 || null,
      city: addr.city,
      state: addr.state,
      postal_code: addr.postal_code,
      country: addr.country,
    };
  }

  async function handleCreatePaymentIntent() {
    setProcessing(true);
    try {
      // Subscription or mixed carts use Stripe Checkout Sessions
      if (hasSubscription) {
        const session = await apiFetch<{ session_url: string; session_id: string }>(
          "/payments/checkout/session",
          {
            method: "POST",
            body: JSON.stringify({
              discount_code: cart.discount_code || null,
            }),
          }
        );
        // Redirect to Stripe-hosted checkout
        await clearCart();
        window.location.href = session.session_url;
        return;
      }

      // One-time only: use embedded PaymentElement flow
      const result = await apiFetch<CheckoutResponse>("/payments/checkout", {
        method: "POST",
        body: JSON.stringify({
          shipping_address: mapAddress(shipping),
          billing_address: sameAsShipping ? null : mapAddress(billing),
          discount_code: cart.discount_code || null,
        }),
      });
      // Cart is consumed when order is created — clear it now
      await clearCart();

      if (!result.client_secret) {
        // Free order — no payment needed, redirect to confirmation
        router.push(`/orders/${result.order_id}/confirmation?free=1`);
        return;
      }

      setClientSecret(result.client_secret);
      setOrderId(result.order_id);
      setStep(3);
    } catch (e: unknown) {
      const err = e as { message?: string };
      showToast(err?.message || "Checkout failed", "error");
    }
    setProcessing(false);
  }

  const stepLabels = subscriptionOnly ? ["Review", "Payment"] : ["Shipping", "Review", "Payment"];
  const steps = subscriptionOnly ? [2, 3] : [1, 2, 3];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="font-serif text-3xl font-bold mb-8">
        <span className="gradient-text">Checkout</span>
      </h1>

      {/* Steps indicator */}
      <div className="flex items-center gap-4 mb-10">
        {steps.map((s, idx) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
              step >= s ? "bg-accent-purple/20 text-accent-purple border border-accent-purple/40" : "glass text-text-muted"
            }`}>
              {idx + 1}
            </div>
            <span className={`text-sm hidden sm:inline ${step >= s ? "text-text-primary" : "text-text-muted"}`}>
              {stepLabels[idx]}
            </span>
            {idx < steps.length - 1 && <div className={`w-10 h-px ${step > s ? "bg-accent-purple/40" : "bg-glass-border"}`} />}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Form */}
        <div className="lg:col-span-2">
          {/* Step 1: Shipping (skipped for subscription-only carts) */}
          {step === 1 && !subscriptionOnly && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Shipping Address</h2>
              <AddressFields data={shipping} onChange={(field, val) => updateField(setShipping, shipping, field, val)} />
              <div className="mt-4">
                <label className="flex items-center gap-2 text-sm text-text-secondary">
                  <input type="checkbox" checked={sameAsShipping} onChange={(e) => setSameAsShipping(e.target.checked)} className="rounded border-glass-border bg-glass-bg text-accent-purple focus:ring-accent-purple/30" />
                  Billing address same as shipping
                </label>
              </div>
              {!sameAsShipping && (
                <div className="mt-6">
                  <h3 className="text-md font-semibold text-text-primary mb-4">Billing Address</h3>
                  <AddressFields data={billing} onChange={(field, val) => updateField(setBilling, billing, field, val)} />
                </div>
              )}
              <button onClick={() => setStep(2)} className="btn-primary w-full mt-6 text-sm">
                Continue to Review
              </button>
            </div>
          )}

          {/* Step 2: Review & Create Payment (also shown as step 1 for subscription-only) */}
          {(step === 2 || (step === 1 && subscriptionOnly)) && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Order Review</h2>
              <div className="space-y-3 mb-6">
                {cart.items.map((item) => (
                  <div key={cartItemKey(item)} className="flex justify-between text-sm">
                    <span className="text-text-secondary">
                      {item.product_name} {item.variant_name ? `(${item.variant_name})` : ""} x{item.quantity}
                      {item.pricing_type === "recurring" && (
                        <span className="ml-1 text-accent-blue text-xs">(subscription)</span>
                      )}
                    </span>
                    <span className="text-text-primary">{formatPrice(item.total_price)}</span>
                  </div>
                ))}
              </div>
              <div className="border-t border-glass-border pt-3 mb-6">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-text-secondary">Subtotal</span>
                  <span>{formatPrice(cart.subtotal)}</span>
                </div>
                {cart.discount_amount > 0 && (
                  <div className="flex justify-between text-sm text-accent-green mb-1">
                    <span>Discount</span>
                    <span>-{formatPrice(cart.discount_amount)}</span>
                  </div>
                )}
                <div className="flex justify-between font-semibold text-lg mt-2">
                  <span>Total</span>
                  <span className="gradient-text">{formatPrice(cart.total)}</span>
                </div>
              </div>
              {!subscriptionOnly && (
                <div className="text-sm text-text-secondary mb-6">
                  <p><strong>Ship to:</strong> {shipping.first_name} {shipping.last_name}, {shipping.address_line1}, {shipping.city}, {shipping.state} {shipping.postal_code}</p>
                </div>
              )}
              {subscriptionOnly && (
                <div className="text-sm text-text-muted mb-6">
                  <p>Digital subscription — no shipping required.</p>
                </div>
              )}
              <div className="flex gap-3">
                {!subscriptionOnly && (
                  <button onClick={() => setStep(1)} className="btn-secondary text-sm flex-1">Back</button>
                )}
                <button
                  onClick={handleCreatePaymentIntent}
                  disabled={processing}
                  className="btn-primary text-sm flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {processing ? "Processing..." : "Proceed to Payment"}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Stripe Payment */}
          {step === 3 && clientSecret && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Payment</h2>
              <Elements
                stripe={stripePromise}
                options={{
                  clientSecret,
                  appearance: {
                    theme: "night",
                    variables: {
                      colorPrimary: "#a855f7",
                      colorBackground: "#1a1a2e",
                      colorText: "#e2e8f0",
                      colorDanger: "#ef4444",
                      borderRadius: "8px",
                    },
                  },
                }}
              >
                <PaymentForm orderId={orderId!} />
              </Elements>
            </div>
          )}
        </div>

        {/* Order summary sidebar */}
        <div className="lg:col-span-1">
          <div className="glass rounded-2xl p-6 sticky top-24">
            <h3 className="text-sm font-semibold text-text-primary mb-4">
              {step < 3 ? `Cart (${cart.item_count} items)` : "Order created"}
            </h3>
            {step < 3 ? (
              <>
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {cart.items.map((item) => (
                    <div key={cartItemKey(item)} className="flex gap-3 text-sm">
                      <div className="w-10 h-10 bg-base-100 rounded shrink-0 overflow-hidden">
                        {item.image_url && (
                          <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-text-primary truncate">{item.product_name}</p>
                        <p className="text-text-muted">x{item.quantity}</p>
                      </div>
                      <p className="text-text-primary shrink-0">{formatPrice(item.total_price)}</p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-glass-border mt-4 pt-4 flex justify-between font-semibold">
                  <span>Total</span>
                  <span className="gradient-text">{formatPrice(cart.total)}</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-text-secondary">Complete payment to confirm your order.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
