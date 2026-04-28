/**
 * Group 3: Users 011-015 — Window Shoppers
 * Browse, search, filter, NO purchases. 10-13 pages each.
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
  visitHomepage,
  visitDashboard,
  visitProfile,
  visitOrders,
  logout,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 011: Isabella Young — iPad Pro — 13 pages
// Products (5s) → view #0 (5s) → back (3s) → view #1 (5s) → back (3s) →
// view #2 (5s) → back (3s) → view #3 (5s) → back (3s) → view #4 (5s) →
// back (3s) → homepage (4s) → products (3s) → view #5 (5s)
// ────────────────────────────────────────────────────────────────
test("User 011 Isabella Young — Window Shopper [iPad Pro]", async ({
  browser,
}) => {
  const user = users[10]; // test011
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  // Step 6: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-3");

  // Step 8: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-3");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-4");

  // Step 10: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "10-product-detail-4");

  // Step 11: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-back-5");

  // Step 12: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-homepage");

  // Step 13: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-products-again");

  // Step 14: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "14-product-detail-5");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 6);

  // Print summary
  journey.printSummary("011 Isabella Young");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 012: Mason King — Mobile Landscape — 11 pages
// Products (4s) → sort name (3s) → view #0 (5s) → back (3s) →
// filter category #0 (4s) → view #0 (5s) → back (3s) →
// view #1 (5s) → back (3s) → products (3s) →
// view #2 (5s) → dashboard/profile (3s)
// ────────────────────────────────────────────────────────────────
test("User 012 Mason King — Window Shopper [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[11]; // test012
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Sort by name ascending
  await changeSort(page, "name");
  await page.waitForTimeout(3000);
  await snap(page, "02-sort-name-asc");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 6: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "06-filter-category-0");

  // Step 7: View product #0 (in category)
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-0-cat");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-2");

  // Step 9: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-1");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  // Step 11: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-products-again");

  // Step 12: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "12-product-detail-2");

  // Step 13: Dashboard profile
  await visitProfile(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-dashboard-profile");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("012 Mason King");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 013: Charlotte Wright — Desktop Chrome — 10 pages
// Products (5s) → view #1 (5s) → back (3s) → view #2 (5s) →
// back (3s) → view #3 (5s) → back (3s) → products (3s) →
// homepage (4s) → logout (3s)
// ────────────────────────────────────────────────────────────────
test("User 013 Charlotte Wright — Window Shopper [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[12]; // test013
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-1");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-2");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  // Step 6: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-3");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-3");

  // Step 8: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-products-again");

  // Step 9: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "09-homepage");

  // Step 10: Logout
  await logout(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-logged-out");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("013 Charlotte Wright");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 014: Logan Lopez — Desktop Large — 12 pages
// Products (4s) → search "xyznothing" (4s) → clear search (3s) →
// search "pro" (4s) → view #0 (5s) → back (3s) → filter category #0 (4s) →
// view #1 (5s) → back (3s) → sort price_asc (3s) → view #0 (5s) →
// back (3s) → homepage (4s) → dashboard/orders (3s)
// ────────────────────────────────────────────────────────────────
test("User 014 Logan Lopez — Window Shopper [Desktop Large]", async ({
  browser,
}) => {
  const user = users[13]; // test014
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Search "xyznothing" (no results)
  await searchProducts(page, "xyznothing");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-no-results");

  // Step 3: Clear search
  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "03-clear-search");

  // Step 4: Search "pro"
  await searchProducts(page, "pro");
  await page.waitForTimeout(4000);
  await snap(page, "04-search-pro");

  // Step 5: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-0");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back");

  // Step 7: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "07-filter-category-0");

  // Step 8: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-1");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-2");

  // Step 10: Sort by price ascending
  await changeSort(page, "price_asc");
  await page.waitForTimeout(3000);
  await snap(page, "10-sort-price-asc");

  // Step 11: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-0-sorted");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-3");

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

  // Print summary
  journey.printSummary("014 Logan Lopez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 015: Amelia Hill — iPhone 13 — 12 pages
// Products (5s) → view #5 (5s) → select variant (3s) → back (3s) →
// sort price_desc (3s) → view #0 (5s) → back (3s) → view #11 (5s) →
// back (3s) → homepage (4s) → products (3s) → view #12 (5s) → logout (3s)
// ────────────────────────────────────────────────────────────────
test("User 015 Amelia Hill — Window Shopper [iPhone 13]", async ({
  browser,
}) => {
  const user = users[14]; // test015
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-5");

  // Step 3: Select variant
  await selectVariant(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-variant-selected");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: Sort by price descending
  await changeSort(page, "price_desc");
  await page.waitForTimeout(3000);
  await snap(page, "05-sort-price-desc");

  // Step 6: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-0");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  // Step 8: View product #11
  await viewNthProduct(page, 11);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-11");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-3");

  // Step 10: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-homepage");

  // Step 11: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-products-again");

  // Step 12: View product #12
  await viewNthProduct(page, 12);
  await page.waitForTimeout(5000);
  await snap(page, "12-product-detail-12");

  // Step 13: Logout
  await logout(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-logged-out");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);

  // Print summary
  journey.printSummary("015 Amelia Hill");
  await finishJourney(page, context, collector);
});
