"use client";

interface CampaignVariant {
  variant_id: string;
  label: string;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  open_rate: number;
  click_rate: number;
  conversion_rate: number;
}

interface VariantComparisonProps {
  variants: CampaignVariant[];
}

function formatPercent(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

export default function VariantComparison({
  variants,
}: VariantComparisonProps) {
  if (variants.length === 0) return null;

  // Find winners for each metric
  const bestOpen = Math.max(...variants.map((v) => v.open_rate));
  const bestClick = Math.max(...variants.map((v) => v.click_rate));
  const bestConv = Math.max(...variants.map((v) => v.conversion_rate));

  return (
    <div className="glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-glass-border">
        <h3 className="text-lg font-semibold">A/B Variant Comparison</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-text-muted border-b border-glass-border text-xs">
              <th className="px-4 py-3">Variant</th>
              <th className="px-4 py-3 text-right">Sent</th>
              <th className="px-4 py-3 text-right">Delivered</th>
              <th className="px-4 py-3 text-right">Open Rate</th>
              <th className="px-4 py-3 text-right">Click Rate</th>
              <th className="px-4 py-3 text-right">Conv. Rate</th>
            </tr>
          </thead>
          <tbody>
            {variants.map((v) => (
              <tr
                key={v.variant_id}
                className="border-b border-glass-border/50 hover:bg-glass-hover"
              >
                <td className="px-4 py-3 font-medium">{v.label}</td>
                <td className="px-4 py-3 text-right font-mono text-text-secondary">
                  {v.sent.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right font-mono text-text-secondary">
                  {v.delivered.toLocaleString()}
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono ${v.open_rate === bestOpen && variants.length > 1 ? "text-accent-green font-bold" : "text-text-secondary"}`}
                >
                  {formatPercent(v.open_rate)}
                  {v.open_rate === bestOpen && variants.length > 1 && (
                    <span className="ml-1 text-xs">W</span>
                  )}
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono ${v.click_rate === bestClick && variants.length > 1 ? "text-accent-green font-bold" : "text-text-secondary"}`}
                >
                  {formatPercent(v.click_rate)}
                  {v.click_rate === bestClick && variants.length > 1 && (
                    <span className="ml-1 text-xs">W</span>
                  )}
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono ${v.conversion_rate === bestConv && variants.length > 1 ? "text-accent-green font-bold" : "text-text-secondary"}`}
                >
                  {formatPercent(v.conversion_rate)}
                  {v.conversion_rate === bestConv && variants.length > 1 && (
                    <span className="ml-1 text-xs">W</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
