"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { useToast } from "../../../../../components/Toast";
import CouponForm, {
  type CouponFormData,
} from "../../../../../components/admin/CouponForm";

interface Discount {
  id: string;
  stripe_sync_status: string;
  stripe_sync_error: string | null;
}

export default function AdminCouponNewPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [creating, setCreating] = useState(false);

  const handleCreate = async (formData: CouponFormData) => {
    setCreating(true);
    try {
      const created = await apiFetch<Discount>("/ecommerce/admin/discounts", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      if (created.stripe_sync_status === "error") {
        showToast(
          `Coupon created, but Stripe sync failed: ${created.stripe_sync_error}`,
          "error",
        );
      } else {
        showToast("Coupon created", "success");
      }
      router.push("/admin/catalog/coupons");
    } catch {
      showToast("Failed to create coupon", "error");
    }
    setCreating(false);
  };

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/catalog/coupons")}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Create Coupon</span>
        </h1>
      </div>

      {/* Coupon Form */}
      <div className="glass rounded-xl p-6">
        <CouponForm
          onSubmit={handleCreate}
          onCancel={() => router.push("/admin/catalog/coupons")}
          loading={creating}
          submitLabel="Create Coupon"
        />
      </div>
    </div>
  );
}
