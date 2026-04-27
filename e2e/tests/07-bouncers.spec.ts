/**
 * Test 07: Bouncer journeys — 5 users who barely interact.
 * Land on the site, view 1 product, leave immediately.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { browseProducts, viewRandomProduct } from "../helpers/actions";

const bouncers = getUsersByPersona("bouncer");

for (const user of bouncers) {
  test(`Bouncer #${user.index} [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    // Land on products page
    await browseProducts(page);

    // Click one product
    const href = await viewRandomProduct(page);
    expect(href).toBeTruthy();

    // Wait briefly for events to fire
    await page.waitForTimeout(1500);

    // Bouncer just leaves — verify at least one product_viewed
    collector.assertFired("product_viewed");

    console.log(`  Bouncer #${user.index} events:`, collector.summary());
    await context.close();
  });
}
