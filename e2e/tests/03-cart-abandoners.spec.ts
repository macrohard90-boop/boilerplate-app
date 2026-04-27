/**
 * Test 03: Cart Abandoner journeys — 20 users who add to cart but don't finish checkout.
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

for (const user of abandoners) {
  test(`Cart Abandoner #${user.index} [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // 1. Browse products
    await browseProducts(page);
    await page.waitForTimeout(500);

    // 2. View and add first product to cart
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // 3. Go back, view and add second product
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // 4. Visit cart
    await viewCart(page);
    await page.waitForTimeout(500);

    // 5. Change quantity on first item
    await increaseQuantity(page);
    await page.waitForTimeout(500);

    // 6. Start checkout
    try {
      await startCheckout(page);
      await page.waitForTimeout(1000);

      // 7. Abandon — navigate away from checkout
      await page.goto("/products");
      await page.waitForLoadState("networkidle");
    } catch {
      // If checkout redirect fails (e.g., auth issue), that's still an abandonment
      await page.goto("/products");
    }

    await page.waitForTimeout(1500);

    // Verify key events
    collector.assertFired("add_to_cart");
    collector.assertFired("cart_viewed");

    console.log(`  Abandoner #${user.index} events:`, collector.summary());
    await context.close();
  });
}
