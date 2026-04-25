"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";

interface CampaignRanking {
  campaign_id: string;
  name: string;
  medium: string;
  sent_at: string | null;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
  conversions: number;
  revenue: number;
  conversion_rate: number;
}

interface RankingsTabProps {
  onSelectCampaign: (id: string, name: string) => void;
}

const MODELS = [
  { value: "last_click", label: "Last Click" },
  { value: "first_touch", label: "First Touch" },
  { value: "linear", label: "Linear" },
  { value: "time_decay", label: "Time Decay" },
  { value: "u_shaped", label: "U-Shaped" },
];

const DAY_OPTIONS = [30, 60, 90, 180, 365];

function formatCurrency(n: number): string {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2 });
}

function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

export default function RankingsTab({ onSelectCampaign }: RankingsTabProps) {
  const [rankings, setRankings] = useState<CampaignRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [model, setModel] = useState("last_click");
  const [days, setDays] = useState(90);
  const [sortKey, setSortKey] = useState<keyof CampaignRanking>("revenue");
  const [sortAsc, setSortAsc] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<CampaignRanking[]>(
        `/marketing/analytics/effectiveness/rankings?model=${model}&days=${days}&limit=50`,
      );
      setRankings(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [model, days]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSort = (key: keyof CampaignRanking) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sorted = [...rankings].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? cmp : -cmp;
  });

  const SortHeader = ({
    label,
    field,
    align,
  }: {
    label: string;
    field: keyof CampaignRanking;
    align?: string;
  }) => (
    <th
      className={`px-3 py-3 cursor-pointer hover:text-text-primary transition-colors ${align || ""}`}
      onClick={() => handleSort(field)}
    >
      {label}
      {sortKey === field && (
        <span className="ml-1 text-accent-pink">{sortAsc ? "^" : "v"}</span>
      )}
    </th>
  );

  const mediumBadge = (m: string) => {
    const cls =
      m === "email"
        ? "badge-blue"
        : m === "sms"
          ? "badge-purple"
          : m === "whatsapp"
            ? "badge-green"
            : "badge-purple";
    return <span className={`badge ${cls} text-xs`}>{m}</span>;
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Attribution:</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="input-glass text-sm py-1 px-2"
          >
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">Period:</label>
          <div className="flex gap-1">
            {DAY_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2 py-1 text-xs rounded transition-all ${
                  days === d
                    ? "bg-accent-pink/20 text-accent-pink"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner size="lg" className="py-20" />
      ) : rankings.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center text-text-secondary">
          No campaign data for this period.
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted border-b border-glass-border text-xs">
                  <SortHeader label="Campaign" field="name" />
                  <th className="px-3 py-3">Channel</th>
                  <SortHeader label="Sent" field="sent" align="text-right" />
                  <SortHeader
                    label="Open %"
                    field="open_rate"
                    align="text-right"
                  />
                  <SortHeader
                    label="Click %"
                    field="click_rate"
                    align="text-right"
                  />
                  <SortHeader
                    label="Conv."
                    field="conversions"
                    align="text-right"
                  />
                  <SortHeader
                    label="Revenue"
                    field="revenue"
                    align="text-right"
                  />
                  <SortHeader
                    label="Conv %"
                    field="conversion_rate"
                    align="text-right"
                  />
                </tr>
              </thead>
              <tbody>
                {sorted.map((c) => (
                  <tr
                    key={c.campaign_id}
                    onClick={() => onSelectCampaign(c.campaign_id, c.name)}
                    className="border-b border-glass-border/50 hover:bg-glass-hover cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-3 max-w-[200px]">
                      <span className="text-text-primary hover:text-accent-blue transition-colors">
                        {c.name}
                      </span>
                      {c.sent_at && (
                        <span className="block text-xs text-text-muted mt-0.5">
                          {new Date(c.sent_at).toLocaleDateString()}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3">{mediumBadge(c.medium)}</td>
                    <td className="px-3 py-3 text-right font-mono text-text-secondary">
                      {formatNumber(c.sent)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-accent-blue">
                      {formatPercent(c.open_rate)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-accent-purple">
                      {formatPercent(c.click_rate)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-text-secondary">
                      {c.conversions}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-accent-green font-medium">
                      {formatCurrency(c.revenue)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-accent-green">
                      {formatPercent(c.conversion_rate)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
