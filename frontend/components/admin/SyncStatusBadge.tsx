"use client";

interface SyncStatusBadgeProps {
  status: string;
  error?: string | null;
  onRetry?: () => void;
}

export default function SyncStatusBadge({ status, error, onRetry }: SyncStatusBadgeProps) {
  if (status === "synced") {
    return <span className="badge-green text-xs">Synced</span>;
  }

  if (status === "error") {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span className="badge-pink text-xs" title={error || "Sync failed"}>Error</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs text-accent-blue hover:text-accent-blue/80 transition-colors underline"
          >
            Retry
          </button>
        )}
      </span>
    );
  }

  return <span className="badge-purple text-xs opacity-60">Unsynced</span>;
}
