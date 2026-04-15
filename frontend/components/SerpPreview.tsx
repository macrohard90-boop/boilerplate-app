/**
 * Google SERP preview component.
 * Shows how a page will appear in Google search results.
 */

interface SerpPreviewProps {
  title: string;
  url: string;
  description: string;
}

export default function SerpPreview({ title, url, description }: SerpPreviewProps) {
  const displayTitle = title.length > 60 ? title.slice(0, 57) + "..." : title;
  const displayDesc =
    description.length > 160
      ? description.slice(0, 157) + "..."
      : description;

  return (
    <div className="glass rounded-lg p-4 max-w-xl">
      <p className="text-xs text-text-muted mb-2 uppercase tracking-wider">
        SERP Preview
      </p>
      <div>
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
    </div>
  );
}
