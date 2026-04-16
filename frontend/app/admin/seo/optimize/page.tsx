"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useToast } from "../../../../components/Toast";
import { useConfig } from "../../../../lib/config-context";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import HtmlSourceViewer from "../../../../components/admin/HtmlSourceViewer";
import SEOAdvisorPanel from "../../../../components/admin/SEOAdvisorPanel";
import { RULE_DESCRIPTIONS } from "../../../../lib/seo-rule-descriptions";

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
  category: string;
  recommendation: string | null;
}

interface CurrentMeta {
  path: string;
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  robots_index: boolean;
  robots_follow: boolean;
  is_custom: boolean;
}

interface VerifyResult {
  rendered: Record<string, string | null>;
  expected: Record<string, string | null>;
  mismatches: { field: string; expected: string | null; actual: string | null }[];
  match: boolean;
}

const CATEGORY_LABELS: Record<string, { label: string; icon: string }> = {
  content: { label: "Content", icon: "\u270F\uFE0F" },
  technical: { label: "Technical", icon: "\u2699\uFE0F" },
  social: { label: "Social", icon: "\uD83D\uDD17" },
  performance: { label: "Performance", icon: "\u26A1" },
  general: { label: "General", icon: "\uD83D\uDCCB" },
};

/** Maps rule_id to the meta field it controls. Only rules here are inline-editable. */
const RULE_FIELD_MAP: Record<
  string,
  { field: string; label: string; type: "text" | "textarea" | "checkbox"; maxLen?: number }
> = {
  title_present: { field: "title", label: "Title", type: "text", maxLen: 60 },
  title_length: { field: "title", label: "Title", type: "text", maxLen: 60 },
  desc_present: { field: "description", label: "Description", type: "textarea", maxLen: 160 },
  desc_length: { field: "description", label: "Description", type: "textarea", maxLen: 160 },
  canonical_set: { field: "canonical_url", label: "Canonical URL", type: "text" },
  canonical_self_ref: { field: "canonical_url", label: "Canonical URL", type: "text" },
  robots_indexable: { field: "robots_index", label: "Allow Indexing", type: "checkbox" },
};

