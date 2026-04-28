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

  // Load saved auth state — preserves consent localStorage + cookie banner state.
  // The JWT inside may be expired, so we always re-login below.
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

  // Always do a fresh login to get a new JWT.
  // The saved storageState JWT expires after 15 min (jwt_expiry=900),
  // and registration alone can take 15+ min for 50 users.
  await loginUser(page, user.email, user.password);

  // Now navigate to the starting page with a fresh session
  await page.goto("/products");
  await page.waitForLoadState("domcontentloaded");
  await acceptAllCookies(page);

  return { context, page, collector };
}

export { expect } from "@playwright/test";
