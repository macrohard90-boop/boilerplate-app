"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useConfig } from "../../../../lib/config-context";
import { useToast } from "../../../../components/Toast";
import LoadingSpinner from "../../../../components/LoadingSpinner";

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

export default function SeoOverviewPage() {
  const { showToast } = useToast();
  const { enable_seo_scoring } = useConfig();
  const [config, setConfig] = useState<SEOConfig | null>(null);
  const [scores, setScores] = useState<PageScore[]>([]);
  const [overrides, setOverrides] = useState<MetaOverride[]>([]);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [scoring, setScoring] = useState(false);

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
        }
      } catch {}
      setLoading(false);
    }
    load();
  }, [enable_seo_scoring]);

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      await apiFetch("/seo/admin/seo/sitemap/regenerate", { method: "POST" });
      showToast("Sitemap cache invalidated", "success");
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
      // Refresh scores
      const scoreData = await apiFetch<{ items: PageScore[] }>(
        "/seo/admin/seo/scores?page_size=50"
      ).catch(() => ({ items: [] }));
      setScores(scoreData.items || []);
    } catch (e) {
      showToast((e as ApiError).message || "Scoring failed", "error");
    }
    setScoring(false);
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  const avgScore =
    scores.length > 0
      ? Math.round(scores.reduce((s, p) => s + p.score, 0) / scores.length)
      : null;

  const lowestScores = [...scores]
    .sort((a, b) => a.score - b.score)
    .slice(0, 5);

  function scoreBadge(score: number) {
    if (score >= 80) return "bg-green-500/20 text-green-400 border-green-500/30";
    if (score >= 50) return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    return "bg-red-500/20 text-red-400 border-red-500/30";
  }

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">SEO Overview</span>
      </h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {enable_seo_scoring && avgScore !== null && (
          <div className="glass rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
              Avg Score
            </p>
            <p className="text-3xl font-bold">
              <span className={`px-2 py-0.5 rounded-lg text-2xl font-bold border ${scoreBadge(avgScore)}`}>
                {avgScore}
              </span>
            </p>
          </div>
        )}
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Pages Scored
          </p>
          <p className="text-3xl font-bold text-text-primary">{scores.length}</p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Custom Overrides
          </p>
          <p className="text-3xl font-bold text-text-primary">
            {overrides.length}
          </p>
        </div>
        <div className="glass rounded-xl p-5">
          <p className="text-xs text-text-muted uppercase tracking-wider mb-1">
            Site
          </p>
          <p className="text-lg font-medium text-text-primary truncate">
            {config?.domain || "—"}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Sitemap */}
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

        {/* Score All */}
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

      {/* Lowest Scoring Pages */}
      {enable_seo_scoring && lowestScores.length > 0 && (
        <div className="glass rounded-xl p-6">
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
                    className="border-b border-glass-border/50 hover:bg-glass-hover"
                  >
                    <td className="py-2 px-3 font-mono text-accent-blue">
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
    </div>
  );
}
