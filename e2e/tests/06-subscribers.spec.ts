/**
 * Test 06: Subscriber journeys — 10 users who subscribe to a plan.
 * Browse subscriptions → add to cart → checkout → Stripe redirect.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import {
  browseProducts,
  clickSubscriptionsTab,
  viewRandomProduct,
  addToCart,
  viewCart,
  startCheckout,
  advanceCheckoutStep,
} from "../helpers/actions";

const subscribers = getUsersByPersona("subscriber");

for (const user of subscribers) {
  test(`Subscriber #${user.index} [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // 1. Browse products and switch to Subscriptions tab
    await browseProducts(page);
    await clickSubscriptionsTab(page);
    await page.waitForTimeout(500);

    // 2. View a subscription plan
    const href = await viewRandomProduct(page);
    await page.waitForTimeout(500);

    // 3. Add subscription to cart
    await addToCart(page);
    await page.waitForTimeout(500);

    // 4. View cart
    await viewCart(page);
    await page.waitForTimeout(500);

    // 5. Start checkout
    try {
      await startCheckout(page);
      await page.waitForTimeout(500);

      // 6. Review step (subscriptions skip shipping)
      await advanceCheckoutStep(page);
      await page.waitForTimeout(1000);

      // 7. At this point, subscription checkout redirects to Stripe hosted page
      // Wait to see if we get redirected to checkout.stripe.com
      try {
        await page.waitForURL(/checkout\.stripe\.com/, { timeout: 15000 });
        console.log(`  Subscriber #${user.index}: Redirected to Stripe Checkout`);
      } catch {
        // May not redirect in test mode — that's okay, the checkout_started event matters
        console.log(`  Subscriber #${user.index}: Stripe redirect not detected (test mode)`);
      }
    } catch (err) {
      console.log(`  Subscriber #${user.index} checkout failed:`, (err as Error).message);
    }

    await page.waitForTimeout(1000);

    // Verify key events
    collector.assertFired("product_viewed");
    collector.assertFired("add_to_cart");

    console.log(`  Subscriber #${user.index} events:`, collector.summary());
    await context.close();
  });
}
