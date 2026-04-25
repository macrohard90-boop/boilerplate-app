"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function WebhookNode({ data, selected }: NodeProps) {
  return (
    <BaseNode
      label={(data.label as string) || "Webhook"}
      icon={
        <svg
          className="w-5 h-5 text-indigo-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
          />
        </svg>
      }
      borderColor="border-indigo-400/50"
      typeBadge="Webhook"
      badgeColor="bg-indigo-400/10 text-indigo-400"
      selected={selected}
    />
  );
}