function groupByCategory(rules: RuleResult[]): Record<string, RuleResult[]> {
  const groups: Record<string, RuleResult[]> = {};
  const order = ["content", "technical", "social", "performance", "general"];
  for (const cat of order) groups[cat] = [];
  for (const r of rules) {
    const cat = r.category || "general";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(r);
  }
  for (const key of Object.keys(groups)) {
    if (groups[key].length === 0) delete groups[key];
  }
  return groups;
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

// ── Site Audit types ──

interface AuditCheck {
  check_id: string;
  category: string;
  severity: string;
  passed: boolean;
  title: string;
  description: string;
  recommendation: string | null;
  affected_pages: string[] | null;
}

interface AuditReport {
  id?: string;
  checks: AuditCheck[];
  summary: Record<string, number>;
  score: number;
  created_at: string;
}

const SEVERITY_BADGES: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  warning: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  info: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

function groupAuditByCategory(
  checks: AuditCheck[]
): Record<string, AuditCheck[]> {
  const groups: Record<string, AuditCheck[]> = {};
  const order = ["technical", "content", "social", "performance"];
  for (const cat of order) groups[cat] = [];
  for (const c of checks) {
    const cat = c.category || "technical";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(c);
  }
  for (const key of Object.keys(groups)) {
    if (groups[key].length === 0) delete groups[key];
  }
  return groups;
}

export default function SeoOptimizePage() {
  const searchParams = useSearchParams();
  const { showToast } = useToast();
  const { enable_seo_advisor } = useConfig();
  const [scores, setScores] = useState<PageScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [detail, setDetail] = useState<PageScore | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [expandedSnapshot, setExpandedSnapshot] = useState<string | null>(null);

  // Site audit state
  const [audit, setAudit] = useState<AuditReport | null>(null);
  const [auditRunning, setAuditRunning] = useState(false);
  const [expandedCheck, setExpandedCheck] = useState<string | null>(null);

  // Inline editing state
  const [currentMeta, setCurrentMeta] = useState<CurrentMeta | null>(null);
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string | boolean>("");
  const [confirmingPassingRule, setConfirmingPassingRule] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [expandedDescRule, setExpandedDescRule] = useState<string | null>(null);

  // Verification state
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  // HTML source viewer state
  const [pageHtml, setPageHtml] = useState<string | null>(null);
  const [htmlLoading, setHtmlLoading] = useState(false);
  const [highlightedRule, setHighlightedRule] = useState<string | null>(null);

  const selectPage = useCallback(
    async (score: PageScore) => {
      setSelectedPath(score.path);
      setDetail(score);
      setEditingRule(null);
      setConfirmingPassingRule(null);
      setVerifyResult(null);
      setHighlightedRule(null);
      setHtmlLoading(true);
      setPageHtml(null);

      try {
        const [snapRes, trendRes, metaRes, htmlRes] = await Promise.all([
          apiFetch<{ items: Snapshot[] }>(
            `/seo/admin/seo/snapshots?path=${encodeURIComponent(score.path)}&page_size=20`
          ).catch(() => ({ items: [] })),
          apiFetch<{ trend: TrendPoint[] }>(
            `/seo/admin/seo/scores/trend?path=${encodeURIComponent(score.path)}&days=30`
          ).catch(() => ({ trend: [] })),
          apiFetch<CurrentMeta>(
            `/seo/admin/seo/meta/current/${encodeURIComponent(score.path)}`
          ).catch(() => null),
          apiFetch<{ html: string; status_code: number }>(
            `/seo/admin/seo/html/${encodeURIComponent(score.path)}`
          ).catch(() => null),
        ]);
        setSnapshots(snapRes.items || []);
        setTrend(trendRes.trend || []);
        setCurrentMeta(metaRes);
        setPageHtml(htmlRes?.html ?? null);
      } catch {}
      setHtmlLoading(false);
    },
    []
  );

  useEffect(() => {
    async function load() {
      try {
        const [scoreRes, auditRes] = await Promise.all([
          apiFetch<{ items: PageScore[] }>(
            "/seo/admin/seo/scores?page_size=100"
          ).catch(() => ({ items: [] })),
          apiFetch<AuditReport>("/seo/admin/seo/audit/latest").catch(
            () => null
          ),
        ]);
        const items = scoreRes.items || [];
        setScores(items);
        if (auditRes) setAudit(auditRes);

        // Auto-select from query param
        const pageParam = searchParams.get("page");
        if (pageParam !== null && items.length > 0) {
          const match = items.find((s) => s.path === pageParam);
          if (match) {
            selectPage(match);
          }
        }
      } catch {}
      setLoading(false);
    }
    load();
  }, [searchParams, selectPage]);

  async function handleRunAudit() {
    setAuditRunning(true);
    try {
      const result = await apiFetch<AuditReport>("/seo/admin/seo/audit/run", {
        method: "POST",
      });
      setAudit(result);
      showToast(`Audit complete: ${result.score}/100`, "success");
    } catch (e) {
      showToast((e as ApiError).message || "Audit failed", "error");
    }
    setAuditRunning(false);
  }

  async function handleScorePage(path: string) {
    const oldScore = detail?.score;
    try {
      await apiFetch(`/seo/admin/seo/scores/${encodeURIComponent(path)}`, {
        method: "POST",
      });
      const res = await apiFetch<{ items: PageScore[] }>(
        "/seo/admin/seo/scores?page_size=100"
      );
      setScores(res.items || []);
      const updated = res.items.find((s: PageScore) => s.path === path);
      if (updated) {
        setDetail(updated);
        const msg =
          oldScore !== undefined && oldScore !== updated.score
            ? `Score: ${oldScore} \u2192 ${updated.score}`
            : `Score: ${updated.score}/100`;
        showToast(msg, "success");
      } else {
        showToast("Page scored", "success");
      }
    } catch (e) {
      showToast((e as ApiError).message || "Scoring failed", "error");
    }
  }

  function handleRuleClick(rule: RuleResult) {
    // Always highlight in HTML viewer regardless of editability
    setHighlightedRule(rule.rule_id);
    // Close description panel when interacting with the rule row
    setExpandedDescRule(null);

    const mapping = RULE_FIELD_MAP[rule.rule_id];

    if (!mapping) {
      // Non-editable: just toggle expand
      setEditingRule(null);
      setConfirmingPassingRule(null);
      return;
    }

    if (rule.passed) {
      // Passing rule: show warning
      setConfirmingPassingRule(rule.rule_id);
      setEditingRule(null);
    } else {
      // Failing rule: open editor directly
      openEditor(rule.rule_id);
    }
  }

  function openEditor(ruleId: string) {
    const mapping = RULE_FIELD_MAP[ruleId];
    if (!mapping || !currentMeta) return;

    setEditingRule(ruleId);
    setConfirmingPassingRule(null);

    const val = currentMeta[mapping.field as keyof CurrentMeta];
    setEditValue(val ?? (mapping.type === "checkbox" ? true : ""));
  }

  function cancelEdit() {
    setEditingRule(null);
    setConfirmingPassingRule(null);
    setHighlightedRule(null);
  }

  async function handleSaveAndRescore() {
    if (!detail || !currentMeta || !editingRule) return;
    const mapping = RULE_FIELD_MAP[editingRule];
    if (!mapping) return;

    setSaving(true);
    try {
      // Build the full override payload using current meta + edited field
      const payload: Record<string, unknown> = {
        title: currentMeta.title,
        description: currentMeta.description,
        canonical_url: currentMeta.canonical_url,
        robots_index: currentMeta.robots_index,
        robots_follow: currentMeta.robots_follow,
      };
      payload[mapping.field] = editValue;

      await apiFetch(
        `/seo/admin/seo/meta/${encodeURIComponent(detail.path)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        }
      );

      // Re-score
      await handleScorePage(detail.path);

      // Refresh current meta
      const metaRes = await apiFetch<CurrentMeta>(
        `/seo/admin/seo/meta/current/${encodeURIComponent(detail.path)}`
      ).catch(() => null);
      setCurrentMeta(metaRes);

      setEditingRule(null);
    } catch (e) {
      showToast((e as ApiError).message || "Save failed", "error");
    }
    setSaving(false);
  }

  async function handleVerify() {
    if (!detail) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await apiFetch<VerifyResult>(
        `/seo/admin/seo/verify/${encodeURIComponent(detail.path)}`,
        { method: "POST" }
      );
      setVerifyResult(result);
      if (result.match) {
        showToast("All meta tags match the rendered page.", "success");
      } else {
        showToast(
          `${result.mismatches.length} mismatch(es) found.`,
          "error"
        );
      }
    } catch (e) {
      showToast((e as ApiError).message || "Verification failed", "error");
    }
    setVerifying(false);
  }

  function scoreBadge(score: number) {
    if (score >= 80)
      return "bg-green-500/20 text-green-400 border-green-500/30";
    if (score >= 50)
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    return "bg-red-500/20 text-red-400 border-red-500/30";
  }

  function triggerBadge(trigger: string) {
    const map: Record<string, string> = {
      manual: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      override_change:
        "bg-purple-500/20 text-purple-400 border-purple-500/30",
      scheduled: "bg-gray-500/20 text-gray-400 border-gray-500/30",
      crawler: "bg-green-500/20 text-green-400 border-green-500/30",
    };
    return map[trigger] || "bg-gray-500/20 text-gray-400 border-gray-500/30";
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Optimize</span>
      </h1>
      <p className="text-sm text-text-secondary mb-6">
        Score, audit, advise, and fix your pages.{" "}
        <a href="/admin/seo/meta" className="text-accent-blue hover:text-accent-purple transition-colors">
          Manage all meta overrides &rarr;
        </a>
      </p>

      {/* ── Site Audit Panel ── */}
      <div className="glass rounded-xl p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">
              Site Audit
            </h2>
            <p className="text-sm text-text-secondary mt-1">
              Site-wide SEO health check: duplicate content, missing metadata,
              broken pages, and more.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {audit && (
              <span
                className={`px-3 py-1 rounded-lg text-xl font-bold border ${scoreBadge(audit.score)}`}
              >
                {audit.score}/100
              </span>
            )}
            <button
              onClick={handleRunAudit}
              disabled={auditRunning}
              className="btn-primary text-sm disabled:opacity-50"
            >
              {auditRunning ? "Running..." : "Run Full Audit"}
            </button>
          </div>
        </div>

        {audit ? (
          <>
            <div className="flex gap-3 mb-4 flex-wrap">
              <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                {audit.summary.passed || 0} passed
              </span>
              {(audit.summary.critical || 0) > 0 && (
                <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30">
                  {audit.summary.critical} critical
                </span>
              )}
              {(audit.summary.warning || 0) > 0 && (
                <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                  {audit.summary.warning} warning
                </span>
              )}
              {(audit.summary.info || 0) > 0 && (
                <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  {audit.summary.info} info
                </span>
              )}
              <span className="text-xs text-text-muted self-center ml-auto">
                Last run: {new Date(audit.created_at).toLocaleString()}
              </span>
            </div>

            <div className="space-y-5">
              {Object.entries(groupAuditByCategory(audit.checks)).map(
                ([cat, checks]) => {
                  const meta = CATEGORY_LABELS[cat] || CATEGORY_LABELS.general;
                  const catPassed = checks.filter((c) => c.passed).length;
                  return (
                    <div key={cat}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm">{meta.icon}</span>
                        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                          {meta.label}
                        </h3>
                        <span className="text-xs text-text-muted ml-auto">
                          {catPassed}/{checks.length} passed
                        </span>
                      </div>
                      <div className="space-y-1">
                        {checks.map((c) => (
                          <div
                            key={c.check_id}
                            className="border-b border-glass-border/30 last:border-0"
                          >
                            <button
                              onClick={() =>
                                setExpandedCheck(
                                  expandedCheck === c.check_id
                                    ? null
                                    : c.check_id
                                )
                              }
                              className="w-full text-left py-2 flex items-center gap-3"
                            >
                              <span
                                className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                                  c.passed
                                    ? "bg-green-500/20 text-green-400"
                                    : "bg-red-500/20 text-red-400"
                                }`}
                              >
                                {c.passed ? "\u2713" : "\u2717"}
                              </span>
                              <span className="text-sm text-text-primary flex-1">
                                {c.title}
                              </span>
                              {!c.passed && (
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                    SEVERITY_BADGES[c.severity] ||
                                    SEVERITY_BADGES.info
                                  }`}
                                >
                                  {c.severity}
                                </span>
                              )}
                              <span className="text-text-muted text-xs">
                                {expandedCheck === c.check_id
                                  ? "\u25B2"
                                  : "\u25BC"}
                              </span>
                            </button>

                            {expandedCheck === c.check_id && (
                              <div className="pb-3 pl-8 space-y-2">
                                <p className="text-xs text-text-secondary">
                                  {c.description}
                                </p>
                                {c.recommendation && (
                                  <p className="text-xs text-accent-blue">
                                    {c.recommendation}
                                  </p>
                                )}
                                {c.affected_pages &&
                                  c.affected_pages.length > 0 && (
                                    <div>
                                      <p className="text-xs text-text-muted mb-1">
                                        Affected pages (
                                        {c.affected_pages.length}):
                                      </p>
                                      <div className="flex flex-wrap gap-1">
                                        {c.affected_pages
                                          .slice(0, 10)
                                          .map((p) => (
                                            <span
                                              key={p}
                                              className="font-mono text-[10px] px-2 py-0.5 rounded bg-base-100 text-text-muted"
                                            >
                                              /{p}
                                            </span>
                                          ))}
                                        {c.affected_pages.length > 10 && (
                                          <span className="text-[10px] text-text-muted">
                                            +{c.affected_pages.length - 10} more
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </>
        ) : (
          <div className="text-center py-6">
            <p className="text-text-muted text-sm">
              No audit results yet. Click &quot;Run Full Audit&quot; to check
              your site.
            </p>
          </div>
        )}
      </div>

      {/* ── Per-Page Scoring ── */}
      <h2 className="text-lg font-semibold text-text-primary mb-2">
        Per-Page Scores
      </h2>
      <p className="text-sm text-text-secondary mb-6">
        Select a page to see its score breakdown and live HTML source.
        Click any rule to highlight its element in the source code.
      </p>

      {/* Full-width page table */}
      <div className="glass rounded-xl overflow-hidden mb-6">
        <div className="p-4 border-b border-glass-border">
          <h2 className="text-sm font-medium text-text-primary">
            All Pages ({scores.length})
          </h2>
        </div>
        {scores.length === 0 ? (
          <p className="p-4 text-sm text-text-muted">
            No scores yet. Score pages from the Discover tab.
          </p>
        ) : (
          <div className="max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-base-100 z-10">
                <tr className="border-b border-glass-border">
                  <th className="text-left py-2 px-4 text-xs font-medium text-text-muted">
                    Page
                  </th>
                  <th className="text-left py-2 px-4 text-xs font-medium text-text-muted">
                    Score
                  </th>
                  <th className="text-left py-2 px-4 text-xs font-medium text-text-muted">
                    Last Scored
                  </th>
                </tr>
              </thead>
              <tbody>
                {scores.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => selectPage(s)}
                    className={`border-b border-glass-border/50 hover:bg-glass-hover cursor-pointer transition-colors ${
                      selectedPath === s.path ? "bg-glass-hover" : ""
                    }`}
                  >
                    <td className="py-2.5 px-4 font-mono text-xs text-accent-blue">
                      /{s.path}
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${scoreBadge(s.score)}`}
                      >
                        {s.score}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-text-muted text-xs">
                      {new Date(s.scored_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Two-column detail area */}
      {!detail ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted">
            Select a page to view its score breakdown and HTML source.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left column: Score breakdown */}
          <div className="space-y-6">
            {/* Score Breakdown */}
            <div className="glass rounded-xl p-6">
                <div className="mb-4 space-y-3">
                  {/* Row 1: path + score badge */}
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2.5 py-0.5 rounded-lg text-lg font-bold border shrink-0 ${scoreBadge(detail.score)}`}
                    >
                      {detail.score}
                    </span>
                    <div className="min-w-0">
                      <h2 className="text-base font-semibold text-text-primary truncate">
                        <span className="font-mono text-accent-blue">
                          /{detail.path}
                        </span>
                      </h2>
                      <p className="text-[11px] text-text-muted">
                        {new Date(detail.scored_at).toLocaleDateString()}
                        {currentMeta?.is_custom && (
                          <span className="ml-2 px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 text-[10px] border border-purple-500/30">
                            Custom
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  {/* Row 2: action buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleScorePage(detail.path)}
                      className="btn-secondary text-xs whitespace-nowrap"
                    >
                      Re-score
                    </button>
                    <button
                      onClick={handleVerify}
                      disabled={verifying}
                      className="btn-secondary text-xs disabled:opacity-50 whitespace-nowrap"
                    >
                      {verifying ? "Verifying..." : "Verify Live Page"}
                    </button>
                  </div>
                </div>

                {/* Verification Results */}
                {verifyResult && (
                  <div
                    className={`mb-4 p-4 rounded-lg border ${
                      verifyResult.match
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-red-500/10 border-red-500/30"
                    }`}
                  >
                    <p
                      className={`text-sm font-medium mb-2 ${
                        verifyResult.match
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      {verifyResult.match
                        ? "All meta tags match the rendered page"
                        : `${verifyResult.mismatches.length} mismatch(es) found`}
                    </p>
                    {verifyResult.mismatches.length > 0 && (
                      <div className="space-y-2">
                        {verifyResult.mismatches.map((m, i) => (
                          <div
                            key={i}
                            className="text-xs border-t border-glass-border/30 pt-2"
                          >
                            <p className="font-medium text-text-primary">
                              {m.field}
                            </p>
                            <div className="grid grid-cols-2 gap-2 mt-1">
                              <div>
                                <p className="text-text-muted">Expected</p>
                                <p className="text-green-400 font-mono break-all">
                                  {m.expected || "\u2014"}
                                </p>
                              </div>
                              <div>
                                <p className="text-text-muted">Rendered</p>
                                <p className="text-red-400 font-mono break-all">
                                  {m.actual || "\u2014"}
                                </p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Rule Breakdown */}
                <div className="space-y-6">
                  {Object.entries(groupByCategory(detail.rule_results)).map(
                    ([cat, rules]) => {
                      const catMeta =
                        CATEGORY_LABELS[cat] || CATEGORY_LABELS.general;
                      const catPassed = rules.filter((r) => r.passed).length;
                      return (
                        <div key={cat}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm">{catMeta.icon}</span>
                            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                              {catMeta.label}
                            </h3>
                            <span className="text-xs text-text-muted ml-auto">
                              {catPassed}/{rules.length} passed
                            </span>
                          </div>
                          <div className="space-y-1">
                            {rules.map((r) => {
                              const editable = !!RULE_FIELD_MAP[r.rule_id];
                              const isEditing = editingRule === r.rule_id;
                              const isConfirming =
                                confirmingPassingRule === r.rule_id;
                              const mapping = RULE_FIELD_MAP[r.rule_id];

                              return (
                                <div
                                  key={r.rule_id}
                                  className="border-b border-glass-border/30 last:border-0"
                                >
                                  {/* Rule row */}
                                  <button
                                    onClick={() => handleRuleClick(r)}
                                    className={`w-full text-left py-2 px-2 flex items-center gap-3 rounded-md transition-colors ${
                                      editable
                                        ? "border-l-2 border-l-accent-purple/60 hover:bg-glass-hover/50 cursor-pointer"
                                        : "border-l-2 border-l-transparent hover:bg-glass-hover/30"
                                    }`}
                                  >
                                    <span
                                      className={`w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${
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
                                    {/* Badge */}
                                    {!r.passed && editable && (
                                      <span className="text-[10px] font-medium text-accent-purple px-2 py-0.5 rounded-full bg-accent-purple/10 border border-accent-purple/30 shrink-0">
                                        Fix in Admin
                                      </span>
                                    )}
                                    {!r.passed && !editable && (
                                      <span className="text-[10px] font-medium text-text-muted px-2 py-0.5 rounded-full bg-glass-bg border border-glass-border shrink-0">
                                        Requires Code
                                      </span>
                                    )}
                                    <span className="text-xs text-text-muted shrink-0">
                                      {r.points}/{r.max_points}
                                    </span>
                                    {/* Info button — always far right */}
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        const opening = expandedDescRule !== r.rule_id;
                                        setExpandedDescRule(opening ? r.rule_id : null);
                                        if (opening) {
                                          setEditingRule(null);
                                          setConfirmingPassingRule(null);
                                        }
                                      }}
                                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 transition-colors ${
                                        expandedDescRule === r.rule_id
                                          ? "bg-accent-blue/20 text-accent-blue"
                                          : "bg-glass-bg text-text-muted hover:text-accent-blue hover:bg-accent-blue/10"
                                      }`}
                                      title="Learn about this rule"
                                    >
                                      ?
                                    </button>
                                  </button>

                                  {/* Educational description panel */}
                                  {expandedDescRule === r.rule_id && RULE_DESCRIPTIONS[r.rule_id] && (
                                    <div className="pb-3 px-3">
                                      <div className="p-4 rounded-lg bg-base-100/50 border border-glass-border/30 space-y-3">
                                        <div>
                                          <p className="text-[10px] font-medium text-accent-blue uppercase tracking-wider mb-1">
                                            What this checks
                                          </p>
                                          <p className="text-xs text-text-secondary leading-relaxed">
                                            {RULE_DESCRIPTIONS[r.rule_id].whatItChecks}
                                          </p>
                                        </div>
                                        <div>
                                          <p className="text-[10px] font-medium text-accent-green uppercase tracking-wider mb-1">
                                            Why it matters
                                          </p>
                                          <p className="text-xs text-text-secondary leading-relaxed">
                                            {RULE_DESCRIPTIONS[r.rule_id].whyItMatters}
                                          </p>
                                        </div>
                                        <div>
                                          <p className="text-[10px] font-medium text-accent-purple uppercase tracking-wider mb-1">
                                            Passing looks like
                                          </p>
                                          <p className="text-xs text-text-secondary leading-relaxed">
                                            {RULE_DESCRIPTIONS[r.rule_id].passingLooks}
                                          </p>
                                        </div>
                                        {RULE_DESCRIPTIONS[r.rule_id].howToFix && (
                                          <div>
                                            <p className="text-[10px] font-medium text-amber-400 uppercase tracking-wider mb-1">
                                              How to fix
                                            </p>
                                            <p className="text-xs text-text-secondary leading-relaxed">
                                              {RULE_DESCRIPTIONS[r.rule_id].howToFix}
                                            </p>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  )}

                                  {/* Recommendation for non-editable failing rules */}
                                  {!editable && !r.passed && r.recommendation && (
                                    <div className="pb-2 pl-4">
                                      <p className="text-xs text-text-secondary">
                                        {r.recommendation}
                                      </p>
                                      <div className="mt-2 px-3 py-2 rounded-lg bg-glass-bg border border-glass-border/50">
                                        <p className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-0.5">
                                          Where to fix
                                        </p>
                                        <p className="text-xs text-text-secondary">
                                          {RULE_DESCRIPTIONS[r.rule_id]?.howToFix || "Requires changes to page code"}
                                        </p>
                                      </div>
                                    </div>
                                  )}

                                  {/* Passing rule confirmation */}
                                  {isConfirming && (
                                    <div className="pb-3 pl-8">
                                      <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                                        <p className="text-xs text-yellow-400 mb-2">
                                          This rule is currently passing. Editing
                                          may affect your score.
                                        </p>
                                        <div className="flex gap-2">
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              openEditor(r.rule_id);
                                            }}
                                            className="btn-secondary text-xs"
                                          >
                                            Continue Editing
                                          </button>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              cancelEdit();
                                            }}
                                            className="text-xs text-text-muted hover:text-text-primary"
                                          >
                                            Cancel
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  )}

                                  {/* Inline editor */}
                                  {isEditing && mapping && (
                                    <div className="pb-3 pl-8">
                                      <div className="p-3 rounded-lg bg-glass-bg border border-glass-border">
                                        <label className="block text-xs font-medium text-text-secondary mb-1">
                                          {mapping.label}
                                          {mapping.maxLen && (
                                            <span
                                              className={`ml-2 ${
                                                typeof editValue === "string" &&
                                                editValue.length > mapping.maxLen
                                                  ? "text-red-400"
                                                  : "text-text-muted"
                                              }`}
                                            >
                                              {typeof editValue === "string"
                                                ? editValue.length
                                                : 0}
                                              /{mapping.maxLen}
                                            </span>
                                          )}
                                        </label>

                                        {mapping.type === "checkbox" ? (
                                          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer mt-1">
                                            <input
                                              type="checkbox"
                                              checked={editValue === true}
                                              onChange={(e) =>
                                                setEditValue(e.target.checked)
                                              }
                                              className="rounded border-glass-border"
                                            />
                                            {mapping.label}
                                          </label>
                                        ) : mapping.type === "textarea" ? (
                                          <textarea
                                            rows={3}
                                            maxLength={mapping.maxLen}
                                            value={
                                              typeof editValue === "string"
                                                ? editValue
                                                : ""
                                            }
                                            onChange={(e) =>
                                              setEditValue(e.target.value)
                                            }
                                            className="w-full px-3 py-2 bg-glass-bg border border-glass-border rounded-lg text-sm text-text-primary placeholder-text-muted focus:border-accent-blue focus:outline-none resize-none"
                                            placeholder={`Enter ${mapping.label.toLowerCase()}...`}
                                          />
                                        ) : (
                                          <input
                                            type="text"
                                            maxLength={mapping.maxLen}
                                            value={
                                              typeof editValue === "string"
                                                ? editValue
                                                : ""
                                            }
                                            onChange={(e) =>
                                              setEditValue(e.target.value)
                                            }
                                            className="w-full px-3 py-2 bg-glass-bg border border-glass-border rounded-lg text-sm text-text-primary placeholder-text-muted focus:border-accent-blue focus:outline-none"
                                            placeholder={`Enter ${mapping.label.toLowerCase()}...`}
                                          />
                                        )}

                                        {r.recommendation && (
                                          <p className="text-[10px] text-accent-blue mt-1">
                                            {r.recommendation}
                                          </p>
                                        )}

                                        <div className="flex gap-2 mt-3">
                                          <button
                                            onClick={handleSaveAndRescore}
                                            disabled={saving}
                                            className="btn-primary text-xs disabled:opacity-50"
                                          >
                                            {saving
                                              ? "Saving..."
                                              : "Save & Re-score"}
                                          </button>
                                          <button
                                            onClick={cancelEdit}
                                            className="text-xs text-text-muted hover:text-text-primary"
                                          >
                                            Cancel
                                          </button>
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
                    }
                  )}
                </div>
              </div>

              {/* SEO Advisor Panel */}
              {enable_seo_advisor && (
                <SEOAdvisorPanel
                  path={detail.path}
                  onRuleClick={(ruleId) => setHighlightedRule(ruleId)}
                />
              )}

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
                        title={`${t.score} \u2014 ${new Date(t.scored_at).toLocaleDateString()}`}
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
                  <p className="text-sm text-text-muted">
                    No snapshots yet.
                  </p>
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
                            {Object.entries(snap.diff).map(
                              ([field, change]) => (
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
                                          : String(change.old ?? "\u2014")}
                                      </p>
                                    </div>
                                    <div>
                                      <p className="text-text-muted">After</p>
                                      <p className="text-green-400 font-mono break-all">
                                        {typeof change.new === "object"
                                          ? JSON.stringify(change.new)
                                          : String(change.new ?? "\u2014")}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right column: HTML Source Viewer */}
            <div className="lg:sticky lg:top-4 lg:self-start">
              <HtmlSourceViewer
                html={pageHtml}
                loading={htmlLoading}
                ruleResults={detail.rule_results}
                highlightedRule={highlightedRule}
              />
            </div>
          </div>
        )}
    </div>
  );
}
