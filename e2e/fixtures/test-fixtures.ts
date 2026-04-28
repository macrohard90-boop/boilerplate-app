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

/**
 * Call POST /auth/refresh and seed sessionStorage with the resulting tokens.
 * Must be called while on a page with the correct origin (so cookies are sent).
 * Retries up to `maxRetries` times with a delay between attempts.
 * Returns true if refresh succeeded.
 */
async function seedSessionTokens(page: Page, maxRetries = 2): Promise<boolean> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const ok = await page.evaluate(async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) return false;
        const data = await res.json();
        if (data.access_token) {
          sessionStorage.setItem("access_token", data.access_token);
        }
        if (data.csrf_token) {
          sessionStorage.setItem("csrf_token", data.csrf_token);
        }
        return true;
      } catch {
        return false;
      }
    });
    if (ok) return true;
    if (attempt < maxRetries) {
      console.log(`  seedSessionTokens attempt ${attempt} failed, retrying...`);
      await page.waitForTimeout(1000);
    }
  }
  return false;
}

/** Navigate to /products and wait for it to be interactive. Retries once on failure. */
async function gotoProducts(page: Page): Promise<void> {
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      await page.goto("/products", { timeout: 30000 });
      await page.waitForLoadState("domcontentloaded");
      // Wait for either product cards or "No products found" to confirm the page rendered
      await page
        .locator('a[href*="/products/"], [class*="text-center"]')
        .first()
        .waitFor({ state: "visible", timeout: 15000 });
      return;
    } catch (err) {
      if (attempt === 2) throw err;
      console.log(
        `  Products page load failed (attempt ${attempt}), retrying...`,
      );
      await page.waitForTimeout(2000);
    }
  }
}

/**
 * Perform a fresh login, ensure sessionStorage has tokens, navigate to /products.
 *
 * After loginUser, React's auth-context on the redirected page will call
 * POST /auth/refresh itself, rotating the token and seeding sessionStorage.
 * We wait for that to happen rather than competing with a second refresh call.
 */
async function freshLoginAndSeed(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await loginUser(page, email, password);

  // Wait for React's auth-context to finish its own refresh cycle.
  // It stores access_token in sessionStorage once it gets a valid response.
  for (let i = 0; i < 10; i++) {
    const hasToken = await page.evaluate(
      () => !!sessionStorage.getItem("access_token"),
    );
    if (hasToken) break;
    await page.waitForTimeout(500);
  }

  // If React didn't seed it (e.g. page landed somewhere unexpected), do it ourselves
  const hasToken = await page.evaluate(
    () => !!sessionStorage.getItem("access_token"),
  );
  if (!hasToken) {
    const seeded = await seedSessionTokens(page);
    if (!seeded) {
      console.log(
        `  WARNING: could not seed sessionStorage for ${email} — continuing anyway`,
      );
    }
  }

  await gotoProducts(page);
}

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
  } else {
    console.log(
      `  WARNING: No auth state file for ${user.email} — will login fresh`,
    );
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
    // StorageState includes cookies (refresh token) and localStorage (consent),
    // but NOT sessionStorage (access token). We must obtain an access token
    // BEFORE navigating to any page — otherwise the auth-context's async
    // refresh races against the dashboard layout's auth guard, causing
    // intermittent redirects to /auth/login.
    //
    // Strategy: navigate to a minimal page (about:blank won't have cookies),
    // so we go to the base URL, call POST /auth/refresh, and seed
    // sessionStorage with the tokens. Then navigate to /products.
    await page.goto("/", { waitUntil: "commit" });
    const refreshed = await seedSessionTokens(page);

    if (refreshed) {
      await gotoProducts(page);
    } else {
      // Refresh token expired — fall back to fresh login
      console.log(
        `  ${user.email}: stored refresh token expired, logging in fresh`,
      );
      await freshLoginAndSeed(page, user.email, user.password);
    }
  } else {
    // No stored auth — do a fresh login
    await freshLoginAndSeed(page, user.email, user.password);
  }

  await acceptAllCookies(page);

  return { context, page, collector };
}

export { expect } from "@playwright/test";
