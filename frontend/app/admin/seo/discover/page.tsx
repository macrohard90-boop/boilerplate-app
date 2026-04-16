"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useConfig } from "../../../../lib/config-context";
import { useToast } from "../../../../components/Toast";
import LoadingSpinner from "../../../../components/LoadingSpinner";
import Modal from "../../../../components/Modal";
import Pagination from "../../../../components/Pagination";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface SEOConfig {
  site_name: string;
  default_og_image: string;
  domain: string;
  sitemap_cache_ttl: number;
}

interface PageScore {
  id: string;
  path: string;
  score: number;
  provider: string;
  scored_at: string;
}

interface MetaOverride {
  id: string;
  path: string;
  title: string;
}

interface TrafficItem {
  path: string;
  views: number;
  unique_sessions: number;
  avg_duration_ms: number | null;
  trend: string;
  seo_score: number | null;
}

interface TrafficReport {
  top_pages: TrafficItem[];
  opportunities: TrafficItem[];
  urgent_fixes: TrafficItem[];
  period_days: number;
}

interface TargetKeyword {
  id: string;
  keyword: string;
  path: string | null;
  priority: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface TargetKeywordList {
  items: TargetKeyword[];
  total: number;
  page: number;
  page_size: number;
}

interface KeywordSuggestion {
  keyword: string;
  search_volume: number | null;
  competition: number | null;
  trend: string | null;
  source: string;
  depth_level: number;
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const EMPTY_FORM = { keyword: "", path: "", priority: 5, notes: "" };

const DEPTH_LABELS: Record<number, string> = {
  1: "Direct",
  2: "Related",
  3: "Adjacent",
};

const TREND_COLORS: Record<string, string> = {
  rising: "text-green-400",
  stable: "text-text-muted",
  declining: "text-red-400",
};

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DiscoverPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const { enable_seo_scoring, enable_seo_keywords, enable_tracking } =
    useConfig();

