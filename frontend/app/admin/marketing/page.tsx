"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { useConfig } from "../../../lib/config-context";
import { useToast } from "../../../components/Toast";
import LoadingSpinner from "../../../components/LoadingSpinner";
import Pagination from "../../../components/Pagination";
import Modal from "../../../components/Modal";
import { formatDate, formatRelativeTime, truncate } from "../../../lib/format";
import type { SegmentFilters } from "../../../components/SegmentBuilder";

const TemplateEditor = dynamic(
  () => import("../../../components/TemplateEditor"),
  { ssr: false },
);

const CampaignWizard = dynamic(
  () => import("../../../components/CampaignWizard"),
  { ssr: false },
);

// ── Interfaces ──────────────────────────────────────────

interface EmailTemplate {
  id: string;
  name: string;
  display_name: string;
  subject: string | null;
  html_content: string | null;
  category: string;
  description: string | null;
  variables: Array<{ name: string; description: string }>;
  is_builtin: boolean;
  version: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

interface TemplateList {
  items: EmailTemplate[];
  total: number;
  page: number;
  per_page: number;
}

interface Campaign {
  id: string;
  name: string;
  subject: string;
  template_id: string;
  status: string;
  provider_campaign_id: string | null;
  recipient_count: number;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
}

interface CampaignList {
  items: Campaign[];
  total: number;
  page: number;
  per_page: number;
}

interface CampaignStats {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  unsubscribed: number;
  fetched_at: string | null;
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

interface EmailLog {
  id: string;
  user_id: string;
  email_type: string;
  template_id: string;
  provider: string;
  provider_message_id: string | null;
  status: string;
  skip_reason: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  created_at: string;
}

interface EmailLogList {
  items: EmailLog[];
  total: number;
  page: number;
  page_size: number;
}

interface SuppressedUser {
  user_id: string;
  email: string;
  suppressed_at: string;
  suppression_reason: string | null;
}

interface SuppressedList {
  items: SuppressedUser[];
  total: number;
  page: number;
  page_size: number;
}

interface CommunicationType {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
}

interface AudienceRecipient {
  user_id: string;
  email: string;
}

interface AudienceResponse {
  count: number;
  recipients: AudienceRecipient[];
}

// ── Helpers ─────────────────────────────────────────────

function statusBadge(status: string): string {
  switch (status) {
    case "draft":
      return "badge-blue";
    case "scheduled":
      return "badge-purple";
    case "sending":
      return "badge-blue";
    case "sent":
    case "delivered":
      return "badge-green";
    case "cancelled":
    case "bounced":
    case "complained":
    case "failed":
      return "badge-pink";
    case "skipped":
      return "badge-purple";
    default:
      return "badge-purple";
  }
}

// ── Tab types ───────────────────────────────────────────

type TabId =
  | "templates"
  | "campaigns"
  | "email_logs"
  | "suppressed"
  | "comm_types"
  | "audience";

const TABS: { id: TabId; label: string }[] = [
  { id: "templates", label: "Templates" },
  { id: "campaigns", label: "Campaigns" },
  { id: "email_logs", label: "Email Logs" },
  { id: "suppressed", label: "Suppressed" },
  { id: "comm_types", label: "Comm Types" },
  { id: "audience", label: "Audience" },
];

// ── Main Page ───────────────────────────────────────────

export default function AdminMarketingPage() {
  const { enable_marketing } = useConfig();
  const [activeTab, setActiveTab] = useState<TabId>("templates");

  if (!enable_marketing) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-text-muted">
          Marketing is disabled. Enable it via{" "}
          <code className="text-accent-pink">ENABLE_MARKETING=true</code>.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-serif text-2xl font-bold mb-6">
        <span className="gradient-text">Marketing</span>
      </h1>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-glass-border/50 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative whitespace-nowrap ${
              activeTab === tab.id
                ? "text-accent-pink"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-pink rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "templates" && <TemplatesTab />}
      {activeTab === "campaigns" && <CampaignsTab />}
      {activeTab === "email_logs" && <EmailLogsTab />}
      {activeTab === "suppressed" && <SuppressedTab />}
      {activeTab === "comm_types" && <CommTypesTab />}
      {activeTab === "audience" && <AudienceTab />}
    </div>
  );
}

// ── Templates Tab ───────────────────────────────────────

function categoryBadge(category: string): string {
  switch (category) {
    case "transactional":
      return "badge-blue";
    case "campaign":
      return "badge-purple";
    case "automation":
      return "badge-green";
    default:
      return "badge-purple";
  }
}

function TemplatesTab() {
  const { showToast } = useToast();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const perPage = 15;

  // Editor state
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(
    null,
  );
  const [saving, setSaving] = useState(false);

  // Form fields
  const [formName, setFormName] = useState("");
  const [formDisplayName, setFormDisplayName] = useState("");
  const [formSubject, setFormSubject] = useState("");
  const [formCategory, setFormCategory] = useState("campaign");
  const [formDescription, setFormDescription] = useState("");
  const [formHtml, setFormHtml] = useState("");

  // Clone modal
  const [cloneSource, setCloneSource] = useState<EmailTemplate | null>(null);
  const [cloneName, setCloneName] = useState("");
  const [cloneDisplayName, setCloneDisplayName] = useState("");
  const [cloning, setCloning] = useState(false);

  // Sample values for the "Rendered Preview" — covers current + future BP variables
  const SAMPLE_VALUES: Record<string, string> = {
    first_name: "John",
    verify_url: "https://example.com/verify?token=abc123",
    reset_url: "https://example.com/reset?token=abc123",
    order_id: "ORD-A1B2C3D4",
    total: "$49.99",
    order_url: "https://example.com/orders/abc123",
    amount: "49.99",
    currency: "USD",
    date: "April 20, 2026",
    payment_method: "Visa ending in 4242",
    reference: "PAY-12345",
    plan_name: "Pro Plan",
    next_billing_date: "May 20, 2026",
    dashboard_url: "https://example.com/dashboard",
    end_date: "May 20, 2026",
    resubscribe_url: "https://example.com/resubscribe",
    download_url: "https://example.com/download/export.zip",
    expires_at: "April 27, 2026",
    deletion_date: "April 20, 2026",
    cart_url: "https://example.com/cart",
    recovery_discount_code: "SAVE10",
    discount_percent: "15",
    discount_code: "WELCOME15",
    browse_url: "https://example.com/shop",
    tier_name: "Gold",
    order_count: "12",
    total_spent: "$1,234.56",
    tracking_url: "https://example.com/track/abc123",
    expected_delivery_date: "April 25, 2026",
    review_url: "https://example.com/review/abc123",
    last_purchased_product_name: "Running Shoes",
    replenishment_url: "https://example.com/reorder",
    points_earned: "150",
    points_balance: "1,200",
    progress_to_next_tier_percent: "75",
    new_tier_name: "Platinum",
    redeem_url: "https://example.com/rewards/redeem",
    product_name: "Premium Headphones",
    product_url: "https://example.com/products/headphones",
    product_image: "https://example.com/images/headphones.jpg",
    old_price: "$99.99",
    new_price: "$79.99",
    birthday_discount_percent: "20",
    days_since_purchase: "45",
    days_since_last_purchase: "30",
    expires_in_hours: "24",
  };

  function buildSampleData(
    vars: Array<Record<string, string>>,
  ): Record<string, string> {
    const data: Record<string, string> = {};
    for (const v of vars) {
      const name = v.name;
      if (name) data[name] = SAMPLE_VALUES[name] || `[${name}]`;
    }
    if (!data.first_name) data.first_name = "John";
    return data;
  }

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (categoryFilter) params.set("category", categoryFilter);
      const data = await apiFetch<TemplateList>(
        `/marketing/admin/templates?${params}`,
      );
      setTemplates(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load templates", "error");
    }
    setLoading(false);
  }, [page, categoryFilter, showToast]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  function openCreate() {
    setEditingTemplate(null);
    setFormName("");
    setFormDisplayName("");
    setFormSubject("");
    setFormCategory("campaign");
    setFormDescription("");
    setFormHtml("<h1>Hello {{ first_name }}</h1>\n<p>Your content here.</p>");
    setEditorOpen(true);
  }

