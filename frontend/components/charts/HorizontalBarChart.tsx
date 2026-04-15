"use client";

interface HBarItem {
  label: string;
  value: number;
  secondary?: number;
}

interface HorizontalBarChartProps {
  data: HBarItem[];
  color?: string;
  formatValue: (v: number) => string;
  formatSecondary?: (v: number) => string;
}

export default function HorizontalBarChart({
  data,
  color = "#ec4899",
  formatValue,
  formatSecondary,
}: HorizontalBarChartProps) {
  if (!data.length) {
    return <p className="text-sm text-text-muted py-4">No data available</p>;
  }

  const maxVal = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="space-y-3">
      {data.map((item, i) => {
        const pct = Math.max(2, (item.value / maxVal) * 100);
        return (
          <div key={i}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-text-secondary truncate flex-1" title={item.label}>
                {item.label}
              </span>
              <span className="text-text-primary font-medium ml-2 tabular-nums whitespace-nowrap">
                {formatValue(item.value)}
                {formatSecondary && item.secondary != null && (
                  <span className="text-text-muted text-xs ml-2">
                    ({formatSecondary(item.secondary)})
                  </span>
                )}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-glass-bg/50 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.7 - i * 0.06 }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
