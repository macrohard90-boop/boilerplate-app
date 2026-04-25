"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useConfig } from "../../../lib/config-context";

const RankingsTab = dynamic(
  () => import("../../../components/campaign-analytics/RankingsTab"),
  { ssr: false },
);
const TrendsTab = dynamic(
  () => import("../../../components/campaign-analytics/TrendsTab"),
  { ssr: false },
);
const FatigueTab = dynamic(
  () => import("../../../components/campaign-analytics/FatigueTab"),
  { ssr: false },
);
const CampaignDetail = dynamic(
  () => import("../../../components/campaign-analytics/CampaignDetail"),
  { ssr: false },
);

type TabId = "rankings" | "trends" | "fatigue";

const TABS: { id: TabId; label: string }[] = [
  { id: "rankings", label: "Rankings" },
  { id: "trends", label: "Trends" },
  { id: "fatigue", label: "Fatigue" },
];

export default function CampaignAnalyticsPage() {
  const { enable_marketing } = useConfig();
  const [activeTab, setActiveTab] = useState<TabId>("rankings");
  const [selectedCampaign, setSelectedCampaign] = useState<{
    id: string;
    name: string;
  } | null>(null);

  if (!enable_marketing) {
    return (
      <div className="glass rounded-xl p-12 text-center text-text-secondary">
        Marketing module is disabled.
      </div>
    );
  }

  // Drill-down mode
  if (selectedCampaign) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">Campaign Analytics</h1>
        <CampaignDetail
          campaignId={selectedCampaign.id}
          campaignName={selectedCampaign.name}
          onBack={() => setSelectedCampaign(null)}
        />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Campaign Analytics</h1>

      {/* Tab nav */}
      <div className="flex gap-1 mb-6 border-b border-glass-border/50 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === tab.id
                ? "text-accent-pink"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-pink rounded-full" />
            )}
          </button>
        ))}
      </div>

      {activeTab === "rankings" && (
        <RankingsTab
          onSelectCampaign={(id, name) => setSelectedCampaign({ id, name })}
        />
      )}
      {activeTab === "trends" && <TrendsTab />}
      {activeTab === "fatigue" && <FatigueTab />}
    </div>
  );
}