  async function openEdit(t: EmailTemplate) {
    try {
      const full = await apiFetch<EmailTemplate>(
        `/marketing/admin/templates/${t.id}`,
      );
      setEditingTemplate(full);
      setFormName(full.name);
      setFormDisplayName(full.display_name);
      setFormSubject(full.subject || "");
      setFormCategory(full.category);
      setFormDescription(full.description || "");
      setFormHtml(full.html_content || "");
      setEditorOpen(true);
    } catch {
      showToast("Failed to load template", "error");
    }
  }

  async function handleSave() {
    if (!formDisplayName.trim() || !formHtml.trim()) {
      showToast("Display name and HTML content are required", "error");
      return;
    }
    setSaving(true);
    try {
      if (editingTemplate) {
        await apiFetch(`/marketing/admin/templates/${editingTemplate.id}`, {
          method: "PUT",
          body: JSON.stringify({
            display_name: formDisplayName,
            subject: formSubject || null,
            html_content: formHtml,
            category: formCategory,
            description: formDescription || null,
          }),
        });
        showToast("Template updated", "success");
      } else {
        if (!formName.trim()) {
          showToast("Template name is required", "error");
          setSaving(false);
          return;
        }
        await apiFetch("/marketing/admin/templates", {
          method: "POST",
          body: JSON.stringify({
            name: formName,
            display_name: formDisplayName,
            subject: formSubject || null,
            html_content: formHtml,
            category: formCategory,
            description: formDescription || null,
            variables: [],
          }),
        });
        showToast("Template created", "success");
      }
      setEditorOpen(false);
      fetchTemplates();
    } catch {
      showToast("Failed to save template", "error");
    }
    setSaving(false);
  }

