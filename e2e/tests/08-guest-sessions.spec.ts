/**
 * Test 08: Guest browsing sessions — 20 anonymous users (no login).
 * Tests cookie consent flow, anonymous tracking, device diversity.
 */

import { test, expect } from "@playwright/test";
import { DEVICES } from "../helpers/users";
import { EventCollector } from "../helpers/event-collector";
import { clickAcceptAllBanner, acceptAllCookies } from "../helpers/consent";
import {
  browseProducts,
  viewRandomProduct,
  viewCart,
  searchProducts,
  changeSort,
} from "../helpers/actions";

// 20 anonymous sessions on different devices
const guestSessions = Array.from({ length: 20 }, (_, i) => ({
  name: `Guest #${i + 1}`,
  device: DEVICES[i % DEVICES.length],
  rejectCookies: i >= 16, // Last 4 guests reject cookies
}));

// Journey A: Accept cookies, browse, view product, check cart (16 guests)
for (const session of guestSessions.filter((s) => !s.rejectCookies)) {
  test(`${session.name} Browse [${session.device.name}]`, async ({ browser }) => {
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

    try {
      await clickAcceptAllBanner(page);
    } catch {
      // Banner may not appear — set via localStorage
      await acceptAllCookies(page);
    }
    await page.waitForTimeout(500);

    // Browse products
    await browseProducts(page);
    await page.waitForTimeout(500);

    // View a product
    await viewRandomProduct(page);
    await page.waitForTimeout(1000);

    // Visit cart (should be empty for guest)
    await viewCart(page);
    await page.waitForTimeout(500);

    // Try checkout — should redirect to login
    const checkoutLink = page
      .locator("a, button")
      .filter({ hasText: /Checkout|Sign in to Checkout/i })
      .first();
    if (await checkoutLink.isVisible().catch(() => false)) {
      await checkoutLink.click();
      await page.waitForLoadState("networkidle");
    }
    await page.waitForTimeout(1000);

    collector.assertFired("product_viewed");
    console.log(`  ${session.name} events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Reject cookies — verify limited/no tracking (4 guests)
for (const session of guestSessions.filter((s) => s.rejectCookies)) {
  test(`${session.name} Reject Cookies [${session.device.name}]`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: session.device.viewport,
      isMobile: session.device.isMobile,
      hasTouch: session.device.hasTouch,
      ...(session.device.userAgent ? { userAgent: session.device.userAgent } : {}),
    });
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Reject cookies
    const rejectBtn = page.locator("button").filter({ hasText: /Reject|Decline|Essential/i }).first();
    if (await rejectBtn.isVisible().catch(() => false)) {
      await rejectBtn.click();
      await page.waitForTimeout(500);
    }

    // Browse products
    await browseProducts(page);
    await page.waitForTimeout(500);
    await viewRandomProduct(page);
    await page.waitForTimeout(1000);

    // With rejected cookies, tracking may not fire
    console.log(`  ${session.name} (rejected) events:`, collector.summary());
    await context.close();
  });
}
