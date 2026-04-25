"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function TriggerNode({ data, selected }: NodeProps) {
  return (
    <BaseNode
      label={(data.label as string) || "Trigger"}
      icon={
        <svg className="w-5 h-5 text-accent-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      }
      borderColor="border-accent-green/50"
      typeBadge="Trigger"
      badgeColor="bg-accent-green/10 text-accent-green"
      selected={selected}
      inputHandle={false}
      outputHandles={[{ id: "default" }]}
    />
  );
}
