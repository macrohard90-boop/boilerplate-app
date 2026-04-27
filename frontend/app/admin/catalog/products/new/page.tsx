"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { useToast } from "../../../../../components/Toast";
import ProductForm, {
  type ProductFormData,
  type CategoryOption,
} from "../../../../../components/admin/ProductForm";

export default function AdminProductNewPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [creating, setCreating] = useState(false);
  const [categories, setCategories] = useState<CategoryOption[]>([]);

  useEffect(() => {
    apiFetch<CategoryOption[]>("/ecommerce/categories")
      .then(setCategories)
      .catch(() => {});
  }, []);

  const handleCreate = async (formData: ProductFormData) => {
    setCreating(true);
    try {
      await apiFetch("/ecommerce/products", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      showToast("Product created", "success");
      router.push("/admin/catalog/products");
    } catch (err: unknown) {
      const msg =
        (err as { message?: string })?.message || "Failed to create product";
      showToast(msg, "error");
    }
    setCreating(false);
  };

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/catalog/products")}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-text-primary">
          Create Product
        </h2>
      </div>
      <div className="glass rounded-xl p-6">
        <ProductForm
          onSubmit={handleCreate}
          onCancel={() => router.push("/admin/catalog/products")}
          loading={creating}
          submitLabel="Create"
          allowRecurring={false}
          categories={categories}
        />
      </div>
    </div>
  );
}
