/**
 * Group 1: Users 001-005 — Window Shoppers
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
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 001: Emma Anderson — Desktop Chrome — 12 pages
// Products → search "premium" → view #0 → back → view #1 → back →
// search "xyznonexistent99" → clear search → view #2 → back →
// homepage → products → view #3 → dashboard/profile
// ────────────────────────────────────────────────────────────────
test("User 001 Emma Anderson — Window Shopper [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[0]; // test001
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing (already on /products from createUserContext)
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: Search "premium"
  await searchProducts(page, "premium");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-premium");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-1");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-to-products-2");

  // Step 7: Search "xyznonexistent99" (no results)
  await searchProducts(page, "xyznonexistent99");
  await page.waitForTimeout(4000);
  await snap(page, "07-search-no-results");

  // Step 8: Clear search
  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "08-clear-search");

  // Step 9: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-2");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-to-products-3");

  // Step 11: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-homepage");

  // Step 12: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-products-again");

  // Step 13: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(4000);
  await snap(page, "13-product-detail-3");

  // Step 14: Dashboard profile
  await visitProfile(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-dashboard-profile");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("001 Emma Anderson");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 002: Liam Martinez — Desktop Large — 13 pages
// Products → sort price_asc → view #0 → back → sort price_desc →
// view #2 → back → sort name → view #4 → back → view #6 →
// back → homepage → dashboard/orders
// ────────────────────────────────────────────────────────────────
test("User 002 Liam Martinez — Window Shopper [Desktop Large]", async ({
  browser,
}) => {
  const user = users[1]; // test002
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Sort by price ascending
  await changeSort(page, "price_asc");
  await page.waitForTimeout(3000);
  await snap(page, "02-sort-price-asc");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: Sort by price descending
  await changeSort(page, "price_desc");
  await page.waitForTimeout(3000);
  await snap(page, "05-sort-price-desc");

  // Step 6: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

  // Step 7: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: Sort by name ascending
  await changeSort(page, "name");
  await page.waitForTimeout(3000);
  await snap(page, "08-sort-name-asc");

  // Step 9: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-4");

  // Step 10: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-6");

  // Step 12: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-4");

  // Step 13: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-homepage");

  // Step 14: Dashboard orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-dashboard-orders");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("002 Liam Martinez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 003: Olivia Thompson — iPhone 13 — 12 pages
// Products → filter category #0 → view #0 → select variant → back →
// view #1 → back → filter category #1 → view #0 → back →
// view #2 → back → dashboard/wishlists
// ────────────────────────────────────────────────────────────────
test("User 003 Olivia Thompson — Window Shopper [iPhone 13]", async ({
  browser,
}) => {
  const user = users[2]; // test003
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

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Select variant
  await selectVariant(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-variant-selected");

  // Step 5: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back");

  // Step 6: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-1");

  // Step 7: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: Filter by category #1
  await filterByNthCategory(page, 1);
  await page.waitForTimeout(4000);
  await snap(page, "08-filter-category-1");

  // Step 9: View product #0 (in new category)
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-0-cat1");

  // Step 10: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-2");

  // Step 12: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-4");

  // Step 13: Dashboard wishlists
  await page.goto("/dashboard/wishlists");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(3000);
  await snap(page, "13-dashboard-wishlists");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("003 Olivia Thompson");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 004: Noah Garcia — Pixel 7 — 13 pages
// Products → view #3 → add wishlist → back → view #5 → add wishlist →
// back → view #7 → back → wishlist page → remove first →
// products → view #9 → dashboard/profile
// ────────────────────────────────────────────────────────────────
test("User 004 Noah Garcia — Window Shopper [Pixel 7]", async ({
  browser,
}) => {
  const user = users[3]; // test004
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-3");

  // Step 3: Add to wishlist
  await addToWishlist(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-wishlist");

  // Step 4: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-5");

  // Step 6: Add to wishlist
  await addToWishlist(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-added-to-wishlist-2");

  // Step 7: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-7");

  // Step 9: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-3");

  // Step 10: Wishlist page
  await viewWishlist(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-wishlist-page");

  // Step 11: Remove first wishlist item
  await removeFromWishlist(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-wishlist-after-remove");

  // Step 12: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-products-again");

  // Step 13: View product #9
  await viewNthProduct(page, 9);
  await page.waitForTimeout(4000);
  await snap(page, "13-product-detail-9");

  // Step 14: Dashboard profile
  await visitProfile(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-dashboard-profile");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("004 Noah Garcia");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 005: Ava Robinson — iPad Pro — 13 pages
// Products → search "pro" → view #0 → back → filter category #0 →
// view #0 → select variant → back → view #1 → back →
// search "bag" → view #0 → back → homepage
// ────────────────────────────────────────────────────────────────
test("User 005 Ava Robinson — Window Shopper [iPad Pro]", async ({
  browser,
}) => {
  const user = users[4]; // test005
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: Search "pro"
  await searchProducts(page, "pro");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-pro");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "05-filter-category-0");

  // Step 6: View product #0 (in category)
  await viewNthProduct(page, 0);
  await page.waitForTimeout(6000);
  await snap(page, "06-product-detail-0-cat");

  // Step 7: Select variant
  await selectVariant(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-variant-selected");

  // Step 8: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-2");

  // Step 9: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-1");

  // Step 10: Back
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: Search "bag"
  await searchProducts(page, "bag");
  await page.waitForTimeout(4000);
  await snap(page, "11-search-bag");

  // Step 12: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "12-product-detail-bag");

  // Step 13: Back
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

  journey.printSummary("005 Ava Robinson");
  await finishJourney(page, context, collector);
});
