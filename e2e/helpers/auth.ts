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

  // Fill registration form
  await page.locator('input[name="firstName"]').fill(user.firstName);
  await page.locator('input[name="lastName"]').fill(user.lastName);
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="password"]').fill(user.password);

  // Submit
  await page.locator('button[type="submit"]').click();

  // Wait for redirect to dashboard (registration success)
  await page.waitForURL("**/dashboard**", { timeout: 15000 });
}

/** Login an existing user via the /auth/login page. */
export async function loginUser(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/auth/login");
  await page.waitForLoadState("networkidle");

  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();

  // Wait for redirect away from login page
  await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
    timeout: 15000,
  });
}

/** Save the current browser context's auth state to a file. */
export async function saveAuthState(
  context: BrowserContext,
  email: string,
): Promise<void> {
  const path = authStatePath(email);
  await context.storageState({ path });
}
