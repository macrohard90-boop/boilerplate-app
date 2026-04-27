/**
 * Test 07: Bouncer journeys — 3 users × 3 journey variants = 9 tests.
 * Quick visits — view 1-2 pages, leave immediately.
 */

import { test, expect } from "@playwright/test";
import { getUsersByPersona } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { browseProducts, viewRandomProduct } from "../helpers/actions";

const bouncers = getUsersByPersona("bouncer");

// Journey A: Land on products, click one product, leave
for (const user of bouncers) {
  test(`Bouncer #${user.index} Product Peek [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await viewRandomProduct(page);
    await page.waitForTimeout(500);

    collector.assertFired("product_viewed");
    console.log(`  Bouncer #${user.index} Peek events:`, collector.summary());
    await context.close();
  });
}

// Journey B: Land on homepage, leave without clicking products
for (const user of bouncers) {
  test(`Bouncer #${user.index} Homepage [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    console.log(`  Bouncer #${user.index} Homepage events:`, collector.summary());
    await context.close();
  });
}

// Journey C: Browse products listing, scroll, leave without clicking any
for (const user of bouncers) {
  test(`Bouncer #${user.index} Browse Only [${user.device.name}]: ${user.email}`, async ({ browser }) => {
    const { context, page, collector } = await createUserContext(browser, user);

    await browseProducts(page);
    await page.waitForTimeout(800);

    // Scroll to simulate browsing
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(500);
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(500);

    console.log(`  Bouncer #${user.index} Browse events:`, collector.summary());
    await context.close();
  });
}
