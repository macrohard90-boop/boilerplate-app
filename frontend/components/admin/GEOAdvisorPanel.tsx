"use client";

import { useState } from "react";
import { apiFetch, type ApiError } from "../../lib/api";
import { useConfig } from "../../lib/config-context";
import { GEO_DIMENSIONS } from "../../lib/geo-rule-descriptions";

interface GEOSuggestion {
  dimension: string;
  priority: string;
  title: string;
  description: string;
  current_value: string | null;
  suggested_value: string | null;
  rule_id: string | null;
  ai_insight: boolean;
}

interface GEOAdvisorResponse {
  path: string;
  suggestions: GEOSuggestion[];
  provider: string;
  model: string | null;
  error: string | null;
}

interface GEOAdvisorPanelProps {
  path: string;
  onRuleClick?: (ruleId: string) => void;
}

const STORAGE_KEY = "geo-advisor-business-context";

function loadBusinessContext(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY) || "";
}

function saveBusinessContext(value: string) {
  if (typeof window === "undefined") return;
  if (value) {
    localStorage.setItem(STORAGE_KEY, value);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-500/20 text-red-400 border-red-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

const DIMENSION_ICONS: Record<string, string> = {
  extractability: "\u2702",
  fact_density: "\uD83D\uDCCA",
  authority: "\uD83D\uDEE1\uFE0F",
  freshness: "\u23F0",
  metadata: "\u2699\uFE0F",
};

export default function GEOAdvisorPanel({
  path,
  onRuleClick,
}: GEOAdvisorPanelProps) {
  const { site_name, site_description } = useConfig();
  const [businessContext, setBusinessContext] = useState(loadBusinessContext);
  const [intent, setIntent] = useState("");
  const [contextExpanded, setContextExpanded] = useState(
    !loadBusinessContext(),
  );

  const [suggestions, setSuggestions] = useState<GEOSuggestion[]>([]);
  const [provider, setProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    setSuggestions([]);
    setProvider(null);
    setExpandedIdx(null);

    saveBusinessContext(businessContext);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 100_000);

    try {
      const res = await apiFetch<GEOAdvisorResponse>(
        `/seo/admin/seo/geo/advisor/${encodeURIComponent(path)}`,
        {
          method: "POST",
          body: JSON.stringify({
            business_context: businessContext || null,
            intent: intent || null,
          }),
          signal: controller.signal,
        },
      );
      setSuggestions(res.suggestions);
      setProvider(res.provider);
      if (res.error) setError(res.error);
    } catch (e) {
      if (controller.signal.aborted) {
        setError(
          "Analysis timed out. Try simplifying your request or removing the intent.",
        );
      } else {
        setError((e as ApiError).message || "GEO Advisor request failed");
      }
    } finally {
      clearTimeout(timeoutId);
    }
    setLoading(false);
  }

  const hasContext = !!businessContext.trim();

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-text-primary">GEO Advisor</h3>
          <p className="text-[11px] text-text-muted mt-0.5">
            AI-powered analysis with citation self-reflection
          </p>
        </div>
      </div>

      {/* Built-in context display */}
      {(site_name || site_description) && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-glass-bg border border-glass-border/50">
          <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">
            App Context (from config)
          </p>
          <p className="text-xs text-text-secondary">
            {site_name}
            {site_description && (
              <span className="text-text-muted"> — {site_description}</span>
            )}
          </p>
        </div>
      )}

      {/* Business context (localStorage) */}
      <div className="mb-3">
        <button
          onClick={() => setContextExpanded(!contextExpanded)}
          className="w-full text-left flex items-center justify-between py-1.5"
        >
          <span className="text-xs font-medium text-text-secondary">
            Business Context
          </span>
          <span className="flex items-center gap-2">
            {hasContext && !contextExpanded && (
              <span className="text-[10px] text-green-400 px-1.5 py-0.5 rounded bg-green-500/10 border border-green-500/20">
                Saved
              </span>
            )}
            <span className="text-text-muted text-xs">
              {contextExpanded ? "\u25B2" : "\u25BC"}
            </span>
          </span>
        </button>
        {contextExpanded && (
          <div className="mt-1">
            <textarea
              rows={3}
              maxLength={2000}
              value={businessContext}
              onChange={(e) => setBusinessContext(e.target.value)}
              onBlur={() => saveBusinessContext(businessContext)}
              className="w-full px-3 py-2 bg-glass-bg border border-glass-border rounded-lg text-xs text-text-primary placeholder-text-muted focus:border-accent-blue focus:outline-none resize-none"
              placeholder="Describe your business and industry. e.g., 'Online store selling handmade Italian leather shoes. Target audience is professionals aged 25-45 who value craftsmanship...'"
            />
            <p className="text-[10px] text-text-muted mt-1">
              Persisted across sessions. Helps the advisor understand your
              business.
            </p>
          </div>
        )}
      </div>

      {/* Intent / goal */}
      <div className="mb-4">
        <label className="text-xs font-medium text-text-secondary block mb-1">
          What are you trying to achieve?
        </label>
        <textarea
          rows={2}
          maxLength={500}
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          className="w-full px-3 py-2 bg-glass-bg border border-glass-border rounded-lg text-xs text-text-primary placeholder-text-muted focus:border-accent-blue focus:outline-none resize-none"
          placeholder="e.g., Get cited by ChatGPT for 'Italian leather shoes', improve extractability, general GEO audit..."
        />
      </div>

      {/* Analyze button */}
      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="w-full btn-primary text-sm disabled:opacity-50 mb-4"
      >
        {loading
          ? "Analyzing..."
          : suggestions.length > 0
            ? "Re-analyze"
            : "Analyze Page"}
      </button>

      {/* Loading state */}
      {loading && (
        <div className="py-6 text-center space-y-2">
          <div className="w-5 h-5 border-2 border-accent-purple/30 border-t-accent-purple rounded-full animate-spin mx-auto" />
          <p className="text-xs text-text-muted">
            Analyzing page for AI citation optimization
            {intent ? " with your goal" : ""}...
          </p>
          <p className="text-[10px] text-text-muted">
            The AI is reflecting on its own citation preferences for this page.
          </p>
        </div>
      )}

      {/* SDK unavailable error */}
      {error && suggestions.length === 0 && !loading && (
        <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
          <p className="text-sm font-medium text-yellow-400 mb-1">
            {error.includes("Claude")
              ? "GEO Advisor Unavailable"
              : "Analysis Error"}
          </p>
          <p className="text-xs text-text-secondary">{error}</p>
          {error.includes("Claude CLI") && (
            <p className="text-xs text-text-muted mt-2">
              The GEO Advisor requires the Claude CLI to be installed and
              authenticated. Run{" "}
              <code className="font-mono bg-base-100 px-1 rounded">
                claude login
              </code>{" "}
              on the server.
            </p>
          )}
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && !loading && (
        <div className="space-y-2">
          {provider && (
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] text-text-muted">
                {suggestions.length} suggestion
                {suggestions.length !== 1 ? "s" : ""}
              </p>
              {error && <p className="text-[10px] text-yellow-400">{error}</p>}
            </div>
          )}

          {suggestions.map((s, idx) => {
            const isExpanded = expandedIdx === idx;
            const prioStyle =
              PRIORITY_STYLES[s.priority] || PRIORITY_STYLES.medium;
            const dimConfig = GEO_DIMENSIONS[s.dimension];
            const dimIcon = DIMENSION_ICONS[s.dimension] || "\uD83D\uDCCB";

            return (
              <div
                key={idx}
                className="border border-glass-border/50 rounded-lg overflow-hidden"
              >
                <button
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                  className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-glass-hover/50 transition-colors"
                >
                  <span className="text-sm shrink-0">{dimIcon}</span>
                  <span className="text-sm text-text-primary flex-1 min-w-0">
                    {s.title}
                  </span>
                  {s.ai_insight && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border bg-accent-purple/20 text-accent-purple border-accent-purple/30 shrink-0">
                      AI Insight
                    </span>
                  )}
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-medium border shrink-0 ${prioStyle}`}
                  >
                    {s.priority}
                  </span>
                  {dimConfig && (
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium border shrink-0 ${dimConfig.bgColor} ${dimConfig.color}`}
                      style={{
                        borderColor: "currentColor",
                        borderWidth: "1px",
                        opacity: 0.6,
                      }}
                    >
                      {dimConfig.label}
                    </span>
                  )}
                  {s.rule_id && (
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        onRuleClick?.(s.rule_id!);
                      }}
                      className="text-[10px] font-mono text-accent-blue hover:underline cursor-pointer shrink-0"
                      title="Highlight in score breakdown"
                    >
                      {s.rule_id}
                    </span>
                  )}
                  <span className="text-text-muted text-xs shrink-0">
                    {isExpanded ? "\u25B2" : "\u25BC"}
                  </span>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 space-y-3">
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {s.description}
                    </p>

                    {(s.current_value || s.suggested_value) && (
                      <div className="space-y-2">
                        {s.current_value && (
                          <div>
                            <p className="text-[10px] text-text-muted mb-0.5">
                              Current
                            </p>
                            <p className="text-xs font-mono text-red-400/80 line-through bg-red-500/5 px-2 py-1 rounded">
                              {s.current_value}
                            </p>
                          </div>
                        )}
                        {s.suggested_value && (
                          <div>
                            <p className="text-[10px] text-text-muted mb-0.5">
                              Suggested
                            </p>
                            <p className="text-xs font-mono text-green-400 bg-green-500/5 px-2 py-1 rounded">
                              {s.suggested_value}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!loading && suggestions.length === 0 && !error && (
        <p className="text-xs text-text-muted text-center py-2">
          Add context above, then click &quot;Analyze Page&quot; to get
          AI-powered GEO suggestions — including what the AI itself would
          prioritize citing.
        </p>
      )}
    </div>
  );
}
