"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../../../../lib/api";
import { formatDate, formatPrice, capitalize } from "../../../../lib/format";
import { useConfig } from "../../../../lib/config-context";
import LoadingSpinner from "../../../../components/LoadingSpinner";

// --- Types ---

interface OrderData {
  id: string;
  order_number: string;
  status: string;
  currency: string;
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  total: number;
  shipping_address: Record<string, string> | null;
  billing_address: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

interface OrderItem {
  product_id: string;
  variant_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  product_snapshot: {
    product_name?: string;
    variant_name?: string;
    product_sku?: string;
    variant_sku?: string;
    product_type?: string;
    image_url?: string;
    attributes?: Record<string, string>;
  };
}

interface CustomerInfo {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  rfm_segment: string | null;
  order_count: number;
  total_spent: number;
  currency: string;
}

interface PaymentInfo {
  provider: string;
  method: string | null;
  status: string;
  amount: number;
  currency: string;
  provider_payment_id: string | null;
  charge_id: string | null;
  created_at: string;
}

interface TouchPoint {
  campaign_id: string;
  campaign_name: string;
  medium: string;
  ts: string;
}

interface AttributionInfo {
  campaign_id: string | null;
  campaign_name: string | null;
  channel: string | null;
  conversion_event: string | null;
  conversion_value: number;
  converted_at: string | null;
  touch_sequence: TouchPoint[];
  utm: {
    source: string | null;
    medium: string | null;
    campaign: string | null;
    content: string | null;
    term: string | null;
  } | null;
}

interface AutomationInfo {
  flow_id: string;
  flow_name: string;
  trigger_event: string;
  status: string;
}

interface FullOrderDetail {
  order: OrderData;
  items: OrderItem[];
  customer: CustomerInfo | null;
  payment: PaymentInfo | null;
  attribution: AttributionInfo | null;
  automation: AutomationInfo | null;
}

// --- Helpers ---

const RFM_COLORS: Record<string, string> = {
  champion: "bg-green-500/20 text-green-300 border-green-500/30",
  loyal: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  potential_loyalist: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  new: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  at_risk: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  hibernating: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  lost: "bg-red-500/20 text-red-300 border-red-500/30",
};

function orderStatusBadge(status: string) {
  const map: Record<string, string> = {
    completed: "bg-green-500/20 text-green-300",
    accepted: "bg-green-500/20 text-green-300",
    processing: "bg-blue-500/20 text-blue-300",
    pending: "bg-yellow-500/20 text-yellow-300",
    rejected: "bg-red-500/20 text-red-300",
    refunded: "bg-orange-500/20 text-orange-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {status}
    </span>
  );
}

function paymentStatusBadge(status: string) {
  const map: Record<string, string> = {
    succeeded: "bg-green-500/20 text-green-300",
    pending: "bg-yellow-500/20 text-yellow-300",
    processing: "bg-blue-500/20 text-blue-300",
    failed: "bg-red-500/20 text-red-300",
    refunded: "bg-orange-500/20 text-orange-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {status}
    </span>
  );
}

function channelBadge(channel: string) {
  const map: Record<string, string> = {
    email: "bg-blue-500/20 text-blue-300",
    sms: "bg-green-500/20 text-green-300",
    whatsapp: "bg-emerald-500/20 text-emerald-300",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[channel] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {channel}
    </span>
  );
}

function productTypeBadge(type: string | undefined) {
  if (!type) return null;
  const map: Record<string, string> = {
    physical: "bg-blue-500/20 text-blue-300",
    digital: "bg-purple-500/20 text-purple-300",
    subscription: "bg-cyan-500/20 text-cyan-300",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded text-xs ${map[type] ?? "bg-gray-500/20 text-gray-300"}`}
    >
      {type === "subscription" ? "Subscription" : capitalize(type)}
    </span>
  );
}

function formatAddress(addr: Record<string, string> | null) {
  if (!addr) return null;
  const parts = [
    addr.line1,
    addr.line2,
    [addr.city, addr.state, addr.postal_code].filter(Boolean).join(", "),
    addr.country,
  ].filter(Boolean);
  return parts;
}

// --- Page ---

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { enable_marketing } = useConfig();

  const [data, setData] = useState<FullOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    try {
      const res = await apiFetch<FullOrderDetail>(
        `/ecommerce/admin/orders/${id}/full-detail`,
      );
      setData(res);
      setError(null);
    } catch {
      setError("Failed to load order details.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-20">
        <p className="text-text-muted mb-4">{error ?? "Order not found."}</p>
        <Link href="/admin/orders" className="text-accent hover:text-accent/80">
          Back to Orders
        </Link>
      </div>
    );
  }

  const { order: o, customer: cu, payment: pr, attribution: attr } = data;
  const customerName = cu
    ? [cu.first_name, cu.last_name].filter(Boolean).join(" ") || cu.email
    : "Unknown";
  const hasPhysical = data.items.some(
    (i) => i.product_snapshot.product_type === "physical",
  );

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/admin/orders")}
          className="p-1.5 rounded-lg hover:bg-white/5 transition-colors text-text-muted hover:text-text-primary"
        >
          <svg
            width="20"
            height="20"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <div className="flex-1">
          <h1 className="font-serif text-2xl font-bold">
            <span className="gradient-text">{o.order_number}</span>
          </h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-text-muted">
            {orderStatusBadge(o.status)}
            <span>{formatDate(o.created_at)}</span>
            <span>·</span>
            {cu ? (
              <Link
                href={`/admin/users/${cu.id}`}
                className="text-accent hover:text-accent/80"
              >
                {customerName}
              </Link>
            ) : (
              <span>{customerName}</span>
            )}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Subtotal</p>
          <p className="text-xl font-bold text-text-primary tabular-nums">
            {formatPrice(o.subtotal, o.currency)}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Discount</p>
          <p className="text-xl font-bold text-text-primary tabular-nums">
            {o.discount_amount > 0
              ? `-${formatPrice(o.discount_amount, o.currency)}`
              : "--"}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Tax</p>
          <p className="text-xl font-bold text-text-primary tabular-nums">
            {o.tax_amount > 0 ? formatPrice(o.tax_amount, o.currency) : "--"}
          </p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted mb-1">Total</p>
          <p className="text-2xl font-bold text-green-400 tabular-nums">
            {formatPrice(o.total, o.currency)}
          </p>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Line Items */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Items ({data.items.length})
            </h2>
            {data.items.length === 0 ? (
              <p className="text-sm text-text-muted py-4">No items</p>
            ) : (
              <div className="space-y-3">
                {data.items.map((item, idx) => {
                  const snap = item.product_snapshot;
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-3 p-3 rounded-lg bg-white/5"
                    >
                      {/* Image */}
                      {snap.image_url ? (
                        <img
                          src={snap.image_url}
                          alt={snap.product_name || "Product"}
                          className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
                        />
                      ) : (
                        <div className="w-12 h-12 rounded-lg bg-glass-bg flex items-center justify-center flex-shrink-0">
                          <svg
                            width="20"
                            height="20"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={1.5}
                            className="text-text-muted"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                            />
                          </svg>
                        </div>
                      )}

                      {/* Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-text-primary truncate">
                            {snap.product_name || "Unknown Product"}
                          </span>
                          {productTypeBadge(snap.product_type)}
                        </div>
                        {snap.variant_name && (
                          <p className="text-xs text-text-muted">
                            {snap.variant_name}
                          </p>
                        )}
                        {(snap.product_sku || snap.variant_sku) && (
                          <p className="text-xs text-text-muted font-mono">
                            SKU: {snap.variant_sku || snap.product_sku}
                          </p>
                        )}
                      </div>

                      {/* Price */}
                      <div className="text-right flex-shrink-0">
                        <p className="text-sm font-medium text-text-primary tabular-nums">
                          {formatPrice(item.total_price, o.currency)}
                        </p>
                        <p className="text-xs text-text-muted tabular-nums">
                          {item.quantity} x{" "}
                          {formatPrice(item.unit_price, o.currency)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Addresses */}
          {(o.shipping_address || o.billing_address) && (
            <div className="glass rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                Addresses
              </h2>
              <div
                className={`grid gap-6 ${o.shipping_address && o.billing_address ? "grid-cols-2" : "grid-cols-1"}`}
              >
                {o.shipping_address && hasPhysical && (
                  <div>
                    <h4 className="text-xs font-medium text-text-muted mb-2">
                      Shipping
                    </h4>
                    {formatAddress(o.shipping_address)?.map((line, i) => (
                      <p key={i} className="text-sm text-text-secondary">
                        {line}
                      </p>
                    ))}
                  </div>
                )}
                {o.billing_address && (
                  <div>
                    <h4 className="text-xs font-medium text-text-muted mb-2">
                      Billing
                    </h4>
                    {formatAddress(o.billing_address)?.map((line, i) => (
                      <p key={i} className="text-sm text-text-secondary">
                        {line}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Payment Info */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Payment
            </h2>
            {pr ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Status</span>
                  {paymentStatusBadge(pr.status)}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Amount</span>
                  <span className="text-sm font-medium text-text-primary tabular-nums">
                    {formatPrice(pr.amount, pr.currency)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Provider</span>
                  <span className="text-sm text-text-secondary">
                    {capitalize(pr.provider)}
                  </span>
                </div>
                {pr.method && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Method</span>
                    <span className="text-sm text-text-secondary">
                      {pr.method}
                    </span>
                  </div>
                )}
                {pr.provider_payment_id && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Payment ID</span>
                    <span
                      className="text-xs text-text-muted font-mono truncate ml-2"
                      title={pr.provider_payment_id}
                    >
                      {pr.provider_payment_id.slice(0, 24)}...
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-text-muted py-2">
                No payment recorded
              </p>
            )}
          </div>

          {/* Customer */}
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              Customer
            </h2>
            {cu ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Link
                    href={`/admin/users/${cu.id}`}
                    className="text-sm font-medium text-accent hover:text-accent/80"
                  >
                    {customerName}
                  </Link>
                  {cu.rfm_segment && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                        RFM_COLORS[cu.rfm_segment] ??
                        "bg-gray-500/20 text-gray-300 border-gray-500/30"
                      }`}
                    >
                      {cu.rfm_segment.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-muted font-mono">{cu.email}</p>
                <div className="flex items-center gap-4 text-xs text-text-muted pt-1">
                  <span>
                    <span className="text-text-primary font-medium">
                      {cu.order_count}
                    </span>{" "}
                    orders
                  </span>
                  <span>
                    <span className="text-text-primary font-medium">
                      {formatPrice(cu.total_spent, cu.currency)}
                    </span>{" "}
                    lifetime
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-text-muted py-2">
                Customer data unavailable
              </p>
            )}
          </div>

