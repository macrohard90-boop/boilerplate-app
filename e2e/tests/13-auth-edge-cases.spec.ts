/**
 * Test 09: Auth edge cases — login failures, signup failures, return visits.
 * 8 tests total.
 */

import { test, expect } from "@playwright/test";
import { EventCollector } from "../helpers/event-collector";
import { acceptAllCookies } from "../helpers/consent";
import { getUsersByPersona } from "../helpers/users";

// Use first registered user for login tests
const firstUser = getUsersByPersona("single_buyer")[0];

async function setupPage(browser: import("@playwright/test").Browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const collector = new EventCollector();
  collector.attach(page);

  // Navigate to the site first, then set cookies
  await page.goto("/auth/login");
  await page.waitForLoadState("networkidle");
  await acceptAllCookies(page);

  return { context, page, collector };
}

test.describe("Auth edge cases", () => {
  test("Login with wrong password", async ({ browser }) => {
    const { context, page, collector } = await setupPage(browser);

    await page.locator('input[type="email"]').fill(firstUser.email);
    await page.locator('input[type="password"]').fill("WrongPassword99!");
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Should still be on login page with error
    await expect(page).toHaveURL(/login/);
    console.log("  Wrong password events:", collector.summary());
    await context.close();
  });

  test("Login with non-existent email", async ({ browser }) => {
    const { context, page, collector } = await setupPage(browser);

    await page.locator('input[type="email"]').fill("nobody-exists-999@estmgroup.com");
    await page.locator('input[type="password"]').fill("TestPass1!");
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    await expect(page).toHaveURL(/login/);
    console.log("  Non-existent email events:", collector.summary());
    await context.close();
  });

  test("Register with weak password", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
    await acceptAllCookies(page);

    await page.locator('input[placeholder="John"]').fill("Weak");
    await page.locator('input[placeholder="Doe"]').fill("Password");
    await page.locator('input[placeholder="you@example.com"]').fill("adrian+weak@estmgroup.com");
    await page.locator('input[placeholder="Min 8 characters"]').fill("abc");
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Should still be on register page (password too weak)
    await expect(page).toHaveURL(/register/);
    console.log("  Weak password events:", collector.summary());
    await context.close();
  });

  test("Register with duplicate email", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
    await acceptAllCookies(page);

    // Try to register with an already-taken email
    await page.locator('input[placeholder="John"]').fill("Dupe");
    await page.locator('input[placeholder="Doe"]').fill("User");
    await page.locator('input[placeholder="you@example.com"]').fill(firstUser.email);
    await page.locator('input[placeholder="Min 8 characters"]').fill("TestPass1!");
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    // Should still be on register page with error
    await expect(page).toHaveURL(/register/);
    console.log("  Duplicate email events:", collector.summary());
    await context.close();
  });

  test("Successful login", async ({ browser }) => {
    const { context, page, collector } = await setupPage(browser);

    await page.locator('input[type="email"]').fill(firstUser.email);
    await page.locator('input[type="password"]').fill(firstUser.password);
    await page.locator('button[type="submit"]').click();

    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });
    await page.waitForTimeout(1500);

    console.log("  Login success events:", collector.summary());
    await context.close();
  });

  test("Logout then re-login (return visit)", async ({ browser }) => {
    const { context, page, collector } = await setupPage(browser);

    // Login
    await page.locator('input[type="email"]').fill(firstUser.email);
    await page.locator('input[type="password"]').fill(firstUser.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });
    await page.waitForTimeout(1000);

    // Open user menu and sign out
    const userMenu = page.locator("div.w-8.h-8.rounded-full").first();
    if (await userMenu.isVisible().catch(() => false)) {
      await userMenu.click();
      await page.waitForTimeout(300);
    }
    const signOutBtn = page.locator("button").filter({ hasText: /Sign out/i }).first();
    if (await signOutBtn.isVisible().catch(() => false)) {
      await signOutBtn.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1000);
    }

    // Login again (return visit)
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    await page.locator('input[type="email"]').fill(firstUser.email);
    await page.locator('input[type="password"]').fill(firstUser.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });
    await page.waitForTimeout(1500);

    console.log("  Logout + re-login events:", collector.summary());
    await context.close();
  });

  test("Visit protected page while logged out redirects to login", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    // Should redirect to login
    expect(page.url()).toContain("/auth/login");
    await context.close();
  });

  test("Visit checkout while logged out redirects to login", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto("/checkout");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);

    expect(page.url()).toContain("/auth/login");
    await context.close();
  });
});
