/**
 * Test 02: Window Shopper journeys — 30 users who browse but never buy.
 * Search, filter, sort, view products, select variants, use wishlist, logout.
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

for (const user of shoppers) {
  test(`Window Shopper #${user.index} [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // 1. Browse products
    await browseProducts(page);
    await page.waitForTimeout(500);

    // 2. Search for a product
    await searchProducts(page, "premium");
    await page.waitForTimeout(500);

    // 3. Search for gibberish (no results)
    await searchProducts(page, "xyznonexistent99");
    await page.waitForTimeout(500);

    // 4. Clear search and change sort
    await searchProducts(page, "");
    await changeSort(page, "price_asc");
    await page.waitForTimeout(500);

    // 5. Click a category filter
    await filterByCategory(page);
    await page.waitForTimeout(500);

    // 6. View 3 product detail pages
    await browseProducts(page); // Reset to product listing
    for (let i = 0; i < 3; i++) {
      await viewRandomProduct(page);
      await page.waitForTimeout(800);

      // On first product, try selecting a variant
      if (i === 0) {
        await selectVariant(page);
      }

      // On second product, add to wishlist
      if (i === 1) {
        await addToWishlist(page);
      }

      // Go back to products listing
      await browseProducts(page);
    }

    // 7. Visit wishlist
    await viewWishlist(page);
    await page.waitForTimeout(500);

    // 8. Remove from wishlist
    await removeFromWishlist(page);
    await page.waitForTimeout(500);

    // 9. Logout
    await logout(page);
    await page.waitForTimeout(1000);

    // Verify key events fired
    collector.assertFired("product_viewed");
    collector.assertFired("search_performed");

    console.log(`  Shopper #${user.index} events:`, collector.summary());
    await context.close();
  });
}
