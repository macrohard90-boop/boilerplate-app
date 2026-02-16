"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { apiFetch } from "./api";
import { useAuth } from "./auth-context";

export interface CartItem {
  id: string;
  product_id: string;
  variant_id: string | null;
  product_name: string;
  variant_name: string | null;
  image_url: string | null;
  quantity: number;
  unit_price: number; // cents
  total_price: number; // cents
  slug: string;
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
  addItem: (productId: string, variantId?: string | null, quantity?: number) => Promise<void>;
  updateQuantity: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
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

  const refreshCart = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch<Cart>("/ecommerce/cart");
      setCart(data);
    } catch {
      setCart(emptyCart);
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

  const addItem = useCallback(async (productId: string, variantId?: string | null, quantity = 1) => {
    try {
      await apiFetch("/ecommerce/cart/items", {
        method: "POST",
        body: JSON.stringify({
          product_id: productId,
          variant_id: variantId || null,
          quantity,
        }),
      });
      await refreshCart();
    } catch (e) {
      throw e;
    }
  }, [refreshCart]);

  const updateQuantity = useCallback(async (itemId: string, quantity: number) => {
    try {
      await apiFetch(`/ecommerce/cart/items/${itemId}`, {
        method: "PATCH",
        body: JSON.stringify({ quantity }),
      });
      await refreshCart();
    } catch (e) {
      throw e;
    }
  }, [refreshCart]);

  const removeItem = useCallback(async (itemId: string) => {
    try {
      await apiFetch(`/ecommerce/cart/items/${itemId}`, {
        method: "DELETE",
      });
      await refreshCart();
    } catch (e) {
      throw e;
    }
  }, [refreshCart]);

  const applyDiscount = useCallback(async (code: string) => {
    try {
      await apiFetch("/ecommerce/cart/discount", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      await refreshCart();
    } catch (e) {
      throw e;
    }
  }, [refreshCart]);

  const removeDiscount = useCallback(async () => {
    try {
      await apiFetch("/ecommerce/cart/discount", {
        method: "DELETE",
      });
      await refreshCart();
    } catch (e) {
      throw e;
    }
  }, [refreshCart]);

  const clearCart = useCallback(async () => {
    try {
      await apiFetch("/ecommerce/cart", { method: "DELETE" });
      setCart(emptyCart);
    } catch (e) {
      throw e;
    }
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
