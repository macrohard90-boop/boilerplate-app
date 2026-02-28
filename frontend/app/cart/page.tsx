"use client";

import { useState } from "react";
import Link from "next/link";
import { useCart, type CartItem, cartItemKey } from "../../lib/cart-context";
import { useAuth } from "../../lib/auth-context";
import { useConfig } from "../../lib/config-context";
import { formatPrice } from "../../lib/format";
import { useToast } from "../../components/Toast";
import LoadingSpinner from "../../components/LoadingSpinner";

export default function CartPage() {
  const { cart, isLoading, updateQuantity, removeItem, applyDiscount, removeDiscount } = useCart();
  const { isAuthenticated } = useAuth();
  const { enable_coupons } = useConfig();
  const { showToast } = useToast();
  const [discountCode, setDiscountCode] = useState("");
  const [applyingDiscount, setApplyingDiscount] = useState(false);

  async function handleApplyDiscount() {
    if (!discountCode.trim()) return;
    setApplyingDiscount(true);
    try {
      await applyDiscount(discountCode.trim());
      showToast("Discount applied!", "success");
    } catch {
      showToast("Invalid discount code", "error");
    }
    setApplyingDiscount(false);
  }

  if (isLoading) {
    return <LoadingSpinner size="lg" className="py-40" />;
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="font-serif text-3xl font-bold mb-8">
        <span className="gradient-text">Shopping Cart</span>
      </h1>

      {cart.items.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-text-muted mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
          </svg>
          <h2 className="text-xl font-medium text-text-primary mb-2">Your cart is empty</h2>
          <p className="text-text-secondary mb-6">Discover our products and add something to your cart</p>
          <Link href="/products" className="btn-primary text-sm">Browse Products</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Items */}
          <div className="lg:col-span-2 space-y-4">
            {cart.items.map((item) => (
              <CartItemRow
                key={cartItemKey(item)}
                item={item}
                onUpdateQuantity={updateQuantity}
                onRemove={removeItem}
              />
            ))}
          </div>

          {/* Summary */}
          <div className="lg:col-span-1">
            <div className="glass rounded-2xl p-6 sticky top-24">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Order Summary</h2>

              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Subtotal ({cart.item_count} item{cart.item_count !== 1 ? "s" : ""})</span>
                  <span className="text-text-primary">{formatPrice(cart.subtotal)}</span>
                </div>
                {cart.discount_amount > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-accent-green">Discount</span>
                    <span className="text-accent-green">-{formatPrice(cart.discount_amount)}</span>
                  </div>
                )}
                <div className="border-t border-glass-border pt-3 flex justify-between">
                  <span className="font-semibold text-text-primary">Total</span>
                  <span className="text-xl font-bold gradient-text">{formatPrice(cart.total)}</span>
                </div>
              </div>

              {/* Discount code */}
              {enable_coupons && (
                <div className="mb-6">
                  {cart.discount_code ? (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-accent-green/10 border border-accent-green/20">
                      <span className="text-sm text-accent-green font-medium">{cart.discount_code}</span>
                      <button onClick={() => removeDiscount()} className="text-xs text-text-muted hover:text-accent-pink transition-colors">
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={discountCode}
                        onChange={(e) => setDiscountCode(e.target.value)}
                        placeholder="Discount code"
                        className="input-glass text-sm flex-1"
                      />
                      <button
                        onClick={handleApplyDiscount}
                        disabled={applyingDiscount}
                        className="btn-secondary text-sm !px-4 shrink-0"
                      >
                        {applyingDiscount ? "..." : "Apply"}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {isAuthenticated ? (
                <Link href="/checkout" className="btn-primary w-full text-center block text-sm">
                  Proceed to Checkout
                </Link>
              ) : (
                <div className="space-y-3">
                  <Link href="/auth/login" className="btn-primary w-full text-center block text-sm">
                    Sign in to Checkout
                  </Link>
                  <p className="text-xs text-text-muted text-center">
                    You need to sign in to complete your purchase
                  </p>
                </div>
              )}

              <Link href="/products" className="block text-center text-sm text-text-muted hover:text-text-secondary transition-colors mt-4">
                Continue Shopping
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CartItemRow({
  item,
  onUpdateQuantity,
  onRemove,
}: {
  item: CartItem;
  onUpdateQuantity: (productId: string, variantId: string, qty: number) => Promise<void>;
  onRemove: (productId: string, variantId: string) => Promise<void>;
}) {
  function handleQuantity(qty: number) {
    onUpdateQuantity(item.product_id, item.variant_id, qty);
  }

  function handleRemove() {
    onRemove(item.product_id, item.variant_id);
  }

  return (
    <div className="glass rounded-xl p-4 flex gap-4">
      <div className="w-20 h-20 bg-base-100 rounded-lg shrink-0 overflow-hidden">
        {item.image_url ? (
          <img src={item.image_url} alt={item.product_name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-text-muted">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-text-primary">
          {item.product_name}
        </span>
        {item.variant_name && (
          <p className="text-xs text-text-muted mt-0.5">{item.variant_name}</p>
        )}
        <p className="text-sm font-semibold text-text-primary mt-1">{formatPrice(item.unit_price)}</p>
      </div>

      <div className="flex flex-col items-end gap-2">
        <button
          onClick={handleRemove}
          className="text-text-muted hover:text-accent-pink transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <div className="flex items-center glass rounded-lg">
          <button onClick={() => handleQuantity(Math.max(1, item.quantity - 1))} className="px-2 py-1 text-sm text-text-secondary hover:text-text-primary">-</button>
          <span className="px-2 py-1 text-sm text-text-primary min-w-[28px] text-center">{item.quantity}</span>
          <button onClick={() => handleQuantity(item.quantity + 1)} className="px-2 py-1 text-sm text-text-secondary hover:text-text-primary">+</button>
        </div>
        <p className="text-sm font-semibold text-text-primary">{formatPrice(item.total_price)}</p>
      </div>
    </div>
  );
}
