/**
 * Group 4: Users 016-020 — Checkout Buyers (continued)
 * Each user browses products, adds items to cart, and goes through checkout.
 * Mirrors file 04 patterns with different product selections for variety.
 *
 * Payment flows:
 *   016-018: One-time products → Stripe Elements (shipping → review → pay → confirmation)
 *   019:     Subscription only → Stripe Checkout Session (review → redirect to Stripe)
 *   020:     Mixed cart (product + subscription) → Stripe Checkout Session (ship → review → redirect)
 *
 * After checkout, all users view the cart:
 *   016-018: Cart is empty (order consumed it)
 *   019-020: Cart still has items (Stripe hasn't confirmed the purchase)
 *
 * At the end of the file, a test.afterAll() prints the expected event fire count
 * matrix for ALL 20 smoke users — for 1:1 comparison with the admin event registry.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import {
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
// User 016: Simple One-Time Purchase (1 product → Stripe Elements)
// Products → view #1 → add to cart → cart → checkout
// (shipping → review → payment → confirmation) → view empty cart
// ────────────────────────────────────────────────────────────────
test("User 016 Alexander Scott — Checkout Buyer: simple one-time [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[15]; // test016
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Browse & add product #1
  await snap(page, "01-products");
  await viewNthProduct(page, 1);
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

  journey.printSummary("016 Alexander Scott");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 017: Two-Product Purchase (2 products → Stripe Elements)
// Products → view #0 → add → back → view #2 → add →
// cart → checkout → confirmation → empty cart
// ────────────────────────────────────────────────────────────────
test("User 017 Harper Green — Checkout Buyer: two-product [Desktop Large]", async ({
  browser,
}) => {
  const user = users[16]; // test017
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add product #0
  await snap(page, "01-products");
  await viewNthProduct(page, 0);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "02-added-product-0");

  // Add product #2
  await backToProducts(page);
  await viewNthProduct(page, 2);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "03-added-product-2");

  // View cart (2 items)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "04-cart-2-items");

  // Checkout: shipping → review → payment
  await startCheckout(page);
  await fillShipping(page);
  await snap(page, "05-shipping-filled");
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "06-checkout-review");
  await advanceCheckoutStep(page); // "Proceed to Payment"
  await page.waitForTimeout(2000);
  await snap(page, "07-checkout-payment");
  await fillStripeAndPay(page);

  // Confirmation
  await waitForConfirmation(page);
  await snap(page, "08-order-confirmed");

  // View cart (empty)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "09-empty-cart");

  // Assertions
  journey.assertMinVisits(5);
  collector.assertFired("product_viewed", 2);

  journey.printSummary("017 Harper Green");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 018: Coupon Buyer (1 product + WELCOME10 → Stripe Elements)
// Products → view #0 → add → cart → apply coupon →
// checkout → confirmation → empty cart
// ────────────────────────────────────────────────────────────────
test("User 018 Benjamin Adams — Checkout Buyer: coupon [iPhone 13]", async ({
  browser,
}) => {
  const user = users[17]; // test018
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add product #0
  await snap(page, "01-products");
  await viewNthProduct(page, 0);
  await page.waitForTimeout(2000);
  await addToCart(page);
  await snap(page, "02-added-product-0");

  // View cart and apply coupon
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "03-cart-1-item");
  await applyCoupon(page, "WELCOME10");
  await snap(page, "04-coupon-applied");

  // Checkout: shipping → review → payment
  await startCheckout(page);
  await fillShipping(page);
  await snap(page, "05-shipping-filled");
  await advanceCheckoutStep(page); // "Continue to Review"
  await snap(page, "06-checkout-review");
  await advanceCheckoutStep(page); // "Proceed to Payment"
  await page.waitForTimeout(2000);
  await snap(page, "07-checkout-payment");
  await fillStripeAndPay(page);

  // Confirmation
  await waitForConfirmation(page);
  await snap(page, "08-order-confirmed");

  // View cart (empty)
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "09-empty-cart");

  // Assertions
  journey.assertMinVisits(5);
  collector.assertFired("product_viewed", 1);

  journey.printSummary("018 Benjamin Adams");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 019: Subscription Purchase (Stripe Checkout Session)
// Products → Subscriptions tab → "Get Access" → cart →
// checkout (review → Stripe redirect) → cart (still has items)
//
// Subscription-only carts skip shipping and go straight to Review.
// Clicking "Proceed to Payment" creates a Stripe Checkout Session
// and redirects to checkout.stripe.com — E2E verifies the API call
// succeeds but can't complete payment on Stripe's hosted page.
// ────────────────────────────────────────────────────────────────
test("User 019 Evelyn Baker — Checkout Buyer: subscription [Pixel 7]", async ({
  browser,
}) => {
  const user = users[18]; // test019
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
  console.log("  019: Stripe Checkout Session created successfully");

  // Page redirects to Stripe — navigate to cart instead.
  // Cart still has items because Stripe hasn't confirmed the purchase.
  await page.waitForTimeout(1500);
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "06-cart-still-has-items");

  // Assertions
  journey.assertMinVisits(3);

  journey.printSummary("019 Evelyn Baker");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 020: Mixed Cart (1 product + 1 subscription → Stripe Checkout Session)
// Products → view #3 → add → back → Subscriptions tab → "Get Access" →
// cart → checkout (shipping → review → Stripe redirect) → cart (still has items)
//
// Mixed carts (one-time + recurring) use Stripe Checkout Session because
// subscriptions require Stripe-hosted checkout. Shipping is still needed
// for the one-time product.
// ────────────────────────────────────────────────────────────────
test("User 020 Daniel Nelson — Checkout Buyer: mixed cart [iPad Pro]", async ({
  browser,
}) => {
  const user = users[19]; // test020
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add one-time product #3
  await snap(page, "01-products");
  await viewNthProduct(page, 3);
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
  console.log("  020: Stripe Checkout Session created successfully");

  // Navigate to cart — still has items (Stripe hasn't confirmed)
  await page.waitForTimeout(1500);
  await viewCart(page);
  await page.waitForTimeout(1000);
  await snap(page, "08-cart-still-has-items");

  // Assertions
  journey.assertMinVisits(4);
  collector.assertFired("product_viewed", 1);

  journey.printSummary("020 Daniel Nelson");
  await finishJourney(page, context, collector);
});

// ════════════════════════════════════════════════════════════════════════
// Expected Event Fire Count Matrix — ALL 20 Smoke Users
//
// Printed after all tests in this file complete.
// Compare these totals with the admin Event Registry (fire_count_30d)
// for a 1:1 verification that the E2E suite fires the expected events.
//
// Notes:
//   - variant_selected (users 001,005,009) is conditional on product variants
//   - category_browsed (user 006) is conditional on footer link visibility
//   - signup_completed/login_completed fire in 01-register (not in journey files)
//   - cookie_consent_given fires in 01-register consent handling
//   - checkout_abandoned may fire on page unload (not reliably counted)
// ════════════════════════════════════════════════════════════════════════

const EXPECTED: Record<string, Record<string, number>> = {
  // ── File 02: Users 001-005 (Window Shoppers / Cart Manipulators) ──────
  "001": {
    product_viewed: 2,
    search_performed: 1,
    sort_changed: 2,
    filter_used: 2,
  },
  "002": {
    product_viewed: 3,
    add_to_cart: 3,
    cart_viewed: 2,
    cart_quantity_changed: 2,
    remove_from_cart: 1,
  },
  "003": {
    product_viewed: 2,
    add_to_cart: 1,
    cart_viewed: 1,
    search_performed: 2,
    filter_used: 1,
  },
  "004": {
    product_viewed: 1,
    add_to_cart: 1,
    cart_viewed: 1,
    sort_changed: 1,
    cart_quantity_changed: 3,
  },
  "005": {
    product_viewed: 2,
    add_to_cart: 2,
    cart_viewed: 1,
    search_performed: 1,
    sort_changed: 1,
    filter_used: 1,
    cart_quantity_changed: 1,
    remove_from_cart: 1,
  },

  // ── File 03: Users 006-010 (Extended Smoke Journeys) ──────────────────
  "006": {
    product_viewed: 1,
    add_to_cart: 1,
    cart_viewed: 1,
    cart_quantity_changed: 1,
  },
  "007": {
    product_viewed: 2,
    add_to_cart: 2,
    cart_viewed: 1,
    search_performed: 3,
    sort_changed: 2,
    filter_used: 1,
    cart_quantity_changed: 2,
  },
  "008": {
    product_viewed: 4,
    add_to_cart: 4,
    cart_viewed: 2,
    cart_quantity_changed: 1,
    remove_from_cart: 3,
  },
  "009": {
    product_viewed: 3,
    add_to_cart: 3,
    cart_viewed: 2,
    filter_used: 2,
    remove_from_cart: 1,
    search_performed: 1,
  },
  "010": {
    product_viewed: 3,
    add_to_cart: 3,
    cart_viewed: 2,
    sort_changed: 1,
    search_performed: 1,
    cart_quantity_changed: 2,
    remove_from_cart: 1,
  },

  // ── File 04: Users 011-015 (Checkout Buyers — Stripe Elements + Sessions) ─
  "011": {
    product_viewed: 1,
    add_to_cart: 1,
    cart_viewed: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "012": {
    product_viewed: 3,
    add_to_cart: 3,
    cart_viewed: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "013": {
    product_viewed: 2,
    add_to_cart: 2,
    cart_viewed: 1,
    coupon_applied: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "014": {
    add_to_cart: 1,
    cart_viewed: 2,
    checkout_started: 1,
    checkout_step_viewed: 1,
    purchase_completed: 1,
  },
  "015": {
    product_viewed: 1,
    add_to_cart: 2,
    cart_viewed: 2,
    checkout_started: 1,
    checkout_step_viewed: 2,
    purchase_completed: 1,
  },

  // ── File 05: Users 016-020 (Checkout Buyers — second batch) ───────────
  "016": {
    product_viewed: 1,
    add_to_cart: 1,
    cart_viewed: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "017": {
    product_viewed: 2,
    add_to_cart: 2,
    cart_viewed: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "018": {
    product_viewed: 1,
    add_to_cart: 1,
    cart_viewed: 1,
    coupon_applied: 1,
    checkout_started: 1,
    checkout_step_viewed: 3,
    payment_submitted: 1,
    purchase_completed: 1,
    empty_cart_viewed: 1,
  },
  "019": {
    add_to_cart: 1,
    cart_viewed: 2,
    checkout_started: 1,
    checkout_step_viewed: 1,
    purchase_completed: 1,
  },
  "020": {
    product_viewed: 1,
    add_to_cart: 2,
    cart_viewed: 2,
    checkout_started: 1,
    checkout_step_viewed: 2,
    purchase_completed: 1,
  },
};

// Event columns in display order (grouped: browse → cart → checkout)
const COLS = [
  "product_viewed",
  "search_performed",
  "sort_changed",
  "filter_used",
  "add_to_cart",
  "cart_viewed",
  "empty_cart_viewed",
  "cart_quantity_changed",
  "remove_from_cart",
  "coupon_applied",
  "checkout_started",
  "checkout_step_viewed",
  "payment_submitted",
  "purchase_completed",
];

// Short column labels to keep table compact
const LABELS: Record<string, string> = {
  product_viewed: "prd_view",
  search_performed: "search",
  sort_changed: "sort",
  filter_used: "filter",
  add_to_cart: "add_cart",
  cart_viewed: "cart_vw",
  empty_cart_viewed: "empty_cv",
  cart_quantity_changed: "qty_chg",
  remove_from_cart: "rm_cart",
  coupon_applied: "coupon",
  checkout_started: "chk_strt",
  checkout_step_viewed: "chk_step",
  payment_submitted: "pay_sub",
  purchase_completed: "purchase",
};

test.afterAll(() => {
  const userIds = Object.keys(EXPECTED).sort();
  const W = 9; // column width

  const sep = "=".repeat(6 + COLS.length * (W + 1) + W + 1);
  console.log("");
  console.log(sep);
  console.log(
    "  EXPECTED EVENT FIRE COUNTS — All 20 Smoke Users (per run)",
  );
  console.log(
    "  Compare with Admin > Analytics > Event Registry",
  );
  console.log(sep);

  // Header row
  const hdr =
    "User  " +
    COLS.map((c) => (LABELS[c] || c).padStart(W)).join(" ") +
    " " +
    "TOTAL".padStart(W);
  console.log(hdr);
  console.log("-".repeat(hdr.length));

  // Column totals accumulator
  const totals: Record<string, number> = {};
  for (const c of COLS) totals[c] = 0;

  // Section separators
  const sectionBreaks: Record<string, string> = {
    "006": "  --- file 03: users 006-010 ---",
    "011": "  --- file 04: users 011-015 (checkout) ---",
    "016": "  --- file 05: users 016-020 (checkout) ---",
  };

  for (const uid of userIds) {
    if (sectionBreaks[uid]) {
      console.log(sectionBreaks[uid]);
    }

    const ev = EXPECTED[uid];
    let rowSum = 0;
    const cells = COLS.map((c) => {
      const v = ev[c] || 0;
      totals[c] += v;
      rowSum += v;
      return v === 0 ? ".".padStart(W) : String(v).padStart(W);
    });
    console.log(
      uid.padEnd(6) + cells.join(" ") + " " + String(rowSum).padStart(W),
    );
  }

  // Totals row
  console.log("-".repeat(hdr.length));
  let grand = 0;
  const totalCells = COLS.map((c) => {
    grand += totals[c];
    return String(totals[c]).padStart(W);
  });
  console.log(
    "TOTAL " + totalCells.join(" ") + " " + String(grand).padStart(W),
  );
  console.log(sep);
  console.log(
    "  Note: variant_selected (~3) and category_browsed (~1) are conditional",
  );
  console.log(
    "  Note: signup_completed (20) and cookie_consent_given (20) fire in 01-register",
  );
  console.log("");
});
