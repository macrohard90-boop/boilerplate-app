/**
 * Group 1: Users 001-005 — Simple diagnostic journeys.
 * Each user tests one core flow to verify the app works end-to-end.
 * Keep these SHORT so failures are easy to diagnose.
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
  visitHomepage,
  visitProfile,
  visitOrders,
  viewCart,
  addToCart,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 001: Browse products — Desktop Chrome
// Just: products → view product → back → view another → profile
// Tests: basic navigation, product detail, dashboard auth
// ────────────────────────────────────────────────────────────────
test("User 001 — Browse products [Desktop Chrome]", async ({ browser }) => {
  const user = users[0];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Already on /products from createUserContext — browse
  await snap(page, "01-products");
  await page.waitForTimeout(2000);

  // Step 2: View first product
  await viewNthProduct(page, 0);
  await snap(page, "02-product-detail");
  await page.waitForTimeout(2000);

  // Step 3: Back to products
  await backToProducts(page);
  await snap(page, "03-back-to-products");
  await page.waitForTimeout(2000);

  // Step 4: View second product
  await viewNthProduct(page, 1);
  await snap(page, "04-product-detail-2");
  await page.waitForTimeout(2000);

  // Step 5: Visit profile (dashboard page — tests auth persistence)
  await visitProfile(page);
  await snap(page, "05-profile");

  // Verify we're still on the profile page (not redirected to login)
  expect(page.url()).toContain("/dashboard/profile");

  journey.printSummary("001 Browse");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 002: Cart flow — Desktop Large
// Just: products → view product → add to cart → view cart → orders
// Tests: add-to-cart, cart page, dashboard orders
// ────────────────────────────────────────────────────────────────
test("User 002 — Cart flow [Desktop Large]", async ({ browser }) => {
  const user = users[1];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: View a product
  await viewNthProduct(page, 2);
  await snap(page, "01-product-detail");
  await page.waitForTimeout(2000);

  // Step 2: Add to cart
  const added = await addToCart(page);
  await snap(page, "02-after-add-to-cart");
  console.log(`  Add to cart: ${added ? "success" : "button not found"}`);
  await page.waitForTimeout(2000);

  // Step 3: View cart
  await viewCart(page);
  await snap(page, "03-cart-page");
  await page.waitForTimeout(2000);

  // Step 4: Visit orders (dashboard page — tests auth)
  await visitOrders(page);
  await snap(page, "04-orders");

  expect(page.url()).toContain("/dashboard/orders");

  journey.printSummary("002 Cart");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 003: Homepage + products — iPhone 13
// Just: homepage → products → view product → homepage
// Tests: mobile viewport, homepage, navigation
// ────────────────────────────────────────────────────────────────
test("User 003 — Homepage + products [iPhone 13]", async ({ browser }) => {
  const user = users[2];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Visit homepage
  await visitHomepage(page);
  await snap(page, "01-homepage");
  await page.waitForTimeout(2000);

  // Step 2: Go to products
  await browseProducts(page);
  await snap(page, "02-products");
  await page.waitForTimeout(2000);

  // Step 3: View a product
  await viewNthProduct(page, 0);
  await snap(page, "03-product-detail");
  await page.waitForTimeout(2000);

  // Step 4: Back to homepage
  await visitHomepage(page);
  await snap(page, "04-homepage-again");

  journey.printSummary("003 Homepage");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 004: Dashboard pages — Pixel 7
// Just: products → profile → orders → products
// Tests: multiple dashboard page visits (auth persistence under stress)
// ────────────────────────────────────────────────────────────────
test("User 004 — Dashboard pages [Pixel 7]", async ({ browser }) => {
  const user = users[3];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Visit profile
  await visitProfile(page);
  await snap(page, "01-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(2000);

  // Step 2: Visit orders
  await visitOrders(page);
  await snap(page, "02-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(2000);

  // Step 3: Back to products
  await browseProducts(page);
  await snap(page, "03-products");
  await page.waitForTimeout(2000);

  // Step 4: Profile again (verify auth still holds)
  await visitProfile(page);
  await snap(page, "04-profile-again");
  expect(page.url()).toContain("/dashboard/profile");

  journey.printSummary("004 Dashboard");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 005: Full loop — iPad Pro
// Just: products → product → add to cart → cart → profile → products
// Tests: complete user flow across public + protected pages
// ────────────────────────────────────────────────────────────────
test("User 005 — Full loop [iPad Pro]", async ({ browser }) => {
  const user = users[4];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: View a product
  await viewNthProduct(page, 3);
  await snap(page, "01-product-detail");
  await page.waitForTimeout(2000);

  // Step 2: Add to cart
  await addToCart(page);
  await snap(page, "02-added-to-cart");
  await page.waitForTimeout(2000);

  // Step 3: View cart
  await viewCart(page);
  await snap(page, "03-cart");
  await page.waitForTimeout(2000);

  // Step 4: Visit profile
  await visitProfile(page);
  await snap(page, "04-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(2000);

  // Step 5: Back to products
  await browseProducts(page);
  await snap(page, "05-products-again");

  journey.printSummary("005 Full Loop");
  await finishJourney(page, context, collector);
});
