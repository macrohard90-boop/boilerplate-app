"use client";

import { useCallback, useEffect, useState } from "react";
import { getFlowCanvasApi } from "./FlowCanvas";

interface FlowConfigPanelProps {
  stepId: string | null;
  stepType: string;
  config: Record<string, unknown>;
  onClose: () => void;
}

export default function FlowConfigPanel({
  stepId,
  stepType,
  config: initialConfig,
  onClose,
}: FlowConfigPanelProps) {
  const [config, setConfig] = useState<Record<string, unknown>>(initialConfig);
  const [saving, setSaving] = useState(false);

  // Reset config when step changes
  useEffect(() => {
    setConfig(initialConfig);
  }, [initialConfig, stepId]);

  const updateField = useCallback((key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!stepId) return;
    setSaving(true);
    const api = getFlowCanvasApi();
    if (api) {
      await api.updateNodeConfig(stepId, config);
    }
    setSaving(false);
  }, [stepId, config]);

  if (!stepId && stepType !== "trigger") return null;

  return (
    <div className="w-[300px] h-full border-l border-glass-border bg-base-50 overflow-y-auto animate-slide-in-right">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-glass-border">
        <div>
          <h3 className="text-sm font-semibold text-text-primary capitalize">
            {stepType} Config
          </h3>
          {stepId && (
            <p className="text-[10px] text-text-muted font-mono mt-0.5">
              {stepId.slice(0, 8)}...
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Config fields */}
      <div className="p-4 space-y-4">
        {/* Label (all types) */}
        <div>
          <label className="text-xs text-text-muted block mb-1">Label</label>
          <input
            className="input-glass w-full text-sm"
            value={(config.label as string) || ""}
            onChange={(e) => updateField("label", e.target.value)}
            placeholder="Step label..."
          />
        </div>

        {/* Type-specific fields */}
        {stepType === "trigger" && <TriggerFields />}
        {stepType === "send" && <SendFields config={config} onUpdate={updateField} />}
        {stepType === "wait" && <WaitFields config={config} onUpdate={updateField} />}
        {stepType === "branch" && <BranchFields config={config} onUpdate={updateField} />}
        {stepType === "split" && <SplitFields config={config} onUpdate={updateField} />}
        {stepType === "update" && <UpdateFields config={config} onUpdate={updateField} />}
        {stepType === "webhook" && <WebhookFields config={config} onUpdate={updateField} />}

        {/* Save button */}
        {stepId && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary w-full text-sm py-2"
          >
            {saving ? "Saving..." : "Save Config"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Trigger (read-only info) ──────────────────────────────

function TriggerFields() {
  return (
    <p className="text-xs text-text-muted">
      The trigger is configured at the flow level. Use the toolbar to change
      the trigger event.
    </p>
  );
}

// ── Send ──────────────────────────────────────────────────

function SendFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">Channel</label>
        <select
          className="input-glass w-full text-sm"
          value={(config.channel as string) || "email"}
          onChange={(e) => onUpdate("channel", e.target.value)}
        >
          <option value="email">Email</option>
          <option value="sms">SMS</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="push">Push</option>
        </select>
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">Template ID</label>
        <input
          className="input-glass w-full text-sm font-mono"
          value={(config.template_id as string) || ""}
          onChange={(e) => onUpdate("template_id", e.target.value)}
          placeholder="welcome_email"
        />
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">Subject Override</label>
        <input
          className="input-glass w-full text-sm"
          value={(config.subject as string) || ""}
          onChange={(e) => onUpdate("subject", e.target.value)}
          placeholder="Optional subject..."
        />
      </div>
    </>
  );
}

// ── Wait ──────────────────────────────────────────────────

function WaitFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  const unit = (config.duration_unit as string) || "minutes";
  const amount = (config.duration_amount as number) || 0;

  // Convert to seconds for storage
  function handleDurationChange(newAmount: number, newUnit: string) {
    const multiplier =
      newUnit === "days" ? 86400 : newUnit === "hours" ? 3600 : 60;
    onUpdate("duration_amount", newAmount);
    onUpdate("duration_unit", newUnit);
    onUpdate("duration_seconds", newAmount * multiplier);
  }

  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">Wait Type</label>
        <select
          className="input-glass w-full text-sm"
          value={(config.wait_type as string) || "duration"}
          onChange={(e) => onUpdate("wait_type", e.target.value)}
        >
          <option value="duration">Fixed duration</option>
          <option value="event">Wait for event</option>
          <option value="date">Until date</option>
        </select>
      </div>

      {((config.wait_type as string) || "duration") === "duration" && (
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-xs text-text-muted block mb-1">Amount</label>
            <input
              type="number"
              min={0}
              className="input-glass w-full text-sm"
              value={amount}
              onChange={(e) =>
                handleDurationChange(parseInt(e.target.value) || 0, unit)
              }
            />
          </div>
          <div className="flex-1">
            <label className="text-xs text-text-muted block mb-1">Unit</label>
            <select
              className="input-glass w-full text-sm"
              value={unit}
              onChange={(e) => handleDurationChange(amount, e.target.value)}
            >
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
              <option value="days">Days</option>
            </select>
          </div>
        </div>
      )}

      {(config.wait_type as string) === "event" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Event Name</label>
          <input
            className="input-glass w-full text-sm font-mono"
            value={(config.wait_event as string) || ""}
            onChange={(e) => onUpdate("wait_event", e.target.value)}
            placeholder="email_opened"
          />
        </div>
      )}

      {(config.wait_type as string) === "date" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Date</label>
          <input
            type="datetime-local"
            className="input-glass w-full text-sm"
            value={(config.wait_date as string) || ""}
            onChange={(e) => onUpdate("wait_date", e.target.value)}
          />
        </div>
      )}
    </>
  );
}

