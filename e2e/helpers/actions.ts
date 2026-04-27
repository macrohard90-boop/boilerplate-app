/**
 * Reusable page actions — composable building blocks for persona journeys.
 * Selectors match the actual frontend components in this app.
 */

import { Page } from "@playwright/test";

// ── Product Browsing ──

/** Navigate to /products and wait for the page to load. */
export async function browseProducts(page: Page): Promise<number> {
  await page.goto("/products");
  await page.waitForLoadState("networkidle");
  const cards = page.locator('a[href*="/products/"]');
  const count = await cards.count();
  return count;
}

/** Type a search query into the product search input. */
export async function searchProducts(page: Page, query: string): Promise<void> {
  const searchInput = page.locator('input[placeholder*="Search"]').first();
  await searchInput.fill(query);
  await page.waitForTimeout(600);
  await page.waitForLoadState("networkidle");
}

/** Change sort via the select dropdown on the products page. */
export async function changeSort(page: Page, sortValue: string): Promise<void> {
  const sortSelect = page.locator("select.input-glass").first();
  if (await sortSelect.isVisible().catch(() => false)) {
    await sortSelect.selectOption(sortValue);
    await page.waitForLoadState("networkidle");
  }
}

/** Click a category filter pill on the products page. */
export async function filterByCategory(page: Page): Promise<string | null> {
  // Category pills are buttons — skip "All", "Products", "Subscriptions"
  const pills = page
    .locator("button")
    .filter({ hasNotText: /^(All|Products|Subscriptions)$/i });
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

/** Click into a random product detail page from the listing. */
export async function viewRandomProduct(page: Page): Promise<string | null> {
  const links = page.locator('a[href*="/products/"]');
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
  // Look for variant-like elements
  const productVariants = page
    .locator('[class*="variant"]')
    .or(page.locator("[data-variant]"));
  const variantCount = await productVariants.count();
  if (variantCount > 1) {
    await productVariants.nth(1).click();
    await page.waitForTimeout(300);
    return true;
  }
  // Fallback: look for short-text buttons that aren't action buttons
  const btns = page.locator("button").filter({
    hasText: /^(?!Add to Cart|Subscribe|Buy|Get Access|Remove|Back|Out of Stock|\+|-).{1,20}$/,
  });
  const count = await btns.count();
  if (count > 1) {
    await btns.nth(1).click();
    await page.waitForTimeout(300);
    return true;
  }
  return false;
}

/** Click the Subscriptions tab on /products page. */
export async function clickSubscriptionsTab(page: Page): Promise<void> {
  const tab = page
    .locator("button")
    .filter({ hasText: "Subscriptions" })
    .first();
  if (await tab.isVisible().catch(() => false)) {
    await tab.click();
    await page.waitForTimeout(500);
    await page.waitForLoadState("networkidle");
  }
}

// ── Cart ──

/** Click "Add to Cart" or "Subscribe" on the current product page. */
export async function addToCart(page: Page): Promise<void> {
  const btn = page
    .locator("button")
    .filter({ hasText: /Add to Cart|Subscribe|Get Access/i })
    .first();
  await btn.waitFor({ state: "visible", timeout: 5000 });
  await btn.click();
  await page.waitForTimeout(1000);
}

/** Navigate to the cart page. */
export async function viewCart(page: Page): Promise<void> {
  await page.goto("/cart");
  await page.waitForLoadState("networkidle");
}

/** Increase quantity of the first item in cart. */
export async function increaseQuantity(page: Page): Promise<void> {
  const plusBtn = page.locator("button").filter({ hasText: "+" }).first();
  if (await plusBtn.isVisible().catch(() => false)) {
    await plusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Decrease quantity of the first item in cart. */
export async function decreaseQuantity(page: Page): Promise<void> {
  const minusBtn = page.locator("button").filter({ hasText: "-" }).first();
  if (await minusBtn.isVisible().catch(() => false)) {
    await minusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Remove an item from cart (clicks the X / trash icon button). */
export async function removeFromCart(page: Page): Promise<void> {
  // The remove button contains an SVG icon, look for small icon buttons in cart
  const removeBtn = page
    .locator("button")
    .filter({ hasText: /Remove|×/i })
    .first();
  if (await removeBtn.isVisible().catch(() => false)) {
    await removeBtn.click();
    await page.waitForTimeout(500);
    return;
  }
  // Fallback: look for icon-only buttons with trash/X SVGs
  const iconBtn = page
    .locator('button:has(svg[viewBox="0 0 24 24"])')
    .first();
  if (await iconBtn.isVisible().catch(() => false)) {
    await iconBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Apply a coupon/discount code in the cart. */
export async function applyCoupon(page: Page, code: string): Promise<void> {
  const input = page.locator('input[placeholder="Discount code"]').first();
  if (await input.isVisible().catch(() => false)) {
    await input.fill(code);
    const applyBtn = page
      .locator("button")
      .filter({ hasText: /Apply/i })
      .first();
    await applyBtn.click();
    await page.waitForTimeout(1000);
  }
}

// ── Checkout ──

/** Click "Proceed to Checkout" from the cart page. */
export async function startCheckout(page: Page): Promise<void> {
  const checkoutBtn = page
    .locator("a, button")
    .filter({ hasText: /Proceed to Checkout/i })
    .first();
  await checkoutBtn.click();
  await page.waitForURL("**/checkout**", { timeout: 10000 });
  await page.waitForLoadState("networkidle");
}

/** Fill the shipping address form (Step 1). Uses label-based targeting. */
export async function fillShipping(page: Page): Promise<void> {
  await page.waitForTimeout(500);

  // The checkout address form has these fields in order:
  // First name, Last name (grid row), Address line 1, Address line 2, City, State, ZIP (grid row)
  const inputs = page.locator("input.input-glass");
  const count = await inputs.count();

  if (count >= 6) {
    // First name
    await inputs.nth(0).fill("Test");
    // Last name
    await inputs.nth(1).fill("User");
    // Address line 1
    await inputs.nth(2).fill("123 Test Street");
    // Address line 2 (optional, skip)
    // City
    await inputs.nth(4).fill("New York");
    // State
    await inputs.nth(5).fill("NY");
    // ZIP
    await inputs.nth(6).fill("10001");
  } else {
    // Fallback: try placeholder-based
    const streetInput = page.locator('input[placeholder="Street address"]');
    if (await streetInput.isVisible().catch(() => false)) {
      await streetInput.fill("123 Test Street");
    }
  }
}

/** Click "Continue to Review" or "Proceed to Payment" to advance checkout. */
export async function advanceCheckoutStep(page: Page): Promise<void> {
  const btn = page
    .locator("button")
    .filter({ hasText: /Continue to Review|Proceed to Payment|Next|Continue/i })
    .first();
  if (await btn.isVisible().catch(() => false)) {
    await btn.click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  }
}

/** Fill Stripe PaymentElement iframe with test card and submit. */
export async function fillStripeAndPay(page: Page): Promise<void> {
  await page.waitForTimeout(3000);

  // Stripe Elements uses iframes
  const stripeFrame = page
    .frameLocator('iframe[name*="__privateStripeFrame"]')
    .first();

  // Fill card number
  const cardInput = stripeFrame
    .locator('[name="number"]')
    .or(stripeFrame.locator('[name="cardnumber"]'))
    .or(stripeFrame.locator('[placeholder*="1234"]'));
  await cardInput.fill("4242424242424242");

  // Fill expiry
  const expInput = stripeFrame
    .locator('[name="expiry"]')
    .or(stripeFrame.locator('[name="exp-date"]'))
    .or(stripeFrame.locator('[placeholder*="MM"]'));
  await expInput.fill("1230");

  // Fill CVC
  const cvcInput = stripeFrame
    .locator('[name="cvc"]')
    .or(stripeFrame.locator('[placeholder*="CVC"]'));
  await cvcInput.fill("123");

  // Submit payment — "Pay Now" button
  const payBtn = page
    .locator("button")
    .filter({ hasText: /Pay Now|Complete|Place Order/i })
    .first();
  await payBtn.click();
}

/** Fill Stripe with a specific decline test card. */
export async function fillStripeDeclineCard(
  page: Page,
  cardNumber: string,
): Promise<void> {
  await page.waitForTimeout(3000);
  const stripeFrame = page
    .frameLocator('iframe[name*="__privateStripeFrame"]')
    .first();

  const cardInput = stripeFrame
    .locator('[name="number"]')
    .or(stripeFrame.locator('[name="cardnumber"]'))
    .or(stripeFrame.locator('[placeholder*="1234"]'));
  await cardInput.fill(cardNumber);

  const expInput = stripeFrame
    .locator('[name="expiry"]')
    .or(stripeFrame.locator('[name="exp-date"]'))
    .or(stripeFrame.locator('[placeholder*="MM"]'));
  await expInput.fill("1230");

  const cvcInput = stripeFrame
    .locator('[name="cvc"]')
    .or(stripeFrame.locator('[placeholder*="CVC"]'));
  await cvcInput.fill("123");

  const payBtn = page
    .locator("button")
    .filter({ hasText: /Pay Now|Complete|Place Order/i })
    .first();
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
  const wishBtn = page
    .locator("button")
    .filter({ hasText: /Wishlist|♡|Save/i })
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
  const removeBtn = page
    .locator("button")
    .filter({ hasText: /Remove/i })
    .first();
  if (await removeBtn.isVisible().catch(() => false)) {
    await removeBtn.click();
    await page.waitForTimeout(500);
    return;
  }
  // Fallback: icon button with SVG
  const iconBtn = page
    .locator('button:has(svg[viewBox="0 0 24 24"])')
    .first();
  if (await iconBtn.isVisible().catch(() => false)) {
    await iconBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Move first wishlist item to cart. */
export async function moveWishlistToCart(page: Page): Promise<void> {
  const moveBtn = page
    .locator("button")
    .filter({ hasText: /Add to Cart|Move to Cart/i })
    .first();
  if (await moveBtn.isVisible().catch(() => false)) {
    await moveBtn.click();
    await page.waitForTimeout(500);
  }
}

// ── Auth ──

/** Click "Sign out" from the user dropdown menu. */
export async function logout(page: Page): Promise<void> {
  // Click the user avatar/menu button in header (circular div)
  const userMenu = page.locator("div.w-8.h-8.rounded-full").first();
  if (await userMenu.isVisible().catch(() => false)) {
    await userMenu.click();
    await page.waitForTimeout(300);
  }

  const logoutBtn = page
    .locator("button")
    .filter({ hasText: /Sign out/i })
    .first();
  if (await logoutBtn.isVisible().catch(() => false)) {
    await logoutBtn.click();
    await page.waitForLoadState("networkidle");
  }
}

// ── Categories ──

/** Navigate to a category page from the products listing. */
export async function browseCategory(page: Page): Promise<void> {
  const categoryLinks = page.locator('a[href^="/categories/"]');
  const count = await categoryLinks.count();
  if (count > 0) {
    const idx = Math.floor(Math.random() * Math.min(count, 5));
    await categoryLinks.nth(idx).click();
    await page.waitForLoadState("networkidle");
  }
}
