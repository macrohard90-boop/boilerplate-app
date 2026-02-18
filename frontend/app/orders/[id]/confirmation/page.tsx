"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
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
  order_number: string;
  status: string;
  total_amount: number;
  currency: string;
  created_at: string;
  items: OrderItem[];
}

interface PaymentStatus {
  order_id: string;
  order_status: string;
  payment_status: string | null;
  amount: number;
  currency: string;
}

type RedirectStatus = "succeeded" | "processing" | "requires_payment_method" | string;

export default function OrderConfirmationPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const redirectStatus = searchParams.get("redirect_status") as RedirectStatus | null;
  const [order, setOrder] = useState<Order | null>(null);
  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load order details
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

  // Poll payment status until terminal
  useEffect(() => {
    if (!id) return;

    async function checkPayment() {
      try {
        const status = await apiFetch<PaymentStatus>(`/payments/orders/${id}/payment`);
        setPaymentStatus(status.payment_status);
        if (status.order_status) {
          setOrder((prev) => prev ? { ...prev, status: status.order_status } : prev);
        }
        // Stop polling on terminal status
        if (["succeeded", "failed", "refunded"].includes(status.payment_status || "")) {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {}
    }

    // Initial check
    checkPayment();

    // Poll every 3 seconds
    pollRef.current = setInterval(checkPayment, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
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

  // Determine display status from Stripe redirect or polled payment status
  const effectiveStatus = paymentStatus || redirectStatus || "processing";

  const isSuccess = effectiveStatus === "succeeded" || order.status === "completed";
  const isProcessing = effectiveStatus === "processing" && order.status !== "completed";
  const isFailed = effectiveStatus === "failed" || effectiveStatus === "requires_payment_method" || order.status === "rejected";

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Status banner */}
      <div className="glass rounded-2xl p-8 text-center mb-8">
        {isSuccess && (
          <>
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-accent-green/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-accent-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="font-serif text-3xl font-bold gradient-text mb-2">Payment Successful!</h1>
            <p className="text-text-secondary">Thank you for your purchase</p>
          </>
        )}
        {isProcessing && (
          <>
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-500/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-yellow-400 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <h1 className="font-serif text-3xl font-bold text-yellow-400 mb-2">Payment Processing</h1>
            <p className="text-text-secondary">Your payment is being processed. We&apos;ll update you when it completes.</p>
          </>
        )}
        {isFailed && (
          <>
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="font-serif text-3xl font-bold text-red-400 mb-2">Payment Failed</h1>
            <p className="text-text-secondary mb-4">Your payment could not be processed. Please try again.</p>
            <Link href={`/orders/${id}/pay`} className="btn-primary text-sm">Retry Payment</Link>
          </>
        )}
        <p className="text-xs text-text-muted mt-2">Order #{order.order_number || order.id.slice(0, 8)}</p>
      </div>

      {/* Order details */}
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
          <p>Status: <span className={
            order.status === "completed" ? "badge-green" :
            order.status === "rejected" ? "badge-red" :
            "badge-yellow"
          }>{order.status}</span></p>
        </div>
      </div>

      <div className="flex gap-4 mt-8 justify-center">
        <Link href="/dashboard/orders" className="btn-secondary text-sm">View Orders</Link>
        <Link href="/products" className="btn-primary text-sm">Continue Shopping</Link>
      </div>
    </div>
  );
}
