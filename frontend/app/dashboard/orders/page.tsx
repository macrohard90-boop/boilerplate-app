"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../../lib/api";
import { formatPrice, formatDate } from "../../../lib/format";
import Pagination from "../../../components/Pagination";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface Order {
  id: string;
  status: string;
  total: number;
  currency: string;
  created_at: string;
  item_count?: number;
}

interface OrderResponse {
  items: Order[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function OrdersPage() {
  const [data, setData] = useState<OrderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    apiFetch<OrderResponse>(`/ecommerce/orders?page=${page}&page_size=10`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Order History</span>
      </h1>

      {loading ? (
        <LoadingSpinner className="py-20" />
      ) : !data || data.items.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-secondary">No orders yet.</p>
          <Link href="/products" className="btn-primary text-sm mt-4 inline-block">Start Shopping</Link>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {data.items.map((order) => (
              <Link key={order.id} href={`/dashboard/orders/${order.id}`} className="glass rounded-xl p-5 flex items-center justify-between group hover:border-accent-purple/20 transition-all block">
                <div>
                  <p className="text-sm font-medium text-text-primary group-hover:text-accent-blue transition-colors">
                    Order #{order.id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-text-muted mt-1">{formatDate(order.created_at)}</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-semibold text-text-primary">{formatPrice(order.total, order.currency)}</p>
                  <span className={`text-xs ${
                    order.status === "completed" || order.status === "delivered" ? "badge-green" :
                    order.status === "cancelled" ? "badge-pink" : "badge-blue"
                  }`}>
                    {order.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
          {data.total_pages > 1 && (
            <div className="mt-8">
              <Pagination currentPage={data.page} totalPages={data.total_pages} onPageChange={setPage} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
