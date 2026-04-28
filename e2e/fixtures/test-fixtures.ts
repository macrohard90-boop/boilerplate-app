/**
 * Custom Playwright fixtures — extends base `test` with EventCollector and device context.
 */

import { test as base, BrowserContext, Page } from "@playwright/test";
import { EventCollector } from "../helpers/event-collector";
import { TestUser, DEVICES, authStatePath } from "../helpers/users";
import { loginUser } from "../helpers/auth";
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

  // Attach event collector before navigation so we capture all events
  const collector = new EventCollector();
  collector.attach(page);

  // Navigate to the site, then accept cookies via localStorage
  await page.goto("/products");
  await page.waitForLoadState("domcontentloaded");
  await acceptAllCookies(page);

  // If JWT expired and we got redirected to login, re-authenticate
  if (page.url().includes("/auth/login") || page.url().includes("/auth/register")) {
    await loginUser(page, user.email, user.password);
    await page.goto("/products");
    await page.waitForLoadState("domcontentloaded");
  }

  return { context, page, collector };
}

export { expect } from "@playwright/test";
