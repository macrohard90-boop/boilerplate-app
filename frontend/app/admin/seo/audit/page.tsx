"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useToast } from "../../../../components/Toast";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface PageScore {
  id: string;
  path: string;
  score: number;
  rule_results: RuleResult[];
  provider: string;
  scored_at: string;
}

interface RuleResult {
  rule_id: string;
  name: string;
  passed: boolean;
  weight: number;
  points: number;
  max_points: number;
  recommendation: string | null;
}

interface Snapshot {
  id: string;
  path: string;
  snapshot: Record<string, unknown>;
  trigger: string;
  changed_by: string | null;
  diff: Record<string, { old: unknown; new: unknown }> | null;
  created_at: string;
}

interface TrendPoint {
  scored_at: string;
  score: number;
}

export default function SeoAuditPage() {
  const { showToast } = useToast();
  const [scores, setScores] = useState<PageScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [detail, setDetail] = useState<PageScore | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [expandedSnapshot, setExpandedSnapshot] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await apiFetch<{ items: PageScore[] }>(
          "/seo/admin/seo/scores?page_size=100"
        );
        setScores(res.items || []);
      } catch {}
      setLoading(false);
    }
    load();
  }, []);

  async function selectPage(score: PageScore) {
    setSelectedPath(score.path);
    setDetail(score);

    // Load snapshots and trend
    try {
      const [snapRes, trendRes] = await Promise.all([
        apiFetch<{ items: Snapshot[] }>(
          `/seo/admin/seo/snapshots?path=${encodeURIComponent(score.path)}&page_size=20`
        ).catch(() => ({ items: [] })),
        apiFetch<{ trend: TrendPoint[] }>(
          `/seo/admin/seo/scores/trend?path=${encodeURIComponent(score.path)}&days=30`
        ).catch(() => ({ trend: [] })),
      ]);
      setSnapshots(snapRes.items || []);
      setTrend(trendRes.trend || []);
    } catch {}
  }

  async function handleScorePage(path: string) {
    try {
      await apiFetch(`/seo/admin/seo/scores/${path}`, { method: "POST" });
      showToast("Page scored", "success");
      // Refresh
      const res = await apiFetch<{ items: PageScore[] }>(
        "/seo/admin/seo/scores?page_size=100"
      );
      setScores(res.items || []);
      const updated = res.items.find((s: PageScore) => s.path === path);
      if (updated) setDetail(updated);
    } catch (e) {
      showToast((e as ApiError).message || "Scoring failed", "error");
    }
  }

  function scoreBadge(score: number) {
    if (score >= 80) return "bg-green-500/20 text-green-400 border-green-500/30";
    if (score >= 50) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    return "bg-red-500/20 text-red-400 border-red-500/30";
  }

  function triggerBadge(trigger: string) {
    const map: Record<string, string> = {
      manual: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      override_change: "bg-purple-500/20 text-purple-400 border-purple-500/30",
      scheduled: "bg-gray-500/20 text-gray-400 border-gray-500/30",
      crawler: "bg-green-500/20 text-green-400 border-green-500/30",
    };
    return map[trigger] || "bg-gray-500/20 text-gray-400 border-gray-500/30";
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Audit & Scores</span>
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score List */}
        <div className="lg:col-span-1">
          <div className="glass rounded-xl overflow-hidden">
            <div className="p-4 border-b border-glass-border">
              <h2 className="text-sm font-medium text-text-primary">
                All Pages ({scores.length})
              </h2>
            </div>
            {scores.length === 0 ? (
              <p className="p-4 text-sm text-text-muted">
                No scores yet. Score pages from the Overview tab.
              </p>
            ) : (
              <div className="max-h-[600px] overflow-y-auto">
                {scores.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => selectPage(s)}
                    className={`w-full text-left px-4 py-3 border-b border-glass-border/50 hover:bg-glass-hover transition-colors ${
                      selectedPath === s.path ? "bg-glass-hover" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-accent-blue truncate max-w-[60%]">
                        /{s.path}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${scoreBadge(s.score)}`}
                      >
                        {s.score}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-2 space-y-6">
          {!detail ? (
            <div className="glass rounded-xl p-8 text-center">
              <p className="text-text-muted">
                Select a page to view its score breakdown and history.
              </p>
            </div>
          ) : (
            <>
              {/* Score Breakdown */}
              <div className="glass rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-text-primary">
                      <span className="font-mono text-accent-blue">
                        /{detail.path}
                      </span>
                    </h2>
                    <p className="text-xs text-text-muted mt-1">
                      Scored: {new Date(detail.scored_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-3 py-1 rounded-lg text-xl font-bold border ${scoreBadge(detail.score)}`}
                    >
                      {detail.score}/100
                    </span>
                    <button
                      onClick={() => handleScorePage(detail.path)}
                      className="btn-secondary text-xs"
                    >
                      Re-score
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  {detail.rule_results.map((r) => (
                    <div
                      key={r.rule_id}
                      className="flex items-center gap-3 py-2 border-b border-glass-border/30 last:border-0"
                    >
                      <span
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                          r.passed
                            ? "bg-green-500/20 text-green-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {r.passed ? "\u2713" : "\u2717"}
                      </span>
                      <span className="text-sm text-text-primary flex-1">
                        {r.name}
                      </span>
                      <span className="text-xs text-text-muted">
                        {r.points}/{r.max_points}
                      </span>
                      {r.recommendation && (
                        <span className="text-xs text-text-secondary max-w-[200px] truncate">
                          {r.recommendation}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Score Trend */}
              {trend.length > 1 && (
                <div className="glass rounded-xl p-6">
                  <h3 className="text-sm font-medium text-text-primary mb-3">
                    Score Trend (30 days)
                  </h3>
                  <div className="flex items-end gap-1 h-24">
                    {trend.map((t, i) => (
                      <div
                        key={i}
                        className="flex-1 rounded-t"
                        style={{
                          height: `${t.score}%`,
                          backgroundColor:
                            t.score >= 80
                              ? "rgba(34, 197, 94, 0.4)"
                              : t.score >= 50
                                ? "rgba(234, 179, 8, 0.4)"
                                : "rgba(239, 68, 68, 0.4)",
                        }}
                        title={`${t.score} — ${new Date(t.scored_at).toLocaleDateString()}`}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Snapshot History */}
              <div className="glass rounded-xl p-6">
                <h3 className="text-sm font-medium text-text-primary mb-3">
                  Change History
                </h3>
                {snapshots.length === 0 ? (
                  <p className="text-sm text-text-muted">No snapshots yet.</p>
                ) : (
                  <div className="space-y-2">
                    {snapshots.map((snap) => (
                      <div
                        key={snap.id}
                        className="border border-glass-border/50 rounded-lg"
                      >
                        <button
                          onClick={() =>
                            setExpandedSnapshot(
                              expandedSnapshot === snap.id ? null : snap.id
                            )
                          }
                          className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-glass-hover transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium border ${triggerBadge(snap.trigger)}`}
                            >
                              {snap.trigger}
                            </span>
                            <span className="text-xs text-text-muted">
                              {new Date(snap.created_at).toLocaleString()}
                            </span>
                          </div>
                          <span className="text-xs text-text-muted">
                            {snap.diff
                              ? `${Object.keys(snap.diff).length} change(s)`
                              : "Initial snapshot"}
                          </span>
                        </button>

                        {expandedSnapshot === snap.id && snap.diff && (
                          <div className="px-4 pb-4 space-y-2">
                            {Object.entries(snap.diff).map(([field, change]) => (
                              <div
                                key={field}
                                className="text-xs border-t border-glass-border/30 pt-2"
                              >
                                <p className="font-medium text-text-primary mb-1">
                                  {field}
                                </p>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <p className="text-text-muted">Before</p>
                                    <p className="text-red-400 font-mono break-all">
                                      {typeof change.old === "object"
                                        ? JSON.stringify(change.old)
                                        : String(change.old ?? "—")}
                                    </p>
                                  </div>
                                  <div>
                                    <p className="text-text-muted">After</p>
                                    <p className="text-green-400 font-mono break-all">
                                      {typeof change.new === "object"
                                        ? JSON.stringify(change.new)
                                        : String(change.new ?? "—")}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
