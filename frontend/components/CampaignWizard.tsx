"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import TemplateEditor from "./TemplateEditor";
import { cleanFilters, type SegmentFilters } from "./SegmentBuilder";
import AudienceSelector, { type SelectedAudience } from "./AudienceSelector";

// ─── Types ───────────────────────────────────────────────

interface Variant {
  label: string;
  subject: string;
  html_content: string;
  source_template_id: string;
  weight: number;
}

interface EmailTemplate {
  id: string;
  name: string;
  display_name: string;
  html_content: string | null;
  variables: Array<{ name: string; description: string }>;
}

interface SendTimeSuggestion {
  suggested_hour: number;
  suggested_day: string;
  confidence: string;
}

interface CampaignWizardProps {
  onClose: () => void;
  onCreated: () => void;
  initialAudience?: SelectedAudience;
  initialName?: string;
}

// ─── Component ───────────────────────────────────────────

export default function CampaignWizard({
  onClose,
  onCreated,
  initialAudience,
  initialName,
}: CampaignWizardProps) {
  // Phase: "audience" or "campaign"
  const [phase, setPhase] = useState<"audience" | "campaign">(
    initialAudience ? "campaign" : "audience",
  );
  const [audience, setAudience] = useState<SelectedAudience | null>(
    initialAudience ?? null,
  );

  // Campaign form state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState(initialName ?? "");

  // Content & Variants
  const [variants, setVariants] = useState<Variant[]>([
    {
      label: "A",
      subject: "",
      html_content: "",
      source_template_id: "",
      weight: 100,
    },
  ]);
  const [activeVariant, setActiveVariant] = useState(0);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);

  // UTM (all 5 fields, always visible)
  const [utmSource, setUtmSource] = useState("brevo");
  const [utmMedium, setUtmMedium] = useState("email");
  const [utmCampaign, setUtmCampaign] = useState("");
  const [utmContent, setUtmContent] = useState("");
  const [utmTerm, setUtmTerm] = useState("");

  // Schedule
  const [sendMode, setSendMode] = useState<"now" | "schedule">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [sendTimeSuggestion, setSendTimeSuggestion] =
    useState<SendTimeSuggestion | null>(null);

  // ─── Load templates on mount ───────────────────────────

  useEffect(() => {
    apiFetch<{ items: EmailTemplate[] }>(
      "/marketing/admin/templates?per_page=100",
    )
      .then((r) => setTemplates(r.items))
      .catch(() => {});
  }, []);

  // ─── Auto-generate UTM campaign slug from name ─────────

  useEffect(() => {
    if (name) {
      setUtmCampaign(
        name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, ""),
      );
    }
  }, [name]);

  // ─── Fetch send time when audience is selected ─────────

  useEffect(() => {
    if (!audience) return;
    apiFetch<SendTimeSuggestion>("/marketing/admin/insights/send-time", {
      method: "POST",
      body: JSON.stringify({ filters: cleanFilters(audience.filters) }),
    })
      .then(setSendTimeSuggestion)
      .catch(() => {});
  }, [audience]);

  // ─── Audience selection handler ────────────────────────

  function handleAudienceSelect(selected: SelectedAudience) {
    setAudience(selected);
    setPhase("campaign");
  }

  // ─── Variant management ────────────────────────────────

  const addVariant = useCallback(() => {
    const nextLabel = String.fromCharCode(65 + variants.length);
    const newWeight = Math.floor(100 / (variants.length + 1));
    const updated = variants.map((v) => ({ ...v, weight: newWeight }));
    updated.push({
      label: nextLabel,
      subject: "",
      html_content: "",
      source_template_id: "",
      weight: newWeight,
    });
    setVariants(updated);
    setActiveVariant(updated.length - 1);
  }, [variants]);

  const removeVariant = useCallback(
    (index: number) => {
      if (variants.length <= 1) return;
      const updated = variants.filter((_, i) => i !== index);
      const evenWeight = Math.floor(100 / updated.length);
      const redistributed = updated.map((v) => ({ ...v, weight: evenWeight }));
      setVariants(redistributed);
      setActiveVariant(Math.min(activeVariant, redistributed.length - 1));
    },
    [variants, activeVariant],
  );

  const updateVariant = useCallback(
    (index: number, field: keyof Variant, value: string | number) => {
      setVariants((prev) =>
        prev.map((v, i) => (i === index ? { ...v, [field]: value } : v)),
      );
    },
    [],
  );

  const handleTemplateSelect = useCallback(
    async (index: number, templateId: string) => {
      if (!templateId) return;
      try {
        const tmpl = await apiFetch<EmailTemplate>(
          `/marketing/admin/templates/${templateId}`,
        );
        setVariants((prev) =>
          prev.map((v, i) =>
            i === index
              ? {
                  ...v,
                  source_template_id: tmpl.name,
                  html_content: tmpl.html_content || "",
                }
              : v,
          ),
        );
      } catch {
        // silently fail
      }
    },
    [],
  );

  // ─── Submit ────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    if (!audience) return;
    setSubmitting(true);
    setError("");

    // Create a segment from the audience filters (or reuse existing for metric audiences)
    const segmentPayload: Array<{
      segment_id: string;
      variant_label?: string;
    }> = [];
    try {
      if (audience.segmentId) {
        // Reuse existing segment (e.g. metric-backed audience already has one)
        segmentPayload.push({ segment_id: audience.segmentId });
      } else {
        const segBody: Record<string, unknown> = {
          name: `${name} — ${audience.label}`,
          filters: cleanFilters(audience.filters),
        };
        if (audience.metricId) {
          segBody.metric_id = audience.metricId;
        }
        const seg = await apiFetch<{ id: string }>(
          "/marketing/admin/segments",
          {
            method: "POST",
            body: JSON.stringify(segBody),
          },
        );
        segmentPayload.push({ segment_id: seg.id });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create segment");
      setSubmitting(false);
      return;
    }

    try {
      await apiFetch("/marketing/admin/campaigns/wizard", {
        method: "POST",
        body: JSON.stringify({
          name,
          variants: variants.map((v) => ({
            label: v.label,
            subject: v.subject,
            html_content: v.html_content,
            source_template_id: v.source_template_id || null,
            weight: v.weight,
          })),
          segments: segmentPayload,
          utm_source: utmSource || null,
          utm_medium: utmMedium || null,
          utm_campaign: utmCampaign || null,
          utm_content: utmContent || null,
          utm_term: utmTerm || null,
          scheduled_at: sendMode === "schedule" ? scheduledAt : null,
        }),
      });
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create campaign");
    }
    setSubmitting(false);
  }, [
    audience,
    name,
    variants,
    utmSource,
    utmMedium,
    utmCampaign,
    utmContent,
    utmTerm,
    sendMode,
    scheduledAt,
    onCreated,
  ]);

  // ─── Validation ────────────────────────────────────────

  const canSubmit =
    name.trim().length > 0 &&
    audience !== null &&
    variants.every((v) => v.subject.trim() && v.html_content.trim()) &&
    (sendMode === "now" || !!scheduledAt);

  // ─── Phase 1: Audience Selection ───────────────────────

  if (phase === "audience") {
    return (
      <AudienceSelector onSelect={handleAudienceSelect} onBack={onClose} />
    );
  }

  // ─── Phase 2: Campaign Creation ────────────────────────

  // Build UTM preview string
  const utmPreviewParts = [
    utmSource && `utm_source=${utmSource}`,
    utmMedium && `utm_medium=${utmMedium}`,
    utmCampaign && `utm_campaign=${utmCampaign}`,
    utmContent && `utm_content=${utmContent}`,
    utmTerm && `utm_term=${utmTerm}`,
  ].filter(Boolean);
  const utmPreview =
    utmPreviewParts.length > 0 ? `?${utmPreviewParts.join("&")}` : "";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => setPhase("audience")}
          className="text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          &larr; Back to Audiences
        </button>
        <span className="text-text-muted/30">|</span>
        <h2 className="text-lg font-semibold text-text-primary">
          Create Campaign
        </h2>
      </div>

      {/* Locked audience bar */}
      {audience && (
        <div className="glass rounded-xl px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-text-muted">Audience:</span>
            <span className="font-semibold text-accent-blue">
              {audience.label}
            </span>
            <span className="text-text-muted">|</span>
            <span className="text-text-secondary">
              {audience.userCount.toLocaleString()} users
            </span>
            {audience.avgOrderValue != null && audience.avgOrderValue > 0 && (
              <>
                <span className="text-text-muted">|</span>
                <span className="text-text-secondary">
                  AOV ${audience.avgOrderValue.toFixed(2)}
                </span>
              </>
            )}
            {audience.totalRevenue != null && audience.totalRevenue > 0 && (
              <>
                <span className="text-text-muted">|</span>
                <span className="text-text-secondary">
                  Rev ${(audience.totalRevenue / 100).toLocaleString()}
                </span>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => setPhase("audience")}
            className="text-xs text-accent-blue hover:text-accent-blue/80 transition-colors"
          >
            Change
          </button>
        </div>
      )}

      {/* Campaign Name (full width) */}
      <div className="glass rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-text-primary">
          Campaign Name
        </h3>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Spring Sale 2026"
          className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
          autoFocus
        />
      </div>

      {/* Email Content (full width) */}
      <div className="glass rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">
            Email Content
          </h3>
          <button
            type="button"
            onClick={addVariant}
            className="text-xs text-accent-blue hover:text-accent-blue/80 transition-colors"
          >
            + Add A/B Variant
          </button>
        </div>

        {/* Variant tabs */}
        {variants.length > 1 && (
          <div className="flex items-center gap-1 border-b border-glass-border pb-0">
            {variants.map((v, i) => (
              <div key={v.label} className="flex items-center">
                <button
                  type="button"
                  onClick={() => setActiveVariant(i)}
                  className={`text-sm px-3 py-1.5 rounded-t-lg transition-colors ${
                    i === activeVariant
                      ? "bg-accent-blue/20 text-accent-blue font-medium"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                >
                  Variant {v.label}
                </button>
                {i === activeVariant && variants.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeVariant(i)}
                    className="text-xs text-text-muted hover:text-accent-pink ml-0.5"
                    title="Remove variant"
                  >
                    &times;
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Active variant editor */}
        {variants[activeVariant] && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-text-muted font-medium block mb-1">
                  Subject Line
                </label>
                <input
                  type="text"
                  value={variants[activeVariant].subject}
                  onChange={(e) =>
                    updateVariant(activeVariant, "subject", e.target.value)
                  }
                  placeholder="e.g., Don't miss our biggest sale!"
                  className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted font-medium block mb-1">
                  Start from template
                </label>
                <select
                  value={
                    templates.find(
                      (t) =>
                        t.name === variants[activeVariant].source_template_id,
                    )?.id || ""
                  }
                  onChange={(e) =>
                    handleTemplateSelect(activeVariant, e.target.value)
                  }
                  className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
                >
                  <option value="">Blank (start from scratch)</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.display_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="min-h-[400px]">
              <TemplateEditor
                initialContent={variants[activeVariant].html_content}
                onChange={(content) =>
                  updateVariant(activeVariant, "html_content", content)
                }
                variables={
                  templates.find(
                    (t) =>
                      t.name === variants[activeVariant].source_template_id,
                  )?.variables || []
                }
              />
            </div>
          </div>
        )}

        {/* Weight bar (multiple variants) */}
        {variants.length > 1 && (
          <div className="pt-3 border-t border-glass-border">
            <label className="text-xs text-text-muted font-medium block mb-2">
              Traffic Split
            </label>
            <div className="flex items-center gap-3">
              {variants.map((v, i) => (
                <div key={v.label} className="flex items-center gap-1">
                  <span className="text-xs text-text-secondary font-medium">
                    {v.label}:
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={v.weight}
                    onChange={(e) =>
                      updateVariant(
                        i,
                        "weight",
                        parseInt(e.target.value, 10) || 1,
                      )
                    }
                    className="w-16 px-2 py-1 text-sm rounded border border-glass-border bg-transparent text-text-primary text-center focus:outline-none focus:border-accent-blue"
                  />
                  <span className="text-xs text-text-muted">%</span>
                </div>
              ))}
            </div>
            <div className="flex h-2 rounded-full overflow-hidden mt-2">
              {variants.map((v, i) => {
                const totalWeight = variants.reduce(
                  (sum, vv) => sum + vv.weight,
                  0,
                );
                const pct = (v.weight / totalWeight) * 100;
                const colors = [
                  "bg-accent-blue",
                  "bg-accent-purple",
                  "bg-accent-green",
                  "bg-accent-pink",
                  "bg-yellow-400",
                  "bg-cyan-400",
                ];
                return (
                  <div
                    key={v.label}
                    className={colors[i % colors.length]}
                    style={{ width: `${pct}%` }}
                    title={`${v.label}: ${Math.round(pct)}%`}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* UTM Tracking (full width, all 5 fields visible) */}
      <div className="glass rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-text-primary">
          UTM Tracking
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div>
            <label className="text-xs text-text-muted font-medium block mb-1">
              utm_source
            </label>
            <input
              type="text"
              value={utmSource}
              onChange={(e) => setUtmSource(e.target.value)}
              placeholder="brevo"
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted font-medium block mb-1">
              utm_medium
            </label>
            <input
              type="text"
              value={utmMedium}
              onChange={(e) => setUtmMedium(e.target.value)}
              placeholder="email"
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted font-medium block mb-1">
              utm_campaign
            </label>
            <input
              type="text"
              value={utmCampaign}
              onChange={(e) => setUtmCampaign(e.target.value)}
              placeholder="Auto from name"
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted font-medium block mb-1">
              utm_content
            </label>
            <input
              type="text"
              value={utmContent}
              onChange={(e) => setUtmContent(e.target.value)}
              placeholder="variant-a"
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted font-medium block mb-1">
              utm_term
            </label>
            <input
              type="text"
              value={utmTerm}
              onChange={(e) => setUtmTerm(e.target.value)}
              placeholder="optional"
              className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
            />
          </div>
        </div>
        {utmPreview && (
          <div className="pt-2 border-t border-glass-border">
            <p className="text-xs text-text-muted mb-1">Preview:</p>
            <code className="text-xs text-accent-green break-all block">
              https://yoursite.com/page{utmPreview}
            </code>
          </div>
        )}
      </div>

      {/* Send Options (full width) */}
      <div className="glass rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-text-primary">
          Send Options
        </h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSendMode("now")}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              sendMode === "now"
                ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/30"
                : "text-text-muted border border-glass-border hover:border-text-secondary"
            }`}
          >
            Save as Draft
          </button>
          <button
            type="button"
            onClick={() => setSendMode("schedule")}
            className={`px-4 py-2 rounded-lg text-sm transition-colors ${
              sendMode === "schedule"
                ? "bg-accent-purple/20 text-accent-purple border border-accent-purple/30"
                : "text-text-muted border border-glass-border hover:border-text-secondary"
            }`}
          >
            Schedule
          </button>
        </div>

        {sendMode === "schedule" && (
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue text-sm"
          />
        )}

        {sendTimeSuggestion && (
          <p className="text-xs text-text-muted">
            Suggested:{" "}
            <span className="text-accent-blue">
              {sendTimeSuggestion.suggested_day} at{" "}
              {sendTimeSuggestion.suggested_hour}:00
            </span>{" "}
            ({sendTimeSuggestion.confidence} confidence)
          </p>
        )}

        {error && <p className="text-sm text-accent-pink">{error}</p>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || !canSubmit}
          className="w-full py-3 rounded-xl bg-accent-green text-white font-medium hover:bg-accent-green/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {submitting
            ? "Creating..."
            : sendMode === "schedule"
              ? "Schedule Campaign"
              : "Create Draft"}
        </button>
      </div>
    </div>
  );
}
