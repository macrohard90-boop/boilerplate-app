/**
 * Group 10: Users 046-050 — Subscribers (046-047) + Bouncers (048-050)
 * 046-047: Browse products, switch to subscriptions tab, add plan to cart, checkout (Stripe redirect).
 * 048-050: Short sessions — browse a few pages and leave.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { EventCollector } from "../helpers/event-collector";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import {
  browseProducts,
  viewNthProduct,
  backToProducts,
  addToCart,
  viewCart,
  clickSubscriptionsTab,
  startCheckout,
  advanceCheckoutStep,
  visitHomepage,
  visitFirstCategory,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 046: Charlotte Lopez — Pixel 7 — 11 pages (Subscriber)
// Products (4s) → view #0 (4s) → back (3s) → view #1 (4s) → back (3s) →
// view #2 (5s) → back (3s) → Subscriptions tab (3s) → view plan #0 (5s) →
// add to cart (3s) → cart (5s) → checkout (4s) → advance to review (4s)
// ────────────────────────────────────────────────────────────────
test("User 046 Charlotte Lopez — Subscriber [Pixel 7]", async ({
  browser,
}) => {
  const user = users[45]; // test046
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "02-product-detail-0");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(4000);
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

  // Step 8: Click Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-subscriptions-tab");

  // Step 9: View plan #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "09-plan-detail-0");

  // Step 10: Add to cart (subscription)
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-added-to-cart");

  // Step 11: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-cart");

  // Step 12: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-checkout");

  // Step 13: Advance to review (Stripe redirect will happen but we can't complete external Stripe Checkout)
  const sessionRequestPromise046 = page.waitForRequest(
    (req) => req.url().includes("/payments/checkout/session") && req.method() === "POST",
    { timeout: 15000 },
  ).catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest046 = await sessionRequestPromise046;
  await page.waitForTimeout(5000);
  await snap(page, "13-checkout-review");

  if (sessionRequest046) {
    console.log("  Subscription checkout session API called");
  } else {
    console.log("  WARNING: checkout session API was NOT called");
  }

  // Assertions
  journey.assertMinVisits(8);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("046 Charlotte Lopez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 047: Logan Hill — iPad Pro — 11 pages (Subscriber)
// Products (5s) → view #0 (5s) → back (3s) → view #1 (5s) → back (3s) →
// view #2 (5s) → back (3s) → Subscriptions tab (3s) → view plan #0 (6s) →
// add to cart (3s) → cart (5s) → checkout (4s) → advance to review (4s)
// ────────────────────────────────────────────────────────────────
test("User 047 Logan Hill — Subscriber [iPad Pro]", async ({ browser }) => {
  const user = users[46]; // test047
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

  // Step 8: Click Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-subscriptions-tab");

  // Step 9: View plan #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(6000);
  await snap(page, "09-plan-detail-0");

  // Step 10: Add to cart (subscription)
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-added-to-cart");

  // Step 11: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-cart");

  // Step 12: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-checkout");

  // Step 13: Advance to review (Stripe redirect will happen but we can't complete external Stripe Checkout)
  const sessionRequestPromise047 = page.waitForRequest(
    (req) => req.url().includes("/payments/checkout/session") && req.method() === "POST",
    { timeout: 15000 },
  ).catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest047 = await sessionRequestPromise047;
  await page.waitForTimeout(5000);
  await snap(page, "13-checkout-review");

  if (sessionRequest047) {
    console.log("  Subscription checkout session API called");
  } else {
    console.log("  WARNING: checkout session API was NOT called");
  }

  // Assertions
  journey.assertMinVisits(8);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("047 Logan Hill");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 048: Amelia Scott — Desktop Chrome — 5 pages (Bouncer)
// Products (5s) → view #0 (5s) → back (3s) → view #1 (5s) → homepage (4s)
// ────────────────────────────────────────────────────────────────
test("User 048 Amelia Scott — Bouncer [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[47]; // test048
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

  // Step 5: View empty cart (triggers empty_cart_viewed event)
  await viewCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-empty-cart");

  // Step 6: Homepage (bounce)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "06-homepage-bounce");

  // Assertions — bouncer uses lower threshold
  journey.assertMinVisits(3);
  collector.assertFired("product_viewed", 2);

  // Print summary
  journey.printSummary("048 Amelia Scott");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 049: Alexander Green — Desktop Large — 4 pages (Bouncer)
// Homepage (5s) → products (4s) → view #0 (5s) → homepage (4s)
// ────────────────────────────────────────────────────────────────
test("User 049 Alexander Green — Bouncer [Desktop Large]", async ({
  browser,
}) => {
  const user = users[48]; // test049
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // createUserContext navigates to /products first, so start by visiting homepage
  // Step 1: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(5000);
  await snap(page, "01-homepage");

  // Step 2: Visit first category page (triggers category_browsed event)
  await visitFirstCategory(page);
  await page.waitForTimeout(4000);
  await snap(page, "02-category-page");

  // Step 3: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "03-product-detail-0");

  // Step 4: Homepage (bounce)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "04-homepage-bounce");

  // Assertions — bouncer uses lower threshold
  journey.assertMinVisits(3);
  collector.assertFired("product_viewed", 1);

  // Print summary
  journey.printSummary("049 Alexander Green");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 050: Benjamin Adams — iPhone 13 — 4 pages (Bouncer — rejected analytics)
// Products (5s) → view #0 (5s) → back (3s) → homepage (4s)
// This user rejected analytics consent — tracking events should NOT fire.
// ────────────────────────────────────────────────────────────────
test("User 050 Benjamin Adams — Bouncer (no analytics) [iPhone 13]", async ({
  browser,
}) => {
  const user = users[49]; // test050
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

  // Step 4: Homepage (bounce)
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "04-homepage-bounce");

  // Assertions — bouncer uses lower threshold
  journey.assertMinVisits(3);

  // User 050 rejected analytics — tracking should be blocked
  // We don't assert events fired since tracking is blocked

  // Print summary
  journey.printSummary("050 Benjamin Adams");
  await finishJourney(page, context, collector);
});
