"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";
import { formatPrice } from "../../../lib/format";
import { useToast } from "../../../components/Toast";
import { useCart } from "../../../lib/cart-context";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface WishlistItem {
  id: string;
  product_id: string;
  product_name: string;
  product_slug: string;
  product_price: number;
  product_currency: string;
  product_image_url?: string;
  created_at: string;
}

interface Wishlist {
  id: string;
  name: string;
  items: WishlistItem[];
}

export default function WishlistsPage() {
  const [wishlists, setWishlists] = useState<Wishlist[]>([]);
  const [loading, setLoading] = useState(true);
  const { addItem } = useCart();
  const { showToast } = useToast();

  async function fetchWishlists() {
    try {
      const data = await apiFetch<Wishlist[]>("/ecommerce/wishlists");
      setWishlists(Array.isArray(data) ? data : []);
    } catch {
      setWishlists([]);
    }
    setLoading(false);
  }

  useEffect(() => { fetchWishlists(); }, []);

  async function handleRemove(wishlistId: string, itemId: string) {
    try {
      await apiFetch(`/ecommerce/wishlists/${wishlistId}/items/${itemId}`, { method: "DELETE" });
      showToast("Removed from wishlist", "info");
      fetchWishlists();
    } catch {
      showToast("Failed to remove", "error");
    }
  }

  async function handleMoveToCart(item: WishlistItem, wishlistId: string) {
    try {
      await addItem(item.product_id);
      await apiFetch(`/ecommerce/wishlists/${wishlistId}/items/${item.id}`, { method: "DELETE" });
      showToast(`${item.product_name} moved to cart`, "success");
      fetchWishlists();
    } catch {
      showToast("Failed to move to cart", "error");
    }
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Wishlists</span>
      </h1>

      {wishlists.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-secondary">No wishlists yet.</p>
          <Link href="/products" className="btn-primary text-sm mt-4 inline-block">Browse Products</Link>
        </div>
      ) : (
        wishlists.map((wl) => (
          <div key={wl.id} className="mb-8">
            <h2 className="text-lg font-semibold text-text-primary mb-4">{wl.name}</h2>
            {wl.items.length === 0 ? (
              <p className="text-sm text-text-muted glass rounded-xl p-4">No items in this wishlist</p>
            ) : (
              <div className="space-y-3">
                {wl.items.map((item) => (
                  <div key={item.id} className="glass rounded-xl p-4 flex items-center gap-4">
                    <Link href={`/products/${item.product_slug}`} className="w-16 h-16 bg-base-100 rounded-lg shrink-0 overflow-hidden relative block">
                      {item.product_image_url ? (
                        <Image src={item.product_image_url} alt={item.product_name} fill sizes="64px" className="object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-text-muted text-xs">No img</div>
                      )}
                    </Link>
                    <div className="flex-1 min-w-0">
                      <Link href={`/products/${item.product_slug}`} className="text-sm font-medium text-text-primary hover:text-accent-blue transition-colors">
                        {item.product_name}
                      </Link>
                      <p className="text-sm text-text-secondary mt-1">{formatPrice(item.product_price, item.product_currency)}</p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button onClick={() => handleMoveToCart(item, wl.id)} className="btn-primary text-xs !px-3 !py-1.5">
                        Add to Cart
                      </button>
                      <button onClick={() => handleRemove(wl.id, item.id)} className="text-text-muted hover:text-accent-pink transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
