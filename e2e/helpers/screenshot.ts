/**
 * Screenshot helper — attaches a full-page screenshot to the Playwright HTML report.
 * Each screenshot appears in the test's "Attachments" section with the given label.
 */

import { test } from "@playwright/test";
import { Page } from "@playwright/test";

/** Take a full-page screenshot and attach it to the current test's report. */
export async function snap(page: Page, label: string): Promise<void> {
  await test.info().attach(label, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}
