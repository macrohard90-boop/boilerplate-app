/**
 * Test 01: Register (or login) all 50 test users.
 * Runs first (setup project). If user already exists, logs in instead.
 * Saves auth state for later tests.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers, authStatePath } from "../helpers/users";
import { loginUser } from "../helpers/auth";
import { acceptAllCookies } from "../helpers/consent";
import { EventCollector } from "../helpers/event-collector";

const allUsers = getAllUsers();

for (const user of allUsers) {
  test(`Register ${user.persona} #${user.index}: ${user.email}`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: user.device.viewport,
      isMobile: user.device.isMobile,
      hasTouch: user.device.hasTouch,
      ...(user.device.userAgent ? { userAgent: user.device.userAgent } : {}),
    });
    const page = await context.newPage();

    const collector = new EventCollector();
    collector.attach(page);

    // Navigate to register page, accept cookies
    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
    await acceptAllCookies(page);

    // Fill registration form
    await page.locator('input[placeholder="John"]').fill(user.firstName);
    await page.locator('input[placeholder="Doe"]').fill(user.lastName);
    await page.locator('input[placeholder="you@example.com"]').fill(user.email);
    await page.locator('input[placeholder="Min 8 characters"]').fill(user.password);

    // Submit
    await page.locator('button[type="submit"]').click();

    // Wait for either dashboard redirect (success) or error message (already registered)
    const result = await Promise.race([
      page.waitForURL("**/dashboard**", { timeout: 15000 }).then(() => "registered" as const),
      page.locator("text=Email already registered").waitFor({ state: "visible", timeout: 15000 }).then(() => "exists" as const),
      page.locator("text=already exists").waitFor({ state: "visible", timeout: 15000 }).then(() => "exists" as const),
    ]).catch(() => "timeout" as const);

    if (result === "exists" || result === "timeout") {
      // User already registered — login instead
      console.log(`  ${user.email}: already registered, logging in`);
      await loginUser(page, user.email, user.password);
    }

    // Should be on dashboard now (either from register or login)
    await page.waitForTimeout(1000);
    expect(page.url()).toMatch(/dashboard|products/);

    // Save auth state for later tests
    const statePath = authStatePath(user.email);
    await context.storageState({ path: statePath });

    console.log(`  ${user.email}: auth state saved, events:`, collector.summary());
    await context.close();
  });
}
