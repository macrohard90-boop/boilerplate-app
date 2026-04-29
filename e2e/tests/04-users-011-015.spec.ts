/**
 * Group 3: Users 011-015 — Checkout Buyers
 * Each user browses products, adds items to cart, and goes through checkout.
 *
 * Payment flows:
 *   011-013: One-time products → Stripe Elements (shipping → review → pay → confirmation)
 *   014:     Subscription only → Stripe Checkout Session (review → redirect to Stripe)
 *   015:     Mixed cart (product + subscription) → Stripe Checkout Session (ship → review → redirect)
 *
 * After checkout, all users view the cart:
 *   011-013: Cart is empty (order consumed it)
 *   014-015: Cart still has items (Stripe hasn't confirmed the purchase)
 */

import { test, expect } from "@playwright/test";
import { getAllUsers } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import {
  browseProducts,
  viewNthProduct,
  backToProducts,
  addToCart,
  viewCart,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeAndPay,
  waitForConfirmation,
  applyCoupon,
  clickSubscriptionsTab,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 011: Simple One-Time Purchase (1 product → Stripe Elements)
// Products → view #0 → add to cart → cart → checkout
// (shipping → review → payment → confirmation) → view empty cart
// ────────────────────────────────────────────────────────────────
test("User 011 Isabella Young — Checkout Buyer: simple one-time [iPad Pro]", async ({
  browser,
}) => {
  const user = users[10]; // test011
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Browse & add product
  await snap(page, "01-products");
  await viewNthProduct(page, 0);
  await page.waitForTimeout(2000);
  await snap(page, "02-product-detail");
  await addToCart(page);
  await snap(page, "03-added-to-cart");

  // View cart
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "04-cart");

  // Checkout: shipping
  await startCheckout(page);
  await snap(page, "05-checkout-shipping");
  await fillShipping(page);
  await snap(page, "06-shipping-filled");

  // Checkout: review
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "07-checkout-review");

  // Checkout: payment (creates PaymentIntent)
  await advanceCheckoutStep(page); // "Proceed to Payment"
  await page.waitForTimeout(2000);
  await snap(page, "08-checkout-payment");

  // Fill Stripe card and submit
  await fillStripeAndPay(page);

  // Wait for confirmation page
  await waitForConfirmation(page);
  await snap(page, "09-order-confirmed");

  // View cart — should be empty after successful purchase
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "10-empty-cart");

  // Assertions
  journey.assertMinVisits(5);
  collector.assertFired("product_viewed", 1);

  journey.printSummary("011 Isabella Young");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 012: Multi-Product Purchase (3 products → Stripe Elements)
// Products → view #0 → add → back → view #1 → add → back →
// view #2 → add → cart → checkout → confirmation → empty cart
// ────────────────────────────────────────────────────────────────
test("User 012 Mason King — Checkout Buyer: multi-product [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[11]; // test012
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add product #0
  await snap(page, "01-products");
  await viewNthProduct(page, 0);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "02-added-product-0");

  // Add product #1
  await backToProducts(page);
  await viewNthProduct(page, 1);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "03-added-product-1");

  // Add product #2
  await backToProducts(page);
  await viewNthProduct(page, 2);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "04-added-product-2");

  // View cart (3 items)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "05-cart-3-items");

  // Checkout: shipping → review → payment
  await startCheckout(page);
  await fillShipping(page);
  await snap(page, "06-shipping-filled");
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "07-checkout-review");
  await advanceCheckoutStep(page); // "Proceed to Payment"
  await page.waitForTimeout(2000);
  await snap(page, "08-checkout-payment");
  await fillStripeAndPay(page);

  // Confirmation
  await waitForConfirmation(page);
  await snap(page, "09-order-confirmed");

  // View cart (empty)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "10-empty-cart");

  // Assertions
  journey.assertMinVisits(5);
  collector.assertFired("product_viewed", 3);

  journey.printSummary("012 Mason King");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 013: Coupon Buyer (2 products + WELCOME10 → Stripe Elements)
