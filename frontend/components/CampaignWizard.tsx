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

interface GlobalInsights {
  total_eligible: number;
  by_rfm_segment: Record<string, number>;
  avg_order_value: number;
  avg_orders_per_user: number;
  active_last_30_days: number;
  cart_abandonment_count: number;
  top_communication_types: Array<{ name: string; subscriber_count: number }>;
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
  /** Pre-fill the audience step with these filters (e.g., from an insight card) */
  initialFilters?: SegmentFilters;
}

const STEPS = ["Basics", "Audience", "Content", "Tracking", "Review"];

const COACHING_TIPS: Record<number, { title: string; body: string }> = {
  0: {
    title: "Getting Started",
    body: "Name your campaign something descriptive so you can find it later. The insights panel shows your full subscriber base at a glance.",
  },
  1: {
    title: "Choose Your Audience",
    body: "Pick a pre-built segment or create a custom one using the filter builder. The insights panel updates to show stats for your selected audience.",
  },
  2: {
    title: "A/B Testing",
    body: "Create multiple variants to test different subject lines or email content. Pick a template as a starting point, then customize each variant. Adjust the weight slider to control what percentage of your audience sees each variant.",
  },
  3: {
    title: "UTM Tracking",
    body: "UTM parameters are added to every link in your email so you can track campaign performance in analytics. They're auto-generated from your campaign name — customize them if needed.",
  },
  4: {
    title: "Final Review",
    body: "Double-check everything before sending. You can schedule for a specific time or send immediately. The suggested send time is based on when your audience is most active.",
  },
};

// ─── Component ───────────────────────────────────────────

