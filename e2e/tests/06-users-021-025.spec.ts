/**
 * Group 5: Users 021-025 — Cart Abandoners
 * Browse, add to cart, maybe start checkout, but never complete purchase.
 * 12-13 pages each.
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
  changeSort,
  addToCart,
  viewCart,
  increaseQuantity,
  decreaseQuantity,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  visitHomepage,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 021: Jack Grace — Mobile Landscape — 12 pages
// Products → filter category #0 → view #0 → add to cart → back →
// view #1 → back → view #2 → back → cart → increase qty →
// decrease qty → products
// ────────────────────────────────────────────────────────────────
test("User 021 Jack Grace — Cart Abandoner [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[20]; // test021
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-filter-category-0");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-add-to-cart");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products");

  // Step 6: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-1");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-2");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-3");

  // Step 10: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-cart");

  // Step 11: Increase quantity
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-increase-qty");

  // Step 12: Decrease quantity
  await decreaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-decrease-qty");

  // Step 13: Back to products (abandon cart)
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-products-abandon");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("021 Jack Grace");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 022: Owen Chloe — Desktop Chrome — 13 pages
// Products → view #6 → add to cart → back → view #7 → back →
// view #8 → back → cart → checkout → fill shipping →
// advance to review → abandon to homepage
// ────────────────────────────────────────────────────────────────
test("User 022 Owen Chloe — Cart Abandoner [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[21]; // test022
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-6");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-add-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-7");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-to-products-2");

  // Step 7: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-8");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-to-products-3");

  // Step 9: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "09-cart");

  // Step 10: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-checkout");

  // Step 11: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-fill-shipping");

  // Step 12: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-advance-to-review");

  // Step 13: Abandon to homepage
  await visitHomepage(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-abandon-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("022 Owen Chloe");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 023: Samuel Lily — Desktop Large — 12 pages
// Products → sort price_asc → view #0 → add to cart → back →
// view #1 → add to cart → back → view #2 → back →
// cart → products → homepage
// ────────────────────────────────────────────────────────────────
test("User 023 Samuel Lily — Cart Abandoner [Desktop Large]", async ({
  browser,
}) => {
  const user = users[22]; // test023
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

  // Step 4: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-add-to-cart");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products");

  // Step 6: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-1");

  // Step 7: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-add-to-cart-2");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-to-products-2");

  // Step 9: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "09-product-detail-2");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-to-products-3");

  // Step 11: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-cart");

  // Step 12: Back to products (abandon cart)
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-products-abandon");

  // Step 13: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("023 Samuel Lily");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 024: Ryan Zoey — iPhone 13 — 12 pages
// Products → view #7 → add to cart → back → view #8 → add to cart →
// back → view #9 → back → cart → checkout → abandon to homepage
// ────────────────────────────────────────────────────────────────
test("User 024 Ryan Zoey — Cart Abandoner [iPhone 13]", async ({
  browser,
}) => {
  const user = users[23]; // test024
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-7");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-add-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-8");

  // Step 6: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-add-to-cart-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #9
  await viewNthProduct(page, 9);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-9");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-3");

  // Step 10: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-cart");

  // Step 11: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-checkout");

  // Step 12: Abandon to homepage
  await visitHomepage(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-abandon-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("024 Ryan Zoey");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 025: Nathan Penelope — Pixel 7 — 12 pages
// Products → search "premium" → view #0 → add to cart → back →
// view #1 → back → view #2 → back → cart → increase qty →
// checkout → abandon to homepage
// ────────────────────────────────────────────────────────────────
test("User 025 Nathan Penelope — Cart Abandoner [Pixel 7]", async ({
  browser,
}) => {
  const user = users[24]; // test025
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Search "premium"
  await searchProducts(page, "premium");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-premium");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-add-to-cart");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products");

  // Step 6: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-1");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-2");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-3");

  // Step 10: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-cart");

  // Step 11: Increase quantity
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-increase-qty");

  // Step 12: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-checkout");

  // Step 13: Abandon to homepage
  await visitHomepage(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-abandon-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("025 Nathan Penelope");
  await finishJourney(page, context, collector);
});
