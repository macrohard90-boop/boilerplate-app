/**
 * Test 05: Power Buyer journeys — 10 users with extensive interaction.
 * Browse many products, search, filter, multi-item cart, coupons, checkout, wishlist.
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

for (const user of powerBuyers) {
  test(`Power Buyer #${user.index} [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    test.setTimeout(120_000); // Power buyers take longer
    const { context, page, collector } = await createUserContext(browser, user);

    // 1. Browse many products (5+)
    await browseProducts(page);
    for (let i = 0; i < 5; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(600);

      // Add to wishlist on one product
      if (i === 2) {
        await addToWishlist(page);
      }

      await browseProducts(page);
    }

    // 2. Search
    await searchProducts(page, "pro");
    await page.waitForTimeout(500);

    // 3. Filter by category
    await filterByCategory(page);
    await page.waitForTimeout(500);

    // 4. Add 3 items to cart
    await browseProducts(page);
    for (let i = 0; i < 3; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(400);
      await addToCart(page);
      await page.waitForTimeout(400);
      await browseProducts(page);
    }

    // 5. View cart
    await viewCart(page);
    await page.waitForTimeout(500);

    // 6. Change quantity
    await increaseQuantity(page);
    await page.waitForTimeout(400);

    // 7. Remove one item
    await removeFromCart(page);
    await page.waitForTimeout(400);

    // 8. Try invalid coupon
    await applyCoupon(page, "FAKECOUPON999");
    await page.waitForTimeout(500);

    // 9. Try valid coupon (from Phase 2 setup — common codes)
    await applyCoupon(page, "WELCOME10");
    await page.waitForTimeout(500);

    // 10. Checkout
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
      console.log(`  Power #${user.index} checkout failed:`, (err as Error).message);
    }

    // 11. After purchase — visit wishlist, move to cart
    await viewWishlist(page);
    await page.waitForTimeout(500);
    await moveWishlistToCart(page);
    await page.waitForTimeout(500);

    // 12. Visit cart (may be empty after purchase cleared it)
    await viewCart(page);
    await page.waitForTimeout(1000);

    // Verify key events
    collector.assertFired("product_viewed", 3);
    collector.assertFired("add_to_cart", 2);
    collector.assertFired("search_performed");

    console.log(`  Power #${user.index} events:`, collector.summary());
    await context.close();
  });
}
