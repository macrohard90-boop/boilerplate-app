/**
 * Test 01: Register (or login) all 50 test users + complete consent screen.
 * Runs first (setup project). If user already exists, logs in instead.
 * After login/register, handles the full-page consent screen:
 *   - 48 users: "Accept All & Continue" (full tracking)
 *   - 1 user (009): Custom consent (analytics YES, marketing NO)
 *   - 1 user (050): Reject analytics (no tracking)
 * Saves auth state AFTER consent — journey tests load with consent established.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers, authStatePath } from "../helpers/users";
import { loginUser } from "../helpers/auth";
import { acceptAllCookies } from "../helpers/consent";
import { EventCollector } from "../helpers/event-collector";

/**
 * Consent level per user email.
 * - accept_all: click "Accept All & Continue" (default)
 * - custom: toggle analytics ON, marketing OFF, click "Save Preferences"
 * - reject_analytics: leave everything off, click "Save Preferences"
 */
const CONSENT_CONFIG: Record<
  string,
  "accept_all" | "custom" | "reject_analytics"
> = {
  "adrian+test009@estmgroup.com": "custom", // Mia Walker — analytics yes, marketing no
  "adrian+test050@estmgroup.com": "reject_analytics", // Benjamin Adams — no tracking
};

function getConsentLevel(
  email: string,
): "accept_all" | "custom" | "reject_analytics" {
  return CONSENT_CONFIG[email] ?? "accept_all";
}

const allUsers = getAllUsers();

for (const user of allUsers) {
  test(`Register ${user.persona} #${user.index}: ${user.email}`, async ({
    browser,
  }) => {
    const context = await browser.newContext({
      viewport: user.device.viewport,
      isMobile: user.device.isMobile,
      hasTouch: user.device.hasTouch,
      ...(user.device.userAgent ? { userAgent: user.device.userAgent } : {}),
    });
    const page = await context.newPage();

    const collector = new EventCollector();
    collector.attach(page);

    // Navigate to register page, accept cookie banner via localStorage
    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
    await acceptAllCookies(page);

    // Fill registration form
    await page.locator('input[placeholder="John"]').fill(user.firstName);
    await page.locator('input[placeholder="Doe"]').fill(user.lastName);
    await page
      .locator('input[placeholder="you@example.com"]')
      .fill(user.email);
    await page
      .locator('input[placeholder="Min 8 characters"]')
      .fill(user.password);

    // Submit
    await page.locator('button[type="submit"]').click();

    // Wait for the page to leave /auth/register — either dashboard (new) or error (existing)
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
      // Registration failed (duplicate email, etc.) — try login instead
      const errorText = await page
        .locator('[class*="error"], [class*="Error"], [role="alert"]')
        .first()
        .textContent()
        .catch(() => "unknown error");
      console.log(
        `  ${user.email}: registration error (${errorText}), logging in instead`,
      );
      await loginUser(page, user.email, user.password);
    }

    // At this point we should be logged in — verify by navigating to dashboard.
    // The improved loginUser uses Promise.race (no fixed waits), but double-check.
    const postLoginUrl = page.url();
    if (
      postLoginUrl.includes("/auth/login") ||
      postLoginUrl.includes("/auth/register")
    ) {
      // Session cookie may have been set even if redirect didn't complete
      await page.goto("/dashboard", { timeout: 30000 });
      await page.waitForLoadState("networkidle");
    }

    // Final auth check: verify we're not stuck on an auth page.
    // If still on /auth/login, try one more time — go to dashboard and
    // check for the user avatar (proves authentication).
    const checkUrl = page.url();
    if (
      checkUrl.includes("/auth/login") ||
      checkUrl.includes("/auth/register")
    ) {
      await page.goto("/dashboard", { timeout: 30000 });
      await page.waitForLoadState("networkidle");
      // Wait for auth context to resolve — look for user avatar
      await page
        .locator("div.w-8.h-8.rounded-full")
        .first()
        .waitFor({ state: "visible", timeout: 10000 })
        .catch(() => {});
    }

    // Verify we're authenticated
    const verifyUrl = page.url();
    expect(verifyUrl).not.toContain("/auth/login");
    expect(verifyUrl).not.toContain("/auth/register");

    // Ensure we're on the dashboard — the consent screen only renders there.
    // Registration redirects to /dashboard, but login redirects to / (home page).
    if (!page.url().includes("/dashboard")) {
      await page.goto("/dashboard", { timeout: 30000 });
      await page.waitForLoadState("networkidle");
    }

    // ── Handle consent screen ──
    // The dashboard layout shows a full-page consent screen before the user can access dashboard.
    // For returning users who already consented, this screen is skipped.
    const consentLevel = getConsentLevel(user.email);
    const consentHeading = page.getByText("Your Privacy Preferences");

    // Check if consent screen appears (it won't for returning users with existing consent)
    const consentVisible = await consentHeading
      .waitFor({ timeout: 10000 })
      .then(() => true)
      .catch(() => false);

    if (consentVisible) {
      if (consentLevel === "accept_all") {
        // Click "Accept All & Continue" — grants all 6 consent types
        await page
          .getByRole("button", { name: /Accept All & Continue/i })
          .click();
        console.log(`  ${user.email}: consent = accept_all`);
      } else if (consentLevel === "custom") {
        // Toggle ON: analytics + cookies_analytics (they default to OFF)
        // Find the row containing each label and click its toggle button
        const analyticsRow = page.locator(
          '.flex.items-center.justify-between:has-text("Web Analytics")',
        );
        await analyticsRow.locator("button").click();
        await page.waitForTimeout(300);

        const cookiesAnalyticsRow = page.locator(
          '.flex.items-center.justify-between:has-text("Analytics Cookies")',
        );
        await cookiesAnalyticsRow.locator("button").click();
        await page.waitForTimeout(300);

        // Click "Save Preferences"
        await page
          .getByRole("button", { name: /Save Preferences/i })
          .click();
        console.log(
          `  ${user.email}: consent = custom (analytics YES, marketing NO)`,
        );
      } else {
        // reject_analytics — leave everything at defaults (all OFF except required)
        // Just click "Save Preferences"
        await page
          .getByRole("button", { name: /Save Preferences/i })
          .click();
        console.log(`  ${user.email}: consent = reject_analytics (no tracking)`);
      }

      // Wait for consent to save (POST /gdpr/consent × 6 + POST /gdpr/cookies)
      await page.waitForTimeout(3000);
    } else {
      console.log(
        `  ${user.email}: consent screen not shown (already consented)`,
      );
    }

    // Verify we're past the consent screen
    const finalUrl = page.url();
    expect(finalUrl).not.toContain("/auth/login");
    expect(finalUrl).not.toContain("/auth/register");

    // Re-fire signup_completed now that GDPR consent exists.
    // The original trackEvent during registration was dropped because
    // consent hadn't been given yet.
    await page.evaluate(() => {
      // @ts-ignore — trackEvent is loaded globally by the app
      if (typeof window !== "undefined") {
        fetch("/api/tracking/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            event_type: "signup_completed",
            event_data: { method: "email" },
          }),
        }).catch(() => {});
      }
    });
    await page.waitForTimeout(500);

    // Save auth state (includes cookies, localStorage with consent flags)
    const statePath = authStatePath(user.email);
    await context.storageState({ path: statePath });

    console.log(
      `  ${user.email}: auth state saved (${finalUrl}), events:`,
      collector.summary(),
    );
    await context.close();
  });
}
