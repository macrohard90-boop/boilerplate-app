/**
 * Authentication helpers — register and login via the real UI forms.
 */

import { Page, BrowserContext } from "@playwright/test";
import { TestUser, authStatePath } from "./users";

/** Register a new user via the /auth/register page. */
export async function registerUser(
  page: Page,
  user: TestUser,
): Promise<void> {
  // Navigate only if not already on the register page
  if (!page.url().includes("/auth/register")) {
    await page.goto("/auth/register");
    await page.waitForLoadState("networkidle");
  }

  // Fill registration form using actual placeholders
  await page.locator('input[placeholder="John"]').fill(user.firstName);
  await page.locator('input[placeholder="Doe"]').fill(user.lastName);
  await page.locator('input[placeholder="you@example.com"]').fill(user.email);
  await page.locator('input[placeholder="Min 8 characters"]').fill(user.password);

  // Submit
  await page.locator('button[type="submit"]').click();

  // Wait for redirect to dashboard (registration success)
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
}

/** Login an existing user via the /auth/login page. */
export async function loginUser(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/auth/login", { timeout: 30000 });
  await page.waitForLoadState("domcontentloaded");

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.locator('button[type="submit"]').click();

  // Wait for redirect away from login page (longer timeout for slow VM)
  try {
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 30000,
    });
  } catch {
    // Redirect may have failed but session cookie might be set — try navigating directly
    await page.goto("/dashboard", { timeout: 30000 });
    await page.waitForLoadState("domcontentloaded");
  }
}

/** Save the current browser context's auth state to a file. */
export async function saveAuthState(
  context: BrowserContext,
  email: string,
): Promise<void> {
  const path = authStatePath(email);
  await context.storageState({ path });
}
