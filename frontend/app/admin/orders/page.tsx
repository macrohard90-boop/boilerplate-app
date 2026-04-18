"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { formatPrice, formatDate } from "../../../lib/format";
import Pagination from "../../../components/Pagination";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface Order {
  id: string;
  user_id: string;
  status: string;
  total: number;
  currency: string;
  created_at: string;
}

interface OrderResponse {
  items: Order[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function AdminOrdersPage() {
  const [data, setData] = useState<OrderResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    apiFetch<OrderResponse>(`/ecommerce/admin/orders?page=${page}&page_size=20`)
      .then(setData)
      .catch(() => {
        // Fallback: try user orders endpoint
        apiFetch<OrderResponse>(`/ecommerce/orders?page=${page}&page_size=20`)
          .then(setData)
          .catch(() => {});
      })
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Orders</span>
        {data && <span className="text-text-muted font-normal text-lg ml-2">({data.total})</span>}
      </h1>

      {!data || data.items.length === 0 ? (
        <p className="text-text-secondary glass rounded-xl p-8 text-center">No orders</p>
      ) : (
        <>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left p-4 text-text-muted font-medium">Order ID</th>
                  <th className="text-left p-4 text-text-muted font-medium">Total</th>
                  <th className="text-left p-4 text-text-muted font-medium">Status</th>
                  <th className="text-left p-4 text-text-muted font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((o) => (
                  <tr key={o.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                    <td className="p-4 text-text-primary font-mono text-xs">{o.id.slice(0, 8)}</td>
                    <td className="p-4 text-text-primary font-medium">{formatPrice(o.total, o.currency)}</td>
                    <td className="p-4">
                      <span className={
                        o.status === "completed" ? "badge-green" :
                        o.status === "cancelled" ? "badge-pink" : "badge-blue"
                      }>{o.status}</span>
                    </td>
                    <td className="p-4 text-text-muted">{formatDate(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.total_pages > 1 && (
            <div className="mt-6"><Pagination currentPage={data.page} totalPages={data.total_pages} onPageChange={setPage} /></div>
          )}
        </>
      )}
    </div>
  );
}
