"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";
import { useConfig } from "../../../lib/config-context";
import { useToast } from "../../../components/Toast";
import LoadingSpinner from "../../../components/LoadingSpinner";
import { formatRelativeTime } from "../../../lib/format";

// ── Interfaces ──────────────────────────────────────────

interface MessageLogItem {
  id: string;
  user_id: string | null;
  channel: string;
  provider: string;
  provider_message_id: string | null;
  to_number: string;
  template_id: string | null;
  body_preview: string | null;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string | null;
}

interface AutomationRule {
  id: string;
  event_name: string;
  channel: string;
  template_id: string;
  delay_seconds: number;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface GuardrailConfig {
  channel: string;
  freq_cap_per_day: number | null;
  freq_cap_per_week: number | null;
  freq_cap_per_month: number | null;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  quiet_hours_timezone: string | null;
  sunset_inactivity_days: number | null;
  enabled: boolean;
}

interface PressureSummary {
  channel: string;
  message_type: string;
  total: number;
  today: number;
  week: number;
}

// ── Page Component ──────────────────────────────────────

export default function NotificationsAdminPage() {
  const { enable_sms, enable_whatsapp } = useConfig();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<
    "test" | "log" | "rules" | "guardrails" | "pressure"
  >("test");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Notifications</h1>

      {/* Tab nav */}
      <div className="flex gap-1 mb-6 glass rounded-lg p-1 w-fit">
        {(
          [
            { key: "test", label: "Test Send" },
            { key: "log", label: "Message Log" },
            { key: "rules", label: "Automation Rules" },
            { key: "guardrails", label: "Guardrails" },
            { key: "pressure", label: "Pressure" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm rounded-md transition-all ${
              activeTab === tab.key
                ? "bg-accent-pink/20 text-accent-pink font-medium"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "test" && (
        <TestSendPanel
          enableSms={enable_sms}
          enableWhatsApp={enable_whatsapp}
          showToast={showToast}
        />
      )}
      {activeTab === "log" && <MessageLogPanel />}
      {activeTab === "rules" && <AutomationRulesPanel showToast={showToast} />}
      {activeTab === "guardrails" && <GuardrailsPanel showToast={showToast} />}
      {activeTab === "pressure" && <PressurePanel />}
    </div>
  );
}

// ── Test Send Panel ─────────────────────────────────────

function TestSendPanel({
  enableSms,
  enableWhatsApp,
  showToast,
}: {
  enableSms: boolean;
  enableWhatsApp: boolean;
  showToast: (msg: string, type?: "success" | "error" | "info") => void;
}) {
  const [smsPhone, setSmsPhone] = useState("");
  const [smsContent, setSmsContent] = useState("");
  const [smsSending, setSmsSending] = useState(false);

  const [waPhone, setWaPhone] = useState("");
  const [waText, setWaText] = useState("");
  const [waSending, setWaSending] = useState(false);

  const sendTestSms = async () => {
    if (!smsPhone || !smsContent) return;
    setSmsSending(true);
    try {
      const res = await apiFetch<{ status: string; error?: string }>(
        "/notifications/admin/test-sms",
        {
          method: "POST",
          body: JSON.stringify({
            to_number: smsPhone,
            content: smsContent,
          }),
        },
      );
      if (res.status === "sent") {
        showToast("SMS sent successfully", "success");
      } else {
        showToast(res.error || "SMS send failed", "error");
      }
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "message" in e
          ? String((e as { message: string }).message)
          : "Failed to send SMS";
      showToast(msg, "error");
    } finally {
      setSmsSending(false);
    }
  };

  const sendTestWhatsApp = async () => {
    if (!waPhone || !waText) return;
    setWaSending(true);
    try {
      const res = await apiFetch<{ status: string; error?: string }>(
        "/notifications/admin/test-whatsapp",
        {
          method: "POST",
          body: JSON.stringify({
            to_number: waPhone,
            text_content: waText,
          }),
        },
      );
      if (res.status === "sent") {
        showToast("WhatsApp message sent successfully", "success");
      } else {
        showToast(res.error || "WhatsApp send failed", "error");
      }
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "message" in e
          ? String((e as { message: string }).message)
          : "Failed to send WhatsApp";
      showToast(msg, "error");
    } finally {
      setWaSending(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* SMS Test */}
      {enableSms && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Test SMS</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Phone Number (E.164)
              </label>
              <input
                type="tel"
                value={smsPhone}
                onChange={(e) => setSmsPhone(e.target.value)}
                placeholder="+1234567890"
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Message
              </label>
              <textarea
                value={smsContent}
                onChange={(e) => setSmsContent(e.target.value)}
                placeholder="Your test SMS message..."
                rows={3}
                className="input w-full"
              />
            </div>
            <button
              onClick={sendTestSms}
              disabled={smsSending || !smsPhone || !smsContent}
              className="btn btn-primary w-full"
            >
              {smsSending ? "Sending..." : "Send Test SMS"}
            </button>
          </div>
        </div>
      )}

      {/* WhatsApp Test */}
      {enableWhatsApp && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Test WhatsApp</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Phone Number (E.164)
              </label>
              <input
                type="tel"
                value={waPhone}
                onChange={(e) => setWaPhone(e.target.value)}
                placeholder="+1234567890"
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Text Message
              </label>
              <textarea
                value={waText}
                onChange={(e) => setWaText(e.target.value)}
                placeholder="Your test WhatsApp message..."
                rows={3}
                className="input w-full"
              />
            </div>
            <button
              onClick={sendTestWhatsApp}
              disabled={waSending || !waPhone || !waText}
              className="btn btn-primary w-full"
            >
              {waSending ? "Sending..." : "Send Test WhatsApp"}
            </button>
          </div>
        </div>
      )}

      {!enableSms && !enableWhatsApp && (
        <div className="glass rounded-xl p-6 col-span-full text-center text-text-secondary">
          Enable SMS or WhatsApp in your .env to use test sends.
        </div>
      )}
    </div>
  );
}

// ── Message Log Panel ───────────────────────────────────

function MessageLogPanel() {
  const [items, setItems] = useState<MessageLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [page, setPage] = useState(0);
  const perPage = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(perPage),
        offset: String(page * perPage),
      });
      if (filter) params.set("channel", filter);

      const res = await apiFetch<{ items: MessageLogItem[]; total: number }>(
        `/notifications/admin/message-log?${params}`,
      );
      setItems(res.items);
      setTotal(res.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    load();
  }, [load]);

