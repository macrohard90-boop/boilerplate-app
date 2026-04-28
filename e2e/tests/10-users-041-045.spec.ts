/**
 * Group 9: Users 041-045 — Power Buyers (041-042) & Subscribers (043-045)
 * 041-042: Heavy browsing, cart manipulation, coupons, full checkout.
 * 043-045: Browse products then switch to subscriptions tab, add plan to cart,
 *          start checkout (subscription checkout redirects to external Stripe Checkout).
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
  increaseQuantity,
  removeFromCart,
  applyCoupon,
  clickSubscriptionsTab,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeAndPay,
  waitForConfirmation,
  visitHomepage,
  visitOrders,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 041: Lucas Walker — Pixel 7 — 14 pages (Power Buyer — MIXED CART)
// Products → view #0 → back → view #1 → add to cart (one-off) → back →
// view #2 → back → Subscriptions tab → view plan #0 → add to cart (subscription) →
// cart (verify mixed) → checkout (should skip shipping — Review step first) →
// advance (triggers POST /payments/checkout/session → Stripe redirect) →
// orders page
// ────────────────────────────────────────────────────────────────
test("User 041 Lucas Walker — Power Buyer MIXED CART [Pixel 7]", async ({
  browser,
}) => {
  const user = users[40]; // test041
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
  await snap(page, "03-back");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  // Step 5: Add one-off product to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-add-to-cart-oneoff");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-2");

  // Step 7: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(5000);
  await snap(page, "07-product-detail-2");

  // Step 8: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-back-3");

  // Step 9: Switch to Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-subscriptions-tab");

  // Step 10: View subscription plan #0 (click "Get Access" which adds to cart directly)
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "10-plan-detail-0");

  // Step 11: Add subscription to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-add-subscription-to-cart");

  // Step 12: View cart — should show both one-off and subscription items
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-mixed-cart");

  // Step 13: Start checkout — mixed cart should skip shipping (Review step first)
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-checkout-review");

  // Step 14: Advance — triggers POST /payments/checkout/session for mixed/subscription carts
  const sessionRequestPromise = page
    .waitForRequest(
      (req) =>
        req.url().includes("/payments/checkout/session") &&
        req.method() === "POST",
      { timeout: 15000 },
    )
    .catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest = await sessionRequestPromise;
  await page.waitForTimeout(5000);
  await snap(page, "14-stripe-redirect");

  if (sessionRequest) {
    console.log("  Mixed cart: checkout session API called (Stripe redirect)");
  } else {
    console.log(
      "  WARNING: checkout session API was NOT called for mixed cart",
    );
  }

  // Step 15: Visit orders page (redirected back or navigate manually)
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "15-orders");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("041 Lucas Walker (Mixed Cart)");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 042: Mia Hall — iPad Pro — 17 pages (Power Buyer)
// Products → view #2 → add to cart → back → view #6 → add to cart →
// back → view #7 → add to cart → back → view #8 → back →
// cart → increase qty → increase qty → coupon "FAKECOUPON" →
// coupon "WELCOME10" → checkout → fill shipping → advance to review →
// Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 042 Mia Hall — Power Buyer [iPad Pro]", async ({ browser }) => {
  const user = users[41]; // test042
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(4000);
  await snap(page, "02-product-detail-2");

  // Step 3: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-add-to-cart");

  // Step 4: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "04-back-to-products");

  // Step 5: View product #6
  await viewNthProduct(page, 6);
  await page.waitForTimeout(4000);
  await snap(page, "05-product-detail-6");

  // Step 6: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-add-to-cart-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(4000);
  await snap(page, "08-product-detail-7");

  // Step 9: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-add-to-cart-3");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-to-products-3");

  // Step 11: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-8");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-to-products-4");

  // Step 13: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-cart");

  // Step 14: Increase quantity (first time)
  await increaseQuantity(page);
  await page.waitForTimeout(2000);
  await snap(page, "14-increase-qty-1");

  // Step 15: Increase quantity (second time)
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "15-increase-qty-2");

  // Step 16: Apply invalid coupon "FAKECOUPON"
  await applyCoupon(page, "FAKECOUPON");
  await page.waitForTimeout(3000);
  await snap(page, "16-coupon-fake");

  // Step 17: Apply valid coupon "WELCOME10"
  await applyCoupon(page, "WELCOME10");
  await page.waitForTimeout(3000);
  await snap(page, "17-coupon-welcome10");

  // Step 18: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "18-checkout");

  // Step 19: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "19-fill-shipping");

  // Step 20: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(4000);
  await snap(page, "20-review-step");

  // Step 21: Fill Stripe and pay
  await fillStripeAndPay(page);
  await page.waitForTimeout(3000);
  await snap(page, "21-stripe-pay");

  // Step 22: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "22-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);
  collector.assertFired("add_to_cart", 3);

  // Print summary
  journey.printSummary("042 Mia Hall");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 043: Ethan Young — Desktop Chrome — 11 pages (Subscriber)
// Products → view #0 → back → view #1 → back → view #2 → back →
// Subscriptions tab → view plan #0 → add to cart → cart →
// checkout → advance to review (Stripe redirect)
// ────────────────────────────────────────────────────────────────
test("User 043 Ethan Young — Subscriber [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[42]; // test043
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
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

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-3");

  // Step 8: Click Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-subscriptions-tab");

  // Step 9: View plan #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "09-plan-detail-0");

  // Step 10: Add plan to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-add-plan-to-cart");

  // Step 11: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "11-cart");

  // Step 12: Start checkout (subscription skips shipping)
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-checkout");

  // Step 13: Advance to review (triggers Stripe Checkout redirect for subscriptions)
  const sessionRequestPromise043 = page
    .waitForRequest(
      (req) =>
        req.url().includes("/payments/checkout/session") &&
        req.method() === "POST",
      { timeout: 15000 },
    )
    .catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest043 = await sessionRequestPromise043;
  await page.waitForTimeout(5000);
  await snap(page, "13-stripe-redirect");

  if (sessionRequest043) {
    console.log("  Subscription checkout session API called");
  } else {
    console.log("  WARNING: checkout session API was NOT called");
  }

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);

  // Print summary
  journey.printSummary("043 Ethan Young");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 044: Isabella King — Desktop Large — 12 pages (Subscriber)
// Products → view #0 → back → view #1 → back → view #2 → back →
// view #3 → back → Subscriptions tab → view plan #0 →
// add to cart → cart → checkout → advance to review (Stripe redirect)
// ────────────────────────────────────────────────────────────────
test("User 044 Isabella King — Subscriber [Desktop Large]", async ({
  browser,
}) => {
  const user = users[43]; // test044
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
  await page.waitForTimeout(4000);
  await snap(page, "06-product-detail-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-3");

  // Step 8: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "08-product-detail-3");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-4");

  // Step 10: Click Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-subscriptions-tab");

  // Step 11: View plan #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(5000);
  await snap(page, "11-plan-detail-0");

  // Step 12: Add plan to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-add-plan-to-cart");

  // Step 13: View cart
  await viewCart(page);
  await page.waitForTimeout(4000);
  await snap(page, "13-cart");

  // Step 14: Start checkout (subscription skips shipping)
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "14-checkout");

  // Step 15: Advance to review (triggers Stripe Checkout redirect for subscriptions)
  const sessionRequestPromise044 = page
    .waitForRequest(
      (req) =>
        req.url().includes("/payments/checkout/session") &&
        req.method() === "POST",
      { timeout: 15000 },
    )
    .catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest044 = await sessionRequestPromise044;
  await page.waitForTimeout(5000);
  await snap(page, "15-stripe-redirect");

  if (sessionRequest044) {
    console.log("  Subscription checkout session API called");
  } else {
    console.log("  WARNING: checkout session API was NOT called");
  }

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);

  // Print summary
  journey.printSummary("044 Isabella King");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 045: Mason Wright — iPhone 13 — 11 pages (Subscriber)
// Products → view #0 → back → view #1 → back → Subscriptions tab →
// view plan #1 → add to cart → cart → checkout →
// advance to review (Stripe redirect) → homepage
// ────────────────────────────────────────────────────────────────
test("User 045 Mason Wright — Subscriber [iPhone 13]", async ({ browser }) => {
  const user = users[44]; // test045
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
  await snap(page, "03-back-to-products");

  // Step 4: View product #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-1");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products-2");

  // Step 6: Click Subscriptions tab
  await clickSubscriptionsTab(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-subscriptions-tab");

  // Step 7: View plan #1
  await viewNthProduct(page, 1);
  await page.waitForTimeout(5000);
  await snap(page, "07-plan-detail-1");

  // Step 8: Add plan to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-add-plan-to-cart");

  // Step 9: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "09-cart");

  // Step 10: Start checkout (subscription skips shipping)
  await startCheckout(page);
  await page.waitForTimeout(4000);
  await snap(page, "10-checkout");

  // Step 11: Advance to review (triggers Stripe Checkout redirect for subscriptions)
  const sessionRequestPromise045 = page
    .waitForRequest(
      (req) =>
        req.url().includes("/payments/checkout/session") &&
        req.method() === "POST",
      { timeout: 15000 },
    )
    .catch(() => null);

  await advanceCheckoutStep(page);
  const sessionRequest045 = await sessionRequestPromise045;
  await page.waitForTimeout(4000);
  await snap(page, "11-stripe-redirect");

  if (sessionRequest045) {
    console.log("  Subscription checkout session API called");
  } else {
    console.log("  WARNING: checkout session API was NOT called");
  }

  // Step 12: Homepage
  await visitHomepage(page);
  await page.waitForTimeout(4000);
  await snap(page, "12-homepage");

  // Assertions
  journey.assertMinVisits(8);
  collector.assertFired("product_viewed", 2);

  // Print summary
  journey.printSummary("045 Mason Wright");
  await finishJourney(page, context, collector);
});
