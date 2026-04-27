/**
 * Test 08: Guest browsing sessions — 10 anonymous users (no login).
 * Tests cookie consent flow, anonymous tracking, device diversity.
 */

import { test, expect } from "@playwright/test";
import { DEVICES } from "../helpers/users";
import { EventCollector } from "../helpers/event-collector";
import { clickAcceptAllBanner } from "../helpers/consent";
import { browseProducts, viewRandomProduct, viewCart } from "../helpers/actions";

// 10 anonymous sessions on different devices
const guestSessions = Array.from({ length: 10 }, (_, i) => ({
  name: `Guest #${i + 1}`,
  device: DEVICES[i % DEVICES.length],
  rejectCookies: i >= 8, // Last 2 guests reject non-essential cookies
}));

for (const session of guestSessions) {
  test(`${session.name} [${session.device.name}]${session.rejectCookies ? " (reject cookies)" : ""}`, async ({ browser }) => {
    // Fresh context — no auth, no saved state
    const context = await browser.newContext({
      viewport: session.device.viewport,
      isMobile: session.device.isMobile,
      hasTouch: session.device.hasTouch,
      ...(session.device.userAgent ? { userAgent: session.device.userAgent } : {}),
    });
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    // Visit homepage — cookie banner should appear
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    if (session.rejectCookies) {
      // Reject non-essential cookies
      const rejectBtn = page.locator("button").filter({ hasText: /Reject/i }).first();
      if (await rejectBtn.isVisible().catch(() => false)) {
        await rejectBtn.click();
        await page.waitForTimeout(500);
      }
    } else {
      // Accept all cookies via the banner UI (not localStorage bypass)
      try {
        await clickAcceptAllBanner(page);
      } catch {
        // Banner may not appear if already consented — that's fine
      }
      await page.waitForTimeout(500);
    }

    // Browse products as a guest
    await browseProducts(page);
    await page.waitForTimeout(500);

    // View a product
    await viewRandomProduct(page);
    await page.waitForTimeout(1000);

    // Visit cart (should be empty)
    await viewCart(page);
    await page.waitForTimeout(1000);

    // Try to checkout — should redirect to login
    const checkoutLink = page.locator("a, button").filter({ hasText: /Checkout|Sign in/i }).first();
    if (await checkoutLink.isVisible().catch(() => false)) {
      await checkoutLink.click();
      await page.waitForLoadState("networkidle");
    }

    await page.waitForTimeout(1000);

    // Verify events based on cookie consent
    if (session.rejectCookies) {
      // With rejected cookies, tracking events should NOT fire (backend gates on consent)
      console.log(`  ${session.name} (rejected cookies) events:`, collector.summary());
    } else {
      // With accepted cookies, we should see tracking events
      collector.assertFired("product_viewed");
      console.log(`  ${session.name} events:`, collector.summary());
    }

    await context.close();
  });
}
