"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "../../../../../lib/api";
import { formatDate } from "../../../../../lib/format";
import LoadingSpinner from "../../../../../components/LoadingSpinner";

// --- Types ---

interface CampaignStats {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  unsubscribed: number;
}

interface CampaignVariant {
  id: string;
  label: string;
  subject: string;
  weight: number;
}

interface VariantStats {
  label: string;
  subject: string;
  weight: number;
  stats: CampaignStats;
}

interface CampaignDetail {
  id: string;
  name: string;
  subject: string;
  template_id: string;
  template_display_name: string | null;
  status: string;
  medium: string;
  recipient_count: number;
  sent_at: string | null;
  created_at: string;
  scheduled_at: string | null;
  stats: CampaignStats;
  variants: CampaignVariant[];
  variant_stats: VariantStats[];
}

interface Recipient {
  id: string;
  to_address: string;
  first_name: string | null;
  last_name: string | null;
  variant_id: string | null;
  variant_label: string | null;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
}

interface RecipientList {
  items: Recipient[];
  total: number;
  page: number;
  per_page: number;
}

// --- Helpers ---

function statusBadge(status: string) {
  const map: Record<string, string> = {
    draft: "badge-purple",
    scheduled: "badge-blue",
    sending: "badge-blue",
    sent: "badge-green",
    cancelled: "badge-pink",
  };
  return map[status] ?? "badge-purple";
}

function recipientBadge(status: string) {
  const map: Record<string, string> = {
    sending: "badge-blue",
    sent: "badge-blue",
    delivered: "badge-green",
    opened: "badge-purple",
    clicked: "badge-green",
    bounced: "badge-pink",
    complained: "badge-pink",
    unsubscribed: "badge-pink",
    failed: "badge-pink",
  };
  return map[status] ?? "badge-purple";
}

function pct(value: number, total: number): string {
  if (!total) return "0%";
  return `${((value / total) * 100).toFixed(1)}%`;
}

function fmtTime(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
}

// --- KPI Card ---

