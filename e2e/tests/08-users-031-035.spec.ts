/**
 * Group 7: Users 031-035 — Single Buyers
 * Browse products, add one item to cart, complete checkout via Stripe. 12 pages each.
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
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeAndPay,
  waitForConfirmation,
  visitOrders,
  visitFirstOrderDetail,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 031: Dylan Maya — Mobile Landscape — 12 pages
// Products (4s) → filter category #0 (4s) → view #0 (5s) → back (3s) →
// view #1 (5s) → back (3s) → view #2 (5s) → add to cart (3s) →
// cart (4s) → checkout → fill shipping → advance to review →
// Stripe pay → confirmation (5s)
// ────────────────────────────────────────────────────────────────
test("User 031 Dylan Maya — Single Buyer [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[30]; // test031
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

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back");

  // Step 5: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-1");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  // Step 7: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-2");

  // Step 8: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-added-to-cart");

  // Step 9: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "09-cart");

  // Step 10: Start checkout
  await startCheckout(page);
  await snap(page, "10-checkout-shipping");

  // Step 11: Fill shipping
  await fillShipping(page);
  await snap(page, "11-shipping-filled");

  // Step 12: Advance to review
  await advanceCheckoutStep(page);
  await snap(page, "12-checkout-review");

  // Step 13: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "13-stripe-paying");

  // Step 14: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "14-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("031 Dylan Maya");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 032: Gabriel Aurora — Desktop Chrome — 12 pages
// Products (4s) → view #3 (5s) → back (3s) → view #4 (5s) → back (3s) →
// view #5 (5s) → add to cart (3s) → cart (4s) → checkout →
// fill shipping → advance to review → Stripe pay → confirmation (5s) →
// orders (3s)
// ────────────────────────────────────────────────────────────────
test("User 032 Gabriel Aurora — Single Buyer [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[31]; // test032
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

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-4");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  // Step 6: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-5");

  // Step 7: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-added-to-cart");

  // Step 8: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-cart");

  // Step 9: Start checkout
  await startCheckout(page);
  await snap(page, "09-checkout-shipping");

  // Step 10: Fill shipping
  await fillShipping(page);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review
  await advanceCheckoutStep(page);
  await snap(page, "11-checkout-review");

  // Step 12: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "12-stripe-paying");

  // Step 13: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-confirmation");

  // Step 14: Visit orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-orders");

  // Step 15: View order detail
  await visitFirstOrderDetail(page);
  await page.waitForTimeout(4000);
  await snap(page, "15-order-detail");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("032 Gabriel Aurora");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 033: Julian Anderson — Desktop Large — 12 pages
// Products (4s) → view #4 (4s) → back (3s) → view #5 (5s) → back (3s) →
// view #6 (5s) → add to cart (3s) → cart (4s) → checkout →
// fill shipping → advance to review → Stripe pay → confirmation (5s)
// ────────────────────────────────────────────────────────────────
test("User 033 Julian Anderson — Single Buyer [Desktop Large]", async ({
  browser,
}) => {
  const user = users[32]; // test033
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(4000);
  await snap(page, "02-product-detail-4");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-5");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  // Step 6: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-6");

  // Step 7: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-added-to-cart");

  // Step 8: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-cart");

  // Step 9: Start checkout
  await startCheckout(page);
  await snap(page, "09-checkout-shipping");

  // Step 10: Fill shipping
  await fillShipping(page);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review
  await advanceCheckoutStep(page);
  await snap(page, "11-checkout-review");

  // Step 12: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "12-stripe-paying");

  // Step 13: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("033 Julian Anderson");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 034: Emma Martinez — iPhone 13 — 12 pages
// Products (5s) → search "shirt" (4s) → view #0 (5s) → back (3s) →
// view #1 (5s) → back (3s) → view #2 (5s) → add to cart (3s) →
// cart (4s) → checkout → fill shipping → advance to review →
// Stripe pay → confirmation (5s)
// ────────────────────────────────────────────────────────────────
test("User 034 Emma Martinez — Single Buyer [iPhone 13]", async ({
  browser,
}) => {
  const user = users[33]; // test034
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
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

  // Step 5: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "05-product-detail-1");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  // Step 7: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-2");

  // Step 8: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-added-to-cart");

  // Step 9: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "09-cart");

  // Step 10: Start checkout
  await startCheckout(page);
  await snap(page, "10-checkout-shipping");

  // Step 11: Fill shipping
  await fillShipping(page);
  await snap(page, "11-shipping-filled");

  // Step 12: Advance to review
  await advanceCheckoutStep(page);
  await snap(page, "12-checkout-review");

  // Step 13: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "13-stripe-paying");

  // Step 14: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "14-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("034 Emma Martinez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 035: Liam Thompson — Pixel 7 — 12 pages
// Products (4s) → view #6 (5s) → back (3s) → view #7 (5s) → back (3s) →
// view #8 (5s) → add to cart (3s) → cart (4s) → checkout →
// fill shipping → advance to review → Stripe pay → confirmation (5s) →
// orders (3s)
// ────────────────────────────────────────────────────────────────
test("User 035 Liam Thompson — Single Buyer [Pixel 7]", async ({
  browser,
}) => {
  const user = users[34]; // test035
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

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-7");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-2");

  // Step 6: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-8");

  // Step 7: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-added-to-cart");

  // Step 8: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "08-cart");

  // Step 9: Start checkout
  await startCheckout(page);
  await snap(page, "09-checkout-shipping");

  // Step 10: Fill shipping
  await fillShipping(page);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review
  await advanceCheckoutStep(page);
  await snap(page, "11-checkout-review");

  // Step 12: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "12-stripe-paying");

  // Step 13: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-confirmation");

  // Step 14: Visit orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-orders");

  // Step 15: View order detail
  await visitFirstOrderDetail(page);
  await page.waitForTimeout(4000);
  await snap(page, "15-order-detail");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("035 Liam Thompson");
  await finishJourney(page, context, collector);
});