          {/* Attribution */}
          {enable_marketing && (
            <div className="glass rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                Campaign Attribution
              </h2>
              {attr?.campaign_name ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">
                      {attr.campaign_name}
                    </span>
                    {attr.channel && channelBadge(attr.channel)}
                  </div>
                  {attr.conversion_value > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-muted">
                        Conversion Value
                      </span>
                      <span className="text-sm text-text-primary tabular-nums">
                        ${attr.conversion_value.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {attr.converted_at && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-muted">
                        Converted At
                      </span>
                      <span className="text-xs text-text-secondary">
                        {formatDate(attr.converted_at)}
                      </span>
                    </div>
                  )}
                  {/* UTM Params */}
                  {attr.utm && (
                    <div className="pt-2 border-t border-glass-border/50">
                      <p className="text-xs text-text-muted mb-1.5">
                        UTM Parameters
                      </p>
                      <div className="grid grid-cols-2 gap-1">
                        {attr.utm.source && (
                          <p className="text-xs">
                            <span className="text-text-muted">Source:</span>{" "}
                            <span className="text-text-secondary">
                              {attr.utm.source}
                            </span>
                          </p>
                        )}
                        {attr.utm.medium && (
                          <p className="text-xs">
                            <span className="text-text-muted">Medium:</span>{" "}
                            <span className="text-text-secondary">
                              {attr.utm.medium}
                            </span>
                          </p>
                        )}
                        {attr.utm.campaign && (
                          <p className="text-xs">
                            <span className="text-text-muted">Campaign:</span>{" "}
                            <span className="text-text-secondary">
                              {attr.utm.campaign}
                            </span>
                          </p>
                        )}
                        {attr.utm.content && (
                          <p className="text-xs">
                            <span className="text-text-muted">Content:</span>{" "}
                            <span className="text-text-secondary">
                              {attr.utm.content}
                            </span>
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : attr?.utm ? (
                <div>
                  <p className="text-xs text-text-muted mb-2">
                    No direct campaign attribution, but UTM parameters detected:
                  </p>
                  <div className="grid grid-cols-2 gap-1">
                    {attr.utm.source && (
                      <p className="text-xs">
                        <span className="text-text-muted">Source:</span>{" "}
                        <span className="text-text-secondary">
                          {attr.utm.source}
                        </span>
                      </p>
                    )}
                    {attr.utm.medium && (
                      <p className="text-xs">
                        <span className="text-text-muted">Medium:</span>{" "}
                        <span className="text-text-secondary">
                          {attr.utm.medium}
                        </span>
                      </p>
                    )}
                    {attr.utm.campaign && (
                      <p className="text-xs">
                        <span className="text-text-muted">Campaign:</span>{" "}
                        <span className="text-text-secondary">
                          {attr.utm.campaign}
                        </span>
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-text-muted py-2">
                  No campaign attribution for this order
                </p>
              )}
            </div>
          )}

          {/* Automation */}
          {enable_marketing && (
            <div className="glass rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                Automation
              </h2>
              {data.automation ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">
                      {data.automation.flow_name}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        data.automation.status === "completed" ||
                        data.automation.status === "goal_reached"
                          ? "bg-green-500/20 text-green-300"
                          : data.automation.status === "active"
                            ? "bg-blue-500/20 text-blue-300"
                            : "bg-gray-500/20 text-gray-300"
                      }`}
                    >
                      {data.automation.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Trigger</span>
                    <span className="text-xs text-text-secondary font-mono">
                      {data.automation.trigger_event}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-text-muted py-2">
                  No automation flow
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Touch Sequence Timeline (full-width) */}
      {enable_marketing &&
        attr?.touch_sequence &&
        attr.touch_sequence.length > 1 && (
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold text-text-primary mb-4 uppercase tracking-wide">
              Customer Journey ({attr.touch_sequence.length} touches)
            </h2>
            <div className="flex items-start overflow-x-auto pb-2">
              {attr.touch_sequence.map((touch, idx) => (
                <div key={idx} className="flex items-start flex-shrink-0">
                  {/* Touch point */}
                  <div className="flex flex-col items-center w-40">
                    <div
                      className={`w-3 h-3 rounded-full flex-shrink-0 ${
                        idx === attr.touch_sequence.length - 1
                          ? "bg-green-400"
                          : "bg-accent"
                      }`}
                    />
                    <div className="mt-2 text-center">
                      <p className="text-xs font-medium text-text-primary truncate max-w-[140px]">
                        {touch.campaign_name}
                      </p>
                      <div className="mt-1">{channelBadge(touch.medium)}</div>
                      <p className="text-xs text-text-muted mt-1">
                        {formatDate(touch.ts)}
                      </p>
                    </div>
                  </div>
                  {/* Connector line */}
                  {idx < attr.touch_sequence.length - 1 && (
                    <div className="flex items-center flex-shrink-0 mt-1">
                      <div className="w-12 h-px bg-glass-border" />
                      <svg
                        width="8"
                        height="8"
                        viewBox="0 0 8 8"
                        className="text-glass-border -ml-1"
                      >
                        <path d="M0 0 L8 4 L0 8 Z" fill="currentColor" />
                      </svg>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
    </div>
  );
}
