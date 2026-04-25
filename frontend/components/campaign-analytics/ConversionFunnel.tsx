"use client";

interface FunnelData {
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  complained: number;
  unsubscribed: number;
  converted: number;
  revenue: number;
}

interface FunnelRates {
  open_rate: number;
  click_rate: number;
  conversion_rate: number;
  bounce_rate: number;
}

interface ConversionFunnelProps {
  funnel: FunnelData;
  rates: FunnelRates;
}

const STAGES: { key: keyof FunnelData; label: string; color: string }[] = [
  { key: "sent", label: "Sent", color: "from-accent-purple to-accent-blue" },
  {
    key: "delivered",
    label: "Delivered",
    color: "from-accent-purple/90 to-accent-blue/90",
  },
  {
    key: "opened",
    label: "Opened",
    color: "from-accent-purple/70 to-accent-blue/70",
  },
  {
    key: "clicked",
    label: "Clicked",
    color: "from-accent-purple/50 to-accent-blue/50",
  },
  {
    key: "converted",
    label: "Converted",
    color: "from-accent-green/60 to-accent-green/40",
  },
];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

function formatCurrency(n: number): string {
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2 });
}

export default function ConversionFunnel({
  funnel,
  rates,
}: ConversionFunnelProps) {
  const maxValue = funnel.sent || 1;

  return (
    <div className="space-y-6">
      {/* Funnel bars */}
      <div className="space-y-1">
        {STAGES.map((stage, i) => {
          const value = funnel[stage.key] as number;
          const widthPct = Math.max((value / maxValue) * 100, 2);
          const prevStage = i > 0 ? STAGES[i - 1] : null;
          const prevValue = prevStage
            ? (funnel[prevStage.key] as number)
            : null;
          const dropoff =
            prevValue !== null && prevValue > 0 ? prevValue - value : null;
          const dropoffPct =
            prevValue !== null && prevValue > 0
              ? ((prevValue - value) / prevValue) * 100
              : null;
          const stageRate =
            prevValue !== null && prevValue > 0 ? value / prevValue : null;

          return (
            <div key={stage.key}>
              {/* Drop-off annotation */}
              {dropoff !== null && dropoff > 0 && (
                <div className="flex items-center gap-2 pl-20 py-1">
                  <div className="h-px flex-1 max-w-[200px] bg-glass-border" />
                  <span className="text-xs text-accent-pink">
                    -{formatNumber(dropoff)} ({dropoffPct?.toFixed(1)}% drop)
                  </span>
                </div>
              )}

              {/* Bar row */}
              <div className="flex items-center gap-3">
                <span className="text-sm text-text-secondary w-20 text-right shrink-0">
                  {stage.label}
                </span>
                <div className="flex-1 relative">
                  <div
                    className={`h-9 rounded-md bg-gradient-to-r ${stage.color} transition-all duration-500 flex items-center px-3`}
                    style={{ width: `${widthPct}%` }}
                  >
                    <span className="text-xs font-mono text-white/90 whitespace-nowrap">
                      {formatNumber(value)}
                    </span>
                  </div>
                </div>
                {stageRate !== null && (
                  <span className="text-xs text-text-muted w-14 text-right shrink-0">
                    {(stageRate * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Revenue callout */}
      {funnel.revenue > 0 && (
        <div className="glass rounded-lg p-4 border border-accent-green/20 text-center">
          <span className="text-sm text-text-secondary">Total Revenue</span>
          <p className="text-2xl font-bold text-accent-green mt-1">
            {formatCurrency(funnel.revenue)}
          </p>
        </div>
      )}

      {/* Rate cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <RateCard
          label="Open Rate"
          value={rates.open_rate}
          color="text-accent-blue"
        />
        <RateCard
          label="Click Rate"
          value={rates.click_rate}
          color="text-accent-purple"
        />
        <RateCard
          label="Conversion Rate"
          value={rates.conversion_rate}
          color="text-accent-green"
        />
        <RateCard
          label="Bounce Rate"
          value={rates.bounce_rate}
          color="text-accent-pink"
        />
      </div>

      {/* Secondary metrics */}
      {(funnel.complained > 0 || funnel.unsubscribed > 0) && (
        <div className="flex gap-4 text-xs text-text-muted">
          {funnel.complained > 0 && (
            <span>Complaints: {formatNumber(funnel.complained)}</span>
          )}
          {funnel.unsubscribed > 0 && (
            <span>Unsubscribed: {formatNumber(funnel.unsubscribed)}</span>
          )}
          {funnel.bounced > 0 && (
            <span>Bounced: {formatNumber(funnel.bounced)}</span>
          )}
        </div>
      )}
    </div>
  );
}

function RateCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="glass rounded-lg p-3 text-center">
      <span className="text-xs text-text-muted">{label}</span>
      <p className={`text-lg font-bold ${color} mt-1`}>
        {formatPercent(value)}
      </p>
    </div>
  );
}
