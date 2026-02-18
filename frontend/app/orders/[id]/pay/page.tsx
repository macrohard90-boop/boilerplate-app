"use client";

import { useEffect, useState, FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { apiFetch } from "../../../../lib/api";
import { getStripe } from "../../../../lib/stripe";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface PaymentStatus {
  order_id: string;
  order_status: string;
  payment_status: string | null;
  client_secret: string | null;
  amount: number;
  currency: string;
}

function RetryPaymentForm({ orderId }: { orderId: string }) {
  const stripe = useStripe();
  const elements = useElements();
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;

    setPaying(true);
    setError(null);

    const { error: stripeError } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/orders/${orderId}/confirmation`,
      },
    });

    if (stripeError) {
      setError(stripeError.message || "Payment failed. Please try again.");
    }
    setPaying(false);
  }

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement options={{ layout: "tabs" }} />
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={!stripe || paying}
        className="btn-primary w-full mt-6 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {paying ? "Processing..." : "Retry Payment"}
      </button>
    </form>
  );
}

export default function PaymentRetryPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<PaymentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stripePromise] = useState(() => getStripe());

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<PaymentStatus>(`/payments/orders/${id}/payment`);
        setStatus(data);

        // If already succeeded, redirect to confirmation
        if (data.payment_status === "succeeded" || data.order_status === "completed") {
          router.replace(`/orders/${id}/confirmation`);
          return;
        }

        // If no client_secret available, can't retry
        if (!data.client_secret) {
          setError("This payment cannot be retried. Please start a new order.");
        }
      } catch {
        setError("Unable to load payment details.");
      }
      setLoading(false);
    }
    if (id) load();
  }, [id, router]);

  if (loading) return <LoadingSpinner size="lg" className="py-40" />;

  if (error || !status?.client_secret) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h1 className="font-serif text-2xl font-bold text-red-400 mb-4">Cannot Retry</h1>
        <p className="text-text-secondary mb-6">{error || "Payment session expired."}</p>
        <Link href="/products" className="btn-primary text-sm">Browse Products</Link>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="glass rounded-2xl p-6">
        <h1 className="font-serif text-2xl font-bold gradient-text mb-2">Retry Payment</h1>
        <p className="text-sm text-text-secondary mb-6">
          Your previous payment attempt failed. Please try again with a different payment method.
        </p>

        <Elements
          stripe={stripePromise}
          options={{
            clientSecret: status.client_secret,
            appearance: {
              theme: "night",
              variables: {
                colorPrimary: "#a855f7",
                colorBackground: "#1a1a2e",
                colorText: "#e2e8f0",
                colorDanger: "#ef4444",
                borderRadius: "8px",
              },
            },
          }}
        >
          <RetryPaymentForm orderId={id} />
        </Elements>
      </div>

      <div className="text-center mt-6">
        <Link href="/dashboard/orders" className="text-sm text-text-muted hover:text-text-secondary">
          Back to Orders
        </Link>
      </div>
    </div>
  );
}
