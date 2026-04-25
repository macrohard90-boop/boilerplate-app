"use client";

import { Handle, Position } from "@xyflow/react";
import type { ReactNode } from "react";

interface BaseNodeProps {
  label: string;
  icon: ReactNode;
  borderColor: string;
  typeBadge: string;
  badgeColor: string;
  selected?: boolean;
  inputHandle?: boolean;
  outputHandles?: { id: string; label?: string }[];
  children?: ReactNode;
}

export default function BaseNode({
  label,
  icon,
  borderColor,
  typeBadge,
  badgeColor,
  selected,
  inputHandle = true,
  outputHandles = [{ id: "default" }],
  children,
}: BaseNodeProps) {
  return (
    <div
      className={`relative w-[160px] rounded-lg border transition-all ${
        selected
          ? `${borderColor} shadow-lg shadow-white/5`
          : "border-glass-border"
      }`}
      style={{
        background: "rgba(255,255,255,0.035)",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Input handle */}
      {inputHandle && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !bg-glass-border !border-2 !border-text-muted hover:!border-accent-blue !-top-1.5"
        />
      )}

      {/* Content */}
      <div className="p-3 text-center">
        <div className="flex items-center justify-center mb-2 text-text-secondary">
          {icon}
        </div>
        <p className="text-xs font-medium text-text-primary truncate">
          {label}
        </p>
        <span className={`inline-block mt-1.5 text-[10px] px-1.5 py-0.5 rounded ${badgeColor}`}>
          {typeBadge}
        </span>
        {children}
      </div>

      {/* Output handles */}
      {outputHandles.length === 1 ? (
        <Handle
          type="source"
          position={Position.Bottom}
          id={outputHandles[0].id}
          className="!w-3 !h-3 !bg-glass-border !border-2 !border-text-muted hover:!border-accent-pink !-bottom-1.5"
        />
      ) : (
        <div className="flex justify-around px-2 pb-1">
          {outputHandles.map((h, i) => (
            <div key={h.id} className="relative flex flex-col items-center">
              {h.label && (
                <span className="text-[9px] text-text-muted mb-0.5">
                  {h.label}
                </span>
              )}
              <Handle
                type="source"
                position={Position.Bottom}
                id={h.id}
                className="!w-3 !h-3 !bg-glass-border !border-2 !border-text-muted hover:!border-accent-pink !relative !transform-none !left-auto !right-auto"
                style={{
                  left: `${((i + 1) / (outputHandles.length + 1)) * 100}%`,
                }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
