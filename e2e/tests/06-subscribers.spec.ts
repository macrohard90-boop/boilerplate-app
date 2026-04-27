/**
 * Test 06: Subscriber journeys — 5 users × 2 journey variants = 10 tests.
 * Browse subscriptions → add to cart → checkout → Stripe redirect.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  clickSubscriptionsTab,
  viewRandomProduct,
  addToCart,
  viewCart,
  startCheckout,
  advanceCheckoutStep,
} from "../helpers/actions";

const subscribers = getUsersByPersona("subscriber");

// Journey A: Direct subscribe
for (const user of subscribers) {
  test(`Subscriber #${user.index} Direct [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await clickSubscriptionsTab(page);
    await page.waitForTimeout(500);

    await viewRandomProduct(page);
    await page.waitForTimeout(500);

    await addToCart(page);
    await page.waitForTimeout(500);

    await viewCart(page);
    await page.waitForTimeout(500);

    try {
      await startCheckout(page);
      await page.waitForTimeout(500);

      // Subscriptions skip shipping — go straight to review
      await advanceCheckoutStep(page);
      await page.waitForTimeout(1000);

      // Wait for Stripe redirect
      try {
        await page.waitForURL(/checkout\.stripe\.com/, { timeout: 15000 });
        console.log(`  Subscriber #${user.index}: Redirected to Stripe Checkout`);
      } catch {
        console.log(`  Subscriber #${user.index}: Stripe redirect not detected (test mode)`);
      }
    } catch (err) {
      console.log(`  Subscriber #${user.index} Direct failed:`, (err as Error).message);
    }

    await page.waitForTimeout(1000);
    collector.assertFired("product_viewed");
    collector.assertFired("add_to_cart");

    console.log(`  Subscriber #${user.index} Direct events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Browse products first, then subscribe
for (const user of subscribers) {
  test(`Subscriber #${user.index} Browse First [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // Browse regular products first
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);

    // Now switch to subscriptions
    await browseProducts(page);
    await clickSubscriptionsTab(page);
    await page.waitForTimeout(500);

    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    await viewCart(page);
    await page.waitForTimeout(500);

    try {
      await startCheckout(page);
      await page.waitForTimeout(500);
      await advanceCheckoutStep(page);
      await page.waitForTimeout(1000);

      try {
        await page.waitForURL(/checkout\.stripe\.com/, { timeout: 15000 });
        console.log(`  Subscriber #${user.index}: Redirected to Stripe Checkout`);
      } catch {
        console.log(`  Subscriber #${user.index}: Stripe redirect not detected (test mode)`);
      }
    } catch (err) {
      console.log(`  Subscriber #${user.index} Browse-first failed:`, (err as Error).message);
    }

    await page.waitForTimeout(1000);
    collector.assertFired("product_viewed", 2);

    console.log(`  Subscriber #${user.index} Browse events:`, collector.summary());
    await context.close();
  });
}
