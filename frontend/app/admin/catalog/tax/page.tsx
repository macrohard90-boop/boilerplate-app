"use client";

export default function TaxRatesPage() {
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
          d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z"
        />
      </svg>
      <p className="text-lg text-text-secondary mb-2">Tax Rates</p>
      <p className="text-sm text-text-muted">
        Coming soon. Configure tax rates and rules for different regions.
      </p>
    </div>
  );
}
