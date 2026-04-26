"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface SimRun {
  id: string;
  started_at: string | null;
  completed_at: string | null;
  target_url: string;
  user_count: number;
  status: string;
  sections_run: string[];
  summary: {
    total_checks: number;
    passed: number;
    failed: number;
    duration_secs: number;
  };
}

interface SimCheck {
  category: string;
  name: string;
  expected: string;
  actual: string;
  passed: boolean;
  detail: string;
}

interface SimPhase {
  phase: string;
  success: boolean;
  message: string;
  duration_ms: number;
}

interface SimUserResult {
  id: string;
  user_email: string;
  persona: string;
  actions: Array<{
    action: string;
    endpoint: string;
    method: string;
    status_code: number;
    passed: boolean;
    detail: string;
  }>;
  events_expected: number;
  events_recorded: number;
  result: string;
}

interface SimRunDetail extends SimRun {
  phase_results: SimPhase[];
  check_results: SimCheck[];
  user_results: SimUserResult[];
}

export default function SimulationTab() {
  const [runs, setRuns] = useState<SimRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<SimRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expandedUsers, setExpandedUsers] = useState<Set<string>>(new Set());
  const [showOnlyFailed, setShowOnlyFailed] = useState(false);

  const fetchRuns = useCallback(async () => {
    try {
      const data = (await apiFetch(
        "/api/tracking/admin/simulation/runs",
      )) as SimRun[];
      setRuns(data);
    } catch {
      // Table might not exist yet
      setRuns([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const loadRunDetail = async (runId: string) => {
    setDetailLoading(true);
    try {
      const data = (await apiFetch(
        `/api/tracking/admin/simulation/runs/${runId}`,
      )) as SimRunDetail;
      setSelectedRun(data);
      setExpandedUsers(new Set());
    } catch {
      setSelectedRun(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleUser = (userId: string) => {
    setExpandedUsers((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  if (loading) return <LoadingSpinner />;

  if (runs.length === 0) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-text-muted mb-2">No simulation runs found.</p>
        <p className="text-text-muted text-sm">
          Run{" "}
          <code className="text-accent-pink text-xs">
            python scripts/simulate/runner.py --target http://your-server
          </code>{" "}
          to create one.
        </p>
      </div>
    );
  }

  // Group checks by category
  const groupedChecks: Record<string, SimCheck[]> = {};
  if (selectedRun?.check_results) {
    for (const c of selectedRun.check_results) {
      if (!groupedChecks[c.category]) groupedChecks[c.category] = [];
      groupedChecks[c.category].push(c);
    }
  }

  const filteredUsers = showOnlyFailed
    ? (selectedRun?.user_results || []).filter((u) => u.result === "FAIL")
    : selectedRun?.user_results || [];

  return (
    <div className="space-y-6">
      {/* Run Selector */}
      <div className="glass rounded-xl p-4">
        <label className="block text-xs text-text-muted mb-2 uppercase tracking-wider">
          Simulation Run
        </label>
        <select
          className="w-full bg-surface-elevated border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
          value={selectedRun?.id || ""}
          onChange={(e) => {
            if (e.target.value) loadRunDetail(e.target.value);
            else setSelectedRun(null);
          }}
        >
          <option value="">Select a run...</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.started_at
                ? new Date(r.started_at).toLocaleString()
                : "Unknown"}{" "}
              — {r.user_count} users — {r.summary?.passed || 0}/
              {r.summary?.total_checks || 0} passed
            </option>
          ))}
        </select>
      </div>

      {detailLoading && <LoadingSpinner />}

      {selectedRun && !detailLoading && (
        <>
          {/* Summary Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryCard
              label="Total Checks"
              value={selectedRun.summary?.total_checks || 0}
            />
            <SummaryCard
              label="Passed"
              value={selectedRun.summary?.passed || 0}
              color="text-green-400"
            />
            <SummaryCard
              label="Failed"
              value={selectedRun.summary?.failed || 0}
              color={
                (selectedRun.summary?.failed || 0) > 0
                  ? "text-red-400"
                  : "text-green-400"
              }
            />
            <SummaryCard
              label="Duration"
              value={`${(selectedRun.summary?.duration_secs || 0).toFixed(0)}s`}
            />
          </div>

          {/* Phase Results */}
          <div className="glass rounded-xl p-4">
            <h3 className="text-sm font-medium text-text-secondary mb-3">
              Phases
            </h3>
            <div className="space-y-2">
              {(selectedRun.phase_results || []).map((phase, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        phase.success ? "text-green-400" : "text-red-400"
                      }
                    >
                      {phase.success ? "[+]" : "[X]"}
                    </span>
                    <span className="text-text-primary">{phase.phase}</span>
                  </div>
                  <div className="flex items-center gap-4 text-text-muted">
                    <span>{phase.message}</span>
                    <span className="text-xs">
                      {(phase.duration_ms / 1000).toFixed(1)}s
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Check Results by Category */}
          <div className="glass rounded-xl p-4">
            <h3 className="text-sm font-medium text-text-secondary mb-3">
              Verification Checks
            </h3>
            <div className="space-y-4">
              {Object.entries(groupedChecks).map(([category, checks]) => (
                <div key={category}>
                  <h4 className="text-xs uppercase tracking-wider text-text-muted mb-2">
                    {category}
                  </h4>
                  <div className="space-y-1">
                    {checks.map((c, i) => (
                      <div key={i} className="text-sm">
                        <div className="flex items-start gap-2">
                          <span
                            className={`shrink-0 ${c.passed ? "text-green-400" : "text-red-400"}`}
                          >
                            {c.passed ? "[+]" : "[X]"}
                          </span>
                          <div className="flex-1 min-w-0">
                            <span className="text-text-primary">{c.name}</span>
                            <span className="text-text-muted ml-2">
                              {c.actual}
                            </span>
                            <span className="text-text-muted/60 ml-1 text-xs">
                              (expected {c.expected})
                            </span>
                          </div>
                        </div>
                        {c.detail && (
                          <p className="text-xs text-text-muted/70 ml-6 mt-0.5">
                            {c.detail}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Failures Panel */}
          {(selectedRun.summary?.failed || 0) > 0 && (
            <div className="glass rounded-xl p-4 border border-red-500/30">
              <h3 className="text-sm font-medium text-red-400 mb-3">
                Failed Checks
              </h3>
              <div className="space-y-2">
                {(selectedRun.check_results || [])
                  .filter((c) => !c.passed)
                  .map((c, i) => (
                    <div key={i} className="text-sm">
                      <div className="flex items-start gap-2">
                        <span className="text-red-400 shrink-0">[X]</span>
                        <div>
                          <span className="text-text-primary font-medium">
                            [{c.category}] {c.name}
                          </span>
                          <p className="text-text-muted text-xs mt-0.5">
                            Expected: {c.expected} | Actual: {c.actual}
                          </p>
                          {c.detail && (
                            <p className="text-red-300/70 text-xs mt-0.5">
                              {c.detail}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* User Results */}
          {(selectedRun.user_results || []).length > 0 && (
            <div className="glass rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-text-secondary">
                  User Results ({selectedRun.user_results.length})
                </h3>
                <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showOnlyFailed}
                    onChange={(e) => setShowOnlyFailed(e.target.checked)}
                    className="rounded"
                  />
                  Show only failures
                </label>
              </div>
              <div className="space-y-1 max-h-[600px] overflow-y-auto">
                {filteredUsers.map((user) => (
                  <div
                    key={user.id}
                    className="border border-glass-border/30 rounded-lg"
                  >
                    <button
                      onClick={() => toggleUser(user.id)}
                      className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-surface-elevated/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={
                            user.result === "PASS"
                              ? "text-green-400"
                              : "text-red-400"
                          }
                        >
                          {user.result === "PASS" ? "[+]" : "[X]"}
                        </span>
                        <span className="text-text-primary font-mono text-xs">
                          {user.user_email}
                        </span>
                        <span className="text-text-muted text-xs px-1.5 py-0.5 bg-surface-elevated rounded">
                          {user.persona}
                        </span>
                      </div>
                      <span className="text-text-muted text-xs">
                        {user.actions?.length || 0} actions
                      </span>
                    </button>
                    {expandedUsers.has(user.id) && (
                      <div className="px-3 pb-3 border-t border-glass-border/20">
                        <div className="mt-2 space-y-0.5 max-h-[300px] overflow-y-auto">
                          {(user.actions || []).map((a, ai) => (
                            <div
                              key={ai}
                              className="flex items-center gap-2 text-xs font-mono"
                            >
                              <span
                                className={
                                  a.passed ? "text-green-400" : "text-red-400"
                                }
                              >
                                {a.passed ? "+" : "X"}
                              </span>
                              <span className="text-text-muted w-16 shrink-0">
                                {a.method || ""}
                              </span>
                              <span className="text-text-primary truncate flex-1">
                                {a.action}
                              </span>
                              {a.status_code > 0 && (
                                <span
                                  className={`shrink-0 ${a.status_code < 400 ? "text-text-muted" : "text-red-400"}`}
                                >
                                  {a.status_code}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  return (
    <div className="glass rounded-xl p-4 text-center">
      <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={`text-2xl font-bold ${color || "text-text-primary"}`}>
        {value}
      </p>
    </div>
  );
}
