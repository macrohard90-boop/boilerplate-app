"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import TemplateEditor from "./TemplateEditor";
import SegmentBuilder, {
  cleanFilters,
  type SegmentFilters,
} from "./SegmentBuilder";

// ─── Types ───────────────────────────────────────────────

interface Segment {
  id: string;
  name: string;
  description: string | null;
  filters: SegmentFilters;
  is_system: boolean;
  user_count: number;
}

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

interface SegmentInsights {
  user_count: number;
  pct_of_total: number;
  avg_order_value: number;
  avg_orders_per_user: number;
  total_revenue: number;
  rfm_breakdown: Record<string, number>;
  top_products: Array<{ name: string; purchase_count: number }>;
  recent_email_stats: Record<string, number>;
}

interface SendTimeSuggestion {
  suggested_hour: number;
  suggested_day: string;
  confidence: string;
  note?: string;
}

interface CampaignWizardProps {
  onClose: () => void;
  onCreated: () => void;
  /** Pre-fill the audience with these filters (e.g., from an insight card) */
  initialFilters?: SegmentFilters;
}

// ─── Component ───────────────────────────────────────────

export default function CampaignWizard({
  onClose,
  onCreated,
  initialFilters,
}: CampaignWizardProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Campaign name
  const [name, setName] = useState("");

  // Audience
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>("");
  const [customFilters, setCustomFilters] = useState<SegmentFilters>(
    initialFilters || {},
  );
  const [useCustom, setUseCustom] = useState(!!initialFilters);
  const [segmentInsights, setSegmentInsights] =
    useState<SegmentInsights | null>(null);

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

  // UTM
  const [utmSource, setUtmSource] = useState("brevo");
  const [utmMedium, setUtmMedium] = useState("email");
  const [utmCampaign, setUtmCampaign] = useState("");
  const [utmContent, setUtmContent] = useState("");
  const [showUtm, setShowUtm] = useState(false);

  // Schedule
  const [sendMode, setSendMode] = useState<"now" | "schedule">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [sendTimeSuggestion, setSendTimeSuggestion] =
    useState<SendTimeSuggestion | null>(null);

  // ─── Data fetching ───────────────────────────────────────

  useEffect(() => {
    apiFetch<{ segments: Segment[] }>("/marketing/admin/segments")
      .then((r) => setSegments(r.segments))
      .catch(() => {});

    apiFetch<{ items: EmailTemplate[] }>(
      "/marketing/admin/templates?per_page=100",
    )
      .then((r) => setTemplates(r.items))
      .catch(() => {});
  }, []);

  // Fetch segment insights when selection changes
  useEffect(() => {
    const filters = useCustom
      ? cleanFilters(customFilters)
      : segments.find((s) => s.id === selectedSegmentId)?.filters || {};

    if (!selectedSegmentId && !useCustom) {
      setSegmentInsights(null);
      return;
    }

    apiFetch<SegmentInsights>("/marketing/admin/insights/segment", {
      method: "POST",
      body: JSON.stringify({ filters }),
    })
      .then(setSegmentInsights)
      .catch(() => setSegmentInsights(null));
  }, [selectedSegmentId, useCustom, customFilters, segments]);

  // Auto-generate UTM campaign from name
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

  // Fetch send time suggestion when audience is selected
  useEffect(() => {
    if (!selectedSegmentId && !useCustom) return;
    const filters = useCustom
      ? cleanFilters(customFilters)
      : segments.find((s) => s.id === selectedSegmentId)?.filters || {};

    apiFetch<SendTimeSuggestion>("/marketing/admin/insights/send-time", {
      method: "POST",
      body: JSON.stringify({ filters }),
    })
      .then(setSendTimeSuggestion)
      .catch(() => {});
  }, [selectedSegmentId, useCustom, customFilters, segments]);

  // ─── Variant management ──────────────────────────────────

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
        // Fetch full template (list endpoint omits html_content for performance)
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
        // silently fail — template list still works
      }
    },
    [],
  );

  // ─── Submit ──────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    setError("");

    const segmentPayload: Array<{
      segment_id: string;
      variant_label?: string;
    }> = [];
    if (useCustom) {
      try {
        const seg = await apiFetch<{ id: string }>(
          "/marketing/admin/segments",
          {
            method: "POST",
            body: JSON.stringify({
              name: `${name} — custom segment`,
              filters: cleanFilters(customFilters),
            }),
          },
        );
        segmentPayload.push({ segment_id: seg.id });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create segment");
        setSubmitting(false);
        return;
      }
    } else if (selectedSegmentId) {
      segmentPayload.push({ segment_id: selectedSegmentId });
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
          scheduled_at: sendMode === "schedule" ? scheduledAt : null,
        }),
      });
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create campaign");
    }
    setSubmitting(false);
  }, [
    name,
    variants,
    selectedSegmentId,
    useCustom,
    customFilters,
    utmSource,
    utmMedium,
    utmCampaign,
    utmContent,
    sendMode,
    scheduledAt,
    onCreated,
  ]);

  // ─── Validation ──────────────────────────────────────────

  const canSubmit =
    name.trim().length > 0 &&
    (selectedSegmentId !== "" || useCustom) &&
    variants.every((v) => v.subject.trim() && v.html_content.trim()) &&
    (sendMode === "now" || !!scheduledAt);

  const selectedSegment = segments.find((s) => s.id === selectedSegmentId);

  // ─── Render ──────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-text-muted hover:text-text-primary transition-colors"
          >
            &larr; Back to Campaigns
          </button>
          <span className="text-text-muted/30">|</span>
          <h2 className="text-lg font-semibold text-text-primary">
            Create Campaign
          </h2>
        </div>
      </div>

      {/* ── Section 1: Name + Audience (side by side) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Campaign Name */}
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

        {/* Audience */}
        <div className="glass rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              Audience
            </h3>
            {segmentInsights && (
              <span className="text-xs text-text-muted">
                <strong className="text-accent-blue">
                  {segmentInsights.user_count.toLocaleString()}
                </strong>{" "}
                users ({segmentInsights.pct_of_total}%)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 mb-2">
            <button
              type="button"
              onClick={() => setUseCustom(false)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                !useCustom
                  ? "bg-accent-blue/20 text-accent-blue"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              Saved Segments
            </button>
            <button
              type="button"
              onClick={() => setUseCustom(true)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                useCustom
                  ? "bg-accent-purple/20 text-accent-purple"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              Custom Filters
            </button>
          </div>

          {!useCustom ? (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {segments.map((seg) => (
                <button
                  key={seg.id}
                  type="button"
                  onClick={() => setSelectedSegmentId(seg.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg border transition-colors text-sm ${
                    selectedSegmentId === seg.id
                      ? "border-accent-blue bg-accent-blue/10"
                      : "border-glass-border/50 hover:border-text-secondary"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-text-primary">{seg.name}</span>
                    <span className="text-xs text-text-muted">
                      {seg.user_count.toLocaleString()}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <SegmentBuilder
              filters={customFilters}
              onChange={setCustomFilters}
              showPreview={true}
            />
          )}
        </div>
      </div>

      {/* ── Section 2: Content & Variants (full width) ── */}
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
                {i === activeVariant && (
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
            {/* Subject + Template row */}
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

            {/* Inline TemplateEditor — full width */}
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

        {/* Weight bar (only when multiple variants) */}
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
                    className={`${colors[i % colors.length]}`}
                    style={{ width: `${pct}%` }}
                    title={`${v.label}: ${Math.round(pct)}%`}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Section 3: UTM + Schedule + Submit ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* UTM Tracking (collapsible) */}
        <div className="glass rounded-xl p-5 space-y-3">
          <button
            type="button"
            onClick={() => setShowUtm(!showUtm)}
            className="flex items-center justify-between w-full"
          >
            <h3 className="text-sm font-semibold text-text-primary">
              UTM Tracking
            </h3>
            <span className="text-xs text-text-muted">
              {showUtm ? "Hide" : "Customize"} &darr;
            </span>
          </button>

          <code className="text-xs text-accent-green break-all block">
            ?utm_source={utmSource}&utm_medium={utmMedium}
            {utmCampaign ? `&utm_campaign=${utmCampaign}` : ""}
            {utmContent ? `&utm_content=${utmContent}` : ""}
          </code>

          {showUtm && (
            <div className="space-y-3 pt-2 border-t border-glass-border">
              <div className="grid grid-cols-2 gap-3">
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
              </div>
              <div>
                <label className="text-xs text-text-muted font-medium block mb-1">
                  utm_campaign
                </label>
                <input
                  type="text"
                  value={utmCampaign}
                  onChange={(e) => setUtmCampaign(e.target.value)}
                  placeholder="Auto-generated from campaign name"
                  className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
                />
              </div>
              {variants.length > 1 && (
                <div>
                  <label className="text-xs text-text-muted font-medium block mb-1">
                    utm_content
                  </label>
                  <input
                    type="text"
                    value={utmContent}
                    onChange={(e) => setUtmContent(e.target.value)}
                    placeholder="Auto-set per variant if blank"
                    className="w-full px-2.5 py-1.5 text-sm rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Schedule + Submit */}
        <div className="glass rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-text-primary">
            Send Options
          </h3>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSendMode("now")}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
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
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
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
            className="w-full mt-2 px-5 py-2.5 rounded-lg bg-accent-green text-white text-sm font-medium hover:bg-accent-green/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {submitting
              ? "Creating..."
              : sendMode === "schedule"
                ? "Schedule Campaign"
                : "Create Draft"}
          </button>
        </div>
      </div>
    </div>
  );
}
