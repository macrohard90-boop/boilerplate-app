/**
 * Custom hook for automation flow CRUD operations.
 * Wraps all /marketing/flows/ endpoints.
 */

import { apiFetch } from "../../lib/api";

// ── Types ────────────────────────────────────────────────

export interface AutomationFlow {
  id: string;
  name: string;
  description: string | null;
  trigger_event: string;
  trigger_conditions: Record<string, unknown>;
  status: "draft" | "active" | "paused" | "archived";
  goal_event: string | null;
  goal_window_days: number;
  allow_reentry: boolean;
  max_chain_depth: number;
  exit_tag: string | null;
  created_by: string | null;
  steps: FlowStep[];
  connections: FlowConnection[];
  created_at: string;
  updated_at: string;
}

export interface FlowStep {
  id: string;
  flow_id: string;
  step_type: "send" | "wait" | "branch" | "split" | "update" | "webhook";
  step_order: number;
  config: Record<string, unknown> & { _position?: { x: number; y: number } };
  created_at: string;
}

export interface FlowConnection {
  id: string;
  from_step_id: string;
  to_step_id: string;
  condition_label: string | null;
  condition_expr: Record<string, unknown> | null;
}

export interface FlowStats {
  flow_id: string;
  total_enrollments: number;
  active: number;
  completed: number;
  goal_reached: number;
  exited: number;
  error: number;
  completion_rate: number;
  goal_rate: number;
}

export interface StepPerformance {
  step_id: string;
  step_type: string;
  step_order: number;
  total_executions: number;
  executed: number;
  waiting: number;
  failed: number;
  skipped: number;
  success_rate: number;
}

// ── API Functions ────────────────────────────────────────

const BASE = "/marketing/flows";

export async function listFlows(status?: string): Promise<AutomationFlow[]> {
  const params = status ? `?status=${status}` : "";
  return apiFetch<AutomationFlow[]>(`${BASE}${params}`);
}

export async function getFlow(flowId: string): Promise<AutomationFlow> {
  return apiFetch<AutomationFlow>(`${BASE}/${flowId}`);
}

export async function createFlow(data: {
  name: string;
  trigger_event: string;
  description?: string;
  goal_event?: string;
  goal_window_days?: number;
  allow_reentry?: boolean;
}): Promise<AutomationFlow> {
  return apiFetch<AutomationFlow>(BASE, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateFlow(
  flowId: string,
  data: Partial<{
    name: string;
    description: string;
    trigger_event: string;
    trigger_conditions: Record<string, unknown>;
    goal_event: string;
    goal_window_days: number;
    allow_reentry: boolean;
    exit_tag: string;
  }>,
): Promise<AutomationFlow> {
  return apiFetch<AutomationFlow>(`${BASE}/${flowId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteFlow(flowId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`${BASE}/${flowId}`, {
    method: "DELETE",
  });
}

export async function addStep(
  flowId: string,
  stepType: FlowStep["step_type"],
  config: Record<string, unknown>,
  stepOrder?: number,
): Promise<FlowStep> {
  return apiFetch<FlowStep>(`${BASE}/${flowId}/steps`, {
    method: "POST",
    body: JSON.stringify({
      step_type: stepType,
      config,
      step_order: stepOrder,
    }),
  });
}

export async function updateStep(
  stepId: string,
  data: { config?: Record<string, unknown>; step_order?: number },
): Promise<FlowStep> {
  return apiFetch<FlowStep>(`${BASE}/steps/${stepId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteStep(stepId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`${BASE}/steps/${stepId}`, {
    method: "DELETE",
  });
}

export async function addConnection(
  flowId: string,
  fromStepId: string,
  toStepId: string,
  conditionLabel?: string,
  conditionExpr?: Record<string, unknown>,
): Promise<FlowConnection> {
  return apiFetch<FlowConnection>(`${BASE}/${flowId}/connections`, {
    method: "POST",
    body: JSON.stringify({
      from_step_id: fromStepId,
      to_step_id: toStepId,
      condition_label: conditionLabel,
      condition_expr: conditionExpr,
    }),
  });
}

export async function deleteConnection(
  connectionId: string,
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`${BASE}/connections/${connectionId}`, {
    method: "DELETE",
  });
}

export async function activateFlow(
  flowId: string,
): Promise<{ status: string; flow_id: string; max_depth: number }> {
  return apiFetch(`${BASE}/${flowId}/activate`, { method: "POST" });
}

export async function pauseFlow(
  flowId: string,
): Promise<{ status: string; flow_id: string }> {
  return apiFetch(`${BASE}/${flowId}/pause`, { method: "POST" });
}

export async function archiveFlow(
  flowId: string,
): Promise<{ status: string; flow_id: string }> {
  return apiFetch(`${BASE}/${flowId}/archive`, { method: "POST" });
}

export async function getFlowStats(flowId: string): Promise<FlowStats> {
  return apiFetch<FlowStats>(`${BASE}/${flowId}/stats`);
}

export async function getStepPerformance(
  flowId: string,
): Promise<StepPerformance[]> {
  return apiFetch<StepPerformance[]>(`${BASE}/${flowId}/step-performance`);
}
