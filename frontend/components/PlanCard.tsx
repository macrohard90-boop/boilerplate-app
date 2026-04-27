"use client";

import { useState } from "react";
import Image from "next/image";
import { formatPrice } from "../lib/format";
import { useCart } from "../lib/cart-context";
import { useToast } from "./Toast";

const INTERVAL_LABELS: Record<string, string> = {
  day: "/day",
  week: "/wk",
  month: "/mo",
  year: "/yr",
};

interface PlanCardProps {
  id: string;
  name: string;
  price: number; // cents
  currency?: string;
  description?: string; // newline-separated benefits
  recurring_interval?: string | null;
  trial_period_days?: number | null;
  image_url?: string | null;
}

export default function PlanCard({
  id,
  name,
  price,
  currency = "USD",
  description,
  recurring_interval,
  trial_period_days,
  image_url,
}: PlanCardProps) {
  const { addItem } = useCart();
  const { showToast } = useToast();
  const [adding, setAdding] = useState(false);

  const benefits = description
    ? description.split("\n").filter((line) => line.trim())
    : [];

  const handleGetAccess = async () => {
    setAdding(true);
    try {
      await addItem(id);
      showToast(`${name} added to cart`, "success");
    } catch {
      showToast("Failed to add plan", "error");
    }
    setAdding(false);
  };

  return (
    <div className="glass rounded-xl overflow-hidden transition-all duration-300 hover:border-accent-purple/30 hover:shadow-lg hover:shadow-accent-purple/5 flex flex-col h-full">
      {/* Image */}
      {image_url && (
        <div className="relative w-full h-40">
          <Image
            src={image_url}
            alt={name}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover"
          />
        </div>
      )}

      <div className="flex flex-col flex-1 p-6">
        {/* Plan Name */}
        <h3 className="text-lg font-semibold text-text-primary">{name}</h3>

        {/* Price */}
        <div className="mt-3">
          <span className="text-3xl font-bold text-text-primary">
            {formatPrice(price, currency)}
          </span>
          {recurring_interval && (
            <span className="text-base font-normal text-text-muted">
              {INTERVAL_LABELS[recurring_interval] || `/${recurring_interval}`}
            </span>
          )}
        </div>

        {/* Trial Badge */}
        {trial_period_days != null && trial_period_days > 0 && (
          <div className="mt-2">
            <span className="inline-block text-xs font-medium text-accent-blue bg-accent-blue/10 border border-accent-blue/20 rounded-full px-2.5 py-0.5">
              {trial_period_days}-day free trial
            </span>
          </div>
        )}

        {/* Divider */}
        {benefits.length > 0 && (
          <div className="border-t border-glass-border my-4" />
        )}

        {/* Benefits List */}
        {benefits.length > 0 && (
          <ul className="space-y-2.5 flex-1">
            {benefits.slice(0, 6).map((benefit, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-text-secondary"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4 text-accent-green shrink-0 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <span>{benefit.trim()}</span>
              </li>
            ))}
          </ul>
        )}

        {/* CTA */}
        <div className="mt-5">
          <button
            onClick={handleGetAccess}
            disabled={adding}
            className="block w-full text-center btn-primary py-2 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {adding ? "Adding..." : "Get Access"}
          </button>
        </div>
      </div>
    </div>
  );
}