// Products → view #1 → add → back → view #3 → add →
// cart → apply coupon → checkout → confirmation → empty cart
// ────────────────────────────────────────────────────────────────
test("User 013 Charlotte Wright — Checkout Buyer: coupon [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[12]; // test013
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add product #1
  await snap(page, "01-products");
  await viewNthProduct(page, 1);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "02-added-product-1");

  // Add product #3
  await backToProducts(page);
  await viewNthProduct(page, 3);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "03-added-product-3");

  // View cart and apply coupon
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "04-cart-2-items");
  await applyCoupon(page, "WELCOME10");
  await snap(page, "05-coupon-applied");

  // Checkout: shipping → review → payment
  await startCheckout(page);
  await fillShipping(page);
  await snap(page, "06-shipping-filled");
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "07-checkout-review");
  await advanceCheckoutStep(page); // "Proceed to Payment"
  await page.waitForTimeout(2000);
  await snap(page, "08-checkout-payment");
  await fillStripeAndPay(page);

  // Confirmation
  await waitForConfirmation(page);
  await snap(page, "09-order-confirmed");

  // View cart (empty)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "10-empty-cart");

  // Assertions
  journey.assertMinVisits(5);
  collector.assertFired("product_viewed", 2);

  journey.printSummary("013 Charlotte Wright");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 014: Subscription Purchase (Stripe Checkout Session)
// Products → Subscriptions tab → "Get Access" → cart →
// checkout (review → Stripe redirect) → cart (still has items)
//
// Subscription-only carts skip shipping and go straight to Review.
// Clicking "Proceed to Payment" creates a Stripe Checkout Session
// and redirects to checkout.stripe.com — E2E verifies the API call
// succeeds but can't complete payment on Stripe's hosted page.
// ────────────────────────────────────────────────────────────────
test("User 014 Logan Lopez — Checkout Buyer: subscription [Desktop Large]", async ({
  browser,
}) => {
  const user = users[13]; // test014
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Browse products → Subscriptions tab
  await snap(page, "01-products");
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(1000);
  await snap(page, "02-subscriptions-tab");

  // Add first subscription plan to cart
  await addToCart(page);
  await snap(page, "03-plan-added");

  // View cart
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "04-cart-subscription");

  // Start checkout — subscription-only shows Review step directly
  await startCheckout(page);
  await page.waitForTimeout(1000);
  await snap(page, "05-checkout-review");

  // Click "Proceed to Payment" — intercept the session creation API call
  const sessionPromise = page.waitForResponse(
    (r) =>
      r.url().includes("/payments/checkout/session") &&
      r.request().method() === "POST",
    { timeout: 30000 },
  );
  await page
    .locator("button")
    .filter({ hasText: /Proceed to Payment/i })
    .first()
    .click();
  const sessionResp = await sessionPromise;
  expect(sessionResp.status()).toBe(200);
  console.log("  014: Stripe Checkout Session created successfully");

  // Page redirects to Stripe — navigate to cart instead.
  // Cart still has items because Stripe hasn't confirmed the purchase.
  await page.waitForTimeout(1500);
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "06-cart-still-has-items");

  // Assertions
  journey.assertMinVisits(3);

  journey.printSummary("014 Logan Lopez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 015: Mixed Cart (1 product + 1 subscription → Stripe Checkout Session)
// Products → view #2 → add → back → Subscriptions tab → "Get Access" →
// cart → checkout (shipping → review → Stripe redirect) → cart (still has items)
//
// Mixed carts (one-time + recurring) use Stripe Checkout Session because
// subscriptions require Stripe-hosted checkout. Shipping is still needed
// for the one-time product.
// ────────────────────────────────────────────────────────────────
test("User 015 Amelia Hill — Checkout Buyer: mixed cart [iPhone 13]", async ({
  browser,
}) => {
  const user = users[14]; // test015
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add one-time product #2
  await snap(page, "01-products");
  await viewNthProduct(page, 2);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "02-added-product");

  // Add subscription plan
  await backToProducts(page);
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(1000);
  await snap(page, "03-subscriptions-tab");
  await addToCart(page);
  await snap(page, "04-plan-added");

  // View cart (1 product + 1 subscription)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "05-cart-mixed");

  // Checkout: shipping (required for mixed cart)
  await startCheckout(page);
  await fillShipping(page);
  await snap(page, "06-shipping-filled");

  // Checkout: review
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "07-checkout-review");

  // Click "Proceed to Payment" — creates Stripe Checkout Session → redirect
  const sessionPromise = page.waitForResponse(
    (r) =>
      r.url().includes("/payments/checkout/session") &&
      r.request().method() === "POST",
    { timeout: 30000 },
  );
  await page
    .locator("button")
    .filter({ hasText: /Proceed to Payment/i })
    .first()
    .click();
  const sessionResp = await sessionPromise;
  expect(sessionResp.status()).toBe(200);
  console.log("  015: Stripe Checkout Session created successfully");

  // Navigate to cart — still has items (Stripe hasn't confirmed)
  await page.waitForTimeout(1500);
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "08-cart-still-has-items");

  // Assertions
  journey.assertMinVisits(4);
  collector.assertFired("product_viewed", 1);

  journey.printSummary("015 Amelia Hill");
  await finishJourney(page, context, collector);
});
