"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "../../lib/auth-context";
import { apiFetch } from "../../lib/api";
import { formatPrice, formatDate } from "../../lib/format";

interface Order {
  id: string;
  status: string;
  total_amount: number;
  currency: string;
  created_at: string;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);

  useEffect(() => {
    apiFetch<{ items: Order[] }>("/ecommerce/orders?page=1&page_size=5")
      .then((data) => setRecentOrders(data.items || []))
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        Welcome back, <span className="gradient-text">{user?.first_name || user?.email}</span>
      </h1>

      {/* Account info */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Email</p>
          <p className="text-sm text-text-primary">{user?.email}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Role</p>
          <p className="text-sm">
            <span className={
              user?.role === "admin" ? "badge-pink" :
              user?.role === "merchant" ? "badge-blue" : "badge-green"
            }>
              {user?.role}
            </span>
          </p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted mb-1">Member since</p>
          <p className="text-sm text-text-primary">{user?.created_at ? formatDate(user.created_at) : "—"}</p>
        </div>
      </div>

      {/* Recent orders */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">Recent Orders</h2>
          <Link href="/dashboard/orders" className="text-sm text-accent-purple hover:text-accent-blue transition-colors">
            View all
          </Link>
        </div>

        {recentOrders.length === 0 ? (
          <p className="text-text-secondary text-sm py-4">No orders yet. <Link href="/products" className="text-accent-purple hover:text-accent-blue transition-colors">Start shopping</Link></p>
        ) : (
          <div className="space-y-3">
            {recentOrders.map((order) => (
              <Link key={order.id} href={`/dashboard/orders/${order.id}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-glass-hover transition-colors group">
                <div>
                  <p className="text-sm text-text-primary group-hover:text-accent-blue transition-colors">
                    Order #{order.id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-text-muted">{formatDate(order.created_at)}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-text-primary">{formatPrice(order.total_amount, order.currency)}</p>
                  <span className={`text-xs ${
                    order.status === "completed" ? "badge-green" :
                    order.status === "cancelled" ? "badge-pink" : "badge-blue"
                  }`}>
                    {order.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
