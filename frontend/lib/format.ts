/**
 * Format price from INT cents to currency string.
 * e.g., 7999 → "$79.99", 500 → "$5.00"
 */
export function formatPrice(cents: number, currency = "USD"): string {
  return (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency,
  });
}

/**
 * Format a date string to a readable format.
 */
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Format a date string to a relative time (e.g., "2 hours ago").
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date();
  const d = new Date(date);
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return formatDate(date);
}

/**
 * Truncate a string with ellipsis.
 */
export function truncate(str: string, len: number): string {
  if (str.length <= len) return str;
  return str.slice(0, len).trimEnd() + "...";
}

/**
 * Generate star rating display info.
 */
export function ratingToStars(rating: number): {
  full: number;
  half: boolean;
  empty: number;
} {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  const empty = 5 - full - (half ? 1 : 0);
  return { full, half, empty };
}

/**
 * Capitalize first letter.
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Get order status color class.
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case "completed":
    case "delivered":
    case "active":
      return "badge-green";
    case "pending":
    case "processing":
      return "badge-blue";
    case "cancelled":
    case "failed":
      return "badge-pink";
    default:
      return "badge-purple";
  }
}