  /* ── Overview state ── */
  const [config, setConfig] = useState<SEOConfig | null>(null);
  const [scores, setScores] = useState<PageScore[]>([]);
  const [overrides, setOverrides] = useState<MetaOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [trafficData, setTrafficData] = useState<TrafficReport | null>(null);
  const [infoCollapsed, setInfoCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("seo-info-collapsed") === "true";
    }
    return false;
  });

  const [kwInfoCollapsed, setKwInfoCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("seo-keywords-info-collapsed") === "true";
    }
    return false;
  });

  /* ── Keywords state ── */
  const [targets, setTargets] = useState<TargetKeywordList | null>(null);
  const [targetsPage, setTargetsPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [seed, setSeed] = useState("");
  const [depth, setDepth] = useState(2);
  const [discovering, setDiscovering] = useState(false);
  const [suggestions, setSuggestions] = useState<KeywordSuggestion[]>([]);
  const [discoverSeed, setDiscoverSeed] = useState("");

  /* ── Data fetching ── */
  useEffect(() => {
    async function load() {
      try {
        const [cfg, meta] = await Promise.all([
          apiFetch<SEOConfig>("/seo/admin/seo/config").catch(() => null),
          apiFetch<{ items: MetaOverride[] }>("/seo/admin/seo/meta").catch(
            () => ({ items: [] })
          ),
        ]);
        setConfig(cfg);
        setOverrides(meta.items || []);

        if (enable_seo_scoring) {
          const scoreData = await apiFetch<{ items: PageScore[] }>(
            "/seo/admin/seo/scores?page_size=50"
          ).catch(() => ({ items: [] }));
          setScores(scoreData.items || []);

          if (enable_tracking) {
            const traffic = await apiFetch<TrafficReport>(
              "/seo/admin/seo/analytics/traffic?days=30&limit=20"
            ).catch(() => null);
            setTrafficData(traffic);
          }
        }
      } catch {}
      setLoading(false);
    }
    load();
  }, [enable_seo_scoring, enable_tracking]);

  /* ── Keyword targets fetch ── */
  async function fetchTargets(pg: number = targetsPage) {
    try {
      const res = await apiFetch<TargetKeywordList>(
        `/seo/admin/seo/keywords/targets?page=${pg}&page_size=20`
      );
      setTargets(res);
    } catch {}
  }

  useEffect(() => {
    if (enable_seo_keywords) fetchTargets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetsPage, enable_seo_keywords]);

  /* ── Overview handlers ── */
  function navigateToPage(path: string) {
    const normalized = path.replace(/^\//, "");
    router.push(
      "/admin/seo/optimize?page=" + encodeURIComponent(normalized)
    );
  }

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      await apiFetch("/seo/admin/seo/sitemap/regenerate", { method: "POST" });
      showToast(
        "Sitemap refreshed! Search engines will see the updated version on their next visit.",
        "success"
      );
    } catch (e) {
      showToast((e as ApiError).message || "Failed", "error");
    }
    setRegenerating(false);
  }

  async function handleScoreAll() {
    setScoring(true);
    try {
      const res = await apiFetch<{ message: string }>(
        "/seo/admin/seo/scores/batch",
        { method: "POST" }
      );
      showToast(res.message, "success");
      const scoreData = await apiFetch<{ items: PageScore[] }>(
        "/seo/admin/seo/scores?page_size=50"
      ).catch(() => ({ items: [] }));
      setScores(scoreData.items || []);
    } catch (e) {
      showToast((e as ApiError).message || "Scoring failed", "error");
    }
    setScoring(false);
  }

  /* ── Keyword CRUD handlers ── */
  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setModalOpen(true);
  }

  function openEdit(kw: TargetKeyword) {
    setForm({
      keyword: kw.keyword,
      path: kw.path || "",
      priority: kw.priority,
      notes: kw.notes || "",
    });
    setEditingId(kw.id);
    setModalOpen(true);
  }

  async function handleSave() {
    if (!form.keyword.trim()) {
      showToast("Keyword is required", "error");
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await apiFetch(`/seo/admin/seo/keywords/targets/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            priority: form.priority,
            notes: form.notes || null,
            path: form.path || null,
          }),
        });
        showToast("Keyword updated", "success");
      } else {
        await apiFetch("/seo/admin/seo/keywords/targets", {
          method: "POST",
          body: JSON.stringify({
            keyword: form.keyword,
            path: form.path || null,
            priority: form.priority,
            notes: form.notes || null,
          }),
        });
        showToast("Keyword assigned", "success");
      }
      setModalOpen(false);
      fetchTargets();
    } catch (e) {
      showToast((e as ApiError).message || "Save failed", "error");
    }
    setSaving(false);
  }

  async function handleDelete(id: string) {
    try {
      await apiFetch(`/seo/admin/seo/keywords/targets/${id}`, {
        method: "DELETE",
      });
      showToast("Keyword removed", "success");
      fetchTargets();
    } catch {
      showToast("Failed to remove keyword", "error");
    }
  }

  /* ── Keyword discovery handlers ── */
  async function handleDiscover() {
    if (!seed.trim()) {
      showToast("Enter a seed keyword", "error");
      return;
    }
    setDiscovering(true);
    setSuggestions([]);
    setDiscoverSeed(seed);
    try {
      const res = await apiFetch<{ items: KeywordSuggestion[] }>(
        "/seo/admin/seo/keywords/discover",
        {
          method: "POST",
          body: JSON.stringify({ seed, depth, limit: 50 }),
        }
      );
      setSuggestions(res.items || []);
      if (!res.items?.length) showToast("No suggestions found", "info");
    } catch (e) {
      showToast((e as ApiError).message || "Discovery failed", "error");
    }
    setDiscovering(false);
  }

  function assignSuggestion(keyword: string) {
    setForm({ keyword, path: "", priority: 5, notes: "" });
    setEditingId(null);
    setModalOpen(true);
  }

  /* ── Helpers ── */
  function scoreBadge(score: number) {
    if (score >= 80) return "bg-green-500/20 text-green-400 border-green-500/30";
    if (score >= 50)
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    return "bg-red-500/20 text-red-400 border-red-500/30";
  }

  function toggleInfo() {
    const next = !infoCollapsed;
    setInfoCollapsed(next);
    localStorage.setItem("seo-info-collapsed", String(next));
  }

  function toggleKwInfo() {
    const next = !kwInfoCollapsed;
    setKwInfoCollapsed(next);
    localStorage.setItem("seo-keywords-info-collapsed", String(next));
  }

  /* ── Loading ── */
  if (loading) return <LoadingSpinner className="py-20" />;

  const avgScore =
    scores.length > 0
      ? Math.round(scores.reduce((s, p) => s + p.score, 0) / scores.length)
      : null;

  const lowestScores = [...scores]
    .sort((a, b) => a.score - b.score)
    .slice(0, 5);

  const totalKwPages = targets ? Math.ceil(targets.total / 20) : 1;

  /* ── Render ── */
  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Discover</span>
      </h1>

      {/* ================================================================ */}
      {/* SECTION: Pages & Scoring Overview                                */}
      {/* ================================================================ */}

      {/* How SEO Scoring Works */}
      {enable_seo_scoring && (
        <div className="glass rounded-xl mb-6 overflow-hidden">
          <button
            onClick={toggleInfo}
            className="w-full text-left px-6 py-4 flex items-center justify-between hover:bg-glass-hover transition-colors"
          >
            <span className="text-sm font-medium text-text-primary">
              How SEO Scoring Works
            </span>
            <span className="text-text-muted text-xs">
              {infoCollapsed ? "Show" : "Hide"}
            </span>
          </button>
          {!infoCollapsed && (
            <div className="px-6 pb-5 border-t border-glass-border/50">
              <p className="text-sm text-text-secondary mt-4 mb-3">
                SEO scoring measures how well your{" "}
                <strong className="text-text-primary">public pages</strong> are
                optimized for search engines. Only pages visible without login
                are scored — these are the pages Google and other search engines
                see and index.
              </p>
              <p className="text-sm text-text-secondary mb-3">
                Each page is scored 0-100 based on 20 rules across 4 categories:
              </p>
              <div className="space-y-3 text-xs text-text-muted mb-3">
                <div>
                  <p className="text-text-secondary font-medium mb-1">
                    Content (8 rules)
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0.5">
                    <span>Title present and 30-60 characters</span>
                    <span>Meta description present and 120-160 characters</span>
                    <span>H1 heading present</span>
                    <span>All images have alt text</span>
                    <span>Content length sufficient (300+ chars)</span>
                    <span>Internal links present (2+)</span>
                    <span>Target keyword in title/desc/H1</span>
                  </div>
                </div>
                <div>
                  <p className="text-text-secondary font-medium mb-1">
                    Technical (5 rules)
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0.5">
                    <span>Canonical URL set</span>
                    <span>Page is indexable (not noindex)</span>
                    <span>Heading hierarchy valid (no skipped levels)</span>
                    <span>URL structure clean (short, hyphens)</span>
                    <span>Canonical is self-referencing</span>
                    <span>HTTPS enforced</span>
                  </div>
                </div>
                <div>
                  <p className="text-text-secondary font-medium mb-1">
                    Social (3 rules)
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0.5">
                    <span>Open Graph tags complete</span>
                    <span>Twitter Card tags complete</span>
                    <span>Page-specific OG image</span>
                  </div>
                </div>
                <div>
                  <p className="text-text-secondary font-medium mb-1">
                    Performance (2 rules)
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0.5">
                    <span>Structured data present (JSON-LD)</span>
                    <span>Structured data has required fields</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-4 text-xs mb-2">
                <span className="text-green-400">80+ = Good</span>
                <span className="text-yellow-400">50-79 = Needs work</span>
                <span className="text-red-400">Below 50 = Poor</span>
              </div>
              <p className="text-xs text-text-muted">
                Click any page to view its full score breakdown and edit SEO
                fields directly.
              </p>
            </div>
          )}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {enable_seo_scoring && avgScore !== null && (
          <div className="glass rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
              Avg Score
            </p>
            <p className="text-3xl font-bold">
              <span
                className={`px-2 py-0.5 rounded-lg text-2xl font-bold border ${scoreBadge(avgScore)}`}
              >
                {avgScore}
              </span>
            </p>
            <p className="text-xs text-text-muted mt-2">across public pages</p>
          </div>
        )}
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Pages Scored
          </p>
          <p className="text-3xl font-bold text-text-primary">{scores.length}</p>
          <p className="text-xs text-text-muted mt-2">public pages analyzed</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Custom Overrides
          </p>
          <p className="text-3xl font-bold text-text-primary">
            {overrides.length}
          </p>
          <p className="text-xs text-text-muted mt-2">
            manual meta customizations
          </p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Site
          </p>
          <p className="text-lg font-medium text-text-primary truncate">
            {config?.domain || "\u2014"}
          </p>
        </div>
      </div>

      {/* Traffic & SEO Correlation */}
      {enable_tracking && trafficData && (
        <div className="mb-8 space-y-6">
          <h2 className="font-serif text-xl font-bold">
            <span className="gradient-text">Traffic &amp; SEO Correlation</span>
          </h2>

          {trafficData.urgent_fixes.length > 0 && (
            <div className="glass rounded-xl p-6">
              <h3 className="text-sm font-semibold text-red-400 mb-1">
                Urgent Fixes
              </h3>
              <p className="text-xs text-text-muted mb-3">
                Pages getting traffic but with low SEO scores — fix these first.
              </p>
              <TrafficTable
                items={trafficData.urgent_fixes}
                scoreBadge={scoreBadge}
                onPageClick={navigateToPage}
              />
            </div>
          )}

          {trafficData.opportunities.length > 0 && (
            <div className="glass rounded-xl p-6">
              <h3 className="text-sm font-semibold text-accent-blue mb-1">
                Opportunities
              </h3>
              <p className="text-xs text-text-muted mb-3">
                Pages with strong SEO scores (70+) that aren&apos;t receiving
                traffic yet — promote these.
              </p>
              <TrafficTable
                items={trafficData.opportunities}
                scoreBadge={scoreBadge}
                onPageClick={navigateToPage}
              />
            </div>
          )}

          {trafficData.top_pages.length > 0 && (
            <div className="glass rounded-xl p-6">
              <h3 className="text-sm font-semibold text-text-primary mb-1">
                Top Pages by Traffic
              </h3>
              <p className="text-xs text-text-muted mb-3">
                Most visited pages in the last {trafficData.period_days} days.
              </p>
              <TrafficTable
                items={trafficData.top_pages}
                scoreBadge={scoreBadge}
                onPageClick={navigateToPage}
              />
            </div>
          )}

          {trafficData.top_pages.length === 0 &&
            trafficData.urgent_fixes.length === 0 &&
            trafficData.opportunities.length === 0 && (
              <div className="glass rounded-xl p-6">
                <p className="text-sm text-text-muted">
                  No traffic data available yet. Traffic will appear here once
                  visitors start browsing your site.
                </p>
              </div>
            )}
        </div>
      )}

      {/* Lowest Scoring Pages */}
      {enable_seo_scoring && lowestScores.length > 0 && (
        <div className="glass rounded-xl p-6 mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Lowest Scoring Pages
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left py-2 px-3 text-xs font-medium text-text-muted">
                    Path
                  </th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-text-muted">
                    Score
                  </th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-text-muted">
                    Last Scored
                  </th>
                </tr>
              </thead>
              <tbody>
                {lowestScores.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-glass-border/50 hover:bg-glass-hover cursor-pointer"
                    onClick={() => navigateToPage(s.path)}
                  >
                    <td className="py-2 px-3 font-mono text-accent-blue text-xs hover:underline">
                      /{s.path}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${scoreBadge(s.score)}`}
                      >
                        {s.score}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-text-muted">
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
        </div>
      )}

      {/* Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="glass rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-2">
            Sitemap
          </h2>
          <p className="text-sm text-text-secondary mb-4">
            Regenerate the cached sitemap.xml (TTL: {config?.sitemap_cache_ttl}s)
          </p>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="btn-secondary text-sm disabled:opacity-50"
          >
            {regenerating ? "Regenerating..." : "Regenerate Sitemap"}
          </button>
        </div>

        {enable_seo_scoring && (
          <div className="glass rounded-xl p-6">
            <h2 className="text-lg font-semibold text-text-primary mb-2">
              Scoring
            </h2>
            <p className="text-sm text-text-secondary mb-4">
              Score all pages now (also runs automatically on schedule)
            </p>
            <button
              onClick={handleScoreAll}
              disabled={scoring}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              {scoring ? "Scoring..." : "Score All Pages"}
            </button>
          </div>
        )}
      </div>

      {/* Config */}
      {config && (
        <div className="glass rounded-xl p-6 mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Configuration
          </h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-text-muted">Site name</p>
              <p className="text-text-primary">{config.site_name}</p>
            </div>
            <div>
              <p className="text-text-muted">Domain</p>
              <p className="text-text-primary">{config.domain}</p>
            </div>
            <div>
              <p className="text-text-muted">OG Image</p>
              <p className="text-text-primary text-xs font-mono">
                {config.default_og_image}
              </p>
            </div>
            <div>
              <p className="text-text-muted">Sitemap TTL</p>
              <p className="text-text-primary">{config.sitemap_cache_ttl}s</p>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* SECTION: Keywords                                                */}
      {/* ================================================================ */}

      {enable_seo_keywords && (
        <div className="space-y-8">
          <div className="border-t border-glass-border pt-8">
            {/* How Keyword Targeting Works */}
            <div className="glass rounded-xl mb-6 overflow-hidden">
              <button
                onClick={toggleKwInfo}
                className="w-full text-left px-6 py-4 flex items-center justify-between hover:bg-glass-hover transition-colors"
              >
                <span className="text-sm font-medium text-text-primary">
                  How Keyword Targeting Works
                </span>
                <span className="text-text-muted text-xs">
                  {kwInfoCollapsed ? "Show" : "Hide"}
                </span>
              </button>
              {!kwInfoCollapsed && (
                <div className="px-6 pb-5 border-t border-glass-border/50">
                  <p className="text-sm text-text-secondary mt-4 mb-4">
                    Target keywords connect your SEO scoring, content optimization,
                    and AI advisor into one workflow. Here&apos;s how the pieces fit
                    together:
                  </p>
                  <div className="space-y-4 text-sm">
                    <div className="flex gap-3">
                      <span className="shrink-0 w-6 h-6 rounded-full bg-accent-purple/20 text-accent-purple text-xs font-bold flex items-center justify-center">
                        1
                      </span>
                      <div>
                        <p className="text-text-primary font-medium">Discover</p>
                        <p className="text-text-secondary text-xs mt-0.5">
                          Enter a seed keyword (e.g., &ldquo;leather shoes&rdquo;) to
                          find related search terms via Google Autocomplete. The depth
                          setting controls how many levels of related terms to explore:
                          Direct (exact completions), Related (completions of completions),
                          or Adjacent (one more level out).
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="shrink-0 w-6 h-6 rounded-full bg-accent-blue/20 text-accent-blue text-xs font-bold flex items-center justify-center">
                        2
                      </span>
                      <div>
                        <p className="text-text-primary font-medium">Assign</p>
                        <p className="text-text-secondary text-xs mt-0.5">
                          Pick promising keywords from the results and assign them to
                          specific pages. Set priority (1&ndash;10) to control which
                          keyword the scoring engine checks first. Leave the page field
                          blank to make a keyword apply site-wide.
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="shrink-0 w-6 h-6 rounded-full bg-accent-green/20 text-accent-green text-xs font-bold flex items-center justify-center">
                        3
                      </span>
                      <div>
                        <p className="text-text-primary font-medium">Score</p>
                        <p className="text-text-secondary text-xs mt-0.5">
                          When a page is scored, the engine checks if your
                          highest-priority keyword appears in the page&apos;s title,
                          meta description, and H1 heading (must appear in at least 2
                          of 3). It also checks keyword density in the body text
                          (ideal: 0.5&ndash;3%). Without assigned keywords, these rules
                          auto-pass.
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="shrink-0 w-6 h-6 rounded-full bg-accent-pink/20 text-accent-pink text-xs font-bold flex items-center justify-center">
                        4
                      </span>
                      <div>
                        <p className="text-text-primary font-medium">Optimize</p>
                        <p className="text-text-secondary text-xs mt-0.5">
                          Go to the Optimize tab, select a page, and use the inline
                          editor to update the title, description, and other fields to
                          include your target keyword. The AI Advisor also receives your
                          keywords and gives targeted suggestions based on what
                          competitors rank for.
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 p-3 rounded-lg bg-base-100/50 border border-glass-border/30">
                    <p className="text-xs text-text-muted">
                      <strong className="text-text-secondary">Data source:</strong>{" "}
                      Keywords are discovered using Google Autocomplete (free, no API
                      key required). Assigned keywords are stored in the database and
                      persist across scoring runs.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* ── Target Keywords ── */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-serif text-xl font-bold">
                  <span className="gradient-text">Target Keywords</span>
                </h2>
                <button onClick={openCreate} className="btn-primary text-sm">
                  + Assign Keyword
                </button>
              </div>

              <p className="text-sm text-text-secondary mb-4">
                Assign keywords to pages so the scoring engine checks whether each
                page&apos;s title, description, and H1 include the target keyword.
              </p>

              <div className="glass rounded-xl overflow-hidden">
                {!targets || targets.items.length === 0 ? (
                  <p className="p-6 text-sm text-text-muted">
                    No target keywords yet. Assign keywords to pages to track SEO
                    optimization for specific search terms.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-glass-border">
                          <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                            Keyword
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                            Page
                          </th>
                          <th className="text-center py-3 px-4 text-xs font-medium text-text-muted">
                            Priority
                          </th>
                          <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                            Notes
                          </th>
                          <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {targets.items.map((kw) => (
                          <tr
                            key={kw.id}
                            className="border-b border-glass-border/50 hover:bg-glass-hover"
                          >
                            <td className="py-3 px-4 text-text-primary font-medium">
                              {kw.keyword}
                            </td>
                            <td className="py-3 px-4 font-mono text-accent-blue text-xs">
                              {kw.path ? `/${kw.path}` : "(site-wide)"}
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-accent-purple/20 text-accent-purple">
                                {kw.priority}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-text-secondary text-xs max-w-[200px] truncate">
                              {kw.notes || "\u2014"}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <button
                                onClick={() => openEdit(kw)}
                                className="text-accent-blue hover:text-accent-purple text-xs mr-3 transition-colors"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => handleDelete(kw.id)}
                                className="text-text-muted hover:text-accent-pink text-xs transition-colors"
                              >
                                Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {totalKwPages > 1 && (
                <div className="mt-4">
                  <Pagination
                    currentPage={targetsPage}
                    totalPages={totalKwPages}
                    onPageChange={setTargetsPage}
                  />
                </div>
              )}
            </section>

            {/* ── Discover Keywords ── */}
            <section className="mt-8">
              <h2 className="font-serif text-xl font-bold mb-4">
                <span className="gradient-text">Discover Keywords</span>
              </h2>

              <p className="text-sm text-text-secondary mb-4">
                Enter a seed keyword to discover related search terms using Google
                Autocomplete. Assign promising suggestions as target keywords.
              </p>

              <div className="glass rounded-xl p-6">
                <div className="flex items-end gap-4 mb-6">
                  <div className="flex-1">
                    <label className="block text-sm text-text-secondary mb-1">
                      Seed Keyword
                    </label>
                    <input
                      type="text"
                      value={seed}
                      onChange={(e) => setSeed(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleDiscover()}
                      placeholder="e.g., energy conference Calgary"
                      className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
                    />
                  </div>
                  <div className="w-28">
                    <label className="block text-sm text-text-secondary mb-1">
                      Depth
                    </label>
                    <select
                      value={depth}
                      onChange={(e) => setDepth(Number(e.target.value))}
                      className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
                    >
                      <option value={1}>1 (Direct)</option>
                      <option value={2}>2 (Related)</option>
                      <option value={3}>3 (Adjacent)</option>
                    </select>
                  </div>
                  <button
                    onClick={handleDiscover}
                    disabled={discovering}
                    className="btn-primary text-sm disabled:opacity-50"
                  >
                    {discovering ? "Discovering..." : "Discover"}
                  </button>
                </div>

                {/* Results */}
                {suggestions.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-text-primary">
                        Results for &ldquo;{discoverSeed}&rdquo;
                        <span className="ml-2 text-xs text-text-muted">
                          ({suggestions.length} suggestions)
                        </span>
                      </h3>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-glass-border">
                            <th className="text-left py-2 px-3 text-xs font-medium text-text-muted">
                              Keyword
                            </th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
                              Depth
                            </th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
                              Trend
                            </th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
                              Competition
                            </th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
                              Source
                            </th>
                            <th className="text-right py-2 px-3 text-xs font-medium text-text-muted">
                              Action
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {suggestions.map((s, i) => (
                            <tr
                              key={`${s.keyword}-${i}`}
                              className="border-b border-glass-border/50 hover:bg-glass-hover"
                            >
                              <td className="py-2 px-3 text-text-primary">
                                {s.keyword}
                              </td>
                              <td className="py-2 px-3 text-center">
                                <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-glass-bg">
                                  {DEPTH_LABELS[s.depth_level] || `L${s.depth_level}`}
                                </span>
                              </td>
                              <td
                                className={`py-2 px-3 text-center text-xs ${TREND_COLORS[s.trend || ""] || "text-text-muted"}`}
                              >
                                {s.trend || "\u2014"}
                              </td>
                              <td className="py-2 px-3 text-center text-xs text-text-muted">
                                {s.competition != null
                                  ? `${Math.round(s.competition * 100)}%`
                                  : "\u2014"}
                              </td>
                              <td className="py-2 px-3 text-center text-xs text-text-muted">
                                {s.source}
                              </td>
                              <td className="py-2 px-3 text-right">
                                <button
                                  onClick={() => assignSuggestion(s.keyword)}
                                  className="text-accent-blue hover:text-accent-purple text-xs transition-colors"
                                >
                                  Assign
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {discovering && (
                  <div className="flex items-center gap-2 text-sm text-text-muted">
                    <LoadingSpinner className="w-4 h-4" />
                    Querying keyword provider...
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* ── Keyword Modal ── */}
          {modalOpen && (
            <Modal
              isOpen={modalOpen}
              title={editingId ? "Edit Target Keyword" : "Assign Target Keyword"}
              onClose={() => setModalOpen(false)}
            >
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-text-secondary mb-1">
                    Keyword
                  </label>
                  <input
                    type="text"
                    value={form.keyword}
                    onChange={(e) => setForm({ ...form, keyword: e.target.value })}
                    disabled={!!editingId}
                    placeholder="e.g., energy conference Calgary"
                    className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary disabled:opacity-50"
                  />
                </div>

                <div>
                  <label className="block text-sm text-text-secondary mb-1">
                    Target Page (leave empty for site-wide)
                  </label>
                  <input
                    type="text"
                    value={form.path}
                    onChange={(e) => setForm({ ...form, path: e.target.value })}
                    placeholder="products/my-product"
                    className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm text-text-secondary mb-1">
                    Priority (1 = low, 10 = high)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={form.priority}
                    onChange={(e) =>
                      setForm({ ...form, priority: Number(e.target.value) })
                    }
                    className="w-24 bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm text-text-secondary mb-1">
                    Notes (optional)
                  </label>
                  <textarea
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    rows={2}
                    placeholder="Why this keyword matters..."
                    className="w-full bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary resize-none"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => setModalOpen(false)}
                    className="btn-secondary text-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="btn-primary text-sm disabled:opacity-50"
                  >
                    {saving ? "Saving..." : editingId ? "Update" : "Assign"}
                  </button>
                </div>
              </div>
            </Modal>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Traffic Table (sub-component) ── */

function TrafficTable({
  items,
  scoreBadge,
  onPageClick,
}: {
  items: TrafficItem[];
  scoreBadge: (score: number) => string;
  onPageClick: (path: string) => void;
}) {
  const TREND_ICON: Record<string, string> = {
    rising: "text-green-400",
    stable: "text-text-muted",
    declining: "text-red-400",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-glass-border">
            <th className="text-left py-2 px-3 text-xs font-medium text-text-muted">
              Path
            </th>
            <th className="text-right py-2 px-3 text-xs font-medium text-text-muted">
              Views
            </th>
            <th className="text-right py-2 px-3 text-xs font-medium text-text-muted">
              Sessions
            </th>
            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
              Trend
            </th>
            <th className="text-center py-2 px-3 text-xs font-medium text-text-muted">
              SEO Score
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr
              key={`${item.path}-${i}`}
              className="border-b border-glass-border/50 hover:bg-glass-hover cursor-pointer"
              onClick={() => onPageClick(item.path)}
            >
              <td className="py-2 px-3 font-mono text-accent-blue text-xs hover:underline">
                {item.path || "/"}
              </td>
              <td className="py-2 px-3 text-right text-text-primary">
                {item.views.toLocaleString()}
              </td>
              <td className="py-2 px-3 text-right text-text-muted">
                {item.unique_sessions.toLocaleString()}
              </td>
              <td
                className={`py-2 px-3 text-center text-xs ${TREND_ICON[item.trend] || "text-text-muted"}`}
              >
                {item.trend === "rising"
                  ? "Rising"
                  : item.trend === "declining"
                    ? "Declining"
                    : "Stable"}
              </td>
              <td className="py-2 px-3 text-center">
                {item.seo_score != null ? (
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium border ${scoreBadge(item.seo_score)}`}
                  >
                    {item.seo_score}
                  </span>
                ) : (
                  <span className="text-xs text-text-muted">{"\u2014"}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