  async function handleDelete(t: EmailTemplate) {
    if (!confirm(`Delete template "${t.display_name}"? This cannot be undone.`))
      return;
    try {
      await apiFetch(`/marketing/admin/templates/${t.id}`, {
        method: "DELETE",
      });
      showToast("Template deleted", "success");
      fetchTemplates();
    } catch {
      showToast("Failed to delete template", "error");
    }
  }

  async function handleSendTest(t: EmailTemplate) {
    try {
      const result = await apiFetch<{
        status: string;
        error?: string;
      }>(`/marketing/admin/templates/${t.id}/send-test`, {
        method: "POST",
      });
      if (result.status === "sent") {
        showToast("Test email sent to your address", "success");
      } else if (result.status === "queued") {
        showToast(
          `Email queued for retry${result.error ? `: ${result.error}` : ""}. Check email provider config.`,
          "error",
        );
      } else {
        showToast(`Email status: ${result.status}`, "error");
      }
    } catch {
      showToast("Failed to send test email", "error");
    }
  }

  function openClone(t: EmailTemplate) {
    setCloneSource(t);
    setCloneName("");
    setCloneDisplayName("");
  }

  async function handleClone() {
    if (!cloneName.trim() || !cloneDisplayName.trim()) {
      showToast("Name and display name are required", "error");
      return;
    }
    setCloning(true);
    try {
      await apiFetch(`/marketing/admin/templates/${cloneSource!.id}/clone`, {
        method: "POST",
        body: JSON.stringify({
          new_name: cloneName,
          new_display_name: cloneDisplayName,
        }),
      });
      showToast("Template cloned", "success");
      setCloneSource(null);
      fetchTemplates();
    } catch {
      showToast("Failed to clone template", "error");
    }
    setCloning(false);
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <select
            className="input-glass text-sm py-1.5 px-3"
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            <option value="transactional">Transactional</option>
            <option value="campaign">Campaign</option>
            <option value="automation">Automation</option>
          </select>
          <span className="text-xs text-text-muted">
            {total} template{total !== 1 ? "s" : ""}
          </span>
        </div>
        <button className="btn-primary text-sm" onClick={openCreate}>
          + New Template
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : templates.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">
          No templates found.
        </div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">
                  Name
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Category
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Subject
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Version
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Updated
                </th>
                <th className="text-right p-3 text-text-muted font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3">
                    <div className="text-text-primary font-medium">
                      {t.display_name}
                    </div>
                    <div className="text-text-muted font-mono text-xs">
                      {t.name}
                    </div>
                  </td>
                  <td className="p-3">
                    <span className={`badge ${categoryBadge(t.category)}`}>
                      {t.category}
                    </span>
                  </td>
                  <td className="p-3 text-text-secondary text-xs">
                    {t.subject ? truncate(t.subject, 35) : "-"}
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    v{t.version}
                    {t.is_builtin && (
                      <span className="badge badge-blue ml-2">built-in</span>
                    )}
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {formatRelativeTime(t.updated_at)}
                  </td>
                  <td className="p-3 text-right space-x-2">
                    <button
                      onClick={() => openEdit(t)}
                      className="text-accent-blue hover:underline text-xs"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => openClone(t)}
                      className="text-accent-purple hover:underline text-xs"
                    >
                      Clone
                    </button>
                    <button
                      onClick={() => handleSendTest(t)}
                      className="text-accent-green hover:underline text-xs"
                    >
                      Test
                    </button>
                    {!t.is_builtin && (
                      <button
                        onClick={() => handleDelete(t)}
                        className="text-accent-pink hover:underline text-xs"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(total / perPage)}
          onPageChange={setPage}
        />
      </div>

      {/* Editor modal (full-screen) */}
      <Modal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        title={
          editingTemplate
            ? `Edit: ${editingTemplate.display_name}`
            : "New Template"
        }
        size="full"
      >
        <div className="space-y-4">
          {/* Meta fields row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Template ID
              </label>
              <input
                className="input-glass w-full font-mono text-sm"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="my_template"
                disabled={!!editingTemplate}
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Display Name
              </label>
              <input
                className="input-glass w-full"
                value={formDisplayName}
                onChange={(e) => setFormDisplayName(e.target.value)}
                placeholder="My Template"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Subject Line
              </label>
              <input
                className="input-glass w-full"
                value={formSubject}
                onChange={(e) => setFormSubject(e.target.value)}
                placeholder="Hello {{first_name}}!"
              />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">
                Category
              </label>
              <select
                className="input-glass w-full"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
              >
                <option value="transactional">Transactional</option>
                <option value="campaign">Campaign</option>
                <option value="automation">Automation</option>
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Description (optional)
            </label>
            <input
              className="input-glass w-full text-sm"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Internal notes about this template..."
            />
          </div>

          {/* Code editor + preview */}
          <TemplateEditor
            initialContent={formHtml}
            onChange={setFormHtml}
            templateData={buildSampleData(editingTemplate?.variables ?? [])}
            variables={editingTemplate?.variables ?? []}
          />

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              className="btn-secondary text-sm"
              onClick={() => setEditorOpen(false)}
            >
              Cancel
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleSave}
              disabled={saving}
            >
              {saving
                ? "Saving..."
                : editingTemplate
                  ? "Update Template"
                  : "Create Template"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Clone modal */}
      <Modal
        isOpen={!!cloneSource}
        onClose={() => setCloneSource(null)}
        title={`Clone: ${cloneSource?.display_name}`}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">
              New Template ID
            </label>
            <input
              className="input-glass w-full font-mono text-sm"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              placeholder="my_custom_welcome"
            />
            <p className="text-xs text-text-muted mt-1">
              Lowercase, underscores only (e.g. cart_abandonment)
            </p>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Display Name
            </label>
            <input
              className="input-glass w-full"
              value={cloneDisplayName}
              onChange={(e) => setCloneDisplayName(e.target.value)}
              placeholder="My Custom Welcome"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              className="btn-secondary text-sm"
              onClick={() => setCloneSource(null)}
            >
              Cancel
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleClone}
              disabled={cloning}
            >
              {cloning ? "Cloning..." : "Clone Template"}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}

