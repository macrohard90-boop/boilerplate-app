/**
 * Test 02: Window Shopper journeys — 15 users × 4 journey variants = 60 tests.
 * Browse, search, filter, sort, view products, select variants, wishlist, logout.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  searchProducts,
  changeSort,
  filterByCategory,
  viewRandomProduct,
  selectVariant,
  addToWishlist,
  viewWishlist,
  removeFromWishlist,
  logout,
} from "../helpers/actions";

const shoppers = getUsersByPersona("window_shopper");

// Journey A: Search behavior
for (const user of shoppers) {
  test(`Shopper #${user.index} Search [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await page.waitForTimeout(500);

    // Search for a real term
    await searchProducts(page, "premium");
    await page.waitForTimeout(500);

    // Search for gibberish (no results)
    await searchProducts(page, "xyznonexistent99");
    await page.waitForTimeout(500);

    // Clear search
    await searchProducts(page, "");
    await page.waitForTimeout(500);

    // View a product from results
    await viewRandomProduct(page);
    await page.waitForTimeout(800);

    collector.assertFired("product_viewed");
    console.log(`  Shopper #${user.index} Search events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Sort & Filter
for (const user of shoppers) {
  test(`Shopper #${user.index} Sort & Filter [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await page.waitForTimeout(500);

    // Change sort
    await changeSort(page, "price_asc");
    await page.waitForTimeout(500);

    // Filter by category
    await filterByCategory(page);
    await page.waitForTimeout(500);

    // View a product
    await viewRandomProduct(page);
    await page.waitForTimeout(800);

    // Go back and try another sort
    await browseProducts(page);
    await changeSort(page, "price_desc");
    await page.waitForTimeout(500);

    collector.assertFired("product_viewed");
    console.log(`  Shopper #${user.index} Sort events:`, collector.summary());
    await context.close();
  });
}

// Journey C: Product Detail exploration
for (const user of shoppers) {
  test(`Shopper #${user.index} Browse Products [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);

    // View 3 product detail pages
    for (let i = 0; i < 3; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(800);

      // Select a variant on the first product
      if (i === 0) {
        await selectVariant(page);
      }

      await browseProducts(page);
    }

    collector.assertFired("product_viewed");
    console.log(`  Shopper #${user.index} Browse events:`, collector.summary());
    await context.close();
  });
}

// Journey D: Wishlist & Logout
for (const user of shoppers) {
  test(`Shopper #${user.index} Wishlist [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);

    // Add to wishlist
    await addToWishlist(page);
    await page.waitForTimeout(500);

    // Visit wishlist
    await viewWishlist(page);
    await page.waitForTimeout(500);

    // Remove from wishlist
    await removeFromWishlist(page);
    await page.waitForTimeout(500);

    // Logout
    await logout(page);
    await page.waitForTimeout(1000);

    collector.assertFired("product_viewed");
    console.log(`  Shopper #${user.index} Wishlist events:`, collector.summary());
    await context.close();
  });
}
