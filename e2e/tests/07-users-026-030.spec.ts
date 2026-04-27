/**
 * Group 6: Users 026-030 — Single Buyers
 * Browse, add to cart, complete full checkout with Stripe test card 4242.
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
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 026: Leo Layla — Desktop Chrome — 13 pages
// Products → view #0 → back → view #1 → back → view #2 →
// add to cart → cart → checkout → fill shipping → advance to review →
// Stripe 4242 pay → confirmation → orders
// ────────────────────────────────────────────────────────────────
test("User 026 Leo Layla — Single Buyer [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[25]; // test026
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

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back-to-products");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products-2");

  // Step 6: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

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
  await page.waitForTimeout(4000);
  await snap(page, "09-checkout");

  // Step 10: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review step
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-review-step");

  // Step 12: Fill Stripe card and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-stripe-pay");

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
  journey.printSummary("026 Leo Layla");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// User 027: Isaac Riley — Desktop Large — 12 pages
// Products → view #1 → back → view #3 → back → view #5 →
// add to cart → cart → checkout → fill shipping → advance to review →
// Stripe pay → confirmation → orders
// ────────────────────────────────────────────────────────────────
test("User 027 Isaac Riley — Single Buyer [Desktop Large]", async ({
  browser,
}) => {
  const user = users[26]; // test027
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

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back-to-products");

  // Step 4: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-3");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products-2");

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
  await page.waitForTimeout(4000);
  await snap(page, "09-checkout");

  // Step 10: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review step
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-review-step");

  // Step 12: Fill Stripe card and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-stripe-pay");

  // Step 13: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-confirmation");

  // Step 14: Visit orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-orders");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("027 Isaac Riley");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// User 028: Caleb Nora — iPhone 13 — 12 pages
// Products → search "pro" → view #0 → back → view #1 → back →
// view #2 → add to cart → cart → checkout → fill shipping →
// advance to review → Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 028 Caleb Nora — Single Buyer [iPhone 13]", async ({ browser }) => {
  const user = users[27]; // test028
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
  await page.waitForTimeout(4000);
  await snap(page, "10-checkout");

  // Step 11: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-shipping-filled");

  // Step 12: Advance to review step
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-review-step");

  // Step 13: Fill Stripe card and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-stripe-pay");

  // Step 14: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "14-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("028 Caleb Nora");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// User 029: Luke Hannah — Pixel 7 — 12 pages
// Products → sort price_asc → view #0 → back → view #1 → back →
// view #2 → add to cart → cart → checkout → fill shipping →
// advance to review → Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 029 Luke Hannah — Single Buyer [Pixel 7]", async ({ browser }) => {
  const user = users[28]; // test029
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
  await page.waitForTimeout(4000);
  await snap(page, "10-checkout");

  // Step 11: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-shipping-filled");

  // Step 12: Advance to review step
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-review-step");

  // Step 13: Fill Stripe card and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-stripe-pay");

  // Step 14: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "14-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("029 Luke Hannah");
  console.log("  Events:", collector.summary());

  await context.close();
});

// ────────────────────────────────────────────────────────────────
// User 030: Aaron Stella — iPad Pro — 14 pages
// Products → view #0 → back → view #1 → back → view #2 → back →
// view #3 → add to cart → cart → checkout → fill shipping →
// advance to review → Stripe pay → confirmation → orders
// ────────────────────────────────────────────────────────────────
test("User 030 Aaron Stella — Single Buyer [iPad Pro]", async ({ browser }) => {
  const user = users[29]; // test030
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-product-detail-0");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back-to-products");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(4000);
  await snap(page, "04-product-detail-1");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products-2");

  // Step 6: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-3");

  // Step 8: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-3");

  // Step 9: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-added-to-cart");

  // Step 10: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-cart");

  // Step 11: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "11-checkout");

  // Step 12: Fill shipping address
  await fillShipping(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-shipping-filled");

  // Step 13: Advance to review step
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-review-step");

  // Step 14: Fill Stripe card and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(5000);
  await snap(page, "14-stripe-pay");

  // Step 15: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "15-confirmation");

  // Step 16: Visit orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "16-orders");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("030 Aaron Stella");
  console.log("  Events:", collector.summary());

  await context.close();
});
