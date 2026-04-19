"use client";

import { useEffect, useMemo, useRef } from "react";

interface RuleResult {
  rule_id: string;
  passed: boolean;
}

interface HtmlSourceViewerProps {
  html: string | null;
  loading: boolean;
  ruleResults: RuleResult[];
  highlightedRule: string | null;
}

/** Maps regex patterns to the rule IDs they represent in the HTML. */
const RULE_HTML_PATTERNS: Array<{ pattern: RegExp; ruleIds: string[] }> = [
  { pattern: /<title[\s>]/i, ruleIds: ["title_present", "title_length"] },
  {
    pattern: /<meta\s[^>]*name=["']description["']/i,
    ruleIds: ["desc_present", "desc_length", "meta_desc_complete"],
  },
  {
    pattern: /<link\s[^>]*rel=["']canonical["']/i,
    ruleIds: ["canonical_set", "canonical_self_ref", "https_enforced"],
  },
  {
    pattern: /<meta\s[^>]*name=["']robots["']/i,
    ruleIds: ["robots_indexable"],
  },
  {
    pattern: /<meta\s[^>]*name=["']viewport["']/i,
    ruleIds: ["viewport_present"],
  },
  {
    pattern: /<meta\s[^>]*property=["']og:/i,
    ruleIds: ["og_complete", "og_image_custom", "og_url_valid"],
  },
  {
    pattern: /<meta\s[^>]*name=["']twitter:/i,
    ruleIds: ["twitter_complete"],
  },
  {
    pattern: /<html[\s>]/i,
    ruleIds: ["lang_attribute"],
  },
  {
    pattern: /<link\s[^>]*rel=["'](?:icon|shortcut icon|apple-touch-icon)["']/i,
    ruleIds: ["favicon_present"],
  },
  {
    pattern: /<h1[\s>]/i,
    ruleIds: ["h1_present", "heading_hierarchy", "title_h1_differentiated"],
  },
  { pattern: /<h[2-6][\s>]/i, ruleIds: ["heading_hierarchy"] },
  { pattern: /<img[\s>]/i, ruleIds: ["images_alt_text", "img_dimensions"] },
  { pattern: /<a\s[^>]*href=["']\//i, ruleIds: ["internal_links"] },
  {
    pattern: /<a\s[^>]*href=["']https?:/i,
    ruleIds: ["external_links_present"],
  },
  {
    pattern: /<script\s[^>]*type=["']application\/ld\+json["']/i,
    ruleIds: ["structured_data", "schema_complete"],
  },
];

/** Also match closing </title> tag to highlight that line too. */
const CLOSING_PATTERNS: Array<{ pattern: RegExp; ruleIds: string[] }> = [
  { pattern: /<\/title>/i, ruleIds: ["title_present", "title_length"] },
  { pattern: /<\/h1>/i, ruleIds: ["h1_present", "heading_hierarchy"] },
  { pattern: /<\/h[2-6]>/i, ruleIds: ["heading_hierarchy"] },
];

interface ProcessedLine {
  raw: string;
  ruleIds: string[];
  bgClass: string;
  tokens: Token[];
}

interface Token {
  text: string;
  className: string;
}

/**
 * Syntax-highlight a single line of HTML source code.
 * Produces token spans: tags (blue), attributes (purple), values (green),
 * comments (muted), text (primary).
 *
 * NOTE: No manual HTML escaping — React's JSX `{t.text}` handles that
 * automatically.  Using escapeHtml() on top would double-escape.
 */
function tokenizeLine(raw: string): Token[] {
  const tokens: Token[] = [];
  let remaining = raw;

  while (remaining.length > 0) {
    // HTML comment
    const commentMatch = remaining.match(/^(<!--[\s\S]*?(?:-->|$))/);
    if (commentMatch) {
      tokens.push({
        text: commentMatch[1],
        className: "text-text-muted italic",
      });
      remaining = remaining.slice(commentMatch[1].length);
      continue;
    }

    // Opening/closing tag start: < or </
    const tagOpenMatch = remaining.match(/^(<\/?[a-zA-Z][a-zA-Z0-9-]*)/);
    if (tagOpenMatch) {
      tokens.push({
        text: tagOpenMatch[1],
        className: "text-accent-blue",
      });
      remaining = remaining.slice(tagOpenMatch[1].length);

      // Parse attributes inside the tag until > or />
      while (remaining.length > 0) {
        // Self-close or close
        const closeMatch = remaining.match(/^(\s*\/?>)/);
        if (closeMatch) {
          tokens.push({
            text: closeMatch[1],
            className: "text-accent-blue",
          });
          remaining = remaining.slice(closeMatch[1].length);
          break;
        }

        // Whitespace
        const wsMatch = remaining.match(/^(\s+)/);
        if (wsMatch) {
          tokens.push({ text: wsMatch[1], className: "" });
          remaining = remaining.slice(wsMatch[1].length);
          continue;
        }

        // Attribute: name="value" or name='value' or name
        const attrMatch = remaining.match(
          /^([a-zA-Z_:][a-zA-Z0-9_.:-]*)(\s*=\s*)(["'])([\s\S]*?)\3/,
        );
        if (attrMatch) {
          tokens.push({
            text: attrMatch[1],
            className: "text-accent-purple",
          });
          tokens.push({
            text: attrMatch[2],
            className: "text-text-muted",
          });
          tokens.push({
            text: attrMatch[3] + attrMatch[4] + attrMatch[3],
            className: "text-accent-green",
          });
          remaining = remaining.slice(attrMatch[0].length);
          continue;
        }

        // Bare attribute name (no value)
        const bareAttr = remaining.match(/^([a-zA-Z_:][a-zA-Z0-9_.:-]*)/);
        if (bareAttr) {
          tokens.push({
            text: bareAttr[1],
            className: "text-accent-purple",
          });
          remaining = remaining.slice(bareAttr[1].length);
          continue;
        }

        // If nothing matches, consume one char to avoid infinite loop
        tokens.push({
          text: remaining[0],
          className: "text-text-primary",
        });
        remaining = remaining.slice(1);
      }
      continue;
    }

    // Plain text until next < or end of line
    const textMatch = remaining.match(/^([^<]+)/);
    if (textMatch) {
      tokens.push({
        text: textMatch[1],
        className: "text-text-primary",
      });
      remaining = remaining.slice(textMatch[1].length);
      continue;
    }

    // Stray < that doesn't match a tag
    tokens.push({
      text: remaining[0],
      className: "text-text-primary",
    });
    remaining = remaining.slice(1);
  }

  return tokens;
}

export default function HtmlSourceViewer({
  html,
  loading,
  ruleResults,
  highlightedRule,
}: HtmlSourceViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);

  const rulePassMap = useMemo(() => {
    const map: Record<string, boolean> = {};
    for (const r of ruleResults) {
      map[r.rule_id] = r.passed;
    }
    return map;
  }, [ruleResults]);

  const processedLines: ProcessedLine[] = useMemo(() => {
    if (!html) return [];
    // HTML arrives pre-prettified from the backend (Python HTMLParser).
    const lines = html.split("\n");

    return lines.map((raw) => {
      // Find all matching rule IDs for this line
      const matchedRuleIds: string[] = [];
      for (const { pattern, ruleIds } of RULE_HTML_PATTERNS) {
        if (pattern.test(raw)) {
          matchedRuleIds.push(...ruleIds);
        }
      }
      for (const { pattern, ruleIds } of CLOSING_PATTERNS) {
        if (pattern.test(raw)) {
          matchedRuleIds.push(...ruleIds);
        }
      }
      const uniqueRuleIds = Array.from(new Set(matchedRuleIds));

      // Determine background color
      let bgClass = "";
      if (uniqueRuleIds.length > 0) {
        const hasFailingRule = uniqueRuleIds.some(
          (id) => rulePassMap[id] === false,
        );
        const hasPassingRule = uniqueRuleIds.some(
          (id) => rulePassMap[id] === true,
        );
        if (hasFailingRule) {
          bgClass = "bg-red-500/10 border-l-2 border-l-red-500/50";
        } else if (hasPassingRule) {
          bgClass = "bg-green-500/10 border-l-2 border-l-green-500/50";
        } else {
          bgClass = "bg-blue-500/8 border-l-2 border-l-blue-500/30";
        }
      }

      return {
        raw,
        ruleIds: uniqueRuleIds,
        bgClass,
        tokens: tokenizeLine(raw),
      };
    });
  }, [html, rulePassMap]);

  // Scroll to highlighted rule's element
  useEffect(() => {
    if (!highlightedRule || !viewerRef.current) return;
    const el = viewerRef.current.querySelector(
      `[data-rule*="${highlightedRule}"]`,
    );
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-1", "ring-accent-pink", "brightness-125");
      const timer = setTimeout(() => {
        el.classList.remove("ring-1", "ring-accent-pink", "brightness-125");
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [highlightedRule]);

  if (loading) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <div className="inline-block w-5 h-5 border-2 border-accent-purple/30 border-t-accent-purple rounded-full animate-spin mb-2" />
        <p className="text-sm text-text-muted">Loading page source...</p>
      </div>
    );
  }

  if (!html) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-sm text-text-muted">
          Could not load page source. The page may not be accessible.
        </p>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-glass-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          {/* Fake window dots */}
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-500/60" />
            <span className="w-3 h-3 rounded-full bg-yellow-500/60" />
            <span className="w-3 h-3 rounded-full bg-green-500/60" />
          </div>
          <h3 className="text-sm font-medium text-text-primary">Page Source</h3>
        </div>
        <span className="text-[10px] text-text-muted">
          {processedLines.length} lines
        </span>
      </div>

      {/* Legend */}
      <div className="px-4 py-1.5 border-b border-glass-border/50 flex gap-4 text-[10px] text-text-muted shrink-0">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-green-500/40" /> Passing rule
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm bg-red-500/40" /> Failing rule
        </span>
      </div>

      {/* Code viewer */}
      <div
        ref={viewerRef}
        className="overflow-auto max-h-[600px] bg-base-100 font-mono text-[11px] leading-5"
      >
        {processedLines.map((line, i) => (
          <div
            key={i}
            data-rule={
              line.ruleIds.length > 0 ? line.ruleIds.join(",") : undefined
            }
            className={`flex transition-all duration-300 ${line.bgClass} hover:bg-white/[0.02]`}
          >
            <span className="select-none text-text-muted/50 w-10 text-right pr-2 py-px border-r border-glass-border/20 shrink-0">
              {i + 1}
            </span>
            <pre className="pl-3 py-px whitespace-pre-wrap break-all flex-1 min-w-0">
              {line.tokens.map((t, j) => (
                <span key={j} className={t.className}>
                  {t.text}
                </span>
              ))}
              {line.tokens.length === 0 && " "}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
