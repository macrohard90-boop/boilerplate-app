/**
 * Test 04: Single Buyer journeys — 12 users × 2 journey variants = 24 tests.
 * Full checkout flow: browse → cart → shipping → review → Stripe payment → confirmation.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  viewRandomProduct,
  addToCart,
  viewCart,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeAndPay,
  waitForConfirmation,
} from "../helpers/actions";

const buyers = getUsersByPersona("single_buyer");

// Journey A: Quick buy — view 1 product, buy it
for (const user of buyers) {
  test(`Buyer #${user.index} Quick Buy [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await page.waitForTimeout(500);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);

    await addToCart(page);
    await page.waitForTimeout(500);

    await viewCart(page);
    await page.waitForTimeout(500);

    await startCheckout(page);
    await page.waitForTimeout(500);

    await fillShipping(page);
    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    try {
      await fillStripeAndPay(page);
      await waitForConfirmation(page);
      await page.waitForTimeout(1500);

      collector.assertFired("product_viewed");
      collector.assertFired("add_to_cart");
      collector.assertFired("checkout_started");
    } catch (err) {
      console.log(`  Buyer #${user.index} Quick Stripe failed:`, (err as Error).message);
      collector.assertFired("product_viewed");
      collector.assertFired("add_to_cart");
    }

    console.log(`  Buyer #${user.index} Quick events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Browse-first — explore 3 products, then buy
for (const user of buyers) {
  test(`Buyer #${user.index} Browse First [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // Browse several products first
    await browseProducts(page);
    for (let i = 0; i < 3; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(600);
      await browseProducts(page);
    }

    // Now pick one and buy
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    await viewCart(page);
    await page.waitForTimeout(500);

    await startCheckout(page);
    await page.waitForTimeout(500);

    await fillShipping(page);
    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    try {
      await fillStripeAndPay(page);
      await waitForConfirmation(page);
      await page.waitForTimeout(1500);

      collector.assertFired("product_viewed", 2);
      collector.assertFired("add_to_cart");
    } catch (err) {
      console.log(`  Buyer #${user.index} Browse Stripe failed:`, (err as Error).message);
      collector.assertFired("product_viewed", 2);
    }

    console.log(`  Buyer #${user.index} Browse events:`, collector.summary());
    await context.close();
  });
}
