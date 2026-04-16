"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../../lib/api";
import { useConfig } from "../../../../lib/config-context";
import { useToast } from "../../../../components/Toast";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import {
  GEO_RULE_DESCRIPTIONS,
  GEO_DIMENSIONS,
} from "../../../../lib/geo-rule-descriptions";
import GEOAdvisorPanel from "../../../../components/admin/GEOAdvisorPanel";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface GEORuleResult {
  rule_id: string;
  name: string;
  passed: boolean;
  weight: number;
  points: number;
  max_points: number;
  category: string;
  recommendation: string | null;
}

interface GEOPageScore {
  id: string;
  path: string;
  score: number;
  dimension_scores: Record<string, number>;
  rule_results: GEORuleResult[];
  provider: string;
  scored_at: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

function scoreBgColor(score: number): string {
  if (score >= 80) return "bg-green-500/20 text-green-400 border-green-500/30";
  if (score >= 50)
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-red-500/20 text-red-400 border-red-500/30";
}

const DIMENSION_ORDER = [
  "extractability",
  "fact_density",
  "authority",
  "freshness",
  "metadata",
];

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function GeoPage() {
  const { showToast } = useToast();
  const { enable_geo_scoring, enable_geo_advisor } = useConfig();

  const [scores, setScores] = useState<GEOPageScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [expandedPath, setExpandedPath] = useState<string | null>(null);
  const [expandedDescRule, setExpandedDescRule] = useState<string | null>(null);
  const [infoCollapsed, setInfoCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("geo-info-collapsed") === "true";
    }
    return false;
  });

  useEffect(() => {
    if (!enable_geo_scoring) {
      setLoading(false);
      return;
    }
    apiFetch<{ items: GEOPageScore[] }>("/seo/admin/seo/geo/scores?page_size=50")
      .then((data) => setScores(data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [enable_geo_scoring]);

  function toggleInfo() {
    const next = !infoCollapsed;
    setInfoCollapsed(next);
    localStorage.setItem("geo-info-collapsed", String(next));
  }

  async function handleScoreAll() {
    setScoring(true);
    try {
      await apiFetch("/seo/admin/seo/geo/scores/batch", { method: "POST" });
      const data = await apiFetch<{ items: GEOPageScore[] }>(
        "/seo/admin/seo/geo/scores?page_size=50"
      );
      setScores(data.items || []);
      showToast("GEO scoring complete", "success");
    } catch {
      showToast("GEO scoring failed", "error");
    } finally {
      setScoring(false);
    }
  }

  if (!enable_geo_scoring) {
    return (
      <div className="mt-6 glass rounded-xl p-8 text-center">
        <p className="text-sm text-text-muted">GEO scoring is disabled.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mt-6 flex items-center justify-center p-12">
        <LoadingSpinner className="w-6 h-6" />
      </div>
    );
  }

  // Compute KPIs
  const avgScore =
    scores.length > 0
      ? Math.round(scores.reduce((s, p) => s + p.score, 0) / scores.length)
      : null;

  // Find best/worst dimension across all pages
  let bestDim = "";
  let worstDim = "";
  if (scores.length > 0) {
    const dimAvgs: Record<string, number[]> = {};
    for (const page of scores) {
      if (!page.dimension_scores) continue;
      for (const [dim, val] of Object.entries(page.dimension_scores)) {
        if (!dimAvgs[dim]) dimAvgs[dim] = [];
        dimAvgs[dim].push(val);
      }
    }
    let bestAvg = -1;
    let worstAvg = 101;
    for (const [dim, vals] of Object.entries(dimAvgs)) {
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      if (avg > bestAvg) {
        bestAvg = avg;
        bestDim = dim;
      }
      if (avg < worstAvg) {
        worstAvg = avg;
        worstDim = dim;
      }
    }
  }

  const expandedPage = scores.find((s) => s.path === expandedPath);

  return (
    <div className="mt-6 space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-2xl font-bold">
          <span className="gradient-text">Generative Engine Optimization</span>
        </h1>
        <button
          onClick={handleScoreAll}
          disabled={scoring}
          className="btn-primary text-sm disabled:opacity-50"
        >
          {scoring ? "Scoring..." : "Score All Pages"}
        </button>
      </div>

      {/* How GEO Scoring Works */}
      <div className="glass rounded-xl overflow-hidden">
        <button
          onClick={toggleInfo}
          className="w-full text-left px-6 py-4 flex items-center justify-between hover:bg-glass-hover transition-colors"
        >
          <span className="text-sm font-medium text-text-primary">
            How GEO Scoring Works
          </span>
          <span className="text-text-muted text-xs">
            {infoCollapsed ? "Show" : "Hide"}
          </span>
        </button>
        {!infoCollapsed && (
          <div className="px-6 pb-5 border-t border-glass-border/50">
            <p className="text-sm text-text-secondary mt-4 mb-3">
              GEO scores measure how likely AI engines (ChatGPT, Perplexity,
              Gemini, Google AI Overviews) are to cite your content. Unlike SEO
              which ranks pages, GEO optimizes for{" "}
              <strong className="text-text-primary">
                sentence-level extraction
              </strong>{" "}
              — AI engines pull individual paragraphs and sections to include in
              their answers.
            </p>
            <p className="text-sm text-text-secondary mb-4">
              Only 12% of ChatGPT citations overlap with Google&apos;s top-10
              results. GEO requires its own optimization strategy. Each page is
              scored 0-100 across 5 dimensions:
            </p>
            <div className="space-y-3 text-xs mb-4">
              {DIMENSION_ORDER.map((dim) => {
                const d = GEO_DIMENSIONS[dim];
                return (
                  <div key={dim} className="flex gap-3">
                    <span
                      className={`shrink-0 w-6 h-6 rounded-full ${d.bgColor} ${d.color} text-[10px] font-bold flex items-center justify-center`}
                    >
                      {DIMENSION_ORDER.indexOf(dim) + 1}
                    </span>
                    <div>
                      <p className={`${d.color} font-medium`}>{d.label}</p>
                      <p className="text-text-muted mt-0.5">{d.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="p-3 rounded-lg bg-base-100/50 border border-glass-border/30">
              <p className="text-xs text-text-muted">
                <strong className="text-text-secondary">How to use:</strong>{" "}
                Score your pages, review failing rules, improve content based on
                recommendations, then rescore. Focus on{" "}
                <strong className="text-text-secondary">Extractability</strong>{" "}
                and{" "}
                <strong className="text-text-secondary">Fact Density</strong>{" "}
                first — these have the highest impact on AI citations.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      {scores.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {avgScore !== null && (
            <div className="glass rounded-xl p-5">
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
                Avg GEO Score
              </p>
              <p className={`text-3xl font-bold ${scoreColor(avgScore)}`}>
                {avgScore}
              </p>
            </div>
          )}
          <div className="glass rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
              Pages Scored
            </p>
            <p className="text-3xl font-bold text-text-primary">
              {scores.length}
            </p>
          </div>
          {bestDim && GEO_DIMENSIONS[bestDim] && (
            <div className="glass rounded-xl p-5">
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
                Strongest Dimension
              </p>
              <p
                className={`text-lg font-bold ${GEO_DIMENSIONS[bestDim].color}`}
              >
                {GEO_DIMENSIONS[bestDim].label}
              </p>
            </div>
          )}
          {worstDim && GEO_DIMENSIONS[worstDim] && (
            <div className="glass rounded-xl p-5">
              <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
                Weakest Dimension
              </p>
              <p
                className={`text-lg font-bold ${GEO_DIMENSIONS[worstDim].color}`}
              >
                {GEO_DIMENSIONS[worstDim].label}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Scores Table */}
      {scores.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-sm text-text-muted">
            No GEO scores yet. Click &ldquo;Score All Pages&rdquo; to analyze
            your pages for AI engine optimization.
          </p>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Page
                  </th>
                  <th className="text-center py-3 px-4 text-xs font-medium text-text-muted">
                    GEO Score
                  </th>
                  {DIMENSION_ORDER.map((dim) => (
                    <th
                      key={dim}
                      className="text-center py-3 px-4 text-xs font-medium text-text-muted hidden lg:table-cell"
                    >
                      {GEO_DIMENSIONS[dim]?.label}
                    </th>
                  ))}
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">
                    Scored
                  </th>
                </tr>
              </thead>
              <tbody>
                {scores.map((page) => (
                  <tr
                    key={page.id}
                    onClick={() =>
                      setExpandedPath(
                        expandedPath === page.path ? null : page.path
                      )
                    }
                    className={`border-b border-glass-border/50 cursor-pointer transition-colors ${
                      expandedPath === page.path
                        ? "bg-glass-hover"
                        : "hover:bg-glass-hover"
                    }`}
                  >
                    <td className="py-3 px-4 font-mono text-accent-blue text-xs">
                      /{page.path || "(home)"}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-lg text-xs font-bold border ${scoreBgColor(page.score)}`}
                      >
                        {page.score}
                      </span>
                    </td>
                    {DIMENSION_ORDER.map((dim) => {
                      const val = page.dimension_scores?.[dim] ?? 0;
                      return (
                        <td
                          key={dim}
                          className="py-3 px-4 text-center hidden lg:table-cell"
                        >
                          <div className="flex items-center justify-center gap-1.5">
                            <div className="w-12 h-1.5 rounded-full bg-glass-bg overflow-hidden">
                              <div
                                className={`h-full rounded-full ${val >= 80 ? "bg-green-500" : val >= 50 ? "bg-yellow-500" : "bg-red-500"}`}
                                style={{ width: `${val}%` }}
                              />
                            </div>
                            <span
                              className={`text-[10px] ${scoreColor(val)}`}
                            >
                              {val}
                            </span>
                          </div>
                        </td>
                      );
                    })}
                    <td className="py-3 px-4 text-right text-xs text-text-muted">
                      {new Date(page.scored_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Expanded Page Detail */}
      {expandedPage && (
        <div className="glass rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-glass-border flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary">
              /{expandedPage.path || "(home)"} — Rule Breakdown
            </h3>
            <button
              onClick={() => setExpandedPath(null)}
              className="text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              Close
            </button>
          </div>

          {/* Dimension groups */}
          <div className="p-4 space-y-4">
            {DIMENSION_ORDER.map((dim) => {
              const dimConfig = GEO_DIMENSIONS[dim];
              const dimRules = expandedPage.rule_results.filter(
                (r) => r.category === dim
              );
              const dimScore = expandedPage.dimension_scores?.[dim] ?? 0;

              return (
                <div key={dim}>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`text-xs font-bold ${dimConfig.color}`}
                    >
                      {dimConfig.label}
                    </span>
                    <span className={`text-xs ${scoreColor(dimScore)}`}>
                      {dimScore}/100
                    </span>
                  </div>
                  <div className="space-y-1">
                    {dimRules.map((r) => {
                      const desc = GEO_RULE_DESCRIPTIONS[r.rule_id];
                      return (
                        <div key={r.rule_id}>
                          <button
                            className={`w-full text-left rounded-lg px-3 py-2 flex items-center justify-between transition-colors ${
                              r.passed
                                ? "bg-green-500/5 hover:bg-green-500/10"
                                : "bg-red-500/5 hover:bg-red-500/10"
                            }`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedDescRule(
                                expandedDescRule === r.rule_id
                                  ? null
                                  : r.rule_id
                              );
                            }}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span
                                className={`shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                                  r.passed
                                    ? "bg-green-500/20 text-green-400"
                                    : "bg-red-500/20 text-red-400"
                                }`}
                              >
                                {r.passed ? "\u2713" : "\u2717"}
                              </span>
                              <span className="text-xs text-text-primary truncate">
                                {r.name}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0 ml-2">
                              <span className="text-[10px] text-text-muted">
                                {r.points}/{r.max_points}
                              </span>
                              <span className="text-text-muted/50 text-[10px]">
                                ?
                              </span>
                            </div>
                          </button>

                          {/* Recommendation */}
                          {!r.passed && r.recommendation && expandedDescRule !== r.rule_id && (
                            <div className="ml-9 mt-1 mb-1">
                              <p className="text-[11px] text-text-muted leading-relaxed">
                                {r.recommendation}
                              </p>
                            </div>
                          )}

                          {/* Educational panel */}
                          {expandedDescRule === r.rule_id && desc && (
                            <div className="pb-2 px-3 mt-1">
                              <div className="p-4 rounded-lg bg-base-100/50 border border-glass-border/30 space-y-3">
                                <div>
                                  <p className="text-[10px] font-medium text-accent-blue uppercase tracking-wider mb-1">
                                    What this checks
                                  </p>
                                  <p className="text-xs text-text-secondary leading-relaxed">
                                    {desc.whatItChecks}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-[10px] font-medium text-accent-green uppercase tracking-wider mb-1">
                                    Why it matters
                                  </p>
                                  <p className="text-xs text-text-secondary leading-relaxed">
                                    {desc.whyItMatters}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-[10px] font-medium text-accent-purple uppercase tracking-wider mb-1">
                                    Passing looks like
                                  </p>
                                  <p className="text-xs text-text-secondary leading-relaxed">
                                    {desc.passingLooks}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-[10px] font-medium text-amber-400 uppercase tracking-wider mb-1">
                                    How to fix
                                  </p>
                                  <p className="text-xs text-text-secondary leading-relaxed">
                                    {desc.howToFix}
                                  </p>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* GEO Advisor Panel */}
      {enable_geo_advisor && expandedPage && (
        <GEOAdvisorPanel
          path={expandedPage.path}
          onRuleClick={(ruleId) => setExpandedDescRule(ruleId)}
        />
      )}

      {/* Score legend */}
      <div className="flex gap-4 text-xs text-text-muted">
        <span className="text-green-400">80+ = Good</span>
        <span className="text-yellow-400">50-79 = Needs work</span>
        <span className="text-red-400">Below 50 = Poor</span>
      </div>
    </div>
  );
}
