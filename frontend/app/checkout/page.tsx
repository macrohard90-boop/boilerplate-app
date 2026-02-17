"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCart, cartItemKey } from "../../lib/cart-context";
import { useAuth } from "../../lib/auth-context";
import { apiFetch } from "../../lib/api";
import { formatPrice } from "../../lib/format";
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

export default function CheckoutPage() {
  const router = useRouter();
  const { cart, isLoading, clearCart } = useCart();
  const { isAuthenticated, user } = useAuth();
  const { showToast } = useToast();
  const [step, setStep] = useState(1);
  const [shipping, setShipping] = useState<AddressForm>({ ...emptyAddress });
  const [billing, setBilling] = useState<AddressForm>({ ...emptyAddress });
  const [sameAsShipping, setSameAsShipping] = useState(true);
  const [processing, setProcessing] = useState(false);

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

  if (cart.items.length === 0) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-4">Cart is Empty</h1>
        <p className="text-text-secondary mb-6">Add some products before checkout.</p>
        <Link href="/products" className="btn-primary text-sm">Browse Products</Link>
      </div>
    );
  }

  function updateField(setter: (v: AddressForm) => void, state: AddressForm, field: keyof AddressForm, value: string) {
    setter({ ...state, [field]: value });
  }

  async function handlePlaceOrder() {
    setProcessing(true);
    try {
      const order = await apiFetch<{ id: string }>("/ecommerce/orders", {
        method: "POST",
        body: JSON.stringify({
          shipping_address: shipping,
          billing_address: sameAsShipping ? shipping : billing,
          payment_method: "mock",
        }),
      });
      await clearCart();
      showToast("Order placed successfully!", "success");
      router.push(`/orders/${order.id}/confirmation`);
    } catch (e: unknown) {
      const err = e as { message?: string };
      showToast(err?.message || "Failed to place order", "error");
    }
    setProcessing(false);
  }

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

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="font-serif text-3xl font-bold mb-8">
        <span className="gradient-text">Checkout</span>
      </h1>

      {/* Steps indicator */}
      <div className="flex items-center gap-4 mb-10">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
              step >= s ? "bg-accent-purple/20 text-accent-purple border border-accent-purple/40" : "glass text-text-muted"
            }`}>
              {s}
            </div>
            <span className={`text-sm hidden sm:inline ${step >= s ? "text-text-primary" : "text-text-muted"}`}>
              {s === 1 ? "Shipping" : s === 2 ? "Payment" : "Review"}
            </span>
            {s < 3 && <div className={`w-10 h-px ${step > s ? "bg-accent-purple/40" : "bg-glass-border"}`} />}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Form */}
        <div className="lg:col-span-2">
          {step === 1 && (
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
                Continue to Payment
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Payment</h2>
              <div className="p-6 rounded-xl bg-accent-blue/5 border border-accent-blue/20 mb-6">
                <p className="text-sm text-accent-blue mb-2 font-medium">Mock Payment Mode</p>
                <p className="text-xs text-text-secondary">
                  This is a demo checkout. No real payment will be processed. Click &quot;Continue&quot; to proceed.
                </p>
              </div>
              <div className="space-y-4 opacity-50 pointer-events-none">
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Card number</label>
                  <input value="4242 4242 4242 4242" readOnly className="input-glass text-sm" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-text-secondary mb-1">Expiry</label>
                    <input value="12/28" readOnly className="input-glass text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm text-text-secondary mb-1">CVC</label>
                    <input value="123" readOnly className="input-glass text-sm" />
                  </div>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setStep(1)} className="btn-secondary text-sm flex-1">Back</button>
                <button onClick={() => setStep(3)} className="btn-primary text-sm flex-1">Continue to Review</button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Order Review</h2>
              <div className="space-y-3 mb-6">
                {cart.items.map((item) => (
                  <div key={cartItemKey(item)} className="flex justify-between text-sm">
                    <span className="text-text-secondary">
                      {item.product_name} {item.variant_name ? `(${item.variant_name})` : ""} x{item.quantity}
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
              <div className="text-sm text-text-secondary mb-6">
                <p><strong>Ship to:</strong> {shipping.first_name} {shipping.last_name}, {shipping.address_line1}, {shipping.city}, {shipping.state} {shipping.postal_code}</p>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setStep(2)} className="btn-secondary text-sm flex-1">Back</button>
                <button
                  onClick={handlePlaceOrder}
                  disabled={processing}
                  className="btn-primary text-sm flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {processing ? "Processing..." : "Place Order"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Order summary sidebar */}
        <div className="lg:col-span-1">
          <div className="glass rounded-2xl p-6 sticky top-24">
            <h3 className="text-sm font-semibold text-text-primary mb-4">Cart ({cart.item_count} items)</h3>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {cart.items.map((item) => (
                <div key={cartItemKey(item)} className="flex gap-3 text-sm">
                  <div className="w-10 h-10 bg-base-100 rounded shrink-0" />
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
          </div>
        </div>
      </div>
    </div>
  );
}
