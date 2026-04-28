/**
 * Group 2: Users 006-010 — Extended smoke journeys (continued).
 * More complex flows: footer navigation, category pages, multi-product
 * cart operations, search variations, and repeated dashboard visits.
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
  visitDashboard,
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
// User 006: Footer navigation + category page — Mobile Landscape
// homepage → click footer "All Products" → products → click footer
// "Electronics" category → view product → add to cart → cart →
// increase qty → homepage → dashboard → orders → profile → products
// ────────────────────────────────────────────────────────────────
test("User 006 — Footer nav + category page [Mobile Landscape]", async ({
  browser,
}) => {
  const user = users[5];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Visit homepage
  await visitHomepage(page);
  await snap(page, "01-homepage");
  await page.waitForTimeout(1500);

  // Step 2: Click "All Products" link in footer
  const footerProducts = page.locator('a[href="/products"]').last();
  if (await footerProducts.isVisible().catch(() => false)) {
    await footerProducts.click();
    await page.waitForLoadState("networkidle");
  } else {
    await browseProducts(page);
  }
  await snap(page, "02-products-from-footer");
  await page.waitForTimeout(1500);

  // Step 3: Navigate to a category page via footer link
  const categoryLink = page.locator('a[href*="/categories/"]').first();
  const categoryVisible = await categoryLink.isVisible().catch(() => false);
  if (categoryVisible) {
    await categoryLink.click();
    await page.waitForLoadState("networkidle");
    await snap(page, "03-category-page");
    await page.waitForTimeout(1500);

    // Step 4: View a product from the category page
    const productLink = page.locator('a[href*="/products/"]').first();
    if (await productLink.isVisible().catch(() => false)) {
      await productLink.click();
      await page.waitForLoadState("networkidle");
      await snap(page, "04-product-from-category");
      await page.waitForTimeout(1500);
    }
  } else {
    // Fallback: just browse products normally
    await viewNthProduct(page, 0);
    await snap(page, "03-product-fallback");
    await page.waitForTimeout(1500);
  }

  // Step 5: Add to cart
  const added = await addToCart(page);
  console.log(`  Add to cart: ${added ? "success" : "skipped"}`);
  await snap(page, "05-added-to-cart");
  await page.waitForTimeout(1500);

  // Step 6: View cart
  await viewCart(page);
  await snap(page, "06-cart");
  await page.waitForTimeout(1500);

  // Step 7: Increase quantity
  await increaseQuantity(page);
  await snap(page, "07-qty-up");
  await page.waitForTimeout(1000);

  // Step 8: Visit homepage
  await visitHomepage(page);
  await snap(page, "08-homepage-again");
  await page.waitForTimeout(1500);

  // Step 9: Dashboard
  await visitDashboard(page);
  await snap(page, "09-dashboard");
  await page.waitForTimeout(1500);

  // Step 10: Orders (auth check)
  await visitOrders(page);
  await snap(page, "10-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1500);

  // Step 11: Profile (auth check)
  await visitProfile(page);
  await snap(page, "11-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1000);

  // Step 12: Back to products
  await browseProducts(page);
  await snap(page, "12-products-final");

  journey.printSummary("006 Footer Nav + Category");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 007: Multi-search + sort exploration — Desktop Chrome
// products → search "blue" → search "leather" → sort price_desc →
// sort newest → filter category → view product → add to cart →
// back → search "pro" → view product → add to cart → cart →
// increase qty → decrease qty → orders → profile → homepage
// ────────────────────────────────────────────────────────────────
test("User 007 — Multi-search + sort [Desktop Chrome]", async ({ browser }) => {
  const user = users[6];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products page
  await snap(page, "01-products");
  await page.waitForTimeout(1500);

  // Step 2: Search "blue"
  await searchProducts(page, "blue");
  await snap(page, "02-search-blue");
  await page.waitForTimeout(1500);

  // Step 3: Search "leather"
  await searchProducts(page, "leather");
  await snap(page, "03-search-leather");
  await page.waitForTimeout(1500);

  // Step 4: Clear search, sort price high-to-low
  await searchProducts(page, "");
  await changeSort(page, "price_desc");
  await snap(page, "04-sort-price-desc");
  await page.waitForTimeout(1500);

  // Step 5: Change sort to newest
  await changeSort(page, "newest");
  await snap(page, "05-sort-newest");
  await page.waitForTimeout(1500);

  // Step 6: Filter by a category
  const cat = await filterByNthCategory(page, 0);
  console.log(`  Category: ${cat}`);
  await snap(page, "06-category");
  await page.waitForTimeout(1500);

  // Step 7: View a product
  await viewNthProduct(page, 0);
  await snap(page, "07-product-1");
  await page.waitForTimeout(1500);

  // Step 8: Add to cart
  const added1 = await addToCart(page);
  console.log(`  Add product 1: ${added1 ? "success" : "skipped"}`);
  await snap(page, "08-added-1");
  await page.waitForTimeout(1500);

  // Step 9: Back to products, clear filter, search "pro"
  await backToProducts(page);
  await resetCategoryFilter(page);
  await searchProducts(page, "pro");
  await snap(page, "09-search-pro");
  await page.waitForTimeout(1500);

  // Step 10: View a product from search
  await viewNthProduct(page, 0);
  await snap(page, "10-product-2");
  await page.waitForTimeout(1500);

  // Step 11: Add second product
  const added2 = await addToCart(page);
  console.log(`  Add product 2: ${added2 ? "success" : "skipped"}`);
  await snap(page, "11-added-2");
  await page.waitForTimeout(1500);

  // Step 12: View cart
  await viewCart(page);
  await snap(page, "12-cart");
  await page.waitForTimeout(1500);

  // Step 13: Increase then decrease qty
  await increaseQuantity(page);
  await page.waitForTimeout(800);
  await decreaseQuantity(page);
  await snap(page, "13-qty-adjusted");
  await page.waitForTimeout(1000);

  // Step 14: Orders (auth check)
  await visitOrders(page);
  await snap(page, "14-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1500);

  // Step 15: Profile (auth check)
  await visitProfile(page);
  await snap(page, "15-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1000);

  // Step 16: Homepage
  await visitHomepage(page);
  await snap(page, "16-homepage");

  journey.printSummary("007 Multi-Search + Sort");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 008: Heavy cart + remove all — Desktop Large
// products → view 3 products and add each → cart → increase qty
// on each → remove all items → empty cart → browse products →
// add one back → cart → profile → orders → homepage
// ────────────────────────────────────────────────────────────────
test("User 008 — Heavy cart + remove all [Desktop Large]", async ({
  browser,
}) => {
  const user = users[7];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Add 3 products to cart
  for (let i = 0; i < 3; i++) {
    await viewNthProduct(page, i);
    await snap(page, `0${i + 1}-product-${i + 1}`);
    await page.waitForTimeout(1000);

    const added = await addToCart(page);
    console.log(`  Add product ${i + 1}: ${added ? "success" : "skipped"}`);
    await snap(page, `0${i + 1}-added-${i + 1}`);
    await page.waitForTimeout(1000);

    if (i < 2) {
      await backToProducts(page);
      await page.waitForTimeout(1000);
    }
  }

  // Step 7: View cart with all items
  await viewCart(page);
  await snap(page, "07-cart-full");
  await page.waitForTimeout(1500);

  // Step 8: Increase qty on first item
  await increaseQuantity(page);
  await snap(page, "08-qty-increased");
  await page.waitForTimeout(1000);

  // Step 9-11: Remove items one by one
  for (let i = 0; i < 3; i++) {
    await removeFromCart(page);
    await page.waitForTimeout(1000);
    await snap(page, `${String(9 + i).padStart(2, "0")}-removed-${i + 1}`);
  }

  // Step 12: Should see empty cart now
  await snap(page, "12-empty-cart");
  await page.waitForTimeout(1500);

  // Step 13: Browse products and add one item back
  await browseProducts(page);
  await viewNthProduct(page, 4);
  await snap(page, "13-product-new");
  await page.waitForTimeout(1000);

  const addedBack = await addToCart(page);
  console.log(`  Add back: ${addedBack ? "success" : "skipped"}`);
  await page.waitForTimeout(1000);

  // Step 14: Cart with 1 item
  await viewCart(page);
  await snap(page, "14-cart-1-item");
  await page.waitForTimeout(1500);

  // Step 15: Profile (auth check)
  await visitProfile(page);
  await snap(page, "15-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1500);

  // Step 16: Orders
  await visitOrders(page);
  await snap(page, "16-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1000);

  // Step 17: Homepage
  await visitHomepage(page);
  await snap(page, "17-homepage");

  journey.printSummary("008 Heavy Cart + Remove All");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 009: Mobile browsing deep dive — iPhone 13
// homepage → products → category filter → view product → variant →
// add to cart → products → different category → view product →
// add → cart → remove one → search from products → view product →
// add → cart → profile → homepage
// ────────────────────────────────────────────────────────────────
test("User 009 — Mobile deep dive [iPhone 13]", async ({ browser }) => {
  const user = users[8];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Homepage
  await visitHomepage(page);
  await snap(page, "01-homepage");
  await page.waitForTimeout(1500);

  // Step 2: Products
  await browseProducts(page);
  await snap(page, "02-products");
  await page.waitForTimeout(1500);

  // Step 3: Filter by first category
  const cat1 = await filterByNthCategory(page, 0);
  console.log(`  Category 1: ${cat1}`);
  await snap(page, "03-category-1");
  await page.waitForTimeout(1500);

  // Step 4: View a product
  await viewNthProduct(page, 0);
  await snap(page, "04-product-1");
  await page.waitForTimeout(1500);

  // Step 5: Try variant selection
  const variant = await selectVariant(page);
  console.log(`  Variant: ${variant}`);
  await snap(page, "05-variant");
  await page.waitForTimeout(1000);

  // Step 6: Add to cart
  const added1 = await addToCart(page);
  console.log(`  Add product 1: ${added1 ? "success" : "skipped"}`);
  await snap(page, "06-added-1");
  await page.waitForTimeout(1500);

  // Step 7: Back to products, switch category
  await backToProducts(page);
  const cat2 = await filterByNthCategory(page, 1);
  console.log(`  Category 2: ${cat2}`);
  await snap(page, "07-category-2");
  await page.waitForTimeout(1500);

  // Step 8: View product from this category
  await viewNthProduct(page, 0);
  await snap(page, "08-product-2");
  await page.waitForTimeout(1500);

  // Step 9: Add second product
  const added2 = await addToCart(page);
  console.log(`  Add product 2: ${added2 ? "success" : "skipped"}`);
  await snap(page, "09-added-2");
  await page.waitForTimeout(1500);

  // Step 10: View cart
  await viewCart(page);
  await snap(page, "10-cart");
  await page.waitForTimeout(1500);

  // Step 11: Remove one item
  await removeFromCart(page);
  await snap(page, "11-removed-one");
  await page.waitForTimeout(1500);

  // Step 12: Back to products, search
  await browseProducts(page);
  await resetCategoryFilter(page);
  await searchProducts(page, "classic");
  await snap(page, "12-search-classic");
  await page.waitForTimeout(1500);

  // Step 13: View a product from search
  await viewNthProduct(page, 0);
  await snap(page, "13-product-3");
  await page.waitForTimeout(1500);

  // Step 14: Add to cart
  const added3 = await addToCart(page);
  console.log(`  Add product 3: ${added3 ? "success" : "skipped"}`);
  await page.waitForTimeout(1000);

  // Step 15: View cart again
  await viewCart(page);
  await snap(page, "15-cart-final");
  await page.waitForTimeout(1500);

  // Step 16: Profile (auth check)
  await visitProfile(page);
  await snap(page, "16-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1000);

  // Step 17: Homepage
  await visitHomepage(page);
  await snap(page, "17-homepage");

  journey.printSummary("009 Mobile Deep Dive");
  await finishJourney(page, context, collector);
});

// ────────────────────────────────────────────────────────────────
// User 010: Subscriptions + products tab switching — Pixel 7
// products → subscriptions tab → view plans → products tab →
// sort by name → view product → add to cart → search → view
// product → add to cart → cart → increase qty → decrease →
// remove → add back from products → cart → dashboard → profile →
// orders → homepage
// ────────────────────────────────────────────────────────────────
test("User 010 — Tabs + subscriptions [Pixel 7]", async ({ browser }) => {
  const user = users[9];
  const { context, page, collector } = await createUserContext(browser, user);
  const journey = new JourneyLogger();
  journey.attach(page);

  // Step 1: Products page
  await snap(page, "01-products");
  await page.waitForTimeout(1500);

  // Step 2: Switch to subscriptions tab
  await clickSubscriptionsTab(page);
  await snap(page, "02-subscriptions-tab");
  await page.waitForTimeout(2000);

  // Step 3: Back to products tab
  const productsTab = page
    .locator("button")
    .filter({ hasText: "Products" })
    .first();
  if (await productsTab.isVisible().catch(() => false)) {
    await productsTab.click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
  }
  await snap(page, "03-products-tab");
  await page.waitForTimeout(1500);

  // Step 4: Sort by name
  await changeSort(page, "name");
  await snap(page, "04-sorted-name");
  await page.waitForTimeout(1500);

  // Step 5: View a product
  await viewNthProduct(page, 0);
  await snap(page, "05-product-1");
  await page.waitForTimeout(1500);

  // Step 6: Add to cart
  const added1 = await addToCart(page);
  console.log(`  Add product 1: ${added1 ? "success" : "skipped"}`);
  await snap(page, "06-added-1");
  await page.waitForTimeout(1500);

  // Step 7: Back, search
  await backToProducts(page);
  await searchProducts(page, "gold");
  await snap(page, "07-search-gold");
  await page.waitForTimeout(1500);

  // Step 8: View a product from search
  await viewNthProduct(page, 0);
  await snap(page, "08-product-2");
  await page.waitForTimeout(1500);

  // Step 9: Add to cart
  const added2 = await addToCart(page);
  console.log(`  Add product 2: ${added2 ? "success" : "skipped"}`);
  await snap(page, "09-added-2");
  await page.waitForTimeout(1500);

  // Step 10: View cart
  await viewCart(page);
  await snap(page, "10-cart");
  await page.waitForTimeout(1500);

  // Step 11: Increase qty
  await increaseQuantity(page);
  await snap(page, "11-qty-up");
  await page.waitForTimeout(1000);

  // Step 12: Decrease qty
  await decreaseQuantity(page);
  await snap(page, "12-qty-down");
  await page.waitForTimeout(1000);

  // Step 13: Remove an item
  await removeFromCart(page);
  await snap(page, "13-removed");
  await page.waitForTimeout(1500);

  // Step 14: Add another product from browse
  await browseProducts(page);
  await viewNthProduct(page, 3);
  await snap(page, "14-product-3");
  await page.waitForTimeout(1000);

  const added3 = await addToCart(page);
  console.log(`  Add product 3: ${added3 ? "success" : "skipped"}`);
  await page.waitForTimeout(1000);

  // Step 15: View cart again
  await viewCart(page);
  await snap(page, "15-cart-final");
  await page.waitForTimeout(1500);

  // Step 16: Dashboard
  await visitDashboard(page);
  await snap(page, "16-dashboard");
  await page.waitForTimeout(1500);

  // Step 17: Profile (auth check)
  await visitProfile(page);
  await snap(page, "17-profile");
  expect(page.url()).toContain("/dashboard/profile");
  await page.waitForTimeout(1000);

  // Step 18: Orders (auth check)
  await visitOrders(page);
  await snap(page, "18-orders");
  expect(page.url()).toContain("/dashboard/orders");
  await page.waitForTimeout(1000);

  // Step 19: Homepage
  await visitHomepage(page);
  await snap(page, "19-homepage");

  journey.printSummary("010 Tabs + Subscriptions");
  await finishJourney(page, context, collector);
});
