"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { useToast } from "../../../../../components/Toast";
import LoadingSpinner from "../../../../../components/LoadingSpinner";
import ProductForm, { type ProductFormData } from "../../../../../components/admin/ProductForm";
import VariantManager from "../../../../../components/admin/VariantManager";
import SyncStatusBadge from "../../../../../components/admin/SyncStatusBadge";
import ImageUploader from "../../../../../components/admin/ImageUploader";

interface Product {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  sku: string | null;
  base_price: number;
  currency: string;
  status: string;
  type: string;
  stripe_product_id: string | null;
  stripe_price_id: string | null;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
  synced_provider: string | null;
  created_at: string;
  updated_at: string;
}

export default function AdminProductEditPage() {
  const params = useParams();
  const router = useRouter();
  const { showToast } = useToast();
  const productId = params.id as string;

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchProduct = useCallback(async () => {
    try {
      const allData = await apiFetch<{ items: Product[] }>(
        `/ecommerce/products?page=1&page_size=100`
      );
      const found = allData.items.find((p) => p.id === productId);
      if (found) {
        setProduct(found);
      } else {
        showToast("Product not found", "error");
        router.push("/admin/catalog/products");
      }
    } catch {
      showToast("Failed to load product", "error");
      router.push("/admin/catalog/products");
    }
    setLoading(false);
  }, [productId, router, showToast]);

  useEffect(() => { fetchProduct(); }, [fetchProduct]);

  const handleUpdate = async (formData: ProductFormData) => {
    setSaving(true);
    try {
      await apiFetch(`/ecommerce/products/${productId}`, {
        method: "PUT",
        body: JSON.stringify(formData),
      });
      showToast("Product updated", "success");
      fetchProduct();
    } catch {
      showToast("Failed to update product", "error");
    }
    setSaving(false);
  };

  const handleRetrySync = async () => {
    setSyncing(true);
    try {
      await apiFetch(`/ecommerce/products/${productId}/sync`, { method: "POST" });
      showToast("Sync successful", "success");
      fetchProduct();
    } catch {
      showToast("Sync failed", "error");
    }
    setSyncing(false);
  };

  if (loading) return <LoadingSpinner className="py-20" />;
  if (!product) return null;

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/catalog/products")}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Edit Product</span>
        </h1>
      </div>

      {/* Sync Status Banner */}
      <div className="glass rounded-xl p-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-xs text-text-muted block">Catalog Sync</span>
            <SyncStatusBadge
              status={product.stripe_sync_status}
              error={product.stripe_sync_error}
              provider={product.synced_provider}
              onRetry={product.stripe_sync_status === "error" ? handleRetrySync : undefined}
            />
          </div>
          {product.stripe_product_id && (
            <div>
              <span className="text-xs text-text-muted block">Stripe Product</span>
              <span className="text-xs text-text-secondary font-mono">{product.stripe_product_id}</span>
            </div>
          )}
          {product.stripe_price_id && (
            <div>
              <span className="text-xs text-text-muted block">Stripe Price</span>
              <span className="text-xs text-text-secondary font-mono">{product.stripe_price_id}</span>
            </div>
          )}
        </div>
        {product.stripe_sync_status !== "synced" && product.status === "active" && (
          <button
            onClick={handleRetrySync}
            className="btn-primary px-3 py-1.5 rounded-lg text-sm"
            disabled={syncing}
          >
            {syncing ? "Syncing..." : "Sync Now"}
          </button>
        )}
      </div>

      {/* Product Form */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Product Details</h2>
        <ProductForm
          initial={{
            name: product.name,
            description: product.description || "",
            sku: product.sku || "",
            base_price: product.base_price,
            currency: product.currency,
            status: product.status,
            type: product.type,
          }}
          onSubmit={handleUpdate}
          onCancel={() => router.push("/admin/catalog/products")}
          loading={saving}
          submitLabel="Update Product"
        />
      </div>

      {/* Images */}
      <div className="glass rounded-xl p-6 mb-6">
        <ImageUploader productId={productId} />
      </div>

      {/* Variant Manager */}
      <div className="glass rounded-xl p-6">
        <VariantManager
          productId={productId}
          productBasePrice={product.base_price}
          currency={product.currency}
        />
      </div>
    </div>
  );
}