// ── Branch ────────────────────────────────────────────────

function BranchFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">Condition</label>
        <select
          className="input-glass w-full text-sm"
          value={(config.condition_type as string) || "email_opened"}
          onChange={(e) => onUpdate("condition_type", e.target.value)}
        >
          <option value="email_opened">Email opened</option>
          <option value="email_clicked">Email clicked</option>
          <option value="has_purchased">Has purchased</option>
          <option value="has_tag">Has tag</option>
          <option value="score_above">Score above</option>
          <option value="custom">Custom expression</option>
        </select>
      </div>

      {(config.condition_type as string) === "has_tag" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Tag</label>
          <input
            className="input-glass w-full text-sm"
            value={(config.tag as string) || ""}
            onChange={(e) => onUpdate("tag", e.target.value)}
            placeholder="vip"
          />
        </div>
      )}

      {(config.condition_type as string) === "score_above" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Threshold</label>
          <input
            type="number"
            className="input-glass w-full text-sm"
            value={(config.threshold as number) || 0}
            onChange={(e) => onUpdate("threshold", parseInt(e.target.value) || 0)}
          />
        </div>
      )}

      {(config.condition_type as string) === "custom" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Expression</label>
          <textarea
            className="input-glass w-full text-sm h-20 font-mono resize-none"
            value={(config.expression as string) || ""}
            onChange={(e) => onUpdate("expression", e.target.value)}
            placeholder='e.g. user.total_spent > 100'
          />
        </div>
      )}

      <div>
        <label className="text-xs text-text-muted block mb-1">
          Lookback Window
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            className="input-glass w-full text-sm"
            value={(config.lookback_hours as number) || 24}
            onChange={(e) => onUpdate("lookback_hours", parseInt(e.target.value) || 24)}
          />
          <span className="text-xs text-text-muted whitespace-nowrap">hours</span>
        </div>
      </div>
    </>
  );
}

// ── Split ─────────────────────────────────────────────────

function SplitFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  const weightA = (config.weight_a as number) ?? 50;
  const weightB = 100 - weightA;

  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">
          Variant A Weight: {weightA}%
        </label>
        <input
          type="range"
          min={5}
          max={95}
          step={5}
          className="w-full accent-accent-purple"
          value={weightA}
          onChange={(e) => onUpdate("weight_a", parseInt(e.target.value))}
        />
        <div className="flex justify-between text-[10px] text-text-muted mt-1">
          <span>A: {weightA}%</span>
          <span>B: {weightB}%</span>
        </div>
      </div>
    </>
  );
}

// ── Update ────────────────────────────────────────────────

function UpdateFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">Action</label>
        <select
          className="input-glass w-full text-sm"
          value={(config.action as string) || "add_tag"}
          onChange={(e) => onUpdate("action", e.target.value)}
        >
          <option value="add_tag">Add tag</option>
          <option value="remove_tag">Remove tag</option>
          <option value="set_attribute">Set attribute</option>
          <option value="adjust_score">Adjust score</option>
        </select>
      </div>

      {((config.action as string) === "add_tag" ||
        (config.action as string) === "remove_tag" ||
        !(config.action as string)) && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Tag Name</label>
          <input
            className="input-glass w-full text-sm"
            value={(config.tag_name as string) || ""}
            onChange={(e) => onUpdate("tag_name", e.target.value)}
            placeholder="vip"
          />
        </div>
      )}

      {(config.action as string) === "set_attribute" && (
        <>
          <div>
            <label className="text-xs text-text-muted block mb-1">Attribute</label>
            <input
              className="input-glass w-full text-sm"
              value={(config.attribute as string) || ""}
              onChange={(e) => onUpdate("attribute", e.target.value)}
              placeholder="lifecycle_stage"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Value</label>
            <input
              className="input-glass w-full text-sm"
              value={(config.attribute_value as string) || ""}
              onChange={(e) => onUpdate("attribute_value", e.target.value)}
              placeholder="active"
            />
          </div>
        </>
      )}

      {(config.action as string) === "adjust_score" && (
        <div>
          <label className="text-xs text-text-muted block mb-1">
            Score Adjustment
          </label>
          <input
            type="number"
            className="input-glass w-full text-sm"
            value={(config.score_delta as number) || 0}
            onChange={(e) => onUpdate("score_delta", parseInt(e.target.value) || 0)}
          />
          <p className="text-[10px] text-text-muted mt-1">
            Positive to add, negative to subtract
          </p>
        </div>
      )}
    </>
  );
}

// ── Webhook ───────────────────────────────────────────────

function WebhookFields({
  config,
  onUpdate,
}: {
  config: Record<string, unknown>;
  onUpdate: (k: string, v: unknown) => void;
}) {
  return (
    <>
      <div>
        <label className="text-xs text-text-muted block mb-1">URL</label>
        <input
          className="input-glass w-full text-sm font-mono"
          value={(config.url as string) || ""}
          onChange={(e) => onUpdate("url", e.target.value)}
          placeholder="https://example.com/webhook"
        />
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">Method</label>
        <select
          className="input-glass w-full text-sm"
          value={(config.method as string) || "POST"}
          onChange={(e) => onUpdate("method", e.target.value)}
        >
          <option value="POST">POST</option>
          <option value="PUT">PUT</option>
          <option value="GET">GET</option>
        </select>
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">
          Headers (JSON)
        </label>
        <textarea
          className="input-glass w-full text-sm h-16 font-mono resize-none"
          value={(config.headers_json as string) || "{}"}
          onChange={(e) => onUpdate("headers_json", e.target.value)}
          placeholder='{"Authorization": "Bearer ..."}'
        />
      </div>
    </>
  );
}
