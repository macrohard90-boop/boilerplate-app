/**
 * Cookie consent helpers — bypass the GDPR consent banner via localStorage.
 */

import { Page } from "@playwright/test";

/** Set localStorage to accept all cookies (analytics, marketing, preferences). */
export async function acceptAllCookies(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.setItem(
      "cookie_consent",
      JSON.stringify({
        necessary: true,
        analytics: true,
        marketing: true,
        preferences: true,
      }),
    );
    localStorage.setItem("consent_modal_completed", "true");
  });
}

/** Click the "Accept All" button on the cookie banner (for testing the banner itself). */
export async function clickAcceptAllBanner(page: Page): Promise<void> {
  const banner = page.locator("text=Accept All").first();
  await banner.waitFor({ state: "visible", timeout: 5000 });
  await banner.click();
}
