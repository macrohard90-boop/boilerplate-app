/**
 * Test 12: Guest (anonymous) sessions — 10 explicit unauthenticated browsing sessions.
 * These users are NOT logged in. They browse products, search, filter, and leave.
 * Tests that tracking works for anonymous visitors (no user_id, session-based only).
 */

import { test, expect } from "@playwright/test";
import { EventCollector } from "../helpers/event-collector";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import { acceptAllCookies } from "../helpers/consent";
import {
  browseProducts,
  searchProducts,
  viewNthProduct,
  backToProducts,
  filterByNthCategory,
  changeSort,
  selectVariant,
  visitHomepage,
} from "../helpers/actions";

/** Create a fresh anonymous browser context (no auth state). */
async function createGuestContext(
  browser: import("@playwright/test").Browser,
  viewport = { width: 1280, height: 720 },
) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const collector = new EventCollector();
  collector.attach(page);

  // Navigate and accept cookies via localStorage
  await page.goto("/products");
  await page.waitForLoadState("networkidle");
  await acceptAllCookies(page);

  return { context, page, collector };
}

// ────────────────────────────────────────────────────────────────
// Guest 01: Desktop — Browse products, view 3 products, homepage
// ────────────────────────────────────────────────────────────────
test("Guest 01 — Browse and view products [Desktop]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser);
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-3");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-homepage");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 01");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 02: Desktop — Search then browse
// ────────────────────────────────────────────────────────────────
test("Guest 02 — Search products [Desktop]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser);
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await searchProducts(page, "premium");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-premium");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "05-clear-search");

  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-3");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-homepage");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 02");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 03: Mobile — Filter by category
// ────────────────────────────────────────────────────────────────
test("Guest 03 — Filter by category [Mobile]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser, {
    width: 390,
    height: 844,
  });
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-filter-category-0");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  await filterByNthCategory(page, 1);
  await page.waitForTimeout(4000);
  await snap(page, "07-filter-category-1");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-0-cat1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-3");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 03");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 04: Desktop — Sort products
// ────────────────────────────────────────────────────────────────
test("Guest 04 — Sort products [Desktop]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser);
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await changeSort(page, "price_asc");
  await page.waitForTimeout(3000);
  await snap(page, "02-sort-price-asc");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await changeSort(page, "price_desc");
  await page.waitForTimeout(3000);
  await snap(page, "05-sort-price-desc");

  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-homepage");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 04");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 05: Mobile — Quick browse (bouncer-like)
// ────────────────────────────────────────────────────────────────
test("Guest 05 — Quick browse [Mobile]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser, {
    width: 412,
    height: 915,
  });
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "04-homepage");

  journey.printSummary("Guest 05");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 06: Desktop — Search with no results then browse
// ────────────────────────────────────────────────────────────────
test("Guest 06 — Search no results [Desktop]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser);
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await searchProducts(page, "xyznonexistent99");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-no-results");

  await searchProducts(page, "");
  await page.waitForTimeout(3000);
  await snap(page, "03-clear-search");

  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-4");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back");

  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-5");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-homepage");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 06");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 07: Tablet — Browse and select variant
// ────────────────────────────────────────────────────────────────
test("Guest 07 — Browse with variant [Tablet]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser, {
    width: 1024,
    height: 1366,
  });
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  await selectVariant(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-variant-selected");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-2");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-4");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-3");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "09-homepage");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 07");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 08: Mobile — Multiple category filters
// ────────────────────────────────────────────────────────────────
test("Guest 08 — Multiple categories [Mobile]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser, {
    width: 390,
    height: 844,
  });
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-filter-category-0");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0-cat0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await filterByNthCategory(page, 1);
  await page.waitForTimeout(4000);
  await snap(page, "05-filter-category-1");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-0-cat1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-2");

  await filterByNthCategory(page, 2);
  await page.waitForTimeout(4000);
  await snap(page, "08-filter-category-2");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-0-cat2");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-3");

  journey.assertMinVisits(6);
  journey.printSummary("Guest 08");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 09: Desktop — Deep product browsing
// ────────────────────────────────────────────────────────────────
test("Guest 09 — Deep browsing [Desktop]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser);
  const journey = new JourneyLogger();
  journey.attach(page);

  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-3");

  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-3");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-4");

  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "10-product-detail-4");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-back-5");

  journey.assertMinVisits(8);
  journey.printSummary("Guest 09");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// Guest 10: Mobile — Homepage then products (bouncer-like)
// ────────────────────────────────────────────────────────────────
test("Guest 10 — Homepage to products [Mobile]", async ({ browser }) => {
  const { context, page, collector } = await createGuestContext(browser, {
    width: 412,
    height: 915,
  });
  const journey = new JourneyLogger();
  journey.attach(page);

  // Start from homepage instead of products
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(4000);
  await snap(page, "01-homepage");

  await browseProducts(page);
  await page.waitForTimeout(4000);
  await snap(page, "02-products-listing");

  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-1");

  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "07-homepage-2");

  journey.assertMinVisits(5);
  journey.printSummary("Guest 10");
  console.log("  Events:", collector.summary());

  await context.close();
});
