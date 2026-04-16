/**
 * Search Engine Results Page preview component.
 * Shows how a page will appear in Google search results (desktop/mobile)
 * and on social media (Facebook/Twitter OG card).
 */

"use client";

import { useState } from "react";

interface SerpPreviewProps {
  title: string;
  url: string;
  description: string;
  ogImage?: string;
  siteName?: string;
}

type PreviewTab = "desktop" | "mobile" | "social";

export default function SerpPreview({
  title,
  url,
  description,
  ogImage,
  siteName,
}: SerpPreviewProps) {
  const [tab, setTab] = useState<PreviewTab>("desktop");

  const tabs: { key: PreviewTab; label: string }[] = [
    { key: "desktop", label: "Desktop" },
    { key: "mobile", label: "Mobile" },
    { key: "social", label: "Social" },
  ];

  return (
    <div className="glass rounded-lg p-4">
      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-3">
        <span className="text-xs text-text-muted uppercase tracking-wider mr-3">
          Preview
        </span>
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
              tab === t.key
                ? "bg-accent-purple/20 text-accent-purple"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "desktop" && (
        <DesktopSerp title={title} url={url} description={description} />
      )}
      {tab === "mobile" && (
        <MobileSerp title={title} url={url} description={description} />
      )}
      {tab === "social" && (
        <SocialPreview
          title={title}
          url={url}
          description={description}
          ogImage={ogImage}
          siteName={siteName}
        />
      )}
    </div>
  );
}

/* ── Desktop SERP ── */

function DesktopSerp({
  title,
  url,
  description,
}: {
  title: string;
  url: string;
  description: string;
}) {
  const displayTitle = title.length > 60 ? title.slice(0, 57) + "..." : title;
  const displayDesc =
    description.length > 160 ? description.slice(0, 157) + "..." : description;

  return (
    <div className="max-w-xl">
      <p
        className="text-lg leading-tight mb-0.5 cursor-pointer hover:underline"
        style={{ color: "#8ab4f8" }}
      >
        {displayTitle || "Page Title"}
      </p>
      <p className="text-xs mb-1" style={{ color: "#bdc1c6" }}>
        {url || "https://example.com/page"}
      </p>
      <p className="text-sm" style={{ color: "#bdc1c6" }}>
        {displayDesc || "Page description will appear here..."}
      </p>
    </div>
  );
}

/* ── Mobile SERP ── */

function MobileSerp({
  title,
  url,
  description,
}: {
  title: string;
  url: string;
  description: string;
}) {
  // Mobile truncates more aggressively
  const displayTitle = title.length > 50 ? title.slice(0, 47) + "..." : title;
  const displayDesc =
    description.length > 120 ? description.slice(0, 117) + "..." : description;

  return (
    <div className="max-w-xs">
      <p className="text-xs mb-1 truncate" style={{ color: "#bdc1c6" }}>
        {url || "https://example.com/page"}
      </p>
      <p
        className="text-base leading-tight mb-0.5 cursor-pointer hover:underline"
        style={{ color: "#8ab4f8" }}
      >
        {displayTitle || "Page Title"}
      </p>
      <p className="text-xs leading-relaxed" style={{ color: "#bdc1c6" }}>
        {displayDesc || "Page description will appear here..."}
      </p>
    </div>
  );
}

/* ── Social Preview (OG Card) ── */

function SocialPreview({
  title,
  url,
  description,
  ogImage,
  siteName,
}: {
  title: string;
  url: string;
  description: string;
  ogImage?: string;
  siteName?: string;
}) {
  const displayTitle = title.length > 65 ? title.slice(0, 62) + "..." : title;
  const displayDesc =
    description.length > 100 ? description.slice(0, 97) + "..." : description;

  // Extract domain from URL for display
  let domain = "";
  try {
    domain = new URL(url).hostname;
  } catch {
    domain = url;
  }

  return (
    <div className="max-w-md rounded-lg overflow-hidden border border-glass-border">
      {/* OG Image area */}
      <div
        className="w-full h-40 flex items-center justify-center"
        style={{ backgroundColor: "#1a1a2e" }}
      >
        {ogImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={ogImage}
            alt="OG preview"
            className="w-full h-full object-cover"
          />
        ) : (
          <span className="text-text-muted text-xs">
            No OG image set
          </span>
        )}
      </div>

      {/* Card body */}
      <div className="p-3 bg-glass-bg">
        <p className="text-[10px] uppercase text-text-muted tracking-wider mb-0.5">
          {siteName || domain}
        </p>
        <p className="text-sm font-medium text-text-primary leading-tight mb-1">
          {displayTitle || "Page Title"}
        </p>
        <p className="text-xs text-text-secondary leading-relaxed">
          {displayDesc || "Page description will appear when shared on social media."}
        </p>
      </div>
    </div>
  );
}
