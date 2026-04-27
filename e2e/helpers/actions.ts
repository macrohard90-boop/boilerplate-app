/**
 * Reusable page actions — composable building blocks for persona journeys.
 * Each function drives real UI interactions on the app.
 */

import { Page, expect } from "@playwright/test";

// ── Product Browsing ──

/** Navigate to /products and wait for the page to load. Returns product count visible. */
export async function browseProducts(page: Page): Promise<number> {
  await page.goto("/products");
  await page.waitForLoadState("networkidle");
  // Wait for either product cards or empty state
  const cards = page.locator('[class*="group relative"]').or(page.locator('[class*="ProductCard"]')).or(page.locator('a[href^="/products/"]'));
  const count = await cards.count();
  return count;
}

/** Type a search query into the product search field. */
export async function searchProducts(page: Page, query: string): Promise<void> {
  const searchInput = page.locator('input[placeholder*="Search"]').or(page.locator('input[type="search"]')).first();
  await searchInput.fill(query);
  // Trigger search — usually debounced, wait for network
  await page.waitForTimeout(500);
  await page.waitForLoadState("networkidle");
}

/** Change the sort option on the products page. */
export async function changeSort(page: Page, sortValue: string): Promise<void> {
  const sortSelect = page.locator("select").filter({ hasText: /newest|price|name/i }).first();
  if (await sortSelect.isVisible()) {
    await sortSelect.selectOption(sortValue);
    await page.waitForLoadState("networkidle");
  }
}

/** Click a category filter pill on the products page. Returns the category name clicked. */
export async function filterByCategory(page: Page): Promise<string | null> {
  // Category pills are typically buttons or links in a filter bar
  const pills = page.locator('button').filter({ hasNotText: /All|Products|Subscriptions|Grid|List/i });
  const count = await pills.count();
  if (count > 0) {
    const idx = Math.floor(Math.random() * Math.min(count, 5));
    const pill = pills.nth(idx);
    const name = await pill.textContent();
    await pill.click();
    await page.waitForLoadState("networkidle");
    return name?.trim() || null;
  }
  return null;
}

/** Click into a product detail page. Clicks a random product from the listing. */
export async function viewRandomProduct(page: Page): Promise<string | null> {
  const links = page.locator('a[href^="/products/"]');
  const count = await links.count();
  if (count === 0) return null;
  const idx = Math.floor(Math.random() * Math.min(count, 12));
  const link = links.nth(idx);
  const href = await link.getAttribute("href");
  await link.click();
  await page.waitForLoadState("networkidle");
  return href;
}

/** Navigate directly to a product by slug. */
export async function viewProduct(page: Page, slug: string): Promise<void> {
  await page.goto(`/products/${slug}`);
  await page.waitForLoadState("networkidle");
}

/** Select a variant on the product detail page if variants exist. */
export async function selectVariant(page: Page): Promise<boolean> {
  // Variant buttons are typically in a group
  const variantBtns = page.locator('button').filter({ hasText: /^(?!Add to Cart|Buy|Get Access|Remove|Back).{1,30}$/ });
  // Look for variant-like buttons (color, size names)
  const productVariants = page.locator('[class*="variant"]').or(page.locator('[data-variant]'));
  const btns = (await productVariants.count()) > 0 ? productVariants : variantBtns;
  const count = await btns.count();
  if (count > 1) {
    // Click the second variant (first is often already selected)
    await btns.nth(1).click();
    await page.waitForTimeout(300);
    return true;
  }
  return false;
}

/** Click the Subscriptions tab on /products page. */
export async function clickSubscriptionsTab(page: Page): Promise<void> {
  const tab = page.locator("button").filter({ hasText: "Subscriptions" }).first();
  if (await tab.isVisible()) {
    await tab.click();
    await page.waitForLoadState("networkidle");
  }
}

// ── Cart ──

/** Click "Add to Cart" on the current product page. */
export async function addToCart(page: Page): Promise<void> {
  const btn = page.locator("button").filter({ hasText: /Add to Cart|Get Access/i }).first();
  await btn.waitFor({ state: "visible", timeout: 5000 });
  await btn.click();
  // Wait for cart update toast or cart count change
  await page.waitForTimeout(1000);
}

