"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { formatDate } from "../../../lib/format";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface ExportRequest {
  id: string;
  user_id: string;
  status: string;
  created_at: string;
}

interface DeletionRequest {
  id: string;
  user_id: string;
  status: string;
  scheduled_at: string;
  created_at: string;
}

export default function AdminGdprPage() {
  const [exports, setExports] = useState<ExportRequest[]>([]);
  const [deletions, setDeletions] = useState<DeletionRequest[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: ExportRequest[] }>("/gdpr/admin/exports").catch(() => ({ items: [] })),
      apiFetch<{ items: DeletionRequest[] }>("/gdpr/admin/deletions").catch(() => ({ items: [] })),
    ]).then(([exp, del]) => {
      setExports(exp.items || []);
      setDeletions(del.items || []);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">GDPR Management</span>
      </h1>

      {/* Export requests */}
      <div className="glass rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Data Export Requests</h2>
        {exports.length === 0 ? (
          <p className="text-sm text-text-muted">No export requests</p>
        ) : (
          <div className="space-y-2">
            {exports.map((req) => (
              <div key={req.id} className="flex justify-between items-center py-2 border-b border-glass-border/50 last:border-0">
                <div>
                  <p className="text-sm text-text-primary font-mono">{req.user_id.slice(0, 8)}</p>
                  <p className="text-xs text-text-muted">{formatDate(req.created_at)}</p>
                </div>
                <span className={req.status === "completed" ? "badge-green" : "badge-blue"}>{req.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Deletion requests */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-accent-pink mb-4">Deletion Requests</h2>
        {deletions.length === 0 ? (
          <p className="text-sm text-text-muted">No deletion requests</p>
        ) : (
          <div className="space-y-2">
            {deletions.map((req) => (
              <div key={req.id} className="flex justify-between items-center py-2 border-b border-glass-border/50 last:border-0">
                <div>
                  <p className="text-sm text-text-primary font-mono">{req.user_id.slice(0, 8)}</p>
                  <p className="text-xs text-text-muted">Requested: {formatDate(req.created_at)}</p>
                </div>
                <span className={req.status === "completed" ? "badge-green" : req.status === "pending" ? "badge-pink" : "badge-blue"}>{req.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
