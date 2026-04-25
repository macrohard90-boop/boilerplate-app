"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function UpdateNode({ data, selected }: NodeProps) {
  return (
    <BaseNode
      label={(data.label as string) || "Update"}
      icon={
        <svg
          className="w-5 h-5 text-teal-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
          />
        </svg>
      }
      borderColor="border-teal-400/50"
      typeBadge="Update"
      badgeColor="bg-teal-400/10 text-teal-400"
      selected={selected}
    />
  );
}
