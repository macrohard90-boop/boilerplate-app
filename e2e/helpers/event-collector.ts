/**
 * Intercepts POST /api/tracking/events requests on a Playwright page.
 * Collects event_type + event_data for assertion.
 */

import { Page, Request } from "@playwright/test";

export interface CapturedEvent {
  event_type: string;
  event_data: Record<string, unknown>;
  timestamp: number;
}

export class EventCollector {
  events: CapturedEvent[] = [];
  private _listening = false;

  /** Attach to a page — start intercepting tracking events. */
  attach(page: Page): void {
    if (this._listening) return;
    this._listening = true;

    page.on("request", (req: Request) => {
      if (
        req.method() === "POST" &&
        req.url().includes("/api/tracking/events")
      ) {
        try {
          const body = req.postDataJSON();
          if (body && body.event_type) {
            this.events.push({
              event_type: body.event_type,
              event_data: body.event_data || {},
              timestamp: Date.now(),
            });
          }
        } catch {
          // Ignore parse errors — fire-and-forget tracking can have keepalive requests
        }
      }
    });
  }

  /** Check if a specific event type was captured. */
  has(eventType: string): boolean {
    return this.events.some((e) => e.event_type === eventType);
  }

  /** Get all instances of a specific event type. */
  get(eventType: string): CapturedEvent[] {
    return this.events.filter((e) => e.event_type === eventType);
  }

  /** Count occurrences of a specific event type. */
  count(eventType: string): number {
    return this.get(eventType).length;
  }

  /** Assert that an event type was fired at least `minCount` times. Throws if not. */
  assertFired(eventType: string, minCount = 1): void {
    const actual = this.count(eventType);
    if (actual < minCount) {
      const seen = this.summary();
      throw new Error(
        `Expected event "${eventType}" to fire at least ${minCount} time(s), ` +
          `but got ${actual}. Events seen: ${JSON.stringify(seen)}`,
      );
    }
  }

  /** Wait for a specific event type to appear (polls every 200ms). */
  async waitFor(eventType: string, timeoutMs = 10000): Promise<CapturedEvent> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const found = this.events.find((e) => e.event_type === eventType);
      if (found) return found;
      await new Promise((r) => setTimeout(r, 200));
    }
    throw new Error(
      `Timed out waiting for event "${eventType}" after ${timeoutMs}ms`,
    );
  }

  /** Grouped count summary: { event_type: count } */
  summary(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const e of this.events) {
      counts[e.event_type] = (counts[e.event_type] || 0) + 1;
    }
    return counts;
  }

  /** Reset collected events. */
  clear(): void {
    this.events = [];
  }
}
