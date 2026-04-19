"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { formatDate } from "../../../lib/format";
import LoadingSpinner from "../../../components/LoadingSpinner";
import { CONSENT_TYPES } from "../../../lib/consent-types";

// --- Types matching backend response schemas ---

interface ConsentTypeStat {
  consent_type: string;
  total_grants: number;
  total_revokes: number;
}

interface AuditLogItem {
  id: string;
  user_id: string;
  action: string;
  consent_type: string;
  old_value: boolean | null;
  new_value: boolean | null;
  ip_address: string | null;
  created_at: string;
}

interface ExportRequest {
  id: string;
  user_id: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
}

interface DeletionRequest {
  id: string;
  user_id: string;
  status: string;
  requested_at: string;
  grace_period_ends: string | null;
  completed_at: string | null;
}

function getConsentLabel(key: string): string {
  return CONSENT_TYPES.find((ct) => ct.key === key)?.label ?? key;
}

export default function AdminGdprPage() {
  const [consentStats, setConsentStats] = useState<ConsentTypeStat[]>([]);
  const [auditItems, setAuditItems] = useState<AuditLogItem[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [auditFilter, setAuditFilter] = useState("");
  const [exports, setExports] = useState<ExportRequest[]>([]);
  const [deletions, setDeletions] = useState<DeletionRequest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<{ stats: ConsentTypeStat[] }>("/gdpr/admin/consent-stats").catch(
        () => ({ stats: [] }),
      ),
      apiFetch<{ items: ExportRequest[] }>("/gdpr/admin/exports").catch(() => ({
        items: [],
      })),
      apiFetch<{ items: DeletionRequest[] }>("/gdpr/admin/deletions").catch(
        () => ({ items: [] }),
      ),
    ])
      .then(([stats, exp, del]) => {
        setConsentStats(stats.stats || []);
        setExports(exp.items || []);
        setDeletions(del.items || []);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({
      page: String(auditPage),
      page_size: "10",
    });
    if (auditFilter) params.set("consent_type", auditFilter);
    apiFetch<{ items: AuditLogItem[]; total: number }>(
      `/gdpr/admin/audit?${params}`,
    )
      .then((d) => {
        setAuditItems(d.items || []);
        setAuditTotal(d.total || 0);
      })
      .catch(() => {
        setAuditItems([]);
        setAuditTotal(0);
      });
  }, [auditPage, auditFilter]);

  if (loading) return <LoadingSpinner className="py-20" />;

  const auditTotalPages = Math.max(1, Math.ceil(auditTotal / 10));

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">GDPR Management</span>
      </h1>

      {/* Consent Stats */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Consent Statistics
        </h2>
        {consentStats.length === 0 ? (
          <p className="text-sm text-text-muted">No consent data yet</p>
        ) : (
          <div className="space-y-4">
            {consentStats.map((stat) => {
              const total = stat.total_grants + stat.total_revokes;
              const rate =
                total > 0 ? Math.round((stat.total_grants / total) * 100) : 0;
              return (
                <div key={stat.consent_type}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-text-primary">
                      {getConsentLabel(stat.consent_type)}
                    </span>
                    <div className="flex items-center gap-3 text-xs text-text-muted">
                      <span className="text-accent-green">
                        {stat.total_grants} grants
                      </span>
                      <span className="text-accent-pink">
                        {stat.total_revokes} revokes
                      </span>
                      <span className="font-medium text-text-primary">
                        {rate}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-2 rounded-full bg-glass-bg overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent-green/60 transition-all"
                      style={{ width: `${rate}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Consent Audit Log */}
      <div className="glass rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">
            Consent Audit Log
          </h2>
          <select
            value={auditFilter}
            onChange={(e) => {
              setAuditFilter(e.target.value);
              setAuditPage(1);
            }}
            className="text-xs bg-glass-bg border border-glass-border rounded-lg px-3 py-1.5 text-text-secondary focus:outline-none focus:border-accent-purple/50"
          >
            <option value="">All types</option>
            {CONSENT_TYPES.map((ct) => (
              <option key={ct.key} value={ct.key}>
                {ct.label}
              </option>
            ))}
          </select>
        </div>

        {auditItems.length === 0 ? (
          <p className="text-sm text-text-muted">No audit log entries</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-muted border-b border-glass-border/50">
                    <th className="pb-2 pr-4">Time</th>
                    <th className="pb-2 pr-4">User</th>
                    <th className="pb-2 pr-4">Action</th>
                    <th className="pb-2 pr-4">Consent Type</th>
                    <th className="pb-2">IP</th>
                  </tr>
                </thead>
                <tbody>
                  {auditItems.map((item) => (
                    <tr
                      key={item.id}
                      className="border-b border-glass-border/30 last:border-0"
                    >
                      <td className="py-2 pr-4 text-xs text-text-muted whitespace-nowrap">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="py-2 pr-4 font-mono text-xs text-text-secondary">
                        {item.user_id.slice(0, 8)}
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={
                            item.action === "grant"
                              ? "badge-green"
                              : "badge-pink"
                          }
                        >
                          {item.action}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-text-secondary">
                        {getConsentLabel(item.consent_type)}
                      </td>
                      <td className="py-2 text-xs text-text-muted font-mono">
                        {item.ip_address || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {auditTotalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-glass-border/30">
                <p className="text-xs text-text-muted">
                  Page {auditPage} of {auditTotalPages} ({auditTotal} entries)
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                    disabled={auditPage <= 1}
                    className="btn-secondary text-xs !px-3 !py-1 disabled:opacity-30"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() =>
                      setAuditPage((p) => Math.min(auditTotalPages, p + 1))
                    }
                    disabled={auditPage >= auditTotalPages}
                    className="btn-secondary text-xs !px-3 !py-1 disabled:opacity-30"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Export Requests */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">
          Data Export Requests
        </h2>
        {exports.length === 0 ? (
          <p className="text-sm text-text-muted">No export requests</p>
        ) : (
          <div className="space-y-2">
            {exports.map((req) => (
              <div
                key={req.id}
                className="flex justify-between items-center py-2 border-b border-glass-border/50 last:border-0"
              >
                <div>
                  <p className="text-sm text-text-primary font-mono">
                    {req.user_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatDate(req.requested_at)}
                  </p>
                </div>
                <span
                  className={
                    req.status === "completed" ? "badge-green" : "badge-blue"
                  }
                >
                  {req.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Deletion Requests */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-accent-pink mb-4">
          Deletion Requests
        </h2>
        {deletions.length === 0 ? (
          <p className="text-sm text-text-muted">No deletion requests</p>
        ) : (
          <div className="space-y-2">
            {deletions.map((req) => (
              <div
                key={req.id}
                className="flex justify-between items-center py-2 border-b border-glass-border/50 last:border-0"
              >
                <div>
                  <p className="text-sm text-text-primary font-mono">
                    {req.user_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-text-muted">
                    Requested: {formatDate(req.requested_at)}
                    {req.grace_period_ends && (
                      <span className="ml-2">
                        | Grace ends: {formatDate(req.grace_period_ends)}
                      </span>
                    )}
                  </p>
                </div>
                <span
                  className={
                    req.status === "completed"
                      ? "badge-green"
                      : req.status === "grace_period"
                        ? "badge-pink"
                        : "badge-blue"
                  }
                >
                  {req.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
