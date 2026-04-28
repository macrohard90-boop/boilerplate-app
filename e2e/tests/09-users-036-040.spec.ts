/**
 * Group 8: Users 036-040
 * 036-037: Single Buyers — browse, add to cart, complete full checkout with Stripe.
 * 038-040: Power Buyers — extensive browsing, multi-item carts, coupons, cart edits, full checkout.
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
  removeFromCart,
  applyCoupon,
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
// User 036: Olivia Garcia — iPad Pro — 12 pages (Single Buyer)
// Products → sort price_desc → view #0 → back → view #1 → back →
// view #2 → add to cart → cart → checkout → shipping → review →
// Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 036 Olivia Garcia — Single Buyer [iPad Pro]", async ({
  browser,
}) => {
  const user = users[35]; // test036
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(5000);
  await snap(page, "01-products-listing");

  // Step 2: Sort by price descending
  await changeSort(page, "price_desc");
  await page.waitForTimeout(3000);
  await snap(page, "02-sort-price-desc");

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
  await page.waitForTimeout(3000);
  await snap(page, "10-checkout");

  // Step 11: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-shipping-filled");

  // Step 12: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-review-step");

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
  journey.printSummary("036 Olivia Garcia");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 037: Noah Robinson — Mobile Landscape — 12 pages (Single Buyer)
// Products → view #7 → back → view #8 → back → view #9 →
// add to cart → cart → checkout → shipping → review →
// Stripe pay → confirmation → orders
// ────────────────────────────────────────────────────────────────
test("User 037 Noah Robinson — Single Buyer [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[36]; // test037
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products listing
  await page.waitForTimeout(4000);
  await snap(page, "01-products-listing");

  // Step 2: View product #7
  await viewNthProduct(page, 7);
  await page.waitForTimeout(5000);
  await snap(page, "02-product-detail-7");

  // Step 3: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "03-back-to-products");

  // Step 4: View product #8
  await viewNthProduct(page, 8);
  await page.waitForTimeout(5000);
  await snap(page, "04-product-detail-8");

  // Step 5: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-back-to-products-2");

  // Step 6: View product #9
  await viewNthProduct(page, 9);
  await page.waitForTimeout(5000);
  await snap(page, "06-product-detail-9");

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
  await page.waitForTimeout(3000);
  await snap(page, "09-checkout");

  // Step 10: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-shipping-filled");

  // Step 11: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-review-step");

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

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 1);

  // Print summary
  journey.printSummary("037 Noah Robinson");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 038: Ava Clark — Desktop Chrome — 16 pages (Power Buyer)
// Products → view #0 → add to cart → back → view #1 → add to cart →
// back → view #2 → add to cart → back → view #3 → back →
// cart → increase qty → remove first → coupon FAKECOUPON →
// coupon WELCOME10 → checkout → shipping → review →
// Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 038 Ava Clark — Power Buyer [Desktop Chrome]", async ({
  browser,
}) => {
  const user = users[37]; // test038
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
  await page.waitForTimeout(4000);
  await snap(page, "05-product-detail-1");

  // Step 6: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-added-to-cart-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-2");

  // Step 8: View product #2
  await viewNthProduct(page, 2);
  await page.waitForTimeout(4000);
  await snap(page, "08-product-detail-2");

  // Step 9: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-added-to-cart-3");

  // Step 10: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "10-back-to-products-3");

  // Step 11: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(5000);
  await snap(page, "11-product-detail-3");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-to-products-4");

  // Step 13: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "13-cart");

  // Step 14: Increase quantity of first item
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-cart-increase-qty");

  // Step 15: Remove first item from cart
  await removeFromCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "15-cart-removed-item");

  // Step 16: Try invalid coupon
  await applyCoupon(page, "FAKECOUPON");
  await page.waitForTimeout(3000);
  await snap(page, "16-coupon-fakecoupon");

  // Step 17: Apply valid coupon
  await applyCoupon(page, "WELCOME10");
  await page.waitForTimeout(3000);
  await snap(page, "17-coupon-welcome10");

  // Step 18: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(3000);
  await snap(page, "18-checkout");

  // Step 19: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "19-shipping-filled");

  // Step 20: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(3000);
  await snap(page, "20-review-step");

  // Step 21: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "21-stripe-paying");

  // Step 22: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "22-confirmation");

  // Step 23: Visit orders
  await visitOrders(page);
  await page.waitForTimeout(3000);
  await snap(page, "23-orders");

  // Step 24: View order detail
  await visitFirstOrderDetail(page);
  await page.waitForTimeout(4000);
  await snap(page, "24-order-detail");

  // Step 25: Continue shopping
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "25-continue-shopping");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 4);
  collector.assertFired("add_to_cart", 3);

  // Print summary
  journey.printSummary("038 Ava Clark");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 039: James Rodriguez — Desktop Large — 15 pages (Power Buyer)
// Products → search "pro" → filter category #0 → view #0 →
// add to cart → back → view #3 → add to cart → back →
// view #4 → back → cart → increase qty → coupon WELCOME10 →
// checkout → shipping → review → Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 039 James Rodriguez — Power Buyer [Desktop Large]", async ({
  browser,
}) => {
  const user = users[38]; // test039
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

  // Step 3: Filter by category #0
  await filterByNthCategory(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "03-filter-category-0");

  // Step 4: View product #0
  await viewNthProduct(page, 0);
  await page.waitForTimeout(4000);
  await snap(page, "04-product-detail-0");

  // Step 5: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "05-added-to-cart");

  // Step 6: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "06-back-to-products");

  // Step 7: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(4000);
  await snap(page, "07-product-detail-3");

  // Step 8: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "08-added-to-cart-2");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-2");

  // Step 10: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(5000);
  await snap(page, "10-product-detail-4");

  // Step 11: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-back-to-products-3");

  // Step 12: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "12-cart");

  // Step 13: Increase quantity of first item
  await increaseQuantity(page);
  await page.waitForTimeout(3000);
  await snap(page, "13-cart-increase-qty");

  // Step 14: Apply coupon
  await applyCoupon(page, "WELCOME10");
  await page.waitForTimeout(3000);
  await snap(page, "14-coupon-welcome10");

  // Step 15: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(3000);
  await snap(page, "15-checkout");

  // Step 16: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "16-shipping-filled");

  // Step 17: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(3000);
  await snap(page, "17-review-step");

  // Step 18: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "18-stripe-paying");

  // Step 19: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "19-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 3);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("039 James Rodriguez");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 040: Sophia Lewis — iPhone 13 — 17 pages (Power Buyer)
// Products → view #0 → back → view #1 → back → view #2 → back →
// view #3 → back → view #4 → add to cart → back →
// view #5 → add to cart → cart → remove first →
// checkout → shipping → review → Stripe pay → confirmation
// ────────────────────────────────────────────────────────────────
test("User 040 Sophia Lewis — Power Buyer [iPhone 13]", async ({
  browser,
}) => {
  const user = users[39]; // test040
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
  await page.waitForTimeout(4000);
  await snap(page, "06-product-detail-2");

  // Step 7: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "07-back-to-products-3");

  // Step 8: View product #3
  await viewNthProduct(page, 3);
  await page.waitForTimeout(4000);
  await snap(page, "08-product-detail-3");

  // Step 9: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "09-back-to-products-4");

  // Step 10: View product #4
  await viewNthProduct(page, 4);
  await page.waitForTimeout(4000);
  await snap(page, "10-product-detail-4");

  // Step 11: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "11-added-to-cart");

  // Step 12: Back to products
  await backToProducts(page);
  await page.waitForTimeout(3000);
  await snap(page, "12-back-to-products-5");

  // Step 13: View product #5
  await viewNthProduct(page, 5);
  await page.waitForTimeout(4000);
  await snap(page, "13-product-detail-5");

  // Step 14: Add to cart
  await addToCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "14-added-to-cart-2");

  // Step 15: View cart
  await viewCart(page);
  await page.waitForTimeout(5000);
  await snap(page, "15-cart");

  // Step 16: Remove first item from cart
  await removeFromCart(page);
  await page.waitForTimeout(3000);
  await snap(page, "16-cart-removed-item");

  // Step 17: Start checkout
  await startCheckout(page);
  await page.waitForTimeout(3000);
  await snap(page, "17-checkout");

  // Step 18: Fill shipping
  await fillShipping(page);
  await page.waitForTimeout(3000);
  await snap(page, "18-shipping-filled");

  // Step 19: Advance to review
  await advanceCheckoutStep(page);
  await page.waitForTimeout(3000);
  await snap(page, "19-review-step");

  // Step 20: Fill Stripe and pay
  await fillStripeAndPay(page);
  await snap(page, "20-stripe-paying");

  // Step 21: Wait for confirmation
  await waitForConfirmation(page);
  await page.waitForTimeout(5000);
  await snap(page, "21-confirmation");

  // Assertions
  journey.assertMinVisits(10);
  collector.assertFired("product_viewed", 6);
  collector.assertFired("add_to_cart", 2);

  // Print summary
  journey.printSummary("040 Sophia Lewis");
  await finishJourney(page, context, collector);
});
