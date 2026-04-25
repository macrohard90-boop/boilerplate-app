"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function SplitNode({ data, selected }: NodeProps) {
  return (
    <BaseNode
      label={(data.label as string) || "A/B Split"}
      icon={
        <svg
          className="w-5 h-5 text-yellow-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"
          />
        </svg>
      }
      borderColor="border-yellow-400/50"
      typeBadge="Split"
      badgeColor="bg-yellow-400/10 text-yellow-400"
      selected={selected}
      outputHandles={[
        { id: "a", label: "A" },
        { id: "b", label: "B" },
      ]}
    />
  );
}
