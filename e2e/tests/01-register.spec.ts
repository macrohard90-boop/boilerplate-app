/**
 * Test 01: Register all 100 test users.
 * Runs first (setup project). Each user registers via the UI, accepts cookies, and saves auth state.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers, authStatePath } from "../helpers/users";
import { registerUser } from "../helpers/auth";
import { acceptAllCookies } from "../helpers/consent";
import { EventCollector } from "../helpers/event-collector";

const allUsers = getAllUsers();

// Register users in parallel batches — each is an independent test
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

    // Navigate to register page, accept cookies, then fill form
    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
    await acceptAllCookies(page);

    // Register
    await registerUser(page, user);

    // Verify we landed on dashboard
    await expect(page).toHaveURL(/dashboard/);

    // Save auth state for later tests
    const statePath = authStatePath(user.email);
    await context.storageState({ path: statePath });

    // Verify signup event fired
    await page.waitForTimeout(1000);
    collector.assertFired("signup_completed");

    await context.close();
  });
}