function KpiCard({
  label,
  value,
  percentage,
  color,
}: {
  label: string;
  value: number;
  percentage: string | null;
  color: string;
}) {
  return (
    <div className="glass rounded-xl p-5">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color} tabular-nums`}>{value}</p>
      {percentage && (
        <p className="text-xs text-text-muted mt-1">{percentage}</p>
      )}
    </div>
  );
}

// --- Status filter options ---

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "sending", label: "Sending" },
  { value: "sent", label: "Sent" },
  { value: "delivered", label: "Delivered" },
  { value: "opened", label: "Opened" },
  { value: "clicked", label: "Clicked" },
  { value: "bounced", label: "Bounced" },
  { value: "failed", label: "Failed" },
  { value: "unsubscribed", label: "Unsubscribed" },
];

// --- Page ---

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [recipients, setRecipients] = useState<RecipientList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const perPage = 20;

  const fetchCampaign = useCallback(async () => {
    try {
      const data = await apiFetch<CampaignDetail>(
        `/marketing/admin/campaigns/${id}`,
      );
      setCampaign(data);
      setError(null);
    } catch {
      setError("Failed to load campaign.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchRecipients = useCallback(async () => {
    try {
      const qs = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (statusFilter) qs.set("status", statusFilter);
      if (selectedVariant) qs.set("variant_id", selectedVariant);
      const data = await apiFetch<RecipientList>(
        `/marketing/admin/campaigns/${id}/recipients?${qs}`,
      );
      setRecipients(data);
    } catch {
      // silent
    }
  }, [id, page, statusFilter, selectedVariant]);

  useEffect(() => {
    fetchCampaign();
  }, [fetchCampaign]);

  useEffect(() => {
    fetchRecipients();
  }, [fetchRecipients]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="p-8">
        <p className="text-accent-pink">{error ?? "Campaign not found."}</p>
        <button
          onClick={() => router.push("/admin/marketing")}
          className="text-accent-blue hover:underline text-sm mt-2"
        >
          Back to campaigns
        </button>
      </div>
    );
  }

  // Determine which stats to show based on selected variant
  const hasVariants = campaign.variants.length > 1;
  const activeStats: CampaignStats = selectedVariant
    ? (campaign.variant_stats.find(
        (vs) =>
          campaign.variants.find((v) => v.id === selectedVariant)?.label ===
          vs.label,
      )?.stats ?? campaign.stats)
    : campaign.stats;
  const s = activeStats;
  const totalPages = recipients ? Math.ceil(recipients.total / perPage) : 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => router.push("/admin/marketing")}
          className="mt-1 text-text-muted hover:text-text-primary transition-colors"
          title="Back to campaigns"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-serif text-2xl font-bold gradient-text truncate">
              {campaign.name}
            </h1>
            <span className={`badge ${statusBadge(campaign.status)}`}>
              {campaign.status}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-1 text-sm text-text-muted flex-wrap">
            {campaign.template_display_name && (
              <span>Template: {campaign.template_display_name}</span>
            )}
            {campaign.subject && (
              <span className="truncate max-w-xs" title={campaign.subject}>
                Subject: {campaign.subject}
              </span>
            )}
            {campaign.sent_at && (
              <span>Sent {formatDate(campaign.sent_at)}</span>
            )}
            {!campaign.sent_at && campaign.scheduled_at && (
              <span>Scheduled {formatDate(campaign.scheduled_at)}</span>
            )}
            {!campaign.sent_at && !campaign.scheduled_at && (
              <span>Created {formatDate(campaign.created_at)}</span>
            )}
          </div>
        </div>
      </div>

      {/* Variant Tabs */}
      {hasVariants && (
        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => {
              setSelectedVariant(null);
              setPage(1);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              selectedVariant === null
                ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/40"
                : "glass text-text-muted hover:text-text-primary"
            }`}
          >
            All
          </button>
          {campaign.variants.map((v) => (
            <button
              key={v.id}
              onClick={() => {
                setSelectedVariant(v.id);
                setPage(1);
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedVariant === v.id
                  ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/40"
                  : "glass text-text-muted hover:text-text-primary"
              }`}
              title={v.subject}
            >
              {v.label}
              <span className="text-xs ml-1.5 opacity-70 max-w-[120px] truncate inline-block align-bottom">
                {v.subject}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard
          label="Sent"
          value={s.sent}
          percentage={null}
          color="text-accent-blue"
        />
        <KpiCard
          label="Delivered"
          value={s.delivered}
          percentage={s.sent ? pct(s.delivered, s.sent) : null}
          color="text-accent-green"
        />
        <KpiCard
          label="Opened"
          value={s.opened}
          percentage={s.delivered ? pct(s.opened, s.delivered) : null}
          color="text-accent-purple"
        />
        <KpiCard
          label="Clicked"
          value={s.clicked}
          percentage={s.opened ? pct(s.clicked, s.opened) : null}
          color="text-accent-blue"
        />
        <KpiCard
          label="Bounced"
          value={s.bounced}
          percentage={s.sent ? pct(s.bounced, s.sent) : null}
          color="text-accent-pink"
        />
        <KpiCard
          label="Unsubscribed"
          value={s.unsubscribed}
          percentage={s.sent ? pct(s.unsubscribed, s.sent) : null}
          color="text-accent-pink"
        />
      </div>

      {/* Recipients Table */}
      <div className="glass rounded-xl p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold text-text-primary">
            Recipients
            {recipients && (
              <span className="text-sm font-normal text-text-muted ml-2">
                ({recipients.total})
              </span>
            )}
          </h2>
          <div className="flex gap-2">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="input-glass text-sm py-1.5 px-3"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border text-left text-text-muted">
                <th className="p-3 font-medium">Recipient</th>
                {hasVariants && !selectedVariant && (
                  <th className="p-3 font-medium">Variant</th>
                )}
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Sent</th>
                <th className="p-3 font-medium">Delivered</th>
                <th className="p-3 font-medium">Opened</th>
                <th className="p-3 font-medium">Clicked</th>
                <th className="p-3 font-medium">Error</th>
              </tr>
            </thead>
            <tbody>
              {recipients?.items.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3 text-text-primary">
                    <div>{r.to_address}</div>
                    {(r.first_name || r.last_name) && (
                      <div className="text-xs text-text-muted">
                        {[r.first_name, r.last_name].filter(Boolean).join(" ")}
                      </div>
                    )}
                  </td>
                  {hasVariants && !selectedVariant && (
                    <td className="p-3 text-text-muted text-xs">
                      {r.variant_label ?? "\u2014"}
                    </td>
                  )}
                  <td className="p-3">
                    <span className={`badge ${recipientBadge(r.status)}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="p-3 text-text-muted tabular-nums">
                    {fmtDateTime(r.sent_at)}
                  </td>
                  <td className="p-3 text-text-muted tabular-nums">
                    {fmtTime(r.delivered_at)}
                  </td>
                  <td className="p-3 text-text-muted tabular-nums">
                    {fmtTime(r.opened_at)}
                  </td>
                  <td className="p-3 text-text-muted tabular-nums">
                    {fmtTime(r.clicked_at)}
                  </td>
                  <td className="p-3 text-text-muted text-xs max-w-[200px] truncate">
                    {r.error_message ?? "\u2014"}
                  </td>
                </tr>
              ))}
              {recipients && recipients.items.length === 0 && (
                <tr>
                  <td
                    colSpan={hasVariants && !selectedVariant ? 8 : 7}
                    className="p-8 text-center text-text-muted"
                  >
                    No recipients
                    {statusFilter ? ` with status "${statusFilter}"` : ""}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-glass-border">
            <p className="text-xs text-text-muted">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="btn-secondary text-xs disabled:opacity-30"
              >
                Previous
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="btn-secondary text-xs disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
