"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../lib/api";
import { formatPrice, formatDate } from "../../../../lib/format";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface OrderItem {
  id: string;
  product_name: string;
  variant_name: string | null;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface Order {
  id: string;
  status: string;
  total_amount: number;
  currency: string;
  created_at: string;
  items: OrderItem[];
}

export default function OrderConfirmationPage() {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<Order>(`/ecommerce/orders/${id}`);
        setOrder(data);
      } catch {}
      setLoading(false);
    }
    if (id) load();
  }, [id]);

  if (loading) return <LoadingSpinner size="lg" className="py-40" />;

  if (!order) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-semibold text-text-primary mb-4">Order Not Found</h1>
        <Link href="/dashboard/orders" className="btn-primary text-sm">View Orders</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="glass rounded-2xl p-8 text-center mb-8">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-accent-green/10 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-accent-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="font-serif text-3xl font-bold gradient-text mb-2">Order Confirmed!</h1>
        <p className="text-text-secondary">Thank you for your purchase</p>
        <p className="text-xs text-text-muted mt-2">Order #{order.id.slice(0, 8)}</p>
      </div>

      <div className="glass rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Order Details</h2>
        <div className="space-y-3 mb-6">
          {order.items?.map((item) => (
            <div key={item.id} className="flex justify-between text-sm">
              <span className="text-text-secondary">
                {item.product_name} {item.variant_name ? `(${item.variant_name})` : ""} x{item.quantity}
              </span>
              <span className="text-text-primary">{formatPrice(item.total_price, order.currency)}</span>
            </div>
          ))}
        </div>
        <div className="border-t border-glass-border pt-3">
          <div className="flex justify-between font-semibold">
            <span>Total</span>
            <span className="gradient-text text-lg">{formatPrice(order.total_amount, order.currency)}</span>
          </div>
        </div>
        <div className="mt-4 text-sm text-text-muted">
          <p>Date: {formatDate(order.created_at)}</p>
          <p>Status: <span className="badge-green">{order.status}</span></p>
        </div>
      </div>

      <div className="flex gap-4 mt-8 justify-center">
        <Link href="/dashboard/orders" className="btn-secondary text-sm">View Orders</Link>
        <Link href="/products" className="btn-primary text-sm">Continue Shopping</Link>
      </div>
    </div>
  );
}
