"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function SendNode({ data, selected }: NodeProps) {
  const channel = (data.config as Record<string, unknown>)?.channel || "email";
  return (
    <BaseNode
      label={(data.label as string) || `Send ${channel}`}
      icon={
        <svg
          className="w-5 h-5 text-accent-blue"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      }
      borderColor="border-accent-blue/50"
      typeBadge="Send"
      badgeColor="bg-accent-blue/10 text-accent-blue"
      selected={selected}
    />
  );
}
