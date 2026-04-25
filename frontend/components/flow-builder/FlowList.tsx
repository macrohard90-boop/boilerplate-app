"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "../Toast";
import LoadingSpinner from "../LoadingSpinner";
import Modal from "../Modal";
import { formatRelativeTime } from "../../lib/format";
import type { AutomationFlow } from "./useFlowApi";
import {
  listFlows,
  createFlow,
  deleteFlow,
  activateFlow,
  pauseFlow,
  archiveFlow,
} from "./useFlowApi";

const TRIGGER_EVENTS = [
  { value: "user_signup", label: "User Signup" },
  { value: "purchase_completed", label: "Purchase Completed" },
  { value: "cart_abandoned", label: "Cart Abandoned" },
  { value: "email_opened", label: "Email Opened" },
  { value: "tag_added", label: "Tag Added" },
  { value: "score_threshold", label: "Score Threshold" },
  { value: "manual", label: "Manual Trigger" },
  { value: "custom", label: "Custom Event" },
];

interface FlowListProps {
  onOpenFlow: (flowId: string) => void;
}

export default function FlowList({ onOpenFlow }: FlowListProps) {
  const { showToast } = useToast();
  const [flows, setFlows] = useState<AutomationFlow[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Create form
  const [formName, setFormName] = useState("");
  const [formTrigger, setFormTrigger] = useState("user_signup");
  const [formDesc, setFormDesc] = useState("");
  const [formGoal, setFormGoal] = useState("");

  const fetchFlows = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listFlows(statusFilter || undefined);
      setFlows(data);
    } catch {
      showToast("Failed to load flows", "error");
    }
    setLoading(false);
  }, [statusFilter, showToast]);

  useEffect(() => {
    fetchFlows();
  }, [fetchFlows]);

  async function handleCreate() {
    if (!formName.trim()) {
      showToast("Name is required", "error");
      return;
    }
    setCreating(true);
    try {
      const flow = await createFlow({
        name: formName,
        trigger_event: formTrigger,
        description: formDesc || undefined,
        goal_event: formGoal || undefined,
      });
      showToast("Flow created", "success");
      setShowCreate(false);
      setFormName("");
      setFormDesc("");
      setFormGoal("");
      fetchFlows();
      // Open the new flow canvas immediately
      onOpenFlow(flow.id);
    } catch {
      showToast("Failed to create flow", "error");
    }
    setCreating(false);
  }

  async function handleAction(flow: AutomationFlow, action: string) {
    try {
      if (action === "activate") {
        await activateFlow(flow.id);
        showToast("Flow activated", "success");
      } else if (action === "pause") {
        await pauseFlow(flow.id);
        showToast("Flow paused", "success");
      } else if (action === "archive") {
        if (!confirm(`Archive "${flow.name}"? This cannot be undone.`)) return;
        await archiveFlow(flow.id);
        showToast("Flow archived", "success");
      } else if (action === "delete") {
        if (!confirm(`Delete "${flow.name}"? This cannot be undone.`)) return;
        await deleteFlow(flow.id);
        showToast("Flow deleted", "success");
      }
      fetchFlows();
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "Action failed";
      showToast(msg, "error");
    }
  }

  function statusBadge(status: string): string {
    switch (status) {
      case "active": return "badge-green";
      case "paused": return "badge-purple";
      case "archived": return "badge-pink";
      default: return "badge-blue";
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
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="archived">Archived</option>
          </select>
          <span className="text-xs text-text-muted whitespace-nowrap">
            {flows.length} flow{flows.length !== 1 ? "s" : ""}
          </span>
        </div>
        <button
          className="btn-primary text-sm"
          onClick={() => setShowCreate(true)}
        >
          + New Flow
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner className="py-16" />
      ) : flows.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <p className="text-text-muted mb-3">No automation flows yet.</p>
          <button
            className="btn-primary text-sm"
            onClick={() => setShowCreate(true)}
          >
            Create Your First Flow
          </button>
        </div>
      ) : (
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-glass-border">
                <th className="text-left p-3 text-text-muted font-medium">Name</th>
                <th className="text-left p-3 text-text-muted font-medium">Trigger</th>
                <th className="text-left p-3 text-text-muted font-medium">Status</th>
                <th className="text-left p-3 text-text-muted font-medium">Steps</th>
                <th className="text-left p-3 text-text-muted font-medium">Updated</th>
                <th className="text-right p-3 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {flows.map((f) => (
                <tr
                  key={f.id}
                  className="border-b border-glass-border/50 hover:bg-glass-hover transition-colors cursor-pointer"
                  onClick={() => onOpenFlow(f.id)}
                >
                  <td className="p-3">
                    <div className="text-text-primary font-medium">{f.name}</div>
                    {f.description && (
                      <div className="text-text-muted text-xs mt-0.5 truncate max-w-[200px]">
                        {f.description}
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-text-secondary text-xs">
                    {f.trigger_event}
                  </td>
                  <td className="p-3">
                    <span className={`badge ${statusBadge(f.status)}`}>
                      {f.status}
                    </span>
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {f.steps?.length || 0}
                  </td>
                  <td className="p-3 text-text-muted text-xs">
                    {formatRelativeTime(f.updated_at)}
                  </td>
                  <td
                    className="p-3 text-right space-x-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {f.status === "draft" && (
                      <button
                        onClick={() => handleAction(f, "activate")}
                        className="text-accent-green hover:underline text-xs"
                      >
                        Activate
                      </button>
                    )}
                    {f.status === "active" && (
                      <button
                        onClick={() => handleAction(f, "pause")}
                        className="text-accent-purple hover:underline text-xs"
                      >
                        Pause
                      </button>
                    )}
                    {f.status === "paused" && (
                      <>
                        <button
                          onClick={() => handleAction(f, "activate")}
                          className="text-accent-green hover:underline text-xs"
                        >
                          Resume
                        </button>
                        <button
                          onClick={() => handleAction(f, "archive")}
                          className="text-accent-pink hover:underline text-xs"
                        >
                          Archive
                        </button>
                      </>
                    )}
                    {f.status === "draft" && (
                      <button
                        onClick={() => handleAction(f, "delete")}
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

      {/* Create modal */}
      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        title="Create Automation Flow"
        size="md"
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">Flow Name</label>
            <input
              className="input-glass w-full"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Welcome Series"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Trigger Event</label>
            <select
              className="input-glass w-full"
              value={formTrigger}
              onChange={(e) => setFormTrigger(e.target.value)}
            >
              {TRIGGER_EVENTS.map((te) => (
                <option key={te.value} value={te.value}>
                  {te.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Description (optional)
            </label>
            <textarea
              className="input-glass w-full h-20 resize-none"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="What does this flow do?"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">
              Goal Event (optional)
            </label>
            <input
              className="input-glass w-full text-sm"
              value={formGoal}
              onChange={(e) => setFormGoal(e.target.value)}
              placeholder="purchase_completed"
            />
            <p className="text-[10px] text-text-muted mt-1">
              When a user triggers this event, they&apos;re marked as having reached the goal
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              className="btn-secondary text-sm"
              onClick={() => setShowCreate(false)}
            >
              Cancel
            </button>
            <button
              className="btn-primary text-sm"
              onClick={handleCreate}
              disabled={creating || !formName.trim()}
            >
              {creating ? "Creating..." : "Create Flow"}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
