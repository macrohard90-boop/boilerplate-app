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

    // Wait for the page to leave /auth/register — either dashboard (new user) or error (existing)
    // Give it 30s since the VM is slow under 6 concurrent registrations + Brevo emails
    try {
      await page.waitForURL(
        (url) => !url.pathname.includes("/auth/register"),
        { timeout: 30000 },
      );
    } catch {
      // Still on register page — check if there's an error message
    }

    const currentUrl = page.url();

    if (currentUrl.includes("/auth/register")) {
      // Registration failed (duplicate email, validation error, etc.) — try login
      const errorText = await page.locator('[class*="error"], [class*="Error"], [role="alert"]')
        .first()
        .textContent()
        .catch(() => "unknown error");
      console.log(`  ${user.email}: registration error (${errorText}), logging in instead`);
      await loginUser(page, user.email, user.password);
    }

    // At this point we should be logged in — either from register redirect or login
    // Wait for page to settle
    await page.waitForTimeout(2000);

    // Verify we're authenticated by checking we're not on an auth page
    const finalUrl = page.url();
    expect(finalUrl).not.toContain("/auth/login");
    expect(finalUrl).not.toContain("/auth/register");

    // Save auth state for later tests
    const statePath = authStatePath(user.email);
    await context.storageState({ path: statePath });

    console.log(`  ${user.email}: auth state saved (${finalUrl}), events:`, collector.summary());
    await context.close();
  });
}
