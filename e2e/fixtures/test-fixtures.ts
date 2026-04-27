/**
 * Custom Playwright fixtures — extends base `test` with EventCollector and device context.
 */

import { test as base, BrowserContext, Page } from "@playwright/test";
import { EventCollector } from "../helpers/event-collector";
import { TestUser, DEVICES, authStatePath } from "../helpers/users";
import { acceptAllCookies } from "../helpers/consent";

/** Extended test with event collector fixture. */
export const test = base.extend<{
  eventCollector: EventCollector;
}>({
  eventCollector: async ({ page }, use) => {
    const collector = new EventCollector();
    collector.attach(page);
    await use(collector);
  },
});

/** Create a browser context for a specific test user (loads auth + device). */
export async function createUserContext(
  browser: import("@playwright/test").Browser,
  user: TestUser,
): Promise<{ context: BrowserContext; page: Page; collector: EventCollector }> {
  const contextOptions: Record<string, unknown> = {
    viewport: user.device.viewport,
    isMobile: user.device.isMobile,
    hasTouch: user.device.hasTouch,
  };

  // Load saved auth state if it exists
  try {
    const path = authStatePath(user.email);
    contextOptions.storageState = path;
  } catch {
    // No auth state saved yet — that's fine for registration
  }

  if (user.device.userAgent) {
    contextOptions.userAgent = user.device.userAgent;
  }

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  // Accept cookies via localStorage before any navigation
  await page.goto("about:blank");
  await acceptAllCookies(page);

  // Attach event collector
  const collector = new EventCollector();
  collector.attach(page);

  return { context, page, collector };
}

export { expect } from "@playwright/test";
