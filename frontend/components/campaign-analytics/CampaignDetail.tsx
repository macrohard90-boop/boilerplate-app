"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import LoadingSpinner from "../LoadingSpinner";
import ConversionFunnel from "./ConversionFunnel";
import VariantComparison from "./VariantComparison";
import CampaignTimeSeries from "./CampaignTimeSeries";
import ClickHeatmap from "./ClickHeatmap";

interface FunnelResponse {
  campaign_id: string;
  funnel: {
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
    bounced: number;
    complained: number;
    unsubscribed: number;
    converted: number;
    revenue: number;
  };
  rates: {
    open_rate: number;
    click_rate: number;
    conversion_rate: number;
    bounce_rate: number;
  };
  computed_at: string | null;
}

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

interface CampaignDetailProps {
  campaignId: string;
  campaignName: string;
  onBack: () => void;
}

export default function CampaignDetail({
  campaignId,
  campaignName,
  onBack,
}: CampaignDetailProps) {
  const [funnelData, setFunnelData] = useState<FunnelResponse | null>(null);
  const [variants, setVariants] = useState<CampaignVariant[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [funnel, vars] = await Promise.all([
        apiFetch<FunnelResponse>(
          `/marketing/analytics/campaigns/${campaignId}/funnel`,
        ),
        apiFetch<CampaignVariant[]>(
          `/marketing/analytics/campaigns/${campaignId}/variants`,
        ),
      ]);
      setFunnelData(funnel);
      setVariants(vars);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSpinner size="lg" className="py-20" />;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2">
        <button
          onClick={onBack}
          className="text-sm text-accent-pink hover:underline flex items-center gap-1"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Rankings
        </button>
        <span className="text-text-muted">/</span>
        <span className="text-sm text-text-primary font-medium">
          {campaignName}
        </span>
      </div>

      {/* Funnel */}
      {funnelData && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Conversion Funnel</h3>
          <ConversionFunnel
            funnel={funnelData.funnel}
            rates={funnelData.rates}
          />
        </div>
      )}

      {/* Time Series */}
      <CampaignTimeSeries campaignId={campaignId} />

      {/* Variant Comparison */}
      {variants.length > 1 && <VariantComparison variants={variants} />}

      {/* Click Heatmap */}
      <ClickHeatmap campaignId={campaignId} />
    </div>
  );
}