// ── Campaigns Tab ───────────────────────────────────────

function CampaignsTab() {
  const { showToast } = useToast();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [wizardMode, setWizardMode] = useState(false);
  const [wizardFilters, setWizardFilters] = useState<
    SegmentFilters | undefined
  >();
  const [insights, setInsights] = useState<GlobalInsights | null>(null);
  const [statsModal, setStatsModal] = useState<CampaignStats | null>(null);
  const [statsName, setStatsName] = useState("");

  const perPage = 15;

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (statusFilter) params.set("status", statusFilter);
      const data = await apiFetch<CampaignList>(
        `/marketing/admin/campaigns?${params}`,
      );
      setCampaigns(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load campaigns", "error");
    }
    setLoading(false);
  }, [page, statusFilter, showToast]);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  // Fetch audience insights for the cards
  useEffect(() => {
    apiFetch<GlobalInsights>("/marketing/admin/insights/global")
      .then(setInsights)
      .catch(() => {});
  }, []);

  function startWizard(filters?: SegmentFilters) {
    setWizardFilters(filters);
    setWizardMode(true);
  }

  async function handleSend(id: string) {
    if (!confirm("Send this campaign now?")) return;
    try {
      await apiFetch(`/marketing/admin/campaigns/${id}/send`, {
        method: "POST",
      });
      showToast("Campaign sent", "success");
      fetchCampaigns();
    } catch {
      showToast("Failed to send campaign", "error");
    }
  }

  async function handleCancel(id: string) {
    if (!confirm("Cancel this campaign?")) return;
    try {
      await apiFetch(`/marketing/admin/campaigns/${id}`, { method: "DELETE" });
      showToast("Campaign cancelled", "success");
      fetchCampaigns();
    } catch {
      showToast("Failed to cancel campaign", "error");
    }
  }

  async function handleStats(c: Campaign) {
    try {
      const data = await apiFetch<CampaignStats>(
        `/marketing/admin/campaigns/${c.id}/stats`,
      );
      setStatsModal(data);
      setStatsName(c.name);
    } catch {
      showToast("Failed to load stats", "error");
    }
  }

  // ─── Wizard mode: render inline wizard ───
  if (wizardMode) {
    return (
      <CampaignWizard
        initialFilters={wizardFilters}
        onClose={() => setWizardMode(false)}
        onCreated={() => {
          setWizardMode(false);
          showToast("Campaign created", "success");
          fetchCampaigns();
        }}
      />
    );
  }

  // ─── Insight card definitions ───
  const insightCards: Array<{
    label: string;
    count: number | null;
    color: string;
    filters: SegmentFilters;
  }> = insights
    ? [
        {
          label: "All Subscribers",
          count: insights.total_eligible,
          color: "text-accent-blue",
          filters: {},
        },
        {
          label: "Champions",
          count: insights.by_rfm_segment?.champion ?? null,
          color: "text-green-400",
          filters: { rfm_segment: ["champion"] },
        },
        {
          label: "At-Risk",
          count:
            (insights.by_rfm_segment?.at_risk ?? 0) +
            (insights.by_rfm_segment?.hibernating ?? 0),
          color: "text-yellow-400",
          filters: { rfm_segment: ["at_risk", "hibernating"] },
        },
        {
          label: "Cart Abandoners",
          count: insights.cart_abandonment_count,
          color: "text-orange-400",
          filters: { cart_status: "abandoned" },
        },
        {
          label: "New Customers",
          count: insights.by_rfm_segment?.new ?? null,
          color: "text-purple-400",
          filters: { rfm_segment: ["new"] },
        },
        {
          label: "Active (30d)",
          count: insights.active_last_30_days,
          color: "text-cyan-400",
          filters: { last_purchase_days_max: 30 },
        },
      ]
    : [];

  return (
    <>
      {/* Audience insight cards */}
      {insightCards.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          {insightCards.map((card) => (
            <div
              key={card.label}
              className="glass rounded-xl p-4 flex flex-col justify-between"
            >
              <div>
                <p className="text-xs text-text-muted font-medium mb-1">
                  {card.label}
                </p>
                <p className={`text-2xl font-bold ${card.color}`}>
                  {card.count !== null ? card.count.toLocaleString() : "—"}
                </p>
              </div>
              <button
                onClick={() =>
                  startWizard(
                    Object.keys(card.filters).length > 0
                      ? card.filters
                      : undefined,
                  )
                }
                className="mt-3 text-xs text-accent-blue hover:text-accent-blue/80 transition-colors text-left"
              >
                Create Campaign &rarr;
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <select
            className="input-glass text-sm py-1.5 px-3"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="scheduled">Scheduled</option>
            <option value="sent">Sent</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <span className="text-xs text-text-muted">
            {total} campaign{total !== 1 ? "s" : ""}
          </span>
        </div>
        <button className="btn-primary text-sm" onClick={() => startWizard()}>
          + New Campaign
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : campaigns.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">
          No campaigns found.
        </div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">
                  Name
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Subject
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Template
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Status
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Date
                </th>
                <th className="text-right p-3 text-text-muted font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3 text-text-primary">
                    {truncate(c.name, 30)}
                  </td>
                  <td className="p-3 text-text-secondary">
                    {truncate(c.subject, 30)}
                  </td>
                  <td className="p-3 text-text-muted font-mono text-xs">
                    {c.template_id}
                  </td>
                  <td className="p-3">
                    <span className={`badge ${statusBadge(c.status)}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {c.sent_at
                      ? formatRelativeTime(c.sent_at)
                      : c.scheduled_at
                        ? `Sched: ${formatDate(c.scheduled_at)}`
                        : formatRelativeTime(c.created_at)}
                  </td>
                  <td className="p-3 text-right space-x-2">
                    {(c.status === "draft" || c.status === "scheduled") && (
                      <>
                        <button
                          onClick={() => handleSend(c.id)}
                          className="text-accent-green hover:underline text-xs"
                        >
                          Send
                        </button>
                        <button
                          onClick={() => handleCancel(c.id)}
                          className="text-accent-pink hover:underline text-xs"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {(c.status === "sent" || c.status === "sending") && (
                      <button
                        onClick={() => handleStats(c)}
                        className="text-accent-blue hover:underline text-xs"
                      >
                        Stats
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(total / perPage)}
          onPageChange={setPage}
        />
      </div>

      {/* Stats modal */}
      <Modal
        isOpen={!!statsModal}
        onClose={() => setStatsModal(null)}
        title={`Stats: ${statsName}`}
        size="md"
      >
        {statsModal && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(
              [
                ["Sent", statsModal.sent, "accent-blue"],
                ["Delivered", statsModal.delivered, "accent-green"],
                ["Opened", statsModal.opened, "accent-purple"],
                ["Clicked", statsModal.clicked, "accent-pink"],
                ["Bounced", statsModal.bounced, "accent-pink"],
                ["Unsubscribed", statsModal.unsubscribed, "accent-pink"],
              ] as [string, number, string][]
            ).map(([label, val, color]) => (
              <div key={label} className="glass rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted mb-1">{label}</p>
                <p className={`text-xl font-bold text-${color}`}>{val}</p>
                {statsModal.sent > 0 && label !== "Sent" && (
                  <p className="text-xs text-text-muted">
                    {((val / statsModal.sent) * 100).toFixed(1)}%
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}

// ── Email Logs Tab ──────────────────────────────────────

function EmailLogsTab() {
  const { showToast } = useToast();
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [userFilter, setUserFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (typeFilter) params.set("email_type", typeFilter);
      if (statusFilter) params.set("status", statusFilter);
      if (userFilter.trim()) params.set("user_id", userFilter.trim());
      const data = await apiFetch<EmailLogList>(
        `/marketing/admin/email-logs?${params}`,
      );
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load email logs", "error");
    }
    setLoading(false);
  }, [page, typeFilter, statusFilter, userFilter, showToast]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  async function handleResend(eventId: string) {
    if (!confirm("Resend this email?")) return;
    try {
      await apiFetch(`/marketing/admin/resend/${eventId}`, { method: "POST" });
      showToast("Email resent", "success");
      fetchLogs();
    } catch {
      showToast("Failed to resend email", "error");
    }
  }

  return (
    <>
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          className="input-glass text-sm py-1.5 px-3"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All types</option>
          <option value="transactional_email">Transactional</option>
          <option value="marketing_email">Marketing</option>
        </select>
        <select
          className="input-glass text-sm py-1.5 px-3"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="delivered">Delivered</option>
          <option value="bounced">Bounced</option>
          <option value="complained">Complained</option>
          <option value="skipped">Skipped</option>
          <option value="queued">Queued</option>
        </select>
        <input
          className="input-glass text-sm py-1.5 px-3 w-48"
          placeholder="Filter by user ID..."
          value={userFilter}
          onChange={(e) => setUserFilter(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setPage(1);
              fetchLogs();
            }
          }}
        />
        <span className="text-xs text-text-muted">
          {total} event{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : logs.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">
          No email events found.
        </div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">
                  Time
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  User
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Type
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Template
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Provider
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Status
                </th>
                <th className="text-right p-3 text-text-muted font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3 text-text-muted text-xs">
                    {formatRelativeTime(log.created_at)}
                  </td>
                  <td className="p-3 text-text-secondary font-mono text-xs">
                    {truncate(log.user_id, 8)}
                  </td>
                  <td className="p-3 text-text-secondary text-xs">
                    {log.email_type === "marketing_email"
                      ? "Marketing"
                      : "Transactional"}
                  </td>
                  <td className="p-3 text-text-muted font-mono text-xs">
                    {log.template_id}
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {log.provider || "-"}
                  </td>
                  <td className="p-3">
                    <span className={`badge ${statusBadge(log.status)}`}>
                      {log.status}
                    </span>
                    {log.skip_reason && (
                      <span className="text-xs text-text-muted ml-1">
                        ({log.skip_reason})
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right">
                    {["bounced", "complained", "skipped"].includes(
                      log.status,
                    ) && (
                      <button
                        onClick={() => handleResend(log.id)}
                        className="text-accent-blue hover:underline text-xs"
                      >
                        Resend
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(total / pageSize)}
          onPageChange={setPage}
        />
      </div>
    </>
  );
}

// ── Suppressed Tab ──────────────────────────────────────

function SuppressedTab() {
  const { showToast } = useToast();
  const [users, setUsers] = useState<SuppressedUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const fetchSuppressed = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<SuppressedList>(
        `/marketing/admin/suppressed?page=${page}&page_size=${pageSize}`,
      );
      setUsers(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load suppressed users", "error");
    }
    setLoading(false);
  }, [page, showToast]);

  useEffect(() => {
    fetchSuppressed();
  }, [fetchSuppressed]);

  return (
    <>
      <p className="text-xs text-text-muted mb-4">
        {total} suppressed user{total !== 1 ? "s" : ""}
      </p>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : users.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">
          No suppressed users. This is a good thing!
        </div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">
                  Email
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  User ID
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Suppressed
                </th>
                <th className="text-left p-3 text-text-muted font-medium">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.user_id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors"
                >
                  <td className="p-3 text-text-primary">{u.email}</td>
                  <td className="p-3 text-text-muted font-mono text-xs">
                    {truncate(u.user_id, 8)}
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {formatRelativeTime(u.suppressed_at)}
                  </td>
                  <td className="p-3">
                    <span className="badge badge-pink">
                      {u.suppression_reason || "unknown"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(total / pageSize)}
          onPageChange={setPage}
        />
      </div>
    </>
  );
}

// ── Communication Types Tab ─────────────────────────────

function CommTypesTab() {
  const { showToast } = useToast();
  const [types, setTypes] = useState<CommunicationType[]>([]);
  const [showDisabled, setShowDisabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<CommunicationType | null>(null);
  const [saving, setSaving] = useState(false);

  // Form
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formEnabled, setFormEnabled] = useState(true);

  const fetchTypes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<CommunicationType[]>(
        `/marketing/admin/communication-types?include_disabled=${showDisabled}`,
      );
      setTypes(data);
    } catch {
      showToast("Failed to load communication types", "error");
    }
    setLoading(false);
  }, [showDisabled, showToast]);

  useEffect(() => {
    fetchTypes();
  }, [fetchTypes]);

  function openEdit(t: CommunicationType) {
    setEditing(t);
    setFormName(t.name);
    setFormDesc(t.description || "");
    setFormEnabled(t.enabled);
  }

  function openCreate() {
    setEditing(null);
    setFormName("");
    setFormDesc("");
    setFormEnabled(true);
    setShowCreate(true);
  }

  async function handleSave() {
    if (!formName.trim()) {
      showToast("Name is required", "error");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await apiFetch(`/marketing/admin/communication-types/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: formName,
            description: formDesc || null,
            enabled: formEnabled,
          }),
        });
        showToast("Updated", "success");
      } else {
        await apiFetch("/marketing/admin/communication-types", {
          method: "POST",
          body: JSON.stringify({
            name: formName,
            description: formDesc || null,
            enabled: formEnabled,
          }),
        });
        showToast("Created", "success");
      }
      setShowCreate(false);
      setEditing(null);
      fetchTypes();
    } catch {
      showToast("Failed to save", "error");
    }
    setSaving(false);
  }

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={showDisabled}
            onChange={(e) => setShowDisabled(e.target.checked)}
            className="rounded"
          />
          Show disabled
        </label>
        <button className="btn-primary text-sm" onClick={openCreate}>
          + New Type
        </button>
      </div>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : types.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">
          No communication types found.
        </div>
      ) : (
        <div className="grid gap-3">
          {types.map((t) => (
            <div
              key={t.id}
              className="glass rounded-xl p-4 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-text-primary font-medium">
                    {t.name}
                  </span>
                  <span
                    className={`badge ${t.enabled ? "badge-green" : "badge-pink"}`}
                  >
                    {t.enabled ? "enabled" : "disabled"}
                  </span>
                </div>
                {t.description && (
                  <p className="text-xs text-text-muted mt-1">
                    {t.description}
                  </p>
                )}
              </div>
              <button
                onClick={() => openEdit(t)}
                className="text-accent-blue hover:underline text-sm"
              >
                Edit
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit modal */}
      <Modal
        isOpen={showCreate || !!editing}
        onClose={() => {
          setShowCreate(false);
          setEditing(null);
        }}
        title={editing ? "Edit Communication Type" : "New Communication Type"}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">Name</label>
            <input
              className="input-glass w-full"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="weekly_digest"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Description
            </label>
            <textarea
              className="input-glass w-full h-20 resize-none"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="What this type is for..."
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={formEnabled}
              onChange={(e) => setFormEnabled(e.target.checked)}
              className="rounded"
            />
            Enabled
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <button
              className="btn-secondary text-sm"
              onClick={() => {
                setShowCreate(false);
                setEditing(null);
              }}
            >
              Cancel
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Saving..." : editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}

// ── Audience Tab ────────────────────────────────────────

function AudienceTab() {
  const { showToast } = useToast();
  const [types, setTypes] = useState<CommunicationType[]>([]);
  const [selectedType, setSelectedType] = useState("");
  const [audience, setAudience] = useState<AudienceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [typesLoading, setTypesLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiFetch<CommunicationType[]>(
          "/marketing/admin/communication-types",
        );
        setTypes(data);
      } catch {
        showToast("Failed to load types", "error");
      }
      setTypesLoading(false);
    })();
  }, [showToast]);

  const fetchAudience = useCallback(async () => {
    setLoading(true);
    try {
      const params = selectedType
        ? `?communication_type_id=${selectedType}`
        : "";
      const data = await apiFetch<AudienceResponse>(
        `/marketing/admin/audience${params}`,
      );
      setAudience(data);
    } catch {
      showToast("Failed to load audience", "error");
    }
    setLoading(false);
  }, [selectedType, showToast]);

  useEffect(() => {
    fetchAudience();
  }, [fetchAudience]);

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        {typesLoading ? (
          <LoadingSpinner size="sm" />
        ) : (
          <select
            className="input-glass text-sm py-1.5 px-3"
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
          >
            <option value="">All eligible users</option>
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : audience ? (
        <>
          <div className="glass rounded-xl p-4 mb-4 text-center">
            <span className="text-2xl font-bold text-accent-green">
              {audience.count}
            </span>
            <span className="text-text-muted ml-2">
              eligible recipient{audience.count !== 1 ? "s" : ""}
            </span>
          </div>

          {audience.recipients.length > 0 && (
            <div className="glass rounded-xl overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-glass-bg">
                  <tr className="border-b border-glass-border">
                    <th className="text-left p-3 text-text-muted font-medium">
                      Email
                    </th>
                    <th className="text-left p-3 text-text-muted font-medium">
                      User ID
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {audience.recipients.map((r) => (
                    <tr
                      key={r.user_id}
                      className="border-b border-glass-border/50"
                    >
                      <td className="p-3 text-text-primary">{r.email}</td>
                      <td className="p-3 text-text-muted font-mono text-xs">
                        {truncate(r.user_id, 8)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </>
  );
}
