"use client";

import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  type OnNodesChange,
  type OnEdgesChange,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import TriggerNode from "./nodes/TriggerNode";
import SendNode from "./nodes/SendNode";
import WaitNode from "./nodes/WaitNode";
import BranchNode from "./nodes/BranchNode";
import SplitNode from "./nodes/SplitNode";
import UpdateNode from "./nodes/UpdateNode";
import WebhookNode from "./nodes/WebhookNode";

import type { AutomationFlow, FlowStep, FlowConnection } from "./useFlowApi";
import {
  getFlow,
  addStep,
  updateStep,
  deleteStep,
  addConnection,
  deleteConnection,
} from "./useFlowApi";

const nodeTypes: NodeTypes = {
  trigger: TriggerNode,
  send: SendNode,
  wait: WaitNode,
  branch: BranchNode,
  split: SplitNode,
  update: UpdateNode,
  webhook: WebhookNode,
};

/** Default Y offset when auto-placing new nodes */
const NODE_Y_GAP = 120;

interface FlowCanvasProps {
  flowId: string;
  onNodeSelect: (
    stepId: string | null,
    stepType: string,
    config: Record<string, unknown>,
  ) => void;
  onFlowLoaded: (flow: AutomationFlow) => void;
  onDirtyChange: (dirty: boolean) => void;
}

