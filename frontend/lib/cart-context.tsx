"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { apiFetch } from "./api";
import { useAuth } from "./auth-context";
import { trackEvent } from "./track-event";

export interface CartItem {
  product_id: string;
  variant_id: string;
  product_name: string;
  variant_name: string | null;
  image_url?: string | null;
  quantity: number;
  unit_price: number; // cents
  total_price: number; // cents
  currency: string;
  pricing_type: string; // "one_time" | "recurring"
}

/** Composite key used by the backend: product_id + "_" + variant_id */
export function cartItemKey(item: CartItem): string {
  return `${item.product_id}_${item.variant_id}`;
}

interface Cart {
  items: CartItem[];
  item_count: number;
  subtotal: number; // cents
  discount_amount: number; // cents
  total: number; // cents
  discount_code: string | null;
}

interface CartState {
  cart: Cart;
  isLoading: boolean;
  addItem: (
    productId: string,
    variantId?: string | null,
    quantity?: number,
  ) => Promise<void>;
  updateQuantity: (
    productId: string,
    variantId: string,
    quantity: number,
  ) => Promise<void>;
  removeItem: (productId: string, variantId: string) => Promise<void>;
  applyDiscount: (code: string) => Promise<void>;
  removeDiscount: () => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
}

const emptyCart: Cart = {
  items: [],
  item_count: 0,
  subtotal: 0,
  discount_amount: 0,
  total: 0,
  discount_code: null,
};

const CartContext = createContext<CartState | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [cart, setCart] = useState<Cart>(emptyCart);
  const [isLoading, setIsLoading] = useState(false);
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const cartRef = useRef(cart);
  cartRef.current = cart;

  const refreshCart = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch<Cart>("/ecommerce/cart");
      setCart(data);
    } catch {
      // Keep existing cart data on refresh errors (network blip, token race).
      // Only explicit clearCart() should wipe the cart.
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch cart when auth state resolves
  useEffect(() => {
    if (!authLoading) {
      refreshCart();
    }
  }, [authLoading, isAuthenticated, refreshCart]);

  const addItem = useCallback(
    async (productId: string, variantId?: string | null, quantity = 1) => {
      const data = await apiFetch<Cart>("/ecommerce/cart/items", {
        method: "POST",
        body: JSON.stringify({
          product_id: productId,
          variant_id: variantId || null,
          quantity,
        }),
      });
      setCart(data);
      const added = data.items.find((it) => it.product_id === productId);
      trackEvent("add_to_cart", {
        product_id: productId,
        name: added?.product_name,
        price: added?.unit_price,
        quantity,
      });
      if (data.total >= 10000) {
        trackEvent("high_value_cart", {
          cart_total: data.total,
          threshold: 10000,
        });
      }
    },
    [],
  );

  const updateQuantity = useCallback(
    async (productId: string, variantId: string, quantity: number) => {
      const prev = cartRef.current;
      setCart((c) => {
        const items = c.items.map((it) =>
          it.product_id === productId && it.variant_id === variantId
            ? { ...it, quantity, total_price: it.unit_price * quantity }
            : it,
        );
        const subtotal = items.reduce((s, it) => s + it.total_price, 0);
        const itemCount = items.reduce((s, it) => s + it.quantity, 0);
        return {
          ...c,
          items,
          subtotal,
          item_count: itemCount,
          total: subtotal - c.discount_amount,
        };
      });
      try {
        const data = await apiFetch<Cart>(
          `/ecommerce/cart/items/${productId}_${variantId}`,
          {
            method: "PUT",
            body: JSON.stringify({ quantity }),
          },
        );
        setCart(data);
        const old = prev.items.find(
          (it) => it.product_id === productId && it.variant_id === variantId,
        );
        trackEvent("cart_quantity_changed", {
          product_id: productId,
          old_qty: old?.quantity,
          new_qty: quantity,
        });
      } catch (e) {
        setCart(prev);
        throw e;
      }
    },
    [],
  );

  const removeItem = useCallback(
    async (productId: string, variantId: string) => {
      const prev = cartRef.current;
      setCart((c) => {
        const items = c.items.filter(
          (it) => !(it.product_id === productId && it.variant_id === variantId),
        );
        const subtotal = items.reduce((s, it) => s + it.total_price, 0);
        const itemCount = items.reduce((s, it) => s + it.quantity, 0);
        return {
          ...c,
          items,
          subtotal,
          item_count: itemCount,
          total: subtotal - c.discount_amount,
        };
      });
      try {
        const data = await apiFetch<Cart>(
          `/ecommerce/cart/items/${productId}_${variantId}`,
          {
            method: "DELETE",
          },
        );
        setCart(data);
        const removed = prev.items.find(
          (it) => it.product_id === productId && it.variant_id === variantId,
        );
        trackEvent("remove_from_cart", {
          product_id: productId,
          name: removed?.product_name,
          price: removed?.unit_price,
        });
      } catch (e) {
        setCart(prev);
        throw e;
      }
    },
    [],
  );

  const applyDiscount = useCallback(async (code: string) => {
    try {
      const data = await apiFetch<Cart>("/ecommerce/cart/discount", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setCart(data);
      trackEvent("coupon_applied", {
        code,
        discount_amount: data.discount_amount,
      });
    } catch (e) {
      trackEvent("coupon_failed", { code });
      throw e;
    }
  }, []);

  const removeDiscount = useCallback(async () => {
    const data = await apiFetch<Cart>("/ecommerce/cart/discount", {
      method: "DELETE",
    });
    setCart(data);
  }, []);

  const clearCart = useCallback(async () => {
    const prev = cartRef.current;
    try {
      await apiFetch("/ecommerce/cart", { method: "DELETE" });
    } catch {
      // Cart may already be consumed by checkout — ignore API errors
    }
    trackEvent("cart_cleared", {
      item_count: prev.item_count,
      cart_total: prev.total,
    });
    setCart(emptyCart);
  }, []);

  return (
    <CartContext.Provider
      value={{
        cart,
        isLoading,
        addItem,
        updateQuantity,
        removeItem,
        applyDiscount,
        removeDiscount,
        clearCart,
        refreshCart,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart(): CartState {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