export default function CampaignWizard({
  onClose,
  onCreated,
  initialFilters,
}: CampaignWizardProps) {
  const [step, setStep] = useState(0);
  const [showTips, setShowTips] = useState(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("campaign_wizard_tips") !== "false";
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Step 1: Basics
  const [name, setName] = useState("");

  // Step 2: Audience
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>("");
  const [customFilters, setCustomFilters] = useState<SegmentFilters>(
    initialFilters || {},
  );
  const [useCustom, setUseCustom] = useState(!!initialFilters);
  const [globalInsights, setGlobalInsights] = useState<GlobalInsights | null>(
    null,
  );
  const [segmentInsights, setSegmentInsights] =
    useState<SegmentInsights | null>(null);

  // Step 3: Content & Variants
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

  // Step 4: UTM
  const [utmSource, setUtmSource] = useState("brevo");
  const [utmMedium, setUtmMedium] = useState("email");
  const [utmCampaign, setUtmCampaign] = useState("");
  const [utmContent, setUtmContent] = useState("");

  // Step 5: Schedule
  const [sendMode, setSendMode] = useState<"now" | "schedule">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [sendTimeSuggestion, setSendTimeSuggestion] =
    useState<SendTimeSuggestion | null>(null);

  // ─── Data fetching ───────────────────────────────────────

  useEffect(() => {
    // Fetch segments
    apiFetch<{ segments: Segment[] }>("/marketing/admin/segments")
      .then((r) => setSegments(r.segments))
      .catch(() => {});

    // Fetch global insights
    apiFetch<GlobalInsights>("/marketing/admin/insights/global")
      .then(setGlobalInsights)
      .catch(() => {});

    // Fetch templates
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

  // Coaching tips persistence
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("campaign_wizard_tips", showTips ? "true" : "false");
    }
  }, [showTips]);

  // ─── Variant management ──────────────────────────────────

  const addVariant = useCallback(() => {
    const nextLabel = String.fromCharCode(65 + variants.length); // A=65, B=66...
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
      // Redistribute weights evenly
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
    (index: number, templateId: string) => {
      const tmpl = templates.find((t) => t.id === templateId);
      if (tmpl) {
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
      }
    },
    [templates],
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
      // Create an ad-hoc segment first
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

  const canProceed = (): boolean => {
    switch (step) {
      case 0:
        return name.trim().length > 0;
      case 1:
        return selectedSegmentId !== "" || useCustom;
      case 2:
        return variants.every((v) => v.subject.trim() && v.html_content.trim());
      case 3:
        return true;
      case 4:
        return sendMode === "now" || !!scheduledAt;
      default:
        return false;
    }
  };

  // Fetch send time suggestion when reaching review step
  useEffect(() => {
    if (step === 4) {
      const filters = useCustom
        ? cleanFilters(customFilters)
        : segments.find((s) => s.id === selectedSegmentId)?.filters || {};

      apiFetch<SendTimeSuggestion>("/marketing/admin/insights/send-time", {
        method: "POST",
        body: JSON.stringify({ filters }),
      })
        .then(setSendTimeSuggestion)
        .catch(() => {});
    }
  }, [step, selectedSegmentId, useCustom, customFilters, segments]);

  // ─── Render ──────────────────────────────────────────────

  const selectedSegment = segments.find((s) => s.id === selectedSegmentId);

  return (
    <div className="space-y-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
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
        <div className="flex items-center gap-3">
          {/* Step indicator */}
          <div className="flex items-center gap-1">
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center">
                <button
                  type="button"
                  onClick={() => i < step && setStep(i)}
                  disabled={i > step}
                  className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                    i === step
                      ? "bg-accent-blue/20 text-accent-blue font-medium"
                      : i < step
                        ? "text-accent-green cursor-pointer hover:text-accent-green/80"
                        : "text-text-muted/40"
                  }`}
                >
                  {i < step ? "\u2713" : i + 1}. {s}
                </button>
                {i < STEPS.length - 1 && (
                  <span className="text-text-muted/30 mx-0.5">&rarr;</span>
                )}
              </div>
            ))}
          </div>
          <label className="flex items-center gap-1.5 text-xs text-text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={showTips}
              onChange={(e) => setShowTips(e.target.checked)}
              className="rounded border-glass-border"
            />
            Tips
          </label>
        </div>
      </div>

      <div className="glass rounded-xl flex flex-col overflow-hidden min-h-[600px]">
        {/* Body */}
        <div className="flex-1 flex overflow-hidden">
          {/* Main content area */}
          <div className="flex-1 overflow-y-auto p-6">
            {/* Step 0: Basics */}
            {step === 0 && (
              <div className="space-y-4 max-w-lg">
                <div>
                  <label className="text-sm text-text-secondary font-medium block mb-1">
                    Campaign Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Spring Sale 2026"
                    className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                    autoFocus
                  />
                </div>
              </div>
            )}

            {/* Step 1: Audience */}
            {step === 1 && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 mb-2">
                  <button
                    type="button"
                    onClick={() => {
                      setUseCustom(false);
                    }}
                    className={`text-sm px-3 py-1.5 rounded-lg transition-colors ${
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
                    className={`text-sm px-3 py-1.5 rounded-lg transition-colors ${
                      useCustom
                        ? "bg-accent-purple/20 text-accent-purple"
                        : "text-text-muted hover:text-text-secondary"
                    }`}
                  >
                    Custom Filters
                  </button>
                </div>

                {!useCustom ? (
                  <div className="space-y-2">
                    {segments.map((seg) => (
                      <button
                        key={seg.id}
                        type="button"
                        onClick={() => setSelectedSegmentId(seg.id)}
                        className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                          selectedSegmentId === seg.id
                            ? "border-accent-blue bg-accent-blue/10"
                            : "border-glass-border hover:border-text-secondary"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-sm font-medium text-text-primary">
                              {seg.name}
                            </span>
                            {seg.is_system && (
                              <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-accent-green/20 text-accent-green">
                                system
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-text-muted">
                            {seg.user_count.toLocaleString()} users
                          </span>
                        </div>
                        {seg.description && (
                          <p className="text-xs text-text-muted mt-0.5">
                            {seg.description}
                          </p>
                        )}
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
            )}

            {/* Step 2: Content & Variants */}
            {step === 2 && (
              <div className="space-y-4 h-full flex flex-col">
                {/* Variant tabs */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  {variants.map((v, i) => (
                    <div key={v.label} className="flex items-center">
                      <button
                        type="button"
                        onClick={() => setActiveVariant(i)}
                        className={`text-sm px-3 py-1.5 rounded-t-lg transition-colors ${
                          i === activeVariant
                            ? "bg-accent-blue/20 text-accent-blue font-medium border border-b-0 border-glass-border"
                            : "text-text-muted hover:text-text-secondary"
                        }`}
                      >
                        Variant {v.label}
                      </button>
                      {variants.length > 1 && i === activeVariant && (
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
                  <button
                    type="button"
                    onClick={addVariant}
                    className="text-sm px-3 py-1.5 text-text-muted hover:text-accent-blue transition-colors"
                    title="Add another variant for A/B testing"
                  >
                    + Add Variant
                  </button>
                </div>

                {/* Active variant editor */}
                {variants[activeVariant] && (
                  <div className="flex-1 flex flex-col min-h-0 space-y-3">
                    {/* Subject */}
                    <div className="flex-shrink-0">
                      <label className="text-xs text-text-muted font-medium block mb-1">
                        Subject Line
                      </label>
                      <input
                        type="text"
                        value={variants[activeVariant].subject}
                        onChange={(e) =>
                          updateVariant(
                            activeVariant,
                            "subject",
                            e.target.value,
                          )
                        }
                        placeholder="e.g., Don't miss our biggest sale of the year!"
                        className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                      />
                    </div>

                    {/* Template selector */}
                    <div className="flex-shrink-0">
                      <label className="text-xs text-text-muted font-medium block mb-1">
                        Start from template
                      </label>
                      <select
                        value={
                          templates.find(
                            (t) =>
                              t.name ===
                              variants[activeVariant].source_template_id,
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

                    {/* Inline TemplateEditor */}
                    <div className="flex-1 min-h-0">
                      <TemplateEditor
                        initialContent={variants[activeVariant].html_content}
                        onChange={(content) =>
                          updateVariant(activeVariant, "html_content", content)
                        }
                        variables={
                          templates.find(
                            (t) =>
                              t.name ===
                              variants[activeVariant].source_template_id,
                          )?.variables || []
                        }
                      />
                    </div>
                  </div>
                )}

                {/* Weight bar */}
                {variants.length > 1 && (
                  <div className="flex-shrink-0 pt-2 border-t border-glass-border">
                    <label className="text-xs text-text-muted font-medium block mb-2">
                      Traffic Split
                    </label>
                    <div className="flex items-center gap-2">
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
                    {/* Visual bar */}
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
            )}

            {/* Step 3: UTM Tracking */}
            {step === 3 && (
              <div className="space-y-4 max-w-lg">
                <p className="text-sm text-text-muted">
                  UTM parameters are appended to every link in your email
                  automatically. Customize them below or keep the auto-generated
                  values.
                </p>
                <div>
                  <label className="text-xs text-text-muted font-medium block mb-1">
                    utm_source
                  </label>
                  <input
                    type="text"
                    value={utmSource}
                    onChange={(e) => setUtmSource(e.target.value)}
                    placeholder="brevo"
                    className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                  />
                  <p className="text-[11px] text-text-muted mt-0.5">
                    Where the traffic comes from (e.g., brevo, mailchimp)
                  </p>
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
                    className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                  />
                  <p className="text-[11px] text-text-muted mt-0.5">
                    The marketing channel (e.g., email, social, cpc)
                  </p>
                </div>
                <div>
                  <label className="text-xs text-text-muted font-medium block mb-1">
                    utm_campaign
                  </label>
                  <input
                    type="text"
                    value={utmCampaign}
                    onChange={(e) => setUtmCampaign(e.target.value)}
                    placeholder="spring-sale-2026"
                    className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                  />
                  <p className="text-[11px] text-text-muted mt-0.5">
                    Auto-generated from your campaign name
                  </p>
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
                      placeholder="variant-a"
                      className="w-full px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent-blue"
                    />
                    <p className="text-[11px] text-text-muted mt-0.5">
                      Auto-set per variant if left blank (variant-a, variant-b,
                      etc.)
                    </p>
                  </div>
                )}

                {/* Preview */}
                <div className="p-3 rounded-lg bg-glass-bg border border-glass-border">
                  <p className="text-xs text-text-muted font-medium mb-1">
                    Link Preview
                  </p>
                  <code className="text-xs text-accent-green break-all">
                    https://example.com/sale?utm_source={utmSource || "..."}
                    &utm_medium=
                    {utmMedium || "..."}&utm_campaign={utmCampaign || "..."}
                    {utmContent ? `&utm_content=${utmContent}` : ""}
                  </code>
                </div>
              </div>
            )}

            {/* Step 4: Review */}
            {step === 4 && (
              <div className="space-y-5 max-w-2xl">
                {/* Summary */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Campaign Summary
                  </h3>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-text-muted">Name:</span>{" "}
                      <span className="text-text-primary font-medium">
                        {name}
                      </span>
                    </div>
                    <div>
                      <span className="text-text-muted">Audience:</span>{" "}
                      <span className="text-text-primary font-medium">
                        {useCustom
                          ? "Custom segment"
                          : selectedSegment?.name || "All subscribers"}
                      </span>
                    </div>
                  </div>

                  {/* Variants table */}
                  <div>
                    <p className="text-xs text-text-muted font-medium mb-1">
                      Variants ({variants.length})
                    </p>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-text-muted text-xs border-b border-glass-border">
                          <th className="py-1.5">Label</th>
                          <th className="py-1.5">Subject</th>
                          <th className="py-1.5">Template</th>
                          <th className="py-1.5">Weight</th>
                        </tr>
                      </thead>
                      <tbody>
                        {variants.map((v) => {
                          const totalWeight = variants.reduce(
                            (sum, vv) => sum + vv.weight,
                            0,
                          );
                          return (
                            <tr
                              key={v.label}
                              className="border-b border-glass-border/50"
                            >
                              <td className="py-1.5 font-medium text-accent-blue">
                                {v.label}
                              </td>
                              <td className="py-1.5 text-text-primary">
                                {v.subject || "(no subject)"}
                              </td>
                              <td className="py-1.5 text-text-muted text-xs">
                                {v.source_template_id || "Custom"}
                              </td>
                              <td className="py-1.5 text-text-muted">
                                {Math.round((v.weight / totalWeight) * 100)}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* UTM */}
                  <div>
                    <p className="text-xs text-text-muted font-medium mb-1">
                      UTM Tracking
                    </p>
                    <code className="text-xs text-accent-green">
                      source={utmSource} | medium={utmMedium} | campaign=
                      {utmCampaign}
                      {utmContent ? ` | content=${utmContent}` : ""}
                    </code>
                  </div>
                </div>

                {/* Send options */}
                <div className="space-y-3 pt-3 border-t border-glass-border">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Send Options
                  </h3>
                  <div className="flex gap-3">
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
                    <div>
                      <input
                        type="datetime-local"
                        value={scheduledAt}
                        onChange={(e) => setScheduledAt(e.target.value)}
                        className="px-3 py-2 rounded-lg border border-glass-border bg-transparent text-text-primary focus:outline-none focus:border-accent-blue"
                      />
                    </div>
                  )}

                  {/* Send time suggestion */}
                  {sendTimeSuggestion && (
                    <div className="p-3 rounded-lg bg-accent-blue/5 border border-accent-blue/20 text-sm">
                      <p className="text-accent-blue font-medium text-xs mb-1">
                        Suggested Send Time
                      </p>
                      <p className="text-text-secondary">
                        {sendTimeSuggestion.suggested_day} at{" "}
                        {sendTimeSuggestion.suggested_hour}:00
                        <span className="text-text-muted ml-2">
                          ({sendTimeSuggestion.confidence} confidence)
                        </span>
                      </p>
                      {sendTimeSuggestion.note && (
                        <p className="text-xs text-text-muted mt-0.5">
                          {sendTimeSuggestion.note}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {error && <p className="text-sm text-accent-pink">{error}</p>}
              </div>
            )}
          </div>

          {/* Right sidebar: Insights + Tips */}
          <div className="w-72 flex-shrink-0 border-l border-glass-border overflow-y-auto p-4 space-y-4">
            {/* Coaching tip */}
            {showTips && COACHING_TIPS[step] && (
              <div className="p-3 rounded-lg bg-accent-blue/5 border border-accent-blue/20">
                <p className="text-xs font-semibold text-accent-blue mb-1">
                  {COACHING_TIPS[step].title}
                </p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {COACHING_TIPS[step].body}
                </p>
              </div>
            )}

            {/* Global insights (shown on step 0) */}
            {step === 0 && globalInsights && (
              <InsightsCard title="Your Audience" insights={globalInsights} />
            )}

            {/* Segment insights (shown on step 1) */}
            {step === 1 && segmentInsights && (
              <SegmentInsightsCard insights={segmentInsights} />
            )}

            {/* Variant weight visualization (step 2) */}
            {step === 2 && variants.length > 1 && (
              <div className="p-3 rounded-lg border border-glass-border">
                <p className="text-xs font-medium text-text-muted mb-2">
                  Audience Split
                </p>
                {variants.map((v) => {
                  const totalWeight = variants.reduce(
                    (sum, vv) => sum + vv.weight,
                    0,
                  );
                  const pct = Math.round((v.weight / totalWeight) * 100);
                  return (
                    <div key={v.label} className="mb-1.5">
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-text-secondary">
                          Variant {v.label}
                        </span>
                        <span className="text-text-muted">{pct}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-glass-border overflow-hidden">
                        <div
                          className="h-full bg-accent-blue rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer nav */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-glass-border">
          <button
            type="button"
            onClick={() => (step > 0 ? setStep(step - 1) : onClose())}
            className="text-sm text-text-muted hover:text-text-secondary transition-colors"
          >
            {step > 0 ? "\u2190 Back" : "Cancel"}
          </button>
          <div className="flex gap-3">
            {step < STEPS.length - 1 ? (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                disabled={!canProceed()}
                className="px-5 py-2 rounded-lg bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next &rarr;
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || !canProceed()}
                className="px-5 py-2 rounded-lg bg-accent-green text-white text-sm font-medium hover:bg-accent-green/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {submitting
                  ? "Creating..."
                  : sendMode === "schedule"
                    ? "Schedule Campaign"
                    : "Create Draft"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────

function InsightsCard({
  title,
  insights,
}: {
  title: string;
  insights: GlobalInsights;
}) {
  const rfmEntries = Object.entries(insights.by_rfm_segment).sort(
    (a, b) => b[1] - a[1],
  );
  return (
    <div className="p-3 rounded-lg border border-glass-border space-y-2">
      <p className="text-xs font-medium text-text-muted">{title}</p>
      <div className="text-2xl font-bold text-text-primary">
        {insights.total_eligible.toLocaleString()}
      </div>
      <p className="text-xs text-text-muted">eligible subscribers</p>

      {/* RFM bars */}
      {rfmEntries.length > 0 && (
        <div className="space-y-1 pt-2">
          <p className="text-[10px] text-text-muted font-medium uppercase tracking-wider">
            RFM Segments
          </p>
          {rfmEntries.slice(0, 5).map(([seg, count]) => (
            <div key={seg}>
              <div className="flex justify-between text-[11px]">
                <span className="text-text-secondary capitalize">{seg}</span>
                <span className="text-text-muted">{count}</span>
              </div>
              <div className="h-1 rounded-full bg-glass-border mt-0.5">
                <div
                  className="h-full bg-accent-blue rounded-full"
                  style={{
                    width: `${(count / insights.total_eligible) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
        <div>
          <span className="text-text-muted block">Avg Order</span>
          <span className="text-text-primary font-medium">
            ${insights.avg_order_value}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Active (30d)</span>
          <span className="text-text-primary font-medium">
            {insights.active_last_30_days}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Avg Orders</span>
          <span className="text-text-primary font-medium">
            {insights.avg_orders_per_user}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Cart Abandons</span>
          <span className="text-text-primary font-medium">
            {insights.cart_abandonment_count}
          </span>
        </div>
      </div>
    </div>
  );
}

function SegmentInsightsCard({ insights }: { insights: SegmentInsights }) {
  return (
    <div className="p-3 rounded-lg border border-glass-border space-y-2">
      <p className="text-xs font-medium text-text-muted">Segment Insights</p>
      <div className="text-2xl font-bold text-text-primary">
        {insights.user_count.toLocaleString()}
      </div>
      <p className="text-xs text-text-muted">
        users ({insights.pct_of_total}% of total)
      </p>

      <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
        <div>
          <span className="text-text-muted block">Avg Order</span>
          <span className="text-text-primary font-medium">
            ${insights.avg_order_value}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Avg Orders</span>
          <span className="text-text-primary font-medium">
            {insights.avg_orders_per_user}
          </span>
        </div>
        <div>
          <span className="text-text-muted block">Total Revenue</span>
          <span className="text-text-primary font-medium">
            ${(insights.total_revenue / 100).toFixed(2)}
          </span>
        </div>
      </div>

      {/* Top products */}
      {insights.top_products.length > 0 && (
        <div className="pt-2">
          <p className="text-[10px] text-text-muted font-medium uppercase tracking-wider mb-1">
            Top Products
          </p>
          {insights.top_products.map((p) => (
            <div
              key={p.name}
              className="flex justify-between text-[11px] py-0.5"
            >
              <span className="text-text-secondary truncate">{p.name}</span>
              <span className="text-text-muted ml-2">{p.purchase_count}</span>
            </div>
          ))}
        </div>
      )}

      {/* Email stats */}
      <div className="pt-2">
        <p className="text-[10px] text-text-muted font-medium uppercase tracking-wider mb-1">
          Recent Email Stats (90d)
        </p>
        <div className="grid grid-cols-2 gap-1 text-[11px]">
          <span className="text-text-muted">
            Sent: {insights.recent_email_stats.sent || 0}
          </span>
          <span className="text-text-muted">
            Delivered: {insights.recent_email_stats.delivered || 0}
          </span>
          <span className="text-text-muted">
            Skipped: {insights.recent_email_stats.skipped || 0}
          </span>
          <span className="text-text-muted">
            Bounced: {insights.recent_email_stats.bounced || 0}
          </span>
        </div>
      </div>
    </div>
  );
}
