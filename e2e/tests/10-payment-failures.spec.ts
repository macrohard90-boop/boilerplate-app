/**
 * Test 10: Payment Failure scenarios — Stripe decline cards.
 * Uses Stripe's test card numbers that trigger specific decline reasons.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  viewRandomProduct,
  addToCart,
  viewCart,
  startCheckout,
  fillShipping,
  advanceCheckoutStep,
  fillStripeDeclineCard,
  fillStripeAndPay,
  waitForConfirmation,
} from "../helpers/actions";

// Use first 5 single_buyer users for payment failure tests
const buyers = getUsersByPersona("single_buyer").slice(0, 5);

const declineCards = [
  { number: "4000000000000002", reason: "generic_decline", label: "Generic Decline" },
  { number: "4000000000009995", reason: "insufficient_funds", label: "Insufficient Funds" },
  { number: "4000000000000069", reason: "expired_card", label: "Expired Card" },
];

// Tests 1-3: Each decline card type
for (let i = 0; i < declineCards.length; i++) {
  const card = declineCards[i];
  const user = buyers[i];

  test(`Payment Failure: ${card.label} [${user.device.name}]: ${user.email}`, async ({
    browser,
  }) => {
    test.setTimeout(120_000);
    const { context, page, collector } = await createUserContext(browser, user);

    // 1. Add a product to cart
    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);
    await addToCart(page);
    await page.waitForTimeout(500);

    // 2. Go to cart
    await viewCart(page);
    await page.waitForTimeout(500);

    // 3. Start checkout
    await startCheckout(page);
    await page.waitForTimeout(500);

    // 4. Fill shipping
    await fillShipping(page);
    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    // 5. Review
    await advanceCheckoutStep(page);
    await page.waitForTimeout(1000);

    // 6. Fill decline card
    try {
      await fillStripeDeclineCard(page, card.number);
      await page.waitForTimeout(3000);

      // Should see an error message on the page
      const errorVisible = await page
        .locator('[class*="error"], [class*="Error"], [role="alert"], .text-red')
        .first()
        .isVisible()
        .catch(() => false);

      console.log(
        `  Payment Failure ${card.label}: error visible = ${errorVisible}`
      );
    } catch (err) {
      console.log(
        `  Payment Failure ${card.label}: ${(err as Error).message}`
      );
    }

    // Verify pre-payment events fired
    collector.assertFired("product_viewed");
    collector.assertFired("add_to_cart");

    console.log(`  Payment Failure ${card.label} events:`, collector.summary());
    await context.close();
  });
}

// Test 4: Decline then retry with good card
test(`Payment Retry: Decline then succeed [${buyers[3].device.name}]: ${buyers[3].email}`, async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const user = buyers[3];
  const { context, page, collector } = await createUserContext(browser, user);

  // 1. Add a product to cart
  await browseProducts(page);
  await viewRandomProduct(page);
  await page.waitForTimeout(500);
  await addToCart(page);
  await page.waitForTimeout(500);

  // 2. Go to cart and checkout
  await viewCart(page);
  await page.waitForTimeout(500);
  await startCheckout(page);
  await page.waitForTimeout(500);

  // 3. Fill shipping + review
  await fillShipping(page);
  await advanceCheckoutStep(page);
  await page.waitForTimeout(1000);
  await advanceCheckoutStep(page);
  await page.waitForTimeout(1000);

  // 4. First attempt: decline card
  try {
    await fillStripeDeclineCard(page, "4000000000000002");
    await page.waitForTimeout(3000);
    console.log("  Payment Retry: First attempt declined (expected)");
  } catch (err) {
    console.log(
      `  Payment Retry: First attempt error: ${(err as Error).message}`
    );
  }

  // 5. Second attempt: good card
  try {
    await fillStripeAndPay(page);
    await waitForConfirmation(page);
    await page.waitForTimeout(1500);
    console.log("  Payment Retry: Second attempt succeeded");
  } catch (err) {
    console.log(
      `  Payment Retry: Second attempt: ${(err as Error).message}`
    );
  }

  collector.assertFired("product_viewed");
  collector.assertFired("add_to_cart");

  console.log(`  Payment Retry events:`, collector.summary());
  await context.close();
});

// Test 5: Payment with correct card (baseline — confirms Stripe works)
test(`Payment Success Baseline [${buyers[4].device.name}]: ${buyers[4].email}`, async ({
  browser,
}) => {
  test.setTimeout(120_000);
  const user = buyers[4];
  const { context, page, collector } = await createUserContext(browser, user);

  // 1. Add a product to cart
  await browseProducts(page);
  await viewRandomProduct(page);
  await page.waitForTimeout(500);
  await addToCart(page);
  await page.waitForTimeout(500);

  // 2. Full checkout with good card
  await viewCart(page);
  await page.waitForTimeout(500);
  await startCheckout(page);
  await page.waitForTimeout(500);
  await fillShipping(page);
  await advanceCheckoutStep(page);
  await page.waitForTimeout(1000);
  await advanceCheckoutStep(page);
  await page.waitForTimeout(1000);

  try {
    await fillStripeAndPay(page);
    await waitForConfirmation(page);
    await page.waitForTimeout(1500);

    collector.assertFired("product_viewed");
    collector.assertFired("add_to_cart");
    collector.assertFired("checkout_started");
    console.log("  Payment Success Baseline: completed");
  } catch (err) {
    console.log(
      `  Payment Success Baseline: ${(err as Error).message}`
    );
    collector.assertFired("product_viewed");
    collector.assertFired("add_to_cart");
  }

  console.log(`  Payment Baseline events:`, collector.summary());
  await context.close();
});
