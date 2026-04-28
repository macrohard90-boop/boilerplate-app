/**
 * Reusable page actions — composable building blocks for persona journeys.
 * Selectors match the actual frontend components in this app.
 */

import { Page, BrowserContext } from "@playwright/test";
import { EventCollector } from "./event-collector";

// ── Journey Lifecycle ──

/** Logout, log events, and close context. Call at end of every journey test. */
export async function finishJourney(
  page: Page,
  context: BrowserContext,
  collector: EventCollector,
): Promise<void> {
  await logout(page);
  console.log("  Events:", collector.summary());
  await context.close();
}

// ── Product Browsing ──

/** Navigate to /products and wait for product cards to render. */
export async function browseProducts(page: Page): Promise<number> {
  await page.goto("/products");
  await page.waitForLoadState("networkidle");
  const cards = page.locator('a[href*="/products/"]');
  // Wait for at least one product card to render (React may still be fetching)
  await cards
    .first()
    .waitFor({ state: "visible", timeout: 10000 })
    .catch(() => {});
  const count = await cards.count();
  return count;
}

/** Type a search query into the product search input. */
export async function searchProducts(page: Page, query: string): Promise<void> {
  const searchInput = page.locator('input[placeholder*="Search"]').first();
  // On mobile viewports the search input may not be visible — skip if hidden
  const visible = await searchInput
    .waitFor({ state: "visible", timeout: 5000 })
    .then(() => true)
    .catch(() => false);
  if (!visible) return;
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
  // Category pills are rounded-full buttons — skip "All"
  const pills = page
    .locator("button.rounded-full")
    .filter({ hasNotText: /^All$/i });
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

/** Click the Nth category filter pill (0-indexed). Deterministic. */
export async function filterByNthCategory(
  page: Page,
  n: number,
): Promise<string | null> {
  // Category pills are rounded-full buttons — skip "All"
  const pills = page
    .locator("button.rounded-full")
    .filter({ hasNotText: /^All$/i });
  const count = await pills.count();
  if (count === 0) return null;
  const idx = n % count;
  const pill = pills.nth(idx);
  const name = await pill.textContent();
  await pill.click();
  await page.waitForLoadState("networkidle");
  return name?.trim() || null;
}

/** Click "All" category filter to reset. */
export async function resetCategoryFilter(page: Page): Promise<void> {
  const allPill = page
    .locator("button.rounded-full")
    .filter({ hasText: /^All$/i })
    .first();
  if (await allPill.isVisible().catch(() => false)) {
    await allPill.click();
    await page.waitForLoadState("networkidle");
  }
}

/** Click into a random product detail page from the listing. */
export async function viewRandomProduct(page: Page): Promise<string | null> {
  const links = page.locator('a[href*="/products/"]');
  // Wait for product cards to render before trying to click
  await links
    .first()
    .waitFor({ state: "visible", timeout: 10000 })
    .catch(() => {});
  const count = await links.count();
  if (count === 0) return null;
  const idx = Math.floor(Math.random() * Math.min(count, 12));
  const link = links.nth(idx);
  const href = await link.getAttribute("href");
  await link.click();
  await page.waitForLoadState("networkidle");
  return href;
}

/** Click the Nth product (0-indexed) from the listing. Deterministic. */
export async function viewNthProduct(
  page: Page,
  n: number,
): Promise<string | null> {
  const links = page.locator('a[href*="/products/"]');
  // Wait for product cards to render before trying to click
  await links
    .first()
    .waitFor({ state: "visible", timeout: 10000 })
    .catch(() => {});
  const count = await links.count();
  if (count === 0) return null;
  const idx = n % count;
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
  // The variant section has a label "Variant" followed by a div of buttons.
  // Find the container by looking for the label, then click a non-selected,
  // non-disabled button inside its sibling div.
  const variantSection = page.locator('label:has-text("Variant") + div');
  const buttons = variantSection.locator("button:not([disabled])");
  const count = await buttons.count().catch(() => 0);
  if (count > 1) {
    // Click the second variant (first is usually pre-selected as "Default")
    await buttons.nth(1).click();
    await page.waitForTimeout(500);
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

/** Click "Add to Cart" or "Subscribe" on the current product page. Returns false if button not found (e.g. out of stock). */
export async function addToCart(page: Page): Promise<boolean> {
  const btn = page
    .locator("button:not([disabled])")
    .filter({ hasText: /Add to Cart|Subscribe|Get Access/i })
    .first();
  const visible = await btn
    .waitFor({ state: "visible", timeout: 5000 })
    .then(() => true)
    .catch(() => false);
  if (!visible) return false;
  await btn.click();
  await page.waitForTimeout(1000);
  return true;
}

/** Navigate to the cart page and wait for it to fully load. */
export async function viewCart(page: Page): Promise<void> {
  await page.goto("/cart");
  await page.waitForLoadState("networkidle");
  // Wait for cart content to render (past the loading spinner).
  // The "Shopping Cart" heading only appears after auth + cart fetch complete,
  // which is also when the cart_viewed / empty_cart_viewed event fires.
  await page
    .getByText("Shopping Cart")
    .first()
    .waitFor({ state: "visible", timeout: 15000 })
    .catch(() => {});
}

/** Increase quantity of the first item in cart. */
export async function increaseQuantity(page: Page): Promise<void> {
  // Scope to cart item rows to avoid hitting unrelated "+" buttons
  const plusBtn = page
    .locator(".glass.rounded-xl button")
    .filter({ hasText: "+" })
    .first();
  if (await plusBtn.isVisible().catch(() => false)) {
    await plusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Decrease quantity of the first item in cart. */
export async function decreaseQuantity(page: Page): Promise<void> {
  const minusBtn = page
    .locator(".glass.rounded-xl button")
    .filter({ hasText: "-" })
    .first();
  if (await minusBtn.isVisible().catch(() => false)) {
    await minusBtn.click();
    await page.waitForTimeout(500);
  }
}

/** Remove an item from cart (clicks the X / trash icon button). */
export async function removeFromCart(page: Page): Promise<void> {
  // Dismiss any open overlays (user dropdown, modals) that block clicks
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);

  // The remove button is inside a cart item row (.glass.rounded-xl)
  // and contains an SVG with the close/X path (M6 18L18 6M6 6l12 12)
  const removeBtn = page
    .locator('.glass.rounded-xl button:has(svg path[d*="M6 18L18 6"])')
    .first();
  if (await removeBtn.isVisible().catch(() => false)) {
    await removeBtn.click();
    await page.waitForTimeout(500);
    return;
  }
  // Fallback: text-based remove button
  const textBtn = page
    .locator("button")
    .filter({ hasText: /Remove|×/i })
    .first();
  if (await textBtn.isVisible().catch(() => false)) {
    await textBtn.click();
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

// ── Navigation ──

/**
 * Navigate to a dashboard page and wait for auth to settle.
 * Dashboard pages have an auth guard that redirects to /auth/login
 * if the session is invalid. This helper detects the redirect and
 * retries by refreshing the auth cookie first.
 */
async function gotoDashboard(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.waitForLoadState("networkidle");

  // Give React auth context a moment to finish initializing.
  // networkidle may resolve before the auth redirect fires.
  await page.waitForTimeout(500);

  // Check if we got redirected to the login page
  if (page.url().includes("/auth/login")) {
    console.log(`  AUTH: redirected to login from ${path} — retrying`);
    // Attempt a manual refresh via the API to get a new access token
    // and seed sessionStorage so subsequent navigations work too
    const refreshOk = await page.evaluate(async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) return false;
        const data = await res.json();
        if (data.access_token)
          sessionStorage.setItem("access_token", data.access_token);
        if (data.csrf_token)
          sessionStorage.setItem("csrf_token", data.csrf_token);
        return true;
      } catch {
        return false;
      }
    });

    if (refreshOk) {
      // Refresh worked — navigate again
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
    } else {
      console.log(`  AUTH: refresh also failed for ${path}`);
    }
  }
}

/** Navigate to the homepage. */
export async function visitHomepage(page: Page): Promise<void> {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
}

/** Navigate to the dashboard overview. */
export async function visitDashboard(page: Page): Promise<void> {
  await gotoDashboard(page, "/dashboard");
}

/** Navigate to the orders page. */
export async function visitOrders(page: Page): Promise<void> {
  await gotoDashboard(page, "/dashboard/orders");
}

/** Navigate to the profile page. */
export async function visitProfile(page: Page): Promise<void> {
  await gotoDashboard(page, "/dashboard/profile");
}

/** Navigate to the privacy settings page. */
export async function visitPrivacy(page: Page): Promise<void> {
  await gotoDashboard(page, "/dashboard/privacy");
}

/** Dismiss any open overlays (user dropdown, modals) by pressing Escape. */
export async function dismissOverlays(page: Page): Promise<void> {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
}

/** Go back to the products listing from a product detail page. */
export async function backToProducts(page: Page): Promise<void> {
  await page.goto("/products");
  await page.waitForLoadState("networkidle");
  // Wait for product cards to render (React SPA may still be fetching)
  await page
    .locator('a[href*="/products/"]')
    .first()
    .waitFor({ state: "visible", timeout: 10000 })
    .catch(() => {});
}

// ── Orders ──

/** Click the first order link on /dashboard/orders to view its detail page. */
export async function visitFirstOrderDetail(page: Page): Promise<void> {
  const orderLink = page.locator('a[href*="/dashboard/orders/"]').first();
  if (await orderLink.isVisible().catch(() => false)) {
    await orderLink.click();
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

/** Click the first category link on the current page (deterministic). */
export async function visitFirstCategory(page: Page): Promise<void> {
  const categoryLink = page.locator('a[href*="/categories/"]').first();
  if (await categoryLink.isVisible().catch(() => false)) {
    await categoryLink.click();
    await page.waitForLoadState("networkidle");
  }
}
