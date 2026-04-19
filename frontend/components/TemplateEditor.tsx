"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-markup";
import { apiFetch } from "../lib/api";

interface TemplateEditorProps {
  /** Initial HTML content to populate the editor */
  initialContent: string;
  /** Called when content changes */
  onChange: (content: string) => void;
  /** Sample data for server-side preview */
  templateData?: Record<string, string>;
}

export default function TemplateEditor({
  initialContent,
  onChange,
  templateData = {},
}: TemplateEditorProps) {
  const [code, setCode] = useState(initialContent);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Sync when initialContent prop changes (e.g., opening a different template)
  useEffect(() => {
    setCode(initialContent);
  }, [initialContent]);

  // Client-side live preview (instant, no server call)
  useEffect(() => {
    if (iframeRef.current) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(code);
        doc.close();
      }
    }
  }, [code]);

  const handleCodeChange = useCallback(
    (newCode: string) => {
      setCode(newCode);
      onChange(newCode);
    },
    [onChange]
  );

  // Server-side preview with rendered variables
  const handleServerPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError("");
    try {
      const res = await apiFetch<{ html: string }>(
        "/marketing/admin/templates/preview",
        {
          method: "POST",
          body: JSON.stringify({
            html_content: code,
            template_data: templateData,
          }),
        }
      );
      setPreviewHtml(res.html);
      if (iframeRef.current) {
        const doc = iframeRef.current.contentDocument;
        if (doc) {
          doc.open();
          doc.write(res.html);
          doc.close();
        }
      }
    } catch (err) {
      setPreviewError(
        err instanceof Error ? err.message : "Preview failed"
      );
    }
    setPreviewLoading(false);
  }, [code, templateData]);

  const highlight = useCallback((value: string) => {
    return Prism.highlight(value, Prism.languages.markup, "markup");
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[60vh]">
      {/* Code editor pane */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-text-muted font-medium">
            HTML / Jinja2
          </span>
          <button
            type="button"
            onClick={handleServerPreview}
            disabled={previewLoading}
            className="text-xs text-accent-blue hover:underline disabled:opacity-50"
          >
            {previewLoading ? "Rendering..." : "Preview with Variables"}
          </button>
        </div>
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

      {/* Preview pane */}
      <div className="flex-1 flex flex-col min-w-0">
        <span className="text-xs text-text-muted font-medium mb-2">
          Preview
        </span>
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