export default function FlowCanvas({
  flowId,
  onNodeSelect,
  onFlowLoaded,
  onDirtyChange,
}: FlowCanvasProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const flowRef = useRef<AutomationFlow | null>(null);
  const dirtyPositions = useRef(false);

  // ── Load flow data ─────────────────────────────────────
  const loadFlow = useCallback(async () => {
    setLoading(true);
    try {
      const flow = await getFlow(flowId);
      flowRef.current = flow;
      onFlowLoaded(flow);

      // Convert steps → nodes
      const newNodes: Node[] = [];

      // Trigger node (virtual — represents the flow entry)
      newNodes.push({
        id: "__trigger__",
        type: "trigger",
        position: (flow as unknown as Record<string, unknown>)._trigger_position
          ? ((flow as unknown as Record<string, unknown>)._trigger_position as {
              x: number;
              y: number;
            })
          : { x: 250, y: 30 },
        data: { label: flow.trigger_event || "Trigger", config: {} },
      });

      flow.steps.forEach((step, idx) => {
        const pos = step.config?._position || {
          x: 250,
          y: 180 + idx * NODE_Y_GAP,
        };
        newNodes.push({
          id: step.id,
          type: step.step_type,
          position: pos,
          data: {
            label: (step.config?.label as string) || "",
            config: step.config || {},
          },
        });
      });

      // Convert connections → edges
      const newEdges: Edge[] = flow.connections.map((conn) => ({
        id: conn.id,
        source:
          conn.from_step_id === "trigger" ? "__trigger__" : conn.from_step_id,
        target: conn.to_step_id,
        sourceHandle: conn.condition_label || "default",
        animated: true,
        style: { stroke: "rgba(192,132,252,0.5)", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "rgba(192,132,252,0.5)",
        },
        label: conn.condition_label || undefined,
        labelStyle: { fill: "rgba(240,240,248,0.6)", fontSize: 11 },
        labelBgStyle: { fill: "rgba(8,8,26,0.8)", fillOpacity: 0.8 },
      }));

      setNodes(newNodes);
      setEdges(newEdges);
      dirtyPositions.current = false;
      onDirtyChange(false);
    } catch {
      // error handled by parent
    }
    setLoading(false);
  }, [flowId, onFlowLoaded, onDirtyChange]);

  useEffect(() => {
    loadFlow();
  }, [loadFlow]);

  // ── Node changes (drag, select, remove) ────────────────
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      // Check if any position changes
      const hasPositionChange = changes.some(
        (c) => c.type === "position" && c.dragging === false,
      );
      if (hasPositionChange && !dirtyPositions.current) {
        dirtyPositions.current = true;
        onDirtyChange(true);
      }

      setNodes((nds) => applyNodeChanges(changes, nds));
    },
    [onDirtyChange],
  );

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  // ── Connect two nodes ──────────────────────────────────
  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target) return;

      const fromStepId =
        connection.source === "__trigger__" ? "trigger" : connection.source;
      const toStepId = connection.target;
      const conditionLabel =
        connection.sourceHandle !== "default"
          ? connection.sourceHandle
          : undefined;

      try {
        const conn = await addConnection(
          flowId,
          fromStepId,
          toStepId,
          conditionLabel || undefined,
        );
        const newEdge: Edge = {
          id: conn.id,
          source: connection.source,
          target: connection.target,
          sourceHandle: connection.sourceHandle,
          animated: true,
          style: { stroke: "rgba(192,132,252,0.5)", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "rgba(192,132,252,0.5)",
          },
          label: conn.condition_label || undefined,
          labelStyle: { fill: "rgba(240,240,248,0.6)", fontSize: 11 },
          labelBgStyle: { fill: "rgba(8,8,26,0.8)", fillOpacity: 0.8 },
        };
        setEdges((eds) => [...eds, newEdge]);
      } catch {
        // connection failed — maybe cycle detected
      }
    },
    [flowId],
  );

  // ── Delete edges via backspace/delete ──────────────────
  const onEdgesDelete = useCallback(async (deletedEdges: Edge[]) => {
    for (const edge of deletedEdges) {
      try {
        await deleteConnection(edge.id);
      } catch {
        // best effort
      }
    }
  }, []);

  // ── Delete nodes via backspace/delete ──────────────────
  const onNodesDelete = useCallback(async (deletedNodes: Node[]) => {
    for (const node of deletedNodes) {
      if (node.id === "__trigger__") continue; // can't delete trigger
      try {
        await deleteStep(node.id);
      } catch {
        // best effort
      }
    }
  }, []);

  // ── Node click → open config panel ─────────────────────
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.id === "__trigger__") {
        onNodeSelect(null, "trigger", {});
        return;
      }
      onNodeSelect(
        node.id,
        node.type || "send",
        (node.data.config as Record<string, unknown>) || {},
      );
    },
    [onNodeSelect],
  );

  // ── Pane click → deselect ──────────────────────────────
  const onPaneClick = useCallback(() => {
    onNodeSelect(null, "", {});
  }, [onNodeSelect]);

  // ── Add a new step (called from toolbar) ───────────────
  const addNewStep = useCallback(
    async (stepType: FlowStep["step_type"]) => {
      // Auto-place below the last node
      const maxY = nodes.reduce((max, n) => Math.max(max, n.position.y), 0);
      const position = { x: 250, y: maxY + NODE_Y_GAP };

      try {
        const step = await addStep(flowId, stepType, { _position: position });
        const newNode: Node = {
          id: step.id,
          type: step.step_type,
          position,
          data: { label: "", config: step.config || {} },
        };
        setNodes((nds) => [...nds, newNode]);
      } catch {
        // error
      }
    },
    [flowId, nodes],
  );

  // ── Save layout (persist positions to step config) ─────
  const saveLayout = useCallback(async () => {
    const updates: Promise<unknown>[] = [];
    for (const node of nodes) {
      if (node.id === "__trigger__") continue;
      const step = flowRef.current?.steps.find((s) => s.id === node.id);
      if (!step) continue;
      const config = {
        ...step.config,
        _position: { x: node.position.x, y: node.position.y },
      };
      updates.push(updateStep(step.id, { config }));
    }
    await Promise.all(updates);
    dirtyPositions.current = false;
    onDirtyChange(false);
  }, [nodes, onDirtyChange]);

  // ── Update a step config (called from config panel) ────
  const updateNodeConfig = useCallback(
    async (stepId: string, config: Record<string, unknown>) => {
      try {
        const step = await updateStep(stepId, { config });
        setNodes((nds) =>
          nds.map((n) =>
            n.id === stepId
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    label: (config.label as string) || "",
                    config,
                  },
                }
              : n,
          ),
        );
        return step;
      } catch {
        return null;
      }
    },
    [],
  );

  // Expose imperative methods via ref-like pattern through props
  // We use a stable ref that the parent can read
  const apiRef = useMemo(
    () => ({ addNewStep, saveLayout, updateNodeConfig, reload: loadFlow }),
    [addNewStep, saveLayout, updateNodeConfig, loadFlow],
  );

  // Expose to parent via a callback-ref pattern
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__flowCanvasApi = apiRef;
    return () => {
      delete (window as unknown as Record<string, unknown>).__flowCanvasApi;
    };
  }, [apiRef]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onEdgesDelete={onEdgesDelete}
        onNodesDelete={onNodesDelete}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        deleteKeyCode={["Backspace", "Delete"]}
        proOptions={{ hideAttribution: true }}
        className="flow-canvas"
      >
        <Background color="rgba(255,255,255,0.03)" gap={20} />
        <Controls className="flow-controls" showInteractive={false} />
        <MiniMap
          className="flow-minimap"
          nodeColor={(node) => {
            switch (node.type) {
              case "trigger":
                return "#34d399";
              case "send":
                return "#38bdf8";
              case "wait":
                return "#c084fc";
              case "branch":
                return "#ff6b9d";
              case "split":
                return "#facc15";
              case "update":
                return "#2dd4bf";
              case "webhook":
                return "#818cf8";
              default:
                return "rgba(255,255,255,0.2)";
            }
          }}
          maskColor="rgba(8,8,26,0.85)"
        />
      </ReactFlow>
    </div>
  );
}

/** Helper type for parent components to call canvas actions */
export interface FlowCanvasApi {
  addNewStep: (stepType: FlowStep["step_type"]) => Promise<void>;
  saveLayout: () => Promise<void>;
  updateNodeConfig: (
    stepId: string,
    config: Record<string, unknown>,
  ) => Promise<FlowStep | null>;
  reload: () => Promise<void>;
}

export function getFlowCanvasApi(): FlowCanvasApi | null {
  return (
    ((window as unknown as Record<string, unknown>)
      .__flowCanvasApi as FlowCanvasApi) || null
  );
}
