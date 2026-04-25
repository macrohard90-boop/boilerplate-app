"use client";

import { useCallback, useEffect, useState } from "react";
import type { FlowStats, StepPerformance } from "./useFlowApi";
import { getFlowStats, getStepPerformance } from "./useFlowApi";
import LoadingSpinner from "../LoadingSpinner";

interface FlowStatsPanelProps {
  flowId: string;
}

export default function FlowStatsPanel({ flowId }: FlowStatsPanelProps) {
  const [stats, setStats] = useState<FlowStats | null>(null);
  const [steps, setSteps] = useState<StepPerformance[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([
        getFlowStats(flowId),
        getStepPerformance(flowId),
      ]);
      setStats(s);
      setSteps(p);
    } catch {
      // ignore
    }
    setLoading(false);
  }, [flowId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="absolute top-12 right-4 w-64 glass rounded-xl p-4 z-40">
        <LoadingSpinner size="sm" />
      </div>
    );
  }

  if (!stats) return null;

  const kpis: [string, number | string, string][] = [
    ["Enrolled", stats.total_enrollments, "accent-blue"],
    ["Active", stats.active, "accent-green"],
    ["Completed", stats.completed, "accent-purple"],
    ["Goal Reached", stats.goal_reached, "accent-green"],
    ["Exited", stats.exited, "text-muted"],
    ["Errors", stats.error, "accent-pink"],
    ["Completion %", `${(stats.completion_rate * 100).toFixed(1)}%`, "accent-blue"],
    ["Goal %", `${(stats.goal_rate * 100).toFixed(1)}%`, "accent-green"],
  ];

  return (
    <div className="absolute top-12 right-4 w-72 glass rounded-xl z-40 overflow-hidden animate-slide-in-right">
      <div className="p-3 border-b border-glass-border">
        <h4 className="text-xs font-semibold text-text-primary">Flow Performance</h4>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-px bg-glass-border">
        {kpis.map(([label, value, color]) => (
          <div key={label} className="bg-base-50 p-2.5 text-center">
            <p className="text-[10px] text-text-muted">{label}</p>
            <p className={`text-sm font-bold text-${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Step performance */}
      {steps.length > 0 && (
        <div className="p-3 border-t border-glass-border">
          <h5 className="text-[10px] font-semibold text-text-muted mb-2 uppercase tracking-wider">
            Step Performance
          </h5>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {steps.map((sp) => (
              <div key={sp.step_id} className="flex items-center gap-2">
                <span className="text-[10px] text-text-muted capitalize w-14 truncate">
                  {sp.step_type}
                </span>
                <div className="flex-1 h-1.5 bg-glass-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-green rounded-full"
                    style={{ width: `${sp.success_rate * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-text-secondary w-10 text-right">
                  {(sp.success_rate * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
