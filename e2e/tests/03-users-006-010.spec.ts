/**
 * Group 2: Users 006-010 — Window Shoppers
 * Browse, search, filter, wishlist, NO purchases. 12-13 pages each.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { EventCollector } from "../helpers/event-collector";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import {
  browseProducts,
  searchProducts,
  viewNthProduct,
  backToProducts,
  filterByNthCategory,
  resetCategoryFilter,
  changeSort,
  selectVariant,
  addToWishlist,
  removeFromWishlist,
  viewWishlist,
  visitHomepage,
  visitDashboard,
  visitProfile,
  visitOrders,
  visitPrivacy,
  logout,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 006: James Clark — Mobile Landscape — 12 pages
// Products → view #6 → back → sort price_asc → view #0 → back →
// view #7 → back → view #8 → back → homepage → products → logout
// ────────────────────────────────────────────────────────────────
test("User 006 James Clark — Window Shopper [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[5]; // test006
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing (already on /products from createUserContext)
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-6");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: Sort by price ascending
  await changeSort(page, "price_asc");
  await page.waitForTimeout(3000);
  await snap(page, "04-sort-price-asc");

  // Step 5: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-0");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  // Step 7: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-7");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-3");

  // Step 9: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-8");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-4");

  // Step 11: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-homepage");

  // Step 12: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-products-again");

  // Step 13: Logout
  await logout(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-logout");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);

  journey.printSummary("006 James Clark");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 007: Sophia Rodriguez — Desktop Chrome — 13 pages
// Products → search "xyznothing" → clear search → sort name →
// view #0 → back → view #1 → back → view #2 → back →
// view #3 → back → homepage → dashboard/profile
// ────────────────────────────────────────────────────────────────
test("User 007 Sophia Rodriguez — Window Shopper [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[6]; // test007
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: Search "xyznothing" (no results)
  await searchProducts(page, "xyznothing");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-no-results");

  // Step 3: Clear search
  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "03-clear-search");

  // Step 4: Sort by name ascending
  await changeSort(page, "name");
  await page.waitForTimeout(3000);
  await snap(page, "04-sort-name-asc");

  // Step 5: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-0");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back");

  // Step 7: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-1");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-2");

  // Step 9: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-2");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-3");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-4");

  // Step 13: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-homepage");

  // Step 14: Dashboard profile
  await visitProfile(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-dashboard-profile");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);

  journey.printSummary("007 Sophia Rodriguez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 008: Lucas Lewis — Desktop Large — 12 pages
// Products → view #8 → add wishlist → back → view #9 → add wishlist →
// back → view #10 → back → wishlist page → products → dashboard/orders
// ────────────────────────────────────────────────────────────────
test("User 008 Lucas Lewis — Window Shopper [Desktop Large]", async ({
  browser,
}) => {
  const user = users[7]; // test008
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-8");

  // Step 3: Add to wishlist
  await addToWishlist(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-wishlist");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: View product #9
  await viewNthProduct(page, 9);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-9");

  // Step 6: Add to wishlist
  await addToWishlist(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-added-to-wishlist-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: View product #10
  await viewNthProduct(page, 10);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-10");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-3");

  // Step 10: Wishlist page
  await viewWishlist(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-wishlist-page");

  // Step 11: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-products-again");

  // Step 12: Dashboard orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-dashboard-orders");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("008 Lucas Lewis");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 009: Mia Walker — iPhone 13 — 13 pages
// Products → filter category #0 → sort price_desc → view #0 →
// select variant → back → view #1 → back → view #2 → back →
// search "premium" → view #0 → back → homepage
// (custom consent user, but tracking still works)
// ────────────────────────────────────────────────────────────────
test("User 009 Mia Walker — Window Shopper [iPhone 13]", async ({
  browser,
}) => {
  const user = users[8]; // test009
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-filter-category-0");

  // Step 3: Sort by price descending
  await changeSort(page, "price_desc");
  await page.waitForTimeout(3000);
  await snap(page, "03-sort-price-desc");

  // Step 4: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-0");

  // Step 5: Select variant
  await selectVariant(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-variant-selected");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back");

  // Step 7: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-1");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-2");

  // Step 9: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-2");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: Search "premium"
  await searchProducts(page, "premium");
  await page.waitForTimeout(4000);
  await snap(page, "11-search-premium");

  // Step 12: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "12-product-detail-premium");

  // Step 13: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-back-4");

  // Step 14: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "14-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("009 Mia Walker");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 010: Ethan Hall — Pixel 7 — 13 pages
// Products → search "shirt" → view #0 → back → search "premium" →
// view #0 → back → clear search → view #10 → back →
// view #11 → back → homepage → dashboard/profile
// ────────────────────────────────────────────────────────────────
test("User 010 Ethan Hall — Window Shopper [Pixel 7]", async ({
  browser,
}) => {
  const user = users[9]; // test010
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Search "shirt"
  await searchProducts(page, "shirt");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-shirt");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: Search "premium"
  await searchProducts(page, "premium");
  await page.waitForTimeout(4000);
  await snap(page, "05-search-premium");

  // Step 6: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-premium");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: Clear search
  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "08-clear-search");

  // Step 9: View product #10
  await viewNthProduct(page, 10);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-10");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: View product #11
  await viewNthProduct(page, 11);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-11");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-4");

  // Step 13: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-homepage");

  // Step 14: Dashboard profile
  await visitProfile(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-dashboard-profile");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);

  journey.printSummary("010 Ethan Hall");
  await finishJourney(page, context, collector);
});
