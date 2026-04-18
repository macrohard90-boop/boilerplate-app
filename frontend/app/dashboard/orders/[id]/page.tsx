"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../lib/api";
import { formatPrice, formatDate } from "../../../../lib/format";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface OrderItem {
  product_id: string;
  variant_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  product_snapshot: {
    product_name: string;
    variant_name: string | null;
    image_url: string | null;
    [key: string]: unknown;
  };
}

interface Order {
  id: string;
  status: string;
  total: number;
  subtotal: number;
  discount_amount: number;
  currency: string;
  created_at: string;
  items: OrderItem[];
  shipping_address?: Record<string, string>;
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<Order>(`/ecommerce/orders/${id}`)
      .then(setOrder)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner className="py-20" />;

  if (!order) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl text-text-primary mb-4">Order not found</h2>
        <Link href="/dashboard/orders" className="btn-primary text-sm">Back to Orders</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link href="/dashboard/orders" className="text-text-muted hover:text-text-secondary transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h1 className="font-serif text-2xl font-bold">
          Order <span className="gradient-text">#{order.id.slice(0, 8)}</span>
        </h1>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted">Status</p>
          <span className={`text-sm mt-1 ${
            order.status === "completed" ? "badge-green" :
            order.status === "cancelled" ? "badge-pink" : "badge-blue"
          }`}>
            {order.status}
          </span>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted">Date</p>
          <p className="text-sm text-text-primary mt-1">{formatDate(order.created_at)}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted">Total</p>
          <p className="text-lg font-semibold gradient-text mt-1">{formatPrice(order.total, order.currency)}</p>
        </div>
      </div>

      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Items</h2>
        <div className="space-y-3">
          {order.items?.map((item) => (
            <div key={item.product_id} className="flex items-center gap-4 py-3 border-b border-glass-border last:border-0">
              {item.product_snapshot?.image_url && (
                <img
                  src={item.product_snapshot.image_url}
                  alt={item.product_snapshot.product_name}
                  className="w-14 h-14 rounded-lg object-cover bg-glass-bg shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary">{item.product_snapshot?.product_name}</p>
                {item.product_snapshot?.variant_name && item.product_snapshot.variant_name !== "Default" && (
                  <p className="text-xs text-text-muted">{item.product_snapshot.variant_name}</p>
                )}
                <p className="text-xs text-text-muted">Qty: {item.quantity} x {formatPrice(item.unit_price, order.currency)}</p>
              </div>
              <p className="text-sm font-medium text-text-primary shrink-0">{formatPrice(item.total_price, order.currency)}</p>
            </div>
          ))}
        </div>

        <div className="border-t border-glass-border mt-4 pt-4 space-y-1">
          {order.discount_amount > 0 && (
            <div className="flex justify-between text-sm text-accent-green">
              <span>Discount</span>
              <span>-{formatPrice(order.discount_amount, order.currency)}</span>
            </div>
          )}
          <div className="flex justify-between font-semibold">
            <span>Total</span>
            <span className="gradient-text">{formatPrice(order.total, order.currency)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
