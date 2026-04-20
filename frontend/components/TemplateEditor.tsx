"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-markup";
import { apiFetch } from "../lib/api";

interface TemplateVariable {
  name: string;
  description: string;
}

interface TemplateEditorProps {
  /** Initial HTML content to populate the editor */
  initialContent: string;
  /** Called when content changes */
  onChange: (content: string) => void;
  /** Sample data for server-side preview */
  templateData?: Record<string, string>;
  /** Variable definitions for the reference panel */
  variables?: TemplateVariable[];
}

const GLOBAL_VARIABLES: TemplateVariable[] = [
  { name: "site_name", description: "Site name from settings" },
  { name: "app_name", description: "Application name" },
  { name: "frontend_url", description: "Frontend base URL" },
  { name: "year", description: "Current year (auto-generated)" },
  {
    name: "unsubscribe_url",
    description: "Unsubscribe link (marketing emails only)",
  },
  {
    name: "first_name",
    description: "User's first name (auto-populated)",
  },
];

export default function TemplateEditor({
  initialContent,
  onChange,
  templateData = {},
  variables = [],
}: TemplateEditorProps) {
  const [code, setCode] = useState(initialContent);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [previewMode, setPreviewMode] = useState<"live" | "rendered">("live");
  const [showVars, setShowVars] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Sync when initialContent prop changes (e.g., opening a different template)
  useEffect(() => {
    setCode(initialContent);
    setPreviewMode("live");
  }, [initialContent]);

  // Write HTML to the preview iframe
  const writeToIframe = useCallback((html: string) => {
    if (iframeRef.current) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(html);
        doc.close();
      }
    }
  }, []);

  // Client-side live preview (instant, no server call)
  useEffect(() => {
    if (previewMode === "live") {
      writeToIframe(code);
    }
  }, [code, previewMode, writeToIframe]);

  const handleCodeChange = useCallback(
    (newCode: string) => {
      setCode(newCode);
      onChange(newCode);
    },
    [onChange],
  );

  // Server-side rendered preview (variables replaced)
  const refreshRenderedPreview = useCallback(
    async (html?: string) => {
      setPreviewLoading(true);
      setPreviewError("");
      try {
        const res = await apiFetch<{ html: string }>(
          "/marketing/admin/templates/preview",
          {
            method: "POST",
            body: JSON.stringify({
              html_content: html ?? code,
              template_data: templateData,
            }),
          },
        );
        writeToIframe(res.html);
      } catch (err) {
        setPreviewError(err instanceof Error ? err.message : "Preview failed");
      }
      setPreviewLoading(false);
    },
    [code, templateData, writeToIframe],
  );

  // Auto-refresh rendered preview on code changes (debounced)
  useEffect(() => {
    if (previewMode !== "rendered") return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      refreshRenderedPreview();
    }, 800);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, previewMode]);

  // Insert a variable tag at the cursor position in the code editor
  const insertVariable = useCallback(
    (varName: string) => {
      const textarea = document.querySelector(
        ".template-editor-textarea",
      ) as HTMLTextAreaElement | null;
      if (!textarea) return;

      const insertion = `{{ ${varName} }}`;
      const start = textarea.selectionStart ?? code.length;
      const end = textarea.selectionEnd ?? start;
      const newCode = code.slice(0, start) + insertion + code.slice(end);

      setCode(newCode);
      onChange(newCode);

      requestAnimationFrame(() => {
        textarea.focus();
        const newPos = start + insertion.length;
        textarea.setSelectionRange(newPos, newPos);
      });
    },
    [code, onChange],
  );

  const highlight = useCallback((value: string) => {
    return Prism.highlight(value, Prism.languages.markup, "markup");
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-3 h-[60vh]">
      {/* Code editor pane */}
      <div className="flex-1 flex flex-col min-w-0">
        <span className="text-xs text-text-muted font-medium mb-2">
          HTML / Jinja2
        </span>
        <div className="flex-1 rounded-lg border border-glass-border bg-[#1a1a2e] overflow-auto">
          <Editor
            value={code}
            onValueChange={handleCodeChange}
            highlight={highlight}
            padding={12}
            textareaClassName="template-editor-textarea"
            style={{
              fontFamily: '"Fira Code", "Fira Mono", monospace',
              fontSize: 13,
              lineHeight: 1.5,
              minHeight: "100%",
              color: "#e0e0e0",
            }}
          />
        </div>
        {previewError && (
          <p className="text-xs text-accent-pink mt-1">{previewError}</p>
        )}
      </div>

      {/* Variables reference panel */}
      <div
        className={`flex-shrink-0 flex flex-col min-w-0 ${showVars ? "w-52" : "w-8"}`}
      >
        <div className="flex items-center justify-between mb-2">
          {showVars && (
            <span className="text-xs text-text-muted font-medium">
              Variables
            </span>
          )}
          <button
            type="button"
            onClick={() => setShowVars(!showVars)}
            className="text-xs text-text-muted hover:text-text-secondary"
            title={showVars ? "Hide variables" : "Show variables"}
          >
            {showVars ? "\u2190" : "\u2192"}
          </button>
        </div>
        {showVars && (
          <div className="flex-1 overflow-y-auto space-y-1 text-xs rounded-lg border border-glass-border p-2">
            {/* Template-specific variables */}
            {variables.length > 0 && (
              <>
                <p className="text-text-muted font-medium uppercase tracking-wider text-[10px] mb-1">
                  Template
                </p>
                {variables.map((v) => (
                  <button
                    key={v.name}
                    type="button"
                    onClick={() => insertVariable(v.name)}
                    className="block w-full text-left px-2 py-1.5 rounded hover:bg-white/5 transition-colors group"
                    title={`Click to insert {{ ${v.name} }}`}
                  >
                    <code className="text-accent-blue group-hover:text-accent-pink font-mono text-[11px]">
                      {"{{ "}
                      {v.name}
                      {" }}"}
                    </code>
                    {v.description && (
                      <p className="text-text-muted text-[10px] mt-0.5 leading-tight">
                        {v.description}
                      </p>
                    )}
                  </button>
                ))}
                <div className="border-t border-glass-border my-2" />
              </>
            )}

            {/* Global auto-injected variables */}
            <p className="text-text-muted font-medium uppercase tracking-wider text-[10px] mb-1">
              Global (auto-injected)
            </p>
            {GLOBAL_VARIABLES.map((v) => (
              <button
                key={v.name}
                type="button"
                onClick={() => insertVariable(v.name)}
                className="block w-full text-left px-2 py-1.5 rounded hover:bg-white/5 transition-colors group"
                title={`Click to insert {{ ${v.name} }}`}
              >
                <code className="text-accent-green group-hover:text-accent-pink font-mono text-[11px]">
                  {"{{ "}
                  {v.name}
                  {" }}"}
                </code>
                <p className="text-text-muted text-[10px] mt-0.5 leading-tight">
                  {v.description}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Preview pane */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <button
            type="button"
            onClick={() => setPreviewMode("live")}
            className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
              previewMode === "live"
                ? "bg-accent-blue/20 text-accent-blue"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            Live Preview
          </button>
          <button
            type="button"
            onClick={() => {
              setPreviewMode("rendered");
              refreshRenderedPreview();
            }}
            disabled={previewLoading}
            className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
              previewMode === "rendered"
                ? "bg-accent-purple/20 text-accent-purple"
                : "text-text-muted hover:text-text-secondary"
            } disabled:opacity-50`}
          >
            {previewLoading && previewMode === "rendered"
              ? "Rendering..."
              : "Rendered Preview"}
          </button>
        </div>
        <div className="flex-1 rounded-lg border border-glass-border bg-white overflow-hidden">
          <iframe
            ref={iframeRef}
            title="Template Preview"
            className="w-full h-full border-0"
            sandbox="allow-same-origin"
          />
        </div>
      </div>
    </div>
  );
}
