"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { useConfig } from "../../../lib/config-context";
import { useToast } from "../../../components/Toast";
import LoadingSpinner from "../../../components/LoadingSpinner";
import Pagination from "../../../components/Pagination";
import Modal from "../../../components/Modal";
import { formatDate, formatRelativeTime, truncate } from "../../../lib/format";

// ── Interfaces ──────────────────────────────────────────

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
    case "draft": return "badge-blue";
    case "scheduled": return "badge-purple";
    case "sending": return "badge-blue";
    case "sent": case "delivered": return "badge-green";
    case "cancelled": case "bounced": case "complained": case "failed": return "badge-pink";
    case "skipped": return "badge-purple";
    default: return "badge-purple";
  }
}

// ── Tab types ───────────────────────────────────────────

type TabId = "campaigns" | "email_logs" | "suppressed" | "comm_types" | "audience";

const TABS: { id: TabId; label: string }[] = [
  { id: "campaigns", label: "Campaigns" },
  { id: "email_logs", label: "Email Logs" },
  { id: "suppressed", label: "Suppressed" },
  { id: "comm_types", label: "Comm Types" },
  { id: "audience", label: "Audience" },
];

// ── Main Page ───────────────────────────────────────────

export default function AdminMarketingPage() {
  const { enable_marketing } = useConfig();
  const [activeTab, setActiveTab] = useState<TabId>("campaigns");

  if (!enable_marketing) {
    return (
      <div className="glass rounded-xl p-8 text-center">
        <p className="text-text-muted">Marketing is disabled. Enable it via <code className="text-accent-pink">ENABLE_MARKETING=true</code>.</p>
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
      {activeTab === "campaigns" && <CampaignsTab />}
      {activeTab === "email_logs" && <EmailLogsTab />}
      {activeTab === "suppressed" && <SuppressedTab />}
      {activeTab === "comm_types" && <CommTypesTab />}
      {activeTab === "audience" && <AudienceTab />}
    </div>
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
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [statsModal, setStatsModal] = useState<CampaignStats | null>(null);
  const [statsName, setStatsName] = useState("");

  // Create form
  const [formName, setFormName] = useState("");
  const [formSubject, setFormSubject] = useState("");
  const [formTemplate, setFormTemplate] = useState("welcome");
  const [formScheduled, setFormScheduled] = useState("");

  const perPage = 15;

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
      if (statusFilter) params.set("status", statusFilter);
      const data = await apiFetch<CampaignList>(`/marketing/admin/campaigns?${params}`);
      setCampaigns(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load campaigns", "error");
    }
    setLoading(false);
  }, [page, statusFilter, showToast]);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  async function handleCreate() {
    if (!formName.trim() || !formSubject.trim()) {
      showToast("Name and subject are required", "error");
      return;
    }
    setCreating(true);
    try {
      await apiFetch("/marketing/admin/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: formName,
          subject: formSubject,
          template_id: formTemplate,
          template_data: {},
          scheduled_at: formScheduled || null,
        }),
      });
      showToast("Campaign created", "success");
      setShowCreate(false);
      setFormName(""); setFormSubject(""); setFormTemplate("welcome"); setFormScheduled("");
      fetchCampaigns();
    } catch {
      showToast("Failed to create campaign", "error");
    }
    setCreating(false);
  }

  async function handleSend(id: string) {
    if (!confirm("Send this campaign now?")) return;
    try {
      await apiFetch(`/marketing/admin/campaigns/${id}/send`, { method: "POST" });
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
      const data = await apiFetch<CampaignStats>(`/marketing/admin/campaigns/${c.id}/stats`);
      setStatsModal(data);
      setStatsName(c.name);
    } catch {
      showToast("Failed to load stats", "error");
    }
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <select
            className="input-glass text-sm py-1.5 px-3"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="scheduled">Scheduled</option>
            <option value="sent">Sent</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <span className="text-xs text-text-muted">{total} campaign{total !== 1 ? "s" : ""}</span>
        </div>
        <button className="btn-primary text-sm" onClick={() => setShowCreate(true)}>
          + New Campaign
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : campaigns.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">No campaigns found.</div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">Name</th>
                <th className="text-left p-3 text-text-muted font-medium">Subject</th>
                <th className="text-left p-3 text-text-muted font-medium">Template</th>
                <th className="text-left p-3 text-text-muted font-medium">Status</th>
                <th className="text-left p-3 text-text-muted font-medium">Date</th>
                <th className="text-right p-3 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                  <td className="p-3 text-text-primary">{truncate(c.name, 30)}</td>
                  <td className="p-3 text-text-secondary">{truncate(c.subject, 30)}</td>
                  <td className="p-3 text-text-muted font-mono text-xs">{c.template_id}</td>
                  <td className="p-3">
                    <span className={`badge ${statusBadge(c.status)}`}>{c.status}</span>
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {c.sent_at ? formatRelativeTime(c.sent_at) : c.scheduled_at ? `Sched: ${formatDate(c.scheduled_at)}` : formatRelativeTime(c.created_at)}
                  </td>
                  <td className="p-3 text-right space-x-2">
                    {(c.status === "draft" || c.status === "scheduled") && (
                      <>
                        <button onClick={() => handleSend(c.id)} className="text-accent-green hover:underline text-xs">Send</button>
                        <button onClick={() => handleCancel(c.id)} className="text-accent-pink hover:underline text-xs">Cancel</button>
                      </>
                    )}
                    {(c.status === "sent" || c.status === "sending") && (
                      <button onClick={() => handleStats(c)} className="text-accent-blue hover:underline text-xs">Stats</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination currentPage={page} totalPages={Math.ceil(total / perPage)} onPageChange={setPage} />
      </div>

      {/* Create modal */}
      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="New Campaign" size="md">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">Campaign Name</label>
            <input className="input-glass w-full" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="Spring Sale 2026" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Email Subject</label>
            <input className="input-glass w-full" value={formSubject} onChange={(e) => setFormSubject(e.target.value)} placeholder="Don't miss our spring collection!" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Template ID</label>
            <select className="input-glass w-full" value={formTemplate} onChange={(e) => setFormTemplate(e.target.value)}>
              <option value="welcome">welcome</option>
              <option value="password_reset">password_reset</option>
              <option value="order_confirmation">order_confirmation</option>
              <option value="payment_receipt">payment_receipt</option>
              <option value="subscription_confirmation">subscription_confirmation</option>
              <option value="subscription_cancelled">subscription_cancelled</option>
              <option value="data_export_ready">data_export_ready</option>
              <option value="account_deletion">account_deletion</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Schedule (optional)</label>
            <input type="datetime-local" className="input-glass w-full" value={formScheduled} onChange={(e) => setFormScheduled(e.target.value)} />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary text-sm" onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn-primary text-sm" onClick={handleCreate} disabled={creating}>
              {creating ? "Creating..." : "Create Campaign"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Stats modal */}
      <Modal isOpen={!!statsModal} onClose={() => setStatsModal(null)} title={`Stats: ${statsName}`} size="md">
        {statsModal && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {([
              ["Sent", statsModal.sent, "accent-blue"],
              ["Delivered", statsModal.delivered, "accent-green"],
              ["Opened", statsModal.opened, "accent-purple"],
              ["Clicked", statsModal.clicked, "accent-pink"],
              ["Bounced", statsModal.bounced, "accent-pink"],
              ["Unsubscribed", statsModal.unsubscribed, "accent-pink"],
            ] as [string, number, string][]).map(([label, val, color]) => (
              <div key={label} className="glass rounded-lg p-3 text-center">
                <p className="text-xs text-text-muted mb-1">{label}</p>
                <p className={`text-xl font-bold text-${color}`}>{val}</p>
                {statsModal.sent > 0 && label !== "Sent" && (
                  <p className="text-xs text-text-muted">{((val / statsModal.sent) * 100).toFixed(1)}%</p>
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
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (typeFilter) params.set("email_type", typeFilter);
      if (statusFilter) params.set("status", statusFilter);
      if (userFilter.trim()) params.set("user_id", userFilter.trim());
      const data = await apiFetch<EmailLogList>(`/marketing/admin/email-logs?${params}`);
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load email logs", "error");
    }
    setLoading(false);
  }, [page, typeFilter, statusFilter, userFilter, showToast]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

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
        <select className="input-glass text-sm py-1.5 px-3" value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          <option value="transactional_email">Transactional</option>
          <option value="marketing_email">Marketing</option>
        </select>
        <select className="input-glass text-sm py-1.5 px-3" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
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
          onKeyDown={(e) => { if (e.key === "Enter") { setPage(1); fetchLogs(); } }}
        />
        <span className="text-xs text-text-muted">{total} event{total !== 1 ? "s" : ""}</span>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : logs.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">No email events found.</div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">Time</th>
                <th className="text-left p-3 text-text-muted font-medium">User</th>
                <th className="text-left p-3 text-text-muted font-medium">Type</th>
                <th className="text-left p-3 text-text-muted font-medium">Template</th>
                <th className="text-left p-3 text-text-muted font-medium">Provider</th>
                <th className="text-left p-3 text-text-muted font-medium">Status</th>
                <th className="text-right p-3 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                  <td className="p-3 text-text-muted text-xs">{formatRelativeTime(log.created_at)}</td>
                  <td className="p-3 text-text-secondary font-mono text-xs">{truncate(log.user_id, 8)}</td>
                  <td className="p-3 text-text-secondary text-xs">{log.email_type === "marketing_email" ? "Marketing" : "Transactional"}</td>
                  <td className="p-3 text-text-muted font-mono text-xs">{log.template_id}</td>
                  <td className="p-3 text-text-muted text-xs">{log.provider || "-"}</td>
                  <td className="p-3">
                    <span className={`badge ${statusBadge(log.status)}`}>{log.status}</span>
                    {log.skip_reason && <span className="text-xs text-text-muted ml-1">({log.skip_reason})</span>}
                  </td>
                  <td className="p-3 text-right">
                    {["bounced", "complained", "skipped"].includes(log.status) && (
                      <button onClick={() => handleResend(log.id)} className="text-accent-blue hover:underline text-xs">Resend</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination currentPage={page} totalPages={Math.ceil(total / pageSize)} onPageChange={setPage} />
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
      const data = await apiFetch<SuppressedList>(`/marketing/admin/suppressed?page=${page}&page_size=${pageSize}`);
      setUsers(data.items);
      setTotal(data.total);
    } catch {
      showToast("Failed to load suppressed users", "error");
    }
    setLoading(false);
  }, [page, showToast]);

  useEffect(() => { fetchSuppressed(); }, [fetchSuppressed]);

  return (
    <>
      <p className="text-xs text-text-muted mb-4">{total} suppressed user{total !== 1 ? "s" : ""}</p>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : users.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">No suppressed users. This is a good thing!</div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">Email</th>
                <th className="text-left p-3 text-text-muted font-medium">User ID</th>
                <th className="text-left p-3 text-text-muted font-medium">Suppressed</th>
                <th className="text-left p-3 text-text-muted font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors">
                  <td className="p-3 text-text-primary">{u.email}</td>
                  <td className="p-3 text-text-muted font-mono text-xs">{truncate(u.user_id, 8)}</td>
                  <td className="p-3 text-text-muted text-xs">{formatRelativeTime(u.suppressed_at)}</td>
                  <td className="p-3"><span className="badge badge-pink">{u.suppression_reason || "unknown"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Pagination currentPage={page} totalPages={Math.ceil(total / pageSize)} onPageChange={setPage} />
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
      const data = await apiFetch<CommunicationType[]>(`/marketing/admin/communication-types?include_disabled=${showDisabled}`);
      setTypes(data);
    } catch {
      showToast("Failed to load communication types", "error");
    }
    setLoading(false);
  }, [showDisabled, showToast]);

  useEffect(() => { fetchTypes(); }, [fetchTypes]);

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
          body: JSON.stringify({ name: formName, description: formDesc || null, enabled: formEnabled }),
        });
        showToast("Updated", "success");
      } else {
        await apiFetch("/marketing/admin/communication-types", {
          method: "POST",
          body: JSON.stringify({ name: formName, description: formDesc || null, enabled: formEnabled }),
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
          <input type="checkbox" checked={showDisabled} onChange={(e) => setShowDisabled(e.target.checked)} className="rounded" />
          Show disabled
        </label>
        <button className="btn-primary text-sm" onClick={openCreate}>+ New Type</button>
      </div>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : types.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center text-text-muted">No communication types found.</div>
      ) : (
        <div className="grid gap-3">
          {types.map((t) => (
            <div key={t.id} className="glass rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-text-primary font-medium">{t.name}</span>
                  <span className={`badge ${t.enabled ? "badge-green" : "badge-pink"}`}>{t.enabled ? "enabled" : "disabled"}</span>
                </div>
                {t.description && <p className="text-xs text-text-muted mt-1">{t.description}</p>}
              </div>
              <button onClick={() => openEdit(t)} className="text-accent-blue hover:underline text-sm">Edit</button>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit modal */}
      <Modal isOpen={showCreate || !!editing} onClose={() => { setShowCreate(false); setEditing(null); }} title={editing ? "Edit Communication Type" : "New Communication Type"} size="sm">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">Name</label>
            <input className="input-glass w-full" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="weekly_digest" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Description</label>
            <textarea className="input-glass w-full h-20 resize-none" value={formDesc} onChange={(e) => setFormDesc(e.target.value)} placeholder="What this type is for..." />
          </div>
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
            <input type="checkbox" checked={formEnabled} onChange={(e) => setFormEnabled(e.target.checked)} className="rounded" />
            Enabled
          </label>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary text-sm" onClick={() => { setShowCreate(false); setEditing(null); }}>Cancel</button>
            <button className="btn-primary text-sm" onClick={handleSave} disabled={saving}>
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
        const data = await apiFetch<CommunicationType[]>("/marketing/admin/communication-types");
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
      const params = selectedType ? `?communication_type_id=${selectedType}` : "";
      const data = await apiFetch<AudienceResponse>(`/marketing/admin/audience${params}`);
      setAudience(data);
    } catch {
      showToast("Failed to load audience", "error");
    }
    setLoading(false);
  }, [selectedType, showToast]);

  useEffect(() => { fetchAudience(); }, [fetchAudience]);

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        {typesLoading ? (
          <LoadingSpinner size="sm" />
        ) : (
          <select className="input-glass text-sm py-1.5 px-3" value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
            <option value="">All eligible users</option>
            {types.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : audience ? (
        <>
          <div className="glass rounded-xl p-4 mb-4 text-center">
            <span className="text-2xl font-bold text-accent-green">{audience.count}</span>
            <span className="text-text-muted ml-2">eligible recipient{audience.count !== 1 ? "s" : ""}</span>
          </div>

          {audience.recipients.length > 0 && (
            <div className="glass rounded-xl overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-glass-bg">
                  <tr className="border-b border-glass-border">
                    <th className="text-left p-3 text-text-muted font-medium">Email</th>
                    <th className="text-left p-3 text-text-muted font-medium">User ID</th>
                  </tr>
                </thead>
                <tbody>
                  {audience.recipients.map((r) => (
                    <tr key={r.user_id} className="border-b border-glass-border/50">
                      <td className="p-3 text-text-primary">{r.email}</td>
                      <td className="p-3 text-text-muted font-mono text-xs">{truncate(r.user_id, 8)}</td>
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
