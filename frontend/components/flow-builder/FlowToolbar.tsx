"use client";

import { useCallback, useRef, useState } from "react";
import type { AutomationFlow, FlowStep } from "./useFlowApi";
import { updateFlow, activateFlow, pauseFlow } from "./useFlowApi";
import { getFlowCanvasApi } from "./FlowCanvas";
import { useToast } from "../Toast";

const STEP_TYPES: {
  type: FlowStep["step_type"];
  label: string;
  icon: string;
}[] = [
  {
    type: "send",
    label: "Send",
    icon: "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
  },
  {
    type: "wait",
    label: "Wait",
    icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    type: "branch",
    label: "Branch",
    icon: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
  },
  {
    type: "split",
    label: "A/B Split",
    icon: "M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z",
  },
  {
    type: "update",
    label: "Update",
    icon: "M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z",
  },
  {
    type: "webhook",
    label: "Webhook",
    icon: "M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14",
  },
];

interface FlowToolbarProps {
  flow: AutomationFlow | null;
  dirty: boolean;
  onBack: () => void;
  onStatsToggle: () => void;
  showStats: boolean;
}

export default function FlowToolbar({
  flow,
  dirty,
  onBack,
  onStatsToggle,
  showStats,
}: FlowToolbarProps) {
  const { showToast } = useToast();
  const [addOpen, setAddOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState(flow?.name || "");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(document.activeElement)
      ) {
        setAddOpen(false);
      }
    }, 150);
  }, []);

  const handleAddStep = useCallback(async (stepType: FlowStep["step_type"]) => {
    setAddOpen(false);
    const api = getFlowCanvasApi();
    if (api) {
      await api.addNewStep(stepType);
    }
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    const api = getFlowCanvasApi();
    if (api) {
      await api.saveLayout();
      showToast("Layout saved", "success");
    }
    setSaving(false);
  }, [showToast]);

  const handleActivate = useCallback(async () => {
    if (!flow) return;
    setActivating(true);
    try {
      if (flow.status === "active") {
        await pauseFlow(flow.id);
        showToast("Flow paused", "success");
      } else {
        await activateFlow(flow.id);
        showToast("Flow activated", "success");
      }
      // Reload flow to get updated status
      const api = getFlowCanvasApi();
      if (api) await api.reload();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Action failed";
      showToast(msg, "error");
    }
    setActivating(false);
  }, [flow, showToast]);

  const handleNameSave = useCallback(async () => {
    if (!flow || !nameValue.trim()) return;
    setEditingName(false);
    if (nameValue !== flow.name) {
      try {
        await updateFlow(flow.id, { name: nameValue });
        showToast("Name updated", "success");
        const api = getFlowCanvasApi();
        if (api) await api.reload();
      } catch {
        showToast("Failed to update name", "error");
      }
    }
  }, [flow, nameValue, showToast]);

  const statusColor =
    flow?.status === "active"
      ? "badge-green"
      : flow?.status === "paused"
        ? "badge-purple"
        : flow?.status === "archived"
          ? "badge-pink"
          : "badge-blue";

  return (
    <div className="flex items-center justify-between px-4 py-2.5 border-b border-glass-border bg-base-50">
      {/* Left: back + name + status */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onBack}
          className="text-text-muted hover:text-text-primary transition-colors shrink-0"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>

        {editingName ? (
          <input
            className="input-glass text-sm py-1 px-2 min-w-[200px]"
            value={nameValue}
            onChange={(e) => setNameValue(e.target.value)}
            onBlur={handleNameSave}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleNameSave();
              if (e.key === "Escape") setEditingName(false);
            }}
            autoFocus
          />
        ) : (
          <button
            onClick={() => {
              setNameValue(flow?.name || "");
              setEditingName(true);
            }}
            className="text-text-primary font-medium text-sm truncate max-w-[200px] hover:text-accent-blue transition-colors"
            title="Click to edit name"
          >
            {flow?.name || "Untitled Flow"}
          </button>
        )}

        {flow && (
          <span className={`badge text-[10px] ${statusColor}`}>
            {flow.status}
          </span>
        )}

        {dirty && <span className="text-[10px] text-accent-pink">unsaved</span>}
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-2">
        {/* Stats toggle */}
        <button
          onClick={onStatsToggle}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
            showStats
              ? "border-accent-purple/50 text-accent-purple bg-accent-purple/10"
              : "border-glass-border text-text-muted hover:text-text-secondary hover:border-text-muted"
          }`}
        >
          Stats
        </button>

        {/* Add step dropdown */}
        <div className="relative" ref={dropdownRef} onBlur={handleBlur}>
          <button
            onClick={() => setAddOpen(!addOpen)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-glass-border text-text-secondary hover:border-accent-green hover:text-accent-green transition-colors"
          >
            + Add Step
          </button>
          {addOpen && (
            <div className="absolute right-0 top-full mt-1 w-44 rounded-lg border border-glass-border bg-base-100 shadow-xl z-50 py-1">
              {STEP_TYPES.map((st) => (
                <button
                  key={st.type}
                  onClick={() => handleAddStep(st.type)}
                  className="flex items-center gap-2 w-full px-3 py-2 text-xs text-text-secondary hover:bg-glass-hover hover:text-text-primary transition-colors"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d={st.icon}
                    />
                  </svg>
                  {st.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Save layout */}
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-glass-border text-text-secondary hover:border-accent-blue hover:text-accent-blue transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save Layout"}
        </button>

        {/* Activate / Pause */}
        {flow && flow.status !== "archived" && (
          <button
            onClick={handleActivate}
            disabled={activating}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              flow.status === "active"
                ? "bg-accent-pink/20 text-accent-pink border border-accent-pink/30 hover:bg-accent-pink/30"
                : "bg-accent-green/20 text-accent-green border border-accent-green/30 hover:bg-accent-green/30"
            }`}
          >
            {activating
              ? "..."
              : flow.status === "active"
                ? "Pause"
                : "Activate"}
          </button>
        )}
      </div>
    </div>
  );
}
