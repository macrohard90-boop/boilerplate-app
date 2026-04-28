/**
 * Group 1: Users 001-005 — Extended smoke journeys.
 * Each user exercises 12-20+ page actions: search, category filter,
 * sort, product browsing, add to cart, cart manipulation (qty, remove),
 * footer navigation, dashboard pages, and auth persistence.
 */

import { test, expect } from "@playwright/test";
import { getAllUsers } from "../helpers/users";
import { createUserContext } from "../fixtures/test-fixtures";
import { JourneyLogger } from "../helpers/journey-logger";
import { snap } from "../helpers/screenshot";
import {
  browseProducts,
  viewNthProduct,
  viewRandomProduct,
  backToProducts,
  visitHomepage,
  visitProfile,
  visitOrders,
  viewCart,
  addToCart,
  searchProducts,
  changeSort,
  filterByNthCategory,
  resetCategoryFilter,
  selectVariant,
  increaseQuantity,
  decreaseQuantity,
  removeFromCart,
  clickSubscriptionsTab,
  finishJourney,
} from "../helpers/actions";

const users = getAllUsers();

// ────────────────────────────────────────────────────────────────
// User 001: Deep browse + search — Desktop Chrome
// products → search → sort → filter category → view product →
// select variant → back → filter another category → view product →
// visit homepage → products again → profile → orders
// ────────────────────────────────────────────────────────────────
test("User 001 — Deep browse + search [Desktop Chrome]", async ({ browser }) => {
  const user = users[0];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products page loaded from createUserContext
  await snap(page, "01-products");
  await page.waitForTimeout(1500);

  // Step 2: Search for something
  await searchProducts(page, "premium");
  await snap(page, "02-search-premium");
  await page.waitForTimeout(1500);

  // Step 3: Clear search, change sort to price low-to-high
  await searchProducts(page, "");
  await changeSort(page, "price_asc");
  await snap(page, "03-sorted-price-asc");
  await page.waitForTimeout(1500);

  // Step 4: Filter by first category
  const cat1 = await filterByNthCategory(page, 0);
  console.log(`  Filtered by category: ${cat1}`);
  await snap(page, "04-category-filter-1");
  await page.waitForTimeout(1500);

  // Step 5: View the first product in this filtered list
  await viewNthProduct(page, 0);
  await snap(page, "05-product-detail");
  await page.waitForTimeout(1500);

  // Step 6: Try selecting a variant
  const variantSelected = await selectVariant(page);
  console.log(`  Variant selected: ${variantSelected}`);
  await snap(page, "06-variant-selected");
  await page.waitForTimeout(1000);

  // Step 7: Back to products
  await backToProducts(page);
  await snap(page, "07-back-to-products");
  await page.waitForTimeout(1500);

  // Step 8: Filter by second category
  const cat2 = await filterByNthCategory(page, 1);
  console.log(`  Filtered by category: ${cat2}`);
  await snap(page, "08-category-filter-2");
  await page.waitForTimeout(1500);

  // Step 9: View a product from this category
  await viewNthProduct(page, 0);
  await snap(page, "09-product-detail-2");
  await page.waitForTimeout(1500);

  // Step 10: Visit homepage
  await visitHomepage(page);
  await snap(page, "10-homepage");
  await page.waitForTimeout(1500);

  // Step 11: Back to products, reset category filter
  await browseProducts(page);
  await resetCategoryFilter(page);
  await snap(page, "11-products-all");
  await page.waitForTimeout(1500);

  // Step 12: Sort by name
  await changeSort(page, "name");
  await snap(page, "12-sorted-name");
  await page.waitForTimeout(1000);

  // Step 13: Visit profile (auth test)
  await visitProfile(page);
  await snap(page, "13-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1500);

  // Step 14: Visit orders (auth test)
  await visitOrders(page);
  await snap(page, "14-orders");
  expect(page.url()).toContain("/dashboard/orders");

  journey.printSummary("001 Deep Browse");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 002: Cart manipulation — Desktop Large
// products → view product → add to cart → view another → add →
// view cart → increase qty → decrease qty → remove first item →
// continue shopping → view product → add → cart again → orders
// ────────────────────────────────────────────────────────────────
test("User 002 — Cart manipulation [Desktop Large]", async ({ browser }) => {
  const user = users[1];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: View first product
  await viewNthProduct(page, 0);
  await snap(page, "01-product-1");
  await page.waitForTimeout(1500);

  // Step 2: Add to cart
  const added1 = await addToCart(page);
  console.log(`  Add product 1: ${added1 ? "success" : "skipped"}`);
  await snap(page, "02-added-1");
  await page.waitForTimeout(1500);

  // Step 3: Back to products, view second product
  await backToProducts(page);
  await viewNthProduct(page, 1);
  await snap(page, "03-product-2");
  await page.waitForTimeout(1500);

  // Step 4: Add second product to cart
  const added2 = await addToCart(page);
  console.log(`  Add product 2: ${added2 ? "success" : "skipped"}`);
  await snap(page, "04-added-2");
  await page.waitForTimeout(1500);

  // Step 5: View cart — should have 2 items
  await viewCart(page);
  await snap(page, "05-cart-2-items");
  await page.waitForTimeout(1500);

  // Step 6: Increase quantity on first item
  await increaseQuantity(page);
  await snap(page, "06-qty-increased");
  await page.waitForTimeout(1000);

  // Step 7: Decrease quantity back
  await decreaseQuantity(page);
  await snap(page, "07-qty-decreased");
  await page.waitForTimeout(1000);

  // Step 8: Remove first item
  await removeFromCart(page);
  await snap(page, "08-removed-item");
  await page.waitForTimeout(1500);

  // Step 9: Continue shopping (back to products)
  await browseProducts(page);
  await snap(page, "09-continue-shopping");
  await page.waitForTimeout(1500);

  // Step 10: View a third product
  await viewNthProduct(page, 2);
  await snap(page, "10-product-3");
  await page.waitForTimeout(1500);

  // Step 11: Add to cart
  const added3 = await addToCart(page);
  console.log(`  Add product 3: ${added3 ? "success" : "skipped"}`);
  await page.waitForTimeout(1500);

  // Step 12: View cart again
  await viewCart(page);
  await snap(page, "12-cart-final");
  await page.waitForTimeout(1500);

  // Step 13: Visit orders (auth check)
  await visitOrders(page);
  await snap(page, "13-orders");
  expect(page.url()).toContain("/dashboard/orders");

  journey.printSummary("002 Cart Manipulation");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 003: Mobile search + category browse — iPhone 13
// homepage → products → search → clear → category filter →
// view product → add to cart → cart → back → another search →
// view product → homepage → profile
// ────────────────────────────────────────────────────────────────
test("User 003 — Mobile search + category [iPhone 13]", async ({ browser }) => {
  const user = users[2];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Visit homepage
  await visitHomepage(page);
  await snap(page, "01-homepage");
  await page.waitForTimeout(1500);

  // Step 2: Go to products
  await browseProducts(page);
  await snap(page, "02-products");
  await page.waitForTimeout(1500);

  // Step 3: Search for a product
  await searchProducts(page, "shirt");
  await snap(page, "03-search-shirt");
  await page.waitForTimeout(1500);

  // Step 4: Clear search
  await searchProducts(page, "");
  await snap(page, "04-search-cleared");
  await page.waitForTimeout(1000);

  // Step 5: Filter by first category
  const cat = await filterByNthCategory(page, 0);
  console.log(`  Category filter: ${cat}`);
  await snap(page, "05-category-filtered");
  await page.waitForTimeout(1500);

  // Step 6: View a product
  await viewNthProduct(page, 0);
  await snap(page, "06-product-detail");
  await page.waitForTimeout(1500);

  // Step 7: Add to cart
  const added = await addToCart(page);
  console.log(`  Add to cart: ${added ? "success" : "skipped"}`);
  await snap(page, "07-added-to-cart");
  await page.waitForTimeout(1500);

  // Step 8: View cart
  await viewCart(page);
  await snap(page, "08-cart");
  await page.waitForTimeout(1500);

  // Step 9: Back to products
  await browseProducts(page);
  await snap(page, "09-back-to-products");
  await page.waitForTimeout(1500);

  // Step 10: Search for something else
  await searchProducts(page, "electronics");
  await snap(page, "10-search-electronics");
  await page.waitForTimeout(1500);

  // Step 11: View a product from search results
  await viewNthProduct(page, 0);
  await snap(page, "11-product-from-search");
  await page.waitForTimeout(1500);

  // Step 12: Visit homepage again
  await visitHomepage(page);
  await snap(page, "12-homepage-again");
  await page.waitForTimeout(1000);

  // Step 13: Visit profile (auth persistence check on mobile)
  await visitProfile(page);
  await snap(page, "13-profile");
  expect(page.url()).toContain("/dashboard/profile");

  journey.printSummary("003 Mobile Search + Category");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 004: Dashboard stress + cart — Pixel 7
// products → profile → orders → products → sort → view product →
// add to cart → cart → increase qty × 2 → decrease qty → cart →
// profile again → orders again → products → homepage
// ────────────────────────────────────────────────────────────────
test("User 004 — Dashboard stress + cart [Pixel 7]", async ({ browser }) => {
  const user = users[3];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Visit profile first (auth test from the start)
  await visitProfile(page);
  await snap(page, "01-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1500);

  // Step 2: Orders page
  await visitOrders(page);
  await snap(page, "02-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1500);

  // Step 3: Back to products
  await browseProducts(page);
  await snap(page, "03-products");
  await page.waitForTimeout(1500);

  // Step 4: Sort by price high-to-low
  await changeSort(page, "price_desc");
  await snap(page, "04-sorted-price-desc");
  await page.waitForTimeout(1500);

  // Step 5: View highest-priced product
  await viewNthProduct(page, 0);
  await snap(page, "05-product-detail");
  await page.waitForTimeout(1500);

  // Step 6: Add to cart
  const added = await addToCart(page);
  console.log(`  Add to cart: ${added ? "success" : "skipped"}`);
  await snap(page, "06-added");
  await page.waitForTimeout(1500);

  // Step 7: View cart
  await viewCart(page);
  await snap(page, "07-cart");
  await page.waitForTimeout(1500);

  // Step 8: Increase quantity twice
  await increaseQuantity(page);
  await page.waitForTimeout(800);
  await increaseQuantity(page);
  await snap(page, "08-qty-increased-twice");
  await page.waitForTimeout(1000);

  // Step 9: Decrease quantity once
  await decreaseQuantity(page);
  await snap(page, "09-qty-decreased");
  await page.waitForTimeout(1000);

  // Step 10: Back to products
  await browseProducts(page);
  await snap(page, "10-products-again");
  await page.waitForTimeout(1500);

  // Step 11: Profile again (auth still holds?)
  await visitProfile(page);
  await snap(page, "11-profile-again");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1500);

  // Step 12: Orders again (auth still holds?)
  await visitOrders(page);
  await snap(page, "12-orders-again");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1000);

  // Step 13: Browse products one more time
  await browseProducts(page);
  await snap(page, "13-products-final");
  await page.waitForTimeout(1000);

  // Step 14: Homepage to wrap up
  await visitHomepage(page);
  await snap(page, "14-homepage");

  journey.printSummary("004 Dashboard Stress + Cart");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 005: Full loop with everything — iPad Pro
// products → search → sort → view product → select variant →
// add to cart → products → filter category → view product →
// add to cart → cart → increase qty → remove one → view cart →
// continue shopping → subscriptions tab → back to products tab →
// profile → orders → homepage
// ────────────────────────────────────────────────────────────────
test("User 005 — Full loop with everything [iPad Pro]", async ({ browser }) => {
  const user = users[4];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Search for products
  await searchProducts(page, "pro");
  await snap(page, "01-search-pro");
  await page.waitForTimeout(1500);

  // Step 2: Sort results by price
  await changeSort(page, "price_asc");
  await snap(page, "02-sorted");
  await page.waitForTimeout(1000);

  // Step 3: Clear search and view first product
  await searchProducts(page, "");
  await viewNthProduct(page, 0);
  await snap(page, "03-product-1");
  await page.waitForTimeout(1500);

  // Step 4: Try selecting a variant
  await selectVariant(page);
  await snap(page, "04-variant");
  await page.waitForTimeout(1000);

  // Step 5: Add to cart
  const added1 = await addToCart(page);
  console.log(`  Add product 1: ${added1 ? "success" : "skipped"}`);
  await snap(page, "05-added-1");
  await page.waitForTimeout(1500);

  // Step 6: Back to products, filter by category
  await backToProducts(page);
  const cat = await filterByNthCategory(page, 0);
  console.log(`  Category: ${cat}`);
  await snap(page, "06-category-filtered");
  await page.waitForTimeout(1500);

  // Step 7: View product from filtered list
  await viewNthProduct(page, 0);
  await snap(page, "07-product-2");
  await page.waitForTimeout(1500);

  // Step 8: Add second product
  const added2 = await addToCart(page);
  console.log(`  Add product 2: ${added2 ? "success" : "skipped"}`);
  await snap(page, "08-added-2");
  await page.waitForTimeout(1500);

  // Step 9: View cart
  await viewCart(page);
  await snap(page, "09-cart");
  await page.waitForTimeout(1500);

  // Step 10: Increase qty on first item
  await increaseQuantity(page);
  await snap(page, "10-qty-up");
  await page.waitForTimeout(1000);

  // Step 11: Remove an item
  await removeFromCart(page);
  await snap(page, "11-removed");
  await page.waitForTimeout(1500);

  // Step 12: Continue shopping — browse products
  await browseProducts(page);
  await resetCategoryFilter(page);
  await snap(page, "12-products-again");
  await page.waitForTimeout(1500);

  // Step 13: Check subscriptions tab
  await clickSubscriptionsTab(page);
  await snap(page, "13-subscriptions-tab");
  await page.waitForTimeout(1500);

  // Step 14: Back to products tab (click "Products" tab button)
  const productsTab = page.locator("button").filter({ hasText: "Products" }).first();
  if (await productsTab.isVisible().catch(() => false)) {
    await productsTab.click();
    await page.waitForLoadState("networkidle");
  }
  await snap(page, "14-products-tab");
  await page.waitForTimeout(1000);

  // Step 15: Profile (auth check)
  await visitProfile(page);
  await snap(page, "15-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1500);

  // Step 16: Orders (auth check)
  await visitOrders(page);
  await snap(page, "16-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1000);

  // Step 17: Homepage to wrap up
  await visitHomepage(page);
  await snap(page, "17-homepage");

  journey.printSummary("005 Full Loop");
  await finishJourney(page, context, collector);
});
