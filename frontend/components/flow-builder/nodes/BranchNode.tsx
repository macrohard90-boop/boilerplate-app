"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function BranchNode({ data, selected }: NodeProps) {
  return (
    <BaseNode
      label={(data.label as string) || "Branch"}
      icon={
        <svg className="w-5 h-5 text-accent-pink" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
        </svg>
      }
      borderColor="border-accent-pink/50"
      typeBadge="Branch"
      badgeColor="bg-accent-pink/10 text-accent-pink"
      selected={selected}
      outputHandles={[
        { id: "yes", label: "Yes" },
        { id: "no", label: "No" },
      ]}
    />
  );
}
