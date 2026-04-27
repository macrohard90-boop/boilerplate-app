/**
 * JourneyLogger — records every page a user visits during their test.
 * Prints a readable summary at the end showing the full navigation path.
 */

import { Page } from "@playwright/test";

export interface PageVisit {
  url: string;
  path: string;
  label: string;
  timestamp: number;
  durationMs?: number;
}

/**
 * Classify a URL path into a human-readable label.
 */
function labelForPath(path: string): string {
  if (path === "/" || path === "") return "Homepage";
  if (path === "/products") return "Products Listing";
  if (path.startsWith("/products/")) return `Product Detail (${path.split("/products/")[1]})`;
  if (path === "/cart") return "Cart";
  if (path === "/checkout") return "Checkout";
  if (path.startsWith("/checkout")) return `Checkout (${path})`;
  if (path === "/dashboard") return "Dashboard";
  if (path === "/dashboard/orders") return "Orders";
  if (path === "/dashboard/profile") return "Profile";
  if (path === "/dashboard/wishlists") return "Wishlists";
  if (path === "/dashboard/privacy") return "Privacy Settings";
  if (path.startsWith("/dashboard/orders/") && path.includes("/confirmation"))
    return "Order Confirmation";
  if (path.startsWith("/dashboard/orders/")) return `Order Detail`;
  if (path === "/auth/login") return "Login";
  if (path === "/auth/register") return "Register";
  return path;
}

export class JourneyLogger {
  visits: PageVisit[] = [];
  private _listening = false;

  /** Attach to a page — automatically logs every navigation. */
  attach(page: Page): void {
    if (this._listening) return;
    this._listening = true;

    // Record initial page load
    page.on("load", () => {
      this._recordVisit(page.url());
    });

    // Record client-side navigations (SPA)
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) {
        this._recordVisit(frame.url());
      }
    });
  }

  /** Manually record a page visit (for actions that don't trigger a full navigation). */
  recordStep(label: string, url?: string): void {
    const path = url ? new URL(url, "http://localhost").pathname : "";
    this.visits.push({
      url: url || "",
      path,
      label,
      timestamp: Date.now(),
    });
  }

  private _recordVisit(rawUrl: string): void {
    try {
      const url = new URL(rawUrl);
      const path = url.pathname;

      // Skip duplicate consecutive visits to the same path
      if (this.visits.length > 0) {
        const last = this.visits[this.visits.length - 1];
        if (last.path === path) return;
      }

      // Calculate duration of previous visit
      if (this.visits.length > 0) {
        const prev = this.visits[this.visits.length - 1];
        if (!prev.durationMs) {
          prev.durationMs = Date.now() - prev.timestamp;
        }
      }

      this.visits.push({
        url: rawUrl,
        path,
        label: labelForPath(path),
        timestamp: Date.now(),
      });
    } catch {
      // about:blank or similar — ignore
    }
  }

  /** Total number of unique pages visited. */
  get pageCount(): number {
    const uniquePaths = new Set(this.visits.map((v) => v.path));
    return uniquePaths.size;
  }

  /** Total number of page visits (including revisits). */
  get totalVisits(): number {
    return this.visits.length;
  }

  /** Print a formatted journey summary to console. */
  printSummary(userName: string): void {
    const lines: string[] = [];
    lines.push(`\n  === Journey: ${userName} (${this.totalVisits} visits, ${this.pageCount} unique pages) ===`);
    for (let i = 0; i < this.visits.length; i++) {
      const v = this.visits[i];
      const duration = v.durationMs ? ` (${(v.durationMs / 1000).toFixed(1)}s)` : "";
      const step = String(i + 1).padStart(2, " ");
      lines.push(`  ${step}. ${v.label}${duration}`);
    }
    lines.push(`  === End Journey ===\n`);
    console.log(lines.join("\n"));
  }

  /** Get a compact array of page labels for assertion / logging. */
  getPath(): string[] {
    return this.visits.map((v) => v.label);
  }

  /** Assert at least N total page visits. */
  assertMinVisits(minVisits: number): void {
    if (this.totalVisits < minVisits) {
      throw new Error(
        `Expected at least ${minVisits} page visits but got ${this.totalVisits}. ` +
          `Pages: ${this.getPath().join(" → ")}`,
      );
    }
  }
}
