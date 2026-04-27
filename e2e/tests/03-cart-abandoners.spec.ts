/**
 * Test 03: Cart Abandoner journeys — 10 users × 2 journey variants = 20 tests.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  viewRandomProduct,
  addToCart,
  viewCart,
  increaseQuantity,
  startCheckout,
} from "../helpers/actions";

const abandoners = getUsersByPersona("cart_abandoner");

// Journey A: Quick abandon — add 1 item, view cart, leave
for (const user of abandoners) {
  test(`Abandoner #${user.index} Quick [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await page.waitForTimeout(500);

    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // Visit cart then leave
    await viewCart(page);
    await page.waitForTimeout(500);

    // Abandon — navigate away
    await page.goto("/products");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    collector.assertFired("add_to_cart");
    console.log(`  Abandoner #${user.index} Quick events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Deep abandon — multiple items, qty change, start checkout, abandon
for (const user of abandoners) {
  test(`Abandoner #${user.index} Deep [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // Add first product
    await browseProducts(page);
    await page.waitForTimeout(500);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // Add second product
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // Visit cart
    await viewCart(page);
    await page.waitForTimeout(500);

    // Change quantity
    await increaseQuantity(page);
    await page.waitForTimeout(500);

    // Start checkout then abandon
    try {
      await startCheckout(page);
      await page.waitForTimeout(1000);
      await page.goto("/products");
      await page.waitForLoadState("networkidle");
    } catch {
      await page.goto("/products");
    }

    await page.waitForTimeout(1500);

    collector.assertFired("add_to_cart");
    console.log(`  Abandoner #${user.index} Deep events:`, collector.summary());
    await context.close();
  });
}
