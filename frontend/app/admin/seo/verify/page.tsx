"use client";

import { useEffect, useState } from "react";
import { apiFetch, type ApiError } from "../../../../lib/api";
import { useToast } from "../../../../components/Toast";
import LoadingSpinner from "../../../../components/LoadingSpinner";

interface CrawlMismatch {
  field: string;
  expected: string | null;
  actual: string | null;
  severity: string;
}

interface CrawlResult {
  id: string;
  path: string;
  status_code: number | null;
  mismatches: CrawlMismatch[];
  crawled_at: string;
}

interface CrawlDetail extends CrawlResult {
  rendered_meta: Record<string, unknown> | null;
  api_meta: Record<string, unknown> | null;
}

export default function SeoVerifyPage() {
  const { showToast } = useToast();
  const [results, setResults] = useState<CrawlResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [crawlPath, setCrawlPath] = useState("");
  const [detail, setDetail] = useState<CrawlDetail | null>(null);

  async function fetchResults() {
    try {
      const res = await apiFetch<{ items: CrawlResult[] }>(
        "/seo/admin/seo/crawl/results?page_size=50"
      );
      setResults(res.items || []);
    } catch {}
    setLoading(false);
  }

  useEffect(() => {
    fetchResults();
  }, []);

  async function handleCrawlSingle() {
    if (!crawlPath.trim()) {
      showToast("Enter a page path", "error");
      return;
    }
    setCrawling(true);
    try {
      const res = await apiFetch<{ message: string }>(
        `/seo/admin/seo/crawl/${crawlPath}`,
        { method: "POST" }
      );
      showToast(res.message, "success");
      fetchResults();
    } catch (e) {
      showToast((e as ApiError).message || "Crawl failed", "error");
    }
    setCrawling(false);
  }

  async function handleCrawlAll() {
    setCrawling(true);
    try {
      const res = await apiFetch<{ message: string }>(
        "/seo/admin/seo/crawl/batch",
        { method: "POST" }
      );
      showToast(res.message, "success");
      fetchResults();
    } catch (e) {
      showToast((e as ApiError).message || "Batch crawl failed", "error");
    }
    setCrawling(false);
  }

  async function viewDetail(id: string) {
    try {
      const res = await apiFetch<CrawlDetail>(
        `/seo/admin/seo/crawl/results/${id}`
      );
      setDetail(res);
    } catch {
      showToast("Failed to load detail", "error");
    }
  }

  function severityBadge(severity: string) {
    if (severity === "critical")
      return "bg-red-500/20 text-red-400 border-red-500/30";
    if (severity === "warning")
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    return "bg-blue-500/20 text-blue-400 border-blue-500/30";
  }

  if (loading) return <LoadingSpinner className="py-20" />;

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Verify</span>
      </h1>

      {/* Controls */}
      <div className="glass rounded-xl p-6 mb-6">
        <p className="text-sm text-text-secondary mb-4">
          Crawl pages with a real browser to verify that rendered meta tags match
          your API-configured values. Detects mismatches in title, description,
          OG tags, and more.
        </p>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 flex gap-2">
            <input
              type="text"
              value={crawlPath}
              onChange={(e) => setCrawlPath(e.target.value)}
              placeholder="products/my-product"
              className="flex-1 bg-glass-bg border border-glass-border rounded-lg px-3 py-2 text-sm text-text-primary"
            />
            <button
              onClick={handleCrawlSingle}
              disabled={crawling}
              className="btn-secondary text-sm disabled:opacity-50 whitespace-nowrap"
            >
              Crawl Page
            </button>
          </div>
          <button
            onClick={handleCrawlAll}
            disabled={crawling}
            className="btn-primary text-sm disabled:opacity-50 whitespace-nowrap"
          >
            {crawling ? "Crawling..." : "Crawl All Pages"}
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="glass rounded-xl overflow-hidden mb-6">
        {results.length === 0 ? (
          <p className="p-6 text-sm text-text-muted">
            No crawl results yet. Trigger a crawl above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border">
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Path
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Status
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Mismatches
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-text-muted">
                    Crawled
                  </th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-glass-border/50 hover:bg-glass-hover"
                  >
                    <td className="py-3 px-4 font-mono text-accent-blue text-xs">
                      /{r.path}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                          r.status_code === 200
                            ? "bg-green-500/20 text-green-400 border-green-500/30"
                            : "bg-red-500/20 text-red-400 border-red-500/30"
                        }`}
                      >
                        {r.status_code || "ERR"}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {r.mismatches.length === 0 ? (
                        <span className="text-green-400 text-xs">All match</span>
                      ) : (
                        <span className="text-yellow-400 text-xs font-medium">
                          {r.mismatches.length} issue(s)
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-text-muted text-xs">
                      {new Date(r.crawled_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => viewDetail(r.id)}
                        className="text-accent-blue hover:text-accent-purple text-xs transition-colors"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {detail && (
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary">
              Crawl Detail: <span className="font-mono text-accent-blue">/{detail.path}</span>
            </h2>
            <button
              onClick={() => setDetail(null)}
              className="text-text-muted hover:text-text-primary text-xs transition-colors"
            >
              Close
            </button>
          </div>

          {detail.mismatches.length === 0 ? (
            <p className="text-sm text-green-400">
              No mismatches found — rendered HTML matches API output.
            </p>
          ) : (
            <div className="space-y-3">
              {detail.mismatches.map((m, i) => (
                <div
                  key={i}
                  className="border border-glass-border/50 rounded-lg p-3"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${severityBadge(m.severity)}`}
                    >
                      {m.severity}
                    </span>
                    <span className="text-sm font-medium text-text-primary">
                      {m.field}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="text-text-muted mb-1">Expected (API)</p>
                      <p className="text-text-secondary font-mono break-all">
                        {m.expected || "\u2014"}
                      </p>
                    </div>
                    <div>
                      <p className="text-text-muted mb-1">Actual (Rendered)</p>
                      <p className="text-text-secondary font-mono break-all">
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
    </div>
  );
}
