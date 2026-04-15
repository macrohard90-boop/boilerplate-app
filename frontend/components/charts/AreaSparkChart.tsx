"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface DataPoint {
  label: string;
  value: number;
  value2?: number;
  value3?: number | null;
}

interface AreaSparkChartProps {
  data: DataPoint[];
  color?: string;
  color2?: string;
  color3?: string;
  height?: number;
  valueLabel?: string;
  valueLabel2?: string;
  valueLabel3?: string;
  showGrid?: boolean;
}

function CustomTooltip({
  active,
  payload,
  label,
  valueLabel,
  valueLabel2,
  valueLabel3,
}: {
  active?: boolean;
  payload?: { value: number; name: string; dataKey: string }[];
  label?: string;
  valueLabel?: string;
  valueLabel2?: string;
  valueLabel3?: string;
}) {
  if (!active || !payload?.length) return null;
  const labels: Record<string, string> = {
    value: valueLabel || "Value",
    value2: valueLabel2 || "Value 2",
    value3: valueLabel3 || "Value 3",
  };
  return (
    <div className="glass rounded-lg px-3 py-2 text-xs border border-glass-border/50 shadow-lg">
      <p className="text-text-muted mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-text-primary font-medium">
          {labels[entry.dataKey] || entry.name}:{" "}
          {entry.dataKey === "value3"
            ? `${entry.value != null ? entry.value : "-"}%`
            : entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

export default function AreaSparkChart({
  data,
  color = "#ec4899",
  color2,
  color3,
  height = 300,
  valueLabel,
  valueLabel2,
  valueLabel3,
  showGrid = true,
}: AreaSparkChartProps) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-text-muted text-sm"
        style={{ height }}
      >
        No data available
      </div>
    );
  }

  const hasValue3 = color3 && data.some((d) => d.value3 != null);
  const id1 = `gradient-${color.replace("#", "")}`;
  const id2 = color2 ? `gradient-${color2.replace("#", "")}` : undefined;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: hasValue3 ? 10 : 5, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id={id1} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          {color2 && id2 && (
            <linearGradient id={id2} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color2} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color2} stopOpacity={0} />
            </linearGradient>
          )}
        </defs>
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.05)"
            vertical={false}
          />
        )}
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "rgba(255,255,255,0.4)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          yAxisId="left"
          tick={{ fontSize: 11, fill: "rgba(255,255,255,0.4)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
          label={valueLabel ? { value: valueLabel, angle: -90, position: "insideLeft", offset: 20, style: { fontSize: 11, fill: "rgba(255,255,255,0.35)" } } : undefined}
        />
        {hasValue3 && (
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: "rgba(255,255,255,0.3)" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}%`}
            label={valueLabel3 ? { value: valueLabel3, angle: 90, position: "insideRight", offset: 10, style: { fontSize: 11, fill: "rgba(255,255,255,0.3)" } } : undefined}
          />
        )}
        <Tooltip
          content={
            <CustomTooltip
              valueLabel={valueLabel}
              valueLabel2={valueLabel2}
              valueLabel3={valueLabel3}
            />
          }
        />
        <Area
          yAxisId="left"
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#${id1})`}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
        {color2 && id2 && (
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="value2"
            stroke={color2}
            strokeWidth={2}
            fill={`url(#${id2})`}
            dot={false}
            activeDot={{ r: 4, fill: color2 }}
          />
        )}
        {hasValue3 && (
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="value3"
            stroke={color3}
            strokeWidth={2}
            fill="transparent"
            dot={false}
            activeDot={{ r: 4, fill: color3 }}
            strokeDasharray="4 2"
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
