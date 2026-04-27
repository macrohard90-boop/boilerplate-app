/**
 * Test 05: Power Buyer journeys — 5 users × 3 journey variants = 15 tests.
 * Multi-item carts, coupons, quantity changes, wishlist, return visits.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  searchProducts,
  filterByCategory,
  viewRandomProduct,
  addToCart,
  viewCart,
  increaseQuantity,
  removeFromCart,
  applyCoupon,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeAndPay,
  waitForConfirmation,
  addToWishlist,
  viewWishlist,
  moveWishlistToCart,
} from "../helpers/actions";

const powerBuyers = getUsersByPersona("power_buyer");

// Journey A: Multi-item + Coupons
for (const user of powerBuyers) {
  test(`Power #${user.index} Multi-item [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    test.setTimeout(120_000);
    const { context, page, collector } = await createUserContext(browser, user);

    // Add 3 items to cart
    await browseProducts(page);
    for (let i = 0; i < 3; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(400);
      await addToCart(page);
      await page.waitForTimeout(400);
      await browseProducts(page);
    }

    await viewCart(page);
    await page.waitForTimeout(500);

    // Change quantity
    await increaseQuantity(page);
    await page.waitForTimeout(400);

    // Remove one item
    await removeFromCart(page);
    await page.waitForTimeout(400);

    // Try invalid coupon
    await applyCoupon(page, "FAKECOUPON999");
    await page.waitForTimeout(500);

    // Try valid coupon
    await applyCoupon(page, "WELCOME10");
    await page.waitForTimeout(500);

    // Full checkout
    try {
      await startCheckout(page);
      await fillShipping(page);
      await advanceCheckoutStep(page);
      await page.waitForTimeout(500);
      await advanceCheckoutStep(page);
      await page.waitForTimeout(500);
      await fillStripeAndPay(page);
      await waitForConfirmation(page);
      await page.waitForTimeout(1000);
    } catch (err) {
      console.log(`  Power #${user.index} Multi checkout failed:`, (err as Error).message);
    }

    collector.assertFired("add_to_cart", 2);
    console.log(`  Power #${user.index} Multi events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Search + Filter + Checkout
for (const user of powerBuyers) {
  test(`Power #${user.index} Search [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    test.setTimeout(120_000);
    const { context, page, collector } = await createUserContext(browser, user);

    // Browse many products
    await browseProducts(page);
    for (let i = 0; i < 5; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(400);
      await browseProducts(page);
    }

    // Search
    await searchProducts(page, "pro");
    await page.waitForTimeout(500);

    // Filter by category
    await filterByCategory(page);
    await page.waitForTimeout(500);

    // Add an item and buy
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(400);
    await addToCart(page);
    await page.waitForTimeout(400);

    await viewCart(page);
    await page.waitForTimeout(500);

    try {
      await startCheckout(page);
      await fillShipping(page);
      await advanceCheckoutStep(page);
      await page.waitForTimeout(500);
      await advanceCheckoutStep(page);
      await page.waitForTimeout(500);
      await fillStripeAndPay(page);
      await waitForConfirmation(page);
    } catch (err) {
      console.log(`  Power #${user.index} Search checkout failed:`, (err as Error).message);
    }

    collector.assertFired("product_viewed", 3);
    console.log(`  Power #${user.index} Search events:`, collector.summary());
    await context.close();
  });
}

// Journey C: Wishlist flow
for (const user of powerBuyers) {
  test(`Power #${user.index} Wishlist [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    test.setTimeout(120_000);
    const { context, page, collector } = await createUserContext(browser, user);

    // Browse and wishlist items
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(400);
    await addToWishlist(page);
    await page.waitForTimeout(400);

    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(400);
    await addToCart(page);
    await page.waitForTimeout(400);

    // Visit wishlist, move to cart
    await viewWishlist(page);
    await page.waitForTimeout(500);
    await moveWishlistToCart(page);
    await page.waitForTimeout(500);

    // Visit cart
    await viewCart(page);
    await page.waitForTimeout(1000);

    collector.assertFired("product_viewed");
    console.log(`  Power #${user.index} Wishlist events:`, collector.summary());
    await context.close();
  });
}
