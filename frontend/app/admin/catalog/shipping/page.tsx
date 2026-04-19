"use client";

export default function ShippingRatesPage() {
  return (
    <div className="glass rounded-xl p-12 text-center">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-12 w-12 mx-auto text-text-muted mb-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
        />
      </svg>
      <p className="text-lg text-text-secondary mb-2">Shipping Rates</p>
      <p className="text-sm text-text-muted">
        Coming soon. Configure shipping rates and zones for your products.
      </p>
    </div>
  );
}
