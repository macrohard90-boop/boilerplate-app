/**
 * Group 4: Users 016-020 — Cart Abandoners
 * Browse, add to cart, sometimes start checkout, but never complete purchase.
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
  addToCart,
  viewCart,
  increaseQuantity,
  decreaseQuantity,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  visitHomepage,
  visitDashboard,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 016: Alexander Harper — Desktop Chrome — 11 pages
// Products → view #0 → add to cart → back → view #1 → back →
// view #2 → back → cart → products → homepage
// ────────────────────────────────────────────────────────────────
test("User 016 Alexander Harper — Cart Abandoner [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[15]; // test016
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing (already on /products from createUserContext)
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-0");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-cart");

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

  // Step 7: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-2");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-to-products-3");

  // Step 9: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "09-cart");

  // Step 10: Back to products
  await browseProducts(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-products-again");

  // Step 11: Homepage (abandon)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("016 Alexander Harper");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 017: Benjamin Evelyn — Desktop Large — 12 pages
// Products → view #1 → add to cart → back → view #2 → add to cart →
// back → view #3 → back → cart → increase qty → products → homepage
// ────────────────────────────────────────────────────────────────
test("User 017 Benjamin Evelyn — Cart Abandoner [Desktop Large]", async ({
  browser,
}) => {
  const user = users[16]; // test017
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-1");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-2");

  // Step 6: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-added-to-cart-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-3");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-3");

  // Step 10: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-cart");

  // Step 11: Increase quantity of first item
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-cart-increase-qty");

  // Step 12: Back to products
  await browseProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-products-again");

  // Step 13: Homepage (abandon)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("017 Benjamin Evelyn");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 018: Daniel Aria — iPhone 13 — 12 pages
// Products → view #3 → add to cart → back → view #4 → back →
// view #5 → back → cart → checkout → fill shipping → abandon to homepage
// ────────────────────────────────────────────────────────────────
test("User 018 Daniel Aria — Cart Abandoner [iPhone 13]", async ({
  browser,
}) => {
  const user = users[17]; // test018
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-3");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-4");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-to-products-2");

  // Step 7: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-5");

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

  // Step 11: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-shipping-filled");

  // Step 12: Abandon to homepage
  await visitHomepage(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-homepage-abandon");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("018 Daniel Aria");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 019: Henry Ella — Pixel 7 — 11 pages
// Products → search "pro" → view #0 → add to cart → back →
// view #1 → back → view #2 → back → cart → products → homepage
// ────────────────────────────────────────────────────────────────
test("User 019 Henry Ella — Cart Abandoner [Pixel 7]", async ({ browser }) => {
  const user = users[18]; // test019
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: Search "pro"
  await searchProducts(page, "pro");
  await page.waitForTimeout(4000);
  await snap(page, "02-search-pro");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-added-to-cart");

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

  // Step 11: Back to products
  await browseProducts(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-products-again");

  // Step 12: Homepage (abandon)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-homepage");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("019 Henry Ella");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 020: Sebastian Scarlett — iPad Pro — 13 pages
// Products → view #4 → add to cart → back → view #5 → add to cart →
// back → view #6 → back → view #7 → back → cart → checkout →
// abandon to homepage
// ────────────────────────────────────────────────────────────────
test("User 020 Sebastian Scarlett — Cart Abandoner [iPad Pro]", async ({
  browser,
}) => {
  const user = users[19]; // test020
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-4");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-added-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-5");

  // Step 6: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-added-to-cart-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-6");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-3");

  // Step 10: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "10-product-detail-7");

  // Step 11: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-back-to-products-4");

  // Step 12: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-cart");

  // Step 13: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-checkout");

  // Step 14: Abandon to homepage
  await visitHomepage(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-homepage-abandon");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("020 Sebastian Scarlett");
  await finishJourney(page, context, collector);
});
