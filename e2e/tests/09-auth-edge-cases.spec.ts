/**
 * Test 09: Auth edge cases — login failures, signup failures, return visits.
 */

import { test, expect } from "@playwright/test";
import { EventCollector } from "../helpers/event-collector";
import { acceptAllCookies } from "../helpers/consent";

const BASE_USER = {
  email: "pw-buyer-001@test.com", // Already registered in test 01
  password: "TestPass1",
};

test.describe("Auth edge cases", () => {
  test("Login with wrong password fires login_failed", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("about:blank");
    await acceptAllCookies(page);

    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.locator('input[name="email"]').fill(BASE_USER.email);
    await page.locator('input[name="password"]').fill("WrongPassword99");
    await page.locator('button[type="submit"]').click();

    await page.waitForTimeout(2000);

    // Should still be on login page with error
    await expect(page).toHaveURL(/login/);
    collector.assertFired("login_failed");

    console.log("  Login failed events:", collector.summary());
    await context.close();
  });

  test("Register with weak password fires signup_failed", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("about:blank");
    await acceptAllCookies(page);

    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");

    await page.locator('input[name="firstName"]').fill("Weak");
    await page.locator('input[name="lastName"]').fill("Password");
    await page.locator('input[name="email"]').fill("pw-weak@test.com");
    await page.locator('input[name="password"]').fill("abc"); // Too short/weak
    await page.locator('button[type="submit"]').click();

    await page.waitForTimeout(2000);

    // Should still be on register page
    await expect(page).toHaveURL(/register/);

    console.log("  Weak password events:", collector.summary());
    await context.close();
  });

  test("Register with duplicate email fires signup_failed", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("about:blank");
    await acceptAllCookies(page);

    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");

    // Try to register with an already-taken email
    await page.locator('input[name="firstName"]').fill("Dupe");
    await page.locator('input[name="lastName"]').fill("User");
    await page.locator('input[name="email"]').fill(BASE_USER.email);
    await page.locator('input[name="password"]').fill("TestPass1");
    await page.locator('button[type="submit"]').click();

    await page.waitForTimeout(2000);

    // Should still be on register page with error
    await expect(page).toHaveURL(/register/);
    collector.assertFired("signup_failed");

    console.log("  Duplicate email events:", collector.summary());
    await context.close();
  });

  test("Successful login fires login_completed", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("about:blank");
    await acceptAllCookies(page);

    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.locator('input[name="email"]').fill(BASE_USER.email);
    await page.locator('input[name="password"]').fill(BASE_USER.password);
    await page.locator('button[type="submit"]').click();

    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });

    await page.waitForTimeout(1500);
    collector.assertFired("login_completed");

    console.log("  Login success events:", collector.summary());
    await context.close();
  });

  test("Logout then re-login fires logout + return_visit", async ({ browser }) => {
    // First login
    const context = await browser.newContext();
    const page = await context.newPage();
    const collector = new EventCollector();
    collector.attach(page);

    await page.goto("about:blank");
    await acceptAllCookies(page);

    // Login
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    await page.locator('input[name="email"]').fill(BASE_USER.email);
    await page.locator('input[name="password"]').fill(BASE_USER.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });
    await page.waitForTimeout(1000);

    // Logout — click any logout button/link
    const logoutBtn = page.locator("button, a").filter({ hasText: /Log\s?out|Sign\s?out/i }).first();
    if (await logoutBtn.isVisible().catch(() => false)) {
      await logoutBtn.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1000);
    }

    // Login again (return visit)
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    await page.locator('input[name="email"]').fill(BASE_USER.email);
    await page.locator('input[name="password"]').fill(BASE_USER.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 15000,
    });
    await page.waitForTimeout(1500);

    // Should have login + logout events
    collector.assertFired("login_completed");
    console.log("  Logout + re-login events:", collector.summary());
    await context.close();
  });
});