  const channelBadge = (ch: string) => {
    if (ch === "sms")
      return <span className="badge badge-blue text-xs">SMS</span>;
    if (ch === "whatsapp")
      return <span className="badge badge-green text-xs">WhatsApp</span>;
    return <span className="badge badge-purple text-xs">{ch}</span>;
  };

  const statusBadge = (st: string) => {
    const cls =
      st === "sent" || st === "delivered"
        ? "badge-green"
        : st === "failed"
          ? "badge-pink"
          : "badge-purple";
    return <span className={`badge ${cls} text-xs`}>{st}</span>;
  };

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-glass-border flex items-center gap-3">
        <h3 className="text-lg font-semibold">Message Log</h3>
        <div className="flex gap-1 ml-auto">
          {["", "sms", "whatsapp"].map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setPage(0);
              }}
              className={`px-3 py-1 text-xs rounded-md transition-all ${
                filter === f
                  ? "bg-accent-pink/20 text-accent-pink"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {f === "" ? "All" : f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="p-8 text-center text-text-secondary">
          No messages yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-glass-border">
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">To</th>
                <th className="px-4 py-3">Preview</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Sent</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr
                  key={m.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover"
                >
                  <td className="px-4 py-3">{channelBadge(m.channel)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.to_number}</td>
                  <td className="px-4 py-3 max-w-[200px] truncate text-text-secondary">
                    {m.body_preview || m.template_id || "-"}
                  </td>
                  <td className="px-4 py-3">
                    {statusBadge(m.status)}
                    {m.error_message && (
                      <span
                        className="ml-1 text-xs text-red-400"
                        title={m.error_message}
                      >
                        !
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-secondary text-xs">
                    {m.provider}
                  </td>
                  <td className="px-4 py-3 text-text-secondary text-xs">
                    {m.sent_at ? formatRelativeTime(m.sent_at) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > perPage && (
        <div className="p-4 flex justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="btn btn-sm"
          >
            Prev
          </button>
          <span className="text-sm text-text-secondary px-2 py-1">
            Page {page + 1} of {Math.ceil(total / perPage)}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={(page + 1) * perPage >= total}
            className="btn btn-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ── Automation Rules Panel ──────────────────────────────

function AutomationRulesPanel({
  showToast,
}: {
  showToast: (msg: string, type?: "success" | "error" | "info") => void;
}) {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<AutomationRule[]>(
        "/notifications/admin/automation-rules",
      );
      setRules(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleRule = async (rule: AutomationRule) => {
    try {
      await apiFetch(`/notifications/admin/automation-rules/${rule.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, enabled: !r.enabled } : r)),
      );
      showToast(
        `Rule ${!rule.enabled ? "enabled" : "disabled"}: ${rule.event_name} / ${rule.channel}`,
        "success",
      );
    } catch {
      showToast("Failed to update rule", "error");
    }
  };

  const channelBadge = (ch: string) => {
    const cls =
      ch === "sms"
        ? "badge-blue"
        : ch === "whatsapp"
          ? "badge-green"
          : "badge-purple";
    return <span className={`badge ${cls} text-xs`}>{ch}</span>;
  };

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-glass-border">
        <h3 className="text-lg font-semibold">Automation Rules</h3>
        <p className="text-sm text-text-secondary mt-1">
          When an event fires, enabled rules dispatch messages on the configured
          channel.
        </p>
      </div>

      {rules.length === 0 ? (
        <div className="p-8 text-center text-text-secondary">
          No automation rules configured.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-glass-border">
                <th className="px-4 py-3">Event</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Template</th>
                <th className="px-4 py-3">Delay</th>
                <th className="px-4 py-3">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr
                  key={rule.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover"
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    {rule.event_name}
                  </td>
                  <td className="px-4 py-3">{channelBadge(rule.channel)}</td>
                  <td className="px-4 py-3 text-text-secondary">
                    {rule.template_id}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {rule.delay_seconds > 0
                      ? `${rule.delay_seconds}s`
                      : "Instant"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleRule(rule)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        rule.enabled ? "bg-accent-pink" : "bg-glass-border"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          rule.enabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Guardrails Panel ────────────────────────────────────

function GuardrailsPanel({
  showToast,
}: {
  showToast: (msg: string, type?: "success" | "error" | "info") => void;
}) {
  const [configs, setConfigs] = useState<GuardrailConfig[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<GuardrailConfig[]>(
        "/notifications/admin/guardrails",
      );
      setConfigs(res);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;

  if (configs.length === 0) {
    return (
      <div className="glass rounded-xl p-8 text-center text-text-secondary">
        No guardrails configuration found. Add channel configs to
        marketing.messaging_config.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {configs.map((cfg) => (
        <GuardrailCard
          key={cfg.channel}
          config={cfg}
          showToast={showToast}
          onUpdate={load}
        />
      ))}
    </div>
  );
}

function GuardrailCard({
  config,
  showToast,
  onUpdate,
}: {
  config: GuardrailConfig;
  showToast: (msg: string, type?: "success" | "error" | "info") => void;
  onUpdate: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [dayLimit, setDayLimit] = useState(config.freq_cap_per_day ?? 0);
  const [weekLimit, setWeekLimit] = useState(config.freq_cap_per_week ?? 0);
  const [monthLimit, setMonthLimit] = useState(config.freq_cap_per_month ?? 0);
  const [sunsetDays, setSunsetDays] = useState(
    config.sunset_inactivity_days ?? 0,
  );
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await apiFetch(`/notifications/admin/guardrails/${config.channel}`, {
        method: "PUT",
        body: JSON.stringify({
          freq_cap_marketing_per_day: dayLimit || null,
          freq_cap_marketing_per_week: weekLimit || null,
          freq_cap_marketing_per_month: monthLimit || null,
          sunset_inactivity_days: sunsetDays || null,
        }),
      });
      showToast(`${config.channel} guardrails updated`, "success");
      setEditing(false);
      onUpdate();
    } catch {
      showToast("Failed to save guardrails", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="glass rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold capitalize">{config.channel}</h3>
        <span
          className={`badge text-xs ${config.enabled ? "badge-green" : "badge-pink"}`}
        >
          {config.enabled ? "Enabled" : "Disabled"}
        </span>
      </div>

      {!editing ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-text-secondary">Daily cap</span>
            <span>{config.freq_cap_per_day ?? "None"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Weekly cap</span>
            <span>{config.freq_cap_per_week ?? "None"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Monthly cap</span>
            <span>{config.freq_cap_per_month ?? "None"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Quiet hours</span>
            <span>
              {config.quiet_hours_start && config.quiet_hours_end
                ? `${config.quiet_hours_start} - ${config.quiet_hours_end}`
                : "Off"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-secondary">Sunset</span>
            <span>
              {config.sunset_inactivity_days
                ? `${config.sunset_inactivity_days} days`
                : "Off"}
            </span>
          </div>
          <button
            onClick={() => setEditing(true)}
            className="btn btn-sm w-full mt-4"
          >
            Edit
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-secondary mb-1">
              Daily cap
            </label>
            <input
              type="number"
              value={dayLimit}
              onChange={(e) => setDayLimit(Number(e.target.value))}
              className="input w-full"
              min={0}
            />
          </div>
          <div>
            <label className="block text-xs text-text-secondary mb-1">
              Weekly cap
            </label>
            <input
              type="number"
              value={weekLimit}
              onChange={(e) => setWeekLimit(Number(e.target.value))}
              className="input w-full"
              min={0}
            />
          </div>
          <div>
            <label className="block text-xs text-text-secondary mb-1">
              Monthly cap
            </label>
            <input
              type="number"
              value={monthLimit}
              onChange={(e) => setMonthLimit(Number(e.target.value))}
              className="input w-full"
              min={0}
            />
          </div>
          <div>
            <label className="block text-xs text-text-secondary mb-1">
              Sunset (days inactive)
            </label>
            <input
              type="number"
              value={sunsetDays}
              onChange={(e) => setSunsetDays(Number(e.target.value))}
              className="input w-full"
              min={0}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="btn btn-primary btn-sm flex-1"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="btn btn-sm flex-1"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Pressure Panel ──────────────────────────────────────

function PressurePanel() {
  const [summary, setSummary] = useState<PressureSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch<{
          summary: PressureSummary[];
        }>("/notifications/admin/message-pressure?days=30");
        setSummary(res.summary);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;

  if (summary.length === 0) {
    return (
      <div className="glass rounded-xl p-8 text-center text-text-secondary">
        No message pressure data yet.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="glass rounded-xl overflow-hidden">
        <div className="p-4 border-b border-glass-border">
          <h3 className="text-lg font-semibold">Message Pressure (30 days)</h3>
          <p className="text-sm text-text-secondary mt-1">
            Total sends per channel and type.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-text-secondary border-b border-glass-border">
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-right">Today</th>
                <th className="px-4 py-3 text-right">This Week</th>
                <th className="px-4 py-3 text-right">30-Day Total</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((s, i) => (
                <tr
                  key={i}
                  className="border-b border-glass-border/50 hover:bg-glass-hover"
                >
                  <td className="px-4 py-3 capitalize">{s.channel}</td>
                  <td className="px-4 py-3 text-text-secondary">
                    {s.message_type}
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{s.today}</td>
                  <td className="px-4 py-3 text-right font-mono">{s.week}</td>
                  <td className="px-4 py-3 text-right font-mono">{s.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
