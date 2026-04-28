/**
 * Custom Playwright fixtures — extends base `test` with EventCollector and device context.
 */

import { test as base, BrowserContext, Page } from "@playwright/test";
import { existsSync } from "fs";
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

  // Load saved auth state — preserves JWT cookies, refresh token,
  // consent localStorage, and cookie banner state.
  let hasStorageState = false;
  const statePath = authStatePath(user.email);
  if (existsSync(statePath)) {
    contextOptions.storageState = statePath;
    hasStorageState = true;
  }

  if (user.device.userAgent) {
    contextOptions.userAgent = user.device.userAgent;
  }

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  // Attach event collector before navigation so we capture all events
  const collector = new EventCollector();
  collector.attach(page);

  if (hasStorageState) {
    // Skip the login page entirely — go straight to /products.
    // StorageState has auth cookies + refresh token (7-day TTL).
    // The frontend's apiFetch auto-refreshes expired JWTs.
    await page.goto("/products", { timeout: 30000 });
    await page.waitForLoadState("networkidle");

    // Verify we're authenticated by checking for user avatar in header
    const userAvatar = page.locator("div.w-8.h-8.rounded-full").first();
    const isAuthenticated = await userAvatar
      .waitFor({ state: "visible", timeout: 8000 })
      .then(() => true)
      .catch(() => false);

    if (!isAuthenticated) {
      // Session fully expired — fall back to login
      await loginUser(page, user.email, user.password);
      await page.goto("/products", { timeout: 30000 });
      await page.waitForLoadState("networkidle");
    }
  } else {
    // No stored auth — do a fresh login
    await loginUser(page, user.email, user.password);
    await page.goto("/products", { timeout: 30000 });
    await page.waitForLoadState("networkidle");
  }

  await acceptAllCookies(page);

  return { context, page, collector };
}

export { expect } from "@playwright/test";
