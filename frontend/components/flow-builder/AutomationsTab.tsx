"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import type { AutomationFlow } from "./useFlowApi";
import FlowList from "./FlowList";
import FlowToolbar from "./FlowToolbar";
import FlowConfigPanel from "./FlowConfigPanel";

const FlowCanvas = dynamic(() => import("./FlowCanvas"), { ssr: false });
const FlowStatsPanel = dynamic(() => import("./FlowStatsPanel"), {
  ssr: false,
});

export default function AutomationsTab() {
  // View mode: "list" or "canvas"
  const [activeFlowId, setActiveFlowId] = useState<string | null>(null);
  const [flow, setFlow] = useState<AutomationFlow | null>(null);
  const [dirty, setDirty] = useState(false);
  const [showStats, setShowStats] = useState(false);

  // Config panel state
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [selectedStepType, setSelectedStepType] = useState("");
  const [selectedStepConfig, setSelectedStepConfig] = useState<
    Record<string, unknown>
  >({});

  const handleOpenFlow = useCallback((flowId: string) => {
    setActiveFlowId(flowId);
    setSelectedStepId(null);
    setSelectedStepType("");
    setShowStats(false);
  }, []);

  const handleBack = useCallback(() => {
    setActiveFlowId(null);
    setFlow(null);
    setSelectedStepId(null);
    setSelectedStepType("");
    setShowStats(false);
    setDirty(false);
  }, []);

  const handleNodeSelect = useCallback(
    (
      stepId: string | null,
      stepType: string,
      config: Record<string, unknown>,
    ) => {
      setSelectedStepId(stepId);
      setSelectedStepType(stepType);
      setSelectedStepConfig(config);
    },
    [],
  );

  const handleFlowLoaded = useCallback((loadedFlow: AutomationFlow) => {
    setFlow(loadedFlow);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedStepId(null);
    setSelectedStepType("");
  }, []);

  // ── List view ──────────────────────────────────────────
  if (!activeFlowId) {
    return <FlowList onOpenFlow={handleOpenFlow} />;
  }

  // ── Canvas view ────────────────────────────────────────
  return (
    <div className="flex flex-col h-[calc(100vh-220px)] -mx-6 -mb-6 border-t border-glass-border">
      {/* Toolbar */}
      <FlowToolbar
        flow={flow}
        dirty={dirty}
        onBack={handleBack}
        onStatsToggle={() => setShowStats((s) => !s)}
        showStats={showStats}
      />

      {/* Canvas + panels */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Canvas */}
        <div className="flex-1 relative">
          <FlowCanvas
            flowId={activeFlowId}
            onNodeSelect={handleNodeSelect}
            onFlowLoaded={handleFlowLoaded}
            onDirtyChange={setDirty}
          />

          {/* Stats overlay */}
          {showStats && <FlowStatsPanel flowId={activeFlowId} />}
        </div>

        {/* Config panel */}
        {(selectedStepId || selectedStepType === "trigger") && (
          <FlowConfigPanel
            stepId={selectedStepId}
            stepType={selectedStepType}
            config={selectedStepConfig}
            onClose={handleClosePanel}
          />
        )}
      </div>
    </div>
  );
}
