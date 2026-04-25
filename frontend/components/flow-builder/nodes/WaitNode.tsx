"use client";

import type { NodeProps } from "@xyflow/react";
import BaseNode from "./BaseNode";

export default function WaitNode({ data, selected }: NodeProps) {
  const config = (data.config as Record<string, unknown>) || {};
  const seconds = (config.duration_seconds as number) || 0;
  const label =
    seconds >= 86400
      ? `Wait ${Math.round(seconds / 86400)}d`
      : seconds >= 3600
        ? `Wait ${Math.round(seconds / 3600)}h`
        : seconds > 0
          ? `Wait ${Math.round(seconds / 60)}m`
          : (data.label as string) || "Wait";

  return (
    <BaseNode
      label={label}
      icon={
        <svg className="w-5 h-5 text-accent-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      }
      borderColor="border-accent-purple/50"
      typeBadge="Wait"
      badgeColor="bg-accent-purple/10 text-accent-purple"
      selected={selected}
    />
  );
}