/** Navigate to the cart page. */
export async function viewCart(page: Page): Promise<void> {
  await page.goto("/cart");
  await page.waitForLoadState("networkidle");
}

/** Increase quantity of the first item in cart by clicking the + button. */
export async function increaseQuantity(page: Page): Promise<void> {
  const plusBtn = page.locator("button").filter({ hasText: "+" }).first();
  if (await plusBtn.isVisible()) {
    await plusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Decrease quantity of the first item in cart. */
export async function decreaseQuantity(page: Page): Promise<void> {
  const minusBtn = page.locator("button").filter({ hasText: "−" }).or(page.locator("button").filter({ hasText: "-" })).first();
  if (await minusBtn.isVisible()) {
    await minusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Remove an item from cart. */
export async function removeFromCart(page: Page): Promise<void> {
  const removeBtn = page.locator("button").filter({ hasText: /Remove|×/i }).first();
  if (await removeBtn.isVisible()) {
    await removeBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Apply a coupon code in the cart. */
export async function applyCoupon(page: Page, code: string): Promise<void> {
  const input = page.locator('input[placeholder*="oupon"]').or(page.locator('input[placeholder*="iscount"]')).or(page.locator('input[name*="coupon"]')).first();
  if (await input.isVisible()) {
    await input.fill(code);
    const applyBtn = page.locator("button").filter({ hasText: /Apply/i }).first();
    await applyBtn.click();
    await page.waitForTimeout(1000);
  }
}

// ── Checkout ──

/** Click "Proceed to Checkout" from the cart page. */
export async function startCheckout(page: Page): Promise<void> {
  const checkoutBtn = page.locator("a, button").filter({ hasText: /Checkout|Proceed/i }).first();
  await checkoutBtn.click();
  await page.waitForURL("**/checkout**", { timeout: 10000 });
  await page.waitForLoadState("networkidle");
}

/** Fill the shipping address form (Step 1). */
export async function fillShipping(page: Page): Promise<void> {
  // The checkout form fields
  const fields: Record<string, string> = {
    firstName: "Test",
    lastName: "User",
    address1: "123 Test Street",
    city: "New York",
    state: "NY",
    zip: "10001",
  };

  // Try various field name patterns
  for (const [key, value] of Object.entries(fields)) {
    const input = page.locator(`input[name*="${key}" i]`).or(page.locator(`input[placeholder*="${key}" i]`)).first();
    if (await input.isVisible().catch(() => false)) {
      await input.fill(value);
    }
  }

  // Also try common shipping form patterns
  const line1 = page.locator('input[name*="line1"]').or(page.locator('input[name*="address"]')).first();
  if (await line1.isVisible().catch(() => false)) {
    await line1.fill("123 Test Street");
  }
  const cityInput = page.locator('input[name*="city"]').first();
  if (await cityInput.isVisible().catch(() => false)) {
    await cityInput.fill("New York");
  }
  const zipInput = page.locator('input[name*="zip"]').or(page.locator('input[name*="postal"]')).first();
  if (await zipInput.isVisible().catch(() => false)) {
    await zipInput.fill("10001");
  }
}

/** Click "Continue" to advance to the next checkout step. */
export async function advanceCheckoutStep(page: Page): Promise<void> {
  const btn = page.locator("button").filter({ hasText: /Continue|Review|Next|Proceed/i }).first();
  if (await btn.isVisible()) {
    await btn.click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  }
}

/** Fill Stripe PaymentElement iframe with test card and submit. */
export async function fillStripeAndPay(page: Page): Promise<void> {
  // Wait for Stripe iframe to load
  await page.waitForTimeout(2000);

  // Stripe Elements uses iframes — find the card number frame
  const stripeFrame = page.frameLocator('iframe[name*="__privateStripeFrame"]').first();

  // Fill card number
  const cardInput = stripeFrame.locator('[name="number"]').or(stripeFrame.locator('[name="cardnumber"]')).or(stripeFrame.locator('[placeholder*="1234"]'));
  await cardInput.fill("4242424242424242");

  // Fill expiry
  const expInput = stripeFrame.locator('[name="expiry"]').or(stripeFrame.locator('[name="exp-date"]')).or(stripeFrame.locator('[placeholder*="MM"]'));
  await expInput.fill("1230");

  // Fill CVC
  const cvcInput = stripeFrame.locator('[name="cvc"]').or(stripeFrame.locator('[placeholder*="CVC"]'));
  await cvcInput.fill("123");

  // Submit payment
  const payBtn = page.locator("button").filter({ hasText: /Pay|Complete|Submit|Place Order/i }).first();
  await payBtn.click();
}

/** Fill Stripe with a specific decline test card. */
export async function fillStripeDeclineCard(page: Page, cardNumber: string): Promise<void> {
  await page.waitForTimeout(2000);
  const stripeFrame = page.frameLocator('iframe[name*="__privateStripeFrame"]').first();

  const cardInput = stripeFrame.locator('[name="number"]').or(stripeFrame.locator('[name="cardnumber"]')).or(stripeFrame.locator('[placeholder*="1234"]'));
  await cardInput.fill(cardNumber);

  const expInput = stripeFrame.locator('[name="expiry"]').or(stripeFrame.locator('[name="exp-date"]')).or(stripeFrame.locator('[placeholder*="MM"]'));
  await expInput.fill("1230");

  const cvcInput = stripeFrame.locator('[name="cvc"]').or(stripeFrame.locator('[placeholder*="CVC"]'));
  await cvcInput.fill("123");

  const payBtn = page.locator("button").filter({ hasText: /Pay|Complete|Submit|Place Order/i }).first();
  await payBtn.click();
}

/** Wait for the order confirmation page. */
export async function waitForConfirmation(page: Page): Promise<void> {
  await page.waitForURL("**/orders/**/confirmation**", { timeout: 30000 });
  await page.waitForLoadState("networkidle");
}

// ── Wishlist ──

/** Click the wishlist/heart button on a product page. */
export async function addToWishlist(page: Page): Promise<void> {
  const wishBtn = page.locator("button").filter({ hasText: /Wishlist|♡|Save/i })
    .or(page.locator('[aria-label*="wishlist" i]'))
    .or(page.locator('[class*="wishlist"]'))
    .first();
  if (await wishBtn.isVisible().catch(() => false)) {
    await wishBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Navigate to the wishlist page. */
export async function viewWishlist(page: Page): Promise<void> {
  await page.goto("/dashboard/wishlists");
  await page.waitForLoadState("networkidle");
}

/** Remove first item from wishlist. */
export async function removeFromWishlist(page: Page): Promise<void> {
  const removeBtn = page.locator("button").filter({ hasText: /Remove/i }).first();
  if (await removeBtn.isVisible().catch(() => false)) {
    await removeBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Move first wishlist item to cart. */
export async function moveWishlistToCart(page: Page): Promise<void> {
  const moveBtn = page.locator("button").filter({ hasText: /Move to Cart|Add to Cart/i }).first();
  if (await moveBtn.isVisible().catch(() => false)) {
    await moveBtn.click();
    await page.waitForTimeout(500);
  }
}

// ── Auth ──

/** Click logout (usually in header dropdown or navigation). */
export async function logout(page: Page): Promise<void> {
  // Try clicking a user menu first
  const userMenu = page.locator('[class*="avatar"]').or(page.locator("button").filter({ hasText: /Account|Profile/i })).first();
  if (await userMenu.isVisible().catch(() => false)) {
    await userMenu.click();
    await page.waitForTimeout(300);
  }

  const logoutBtn = page.locator("button, a").filter({ hasText: /Log\s?out|Sign\s?out/i }).first();
  await logoutBtn.click();
  await page.waitForLoadState("networkidle");
}

// ── Categories ──

/** Navigate to a category page. Picks a random category from the products page. */
export async function browseCategory(page: Page): Promise<void> {
  const categoryLinks = page.locator('a[href^="/categories/"]');
  const count = await categoryLinks.count();
  if (count > 0) {
    const idx = Math.floor(Math.random() * Math.min(count, 5));
    await categoryLinks.nth(idx).click();
    await page.waitForLoadState("networkidle");
  }
}
