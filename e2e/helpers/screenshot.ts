/**
 * Screenshot helper — saves step screenshots to both the Playwright HTML report
 * and to disk in the test's output directory for easy browsing.
 */

import { test } from "@playwright/test";
import { Page } from "@playwright/test";
import { writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";

/** Take a full-page screenshot: attach to report AND save to test output dir. */
export async function snap(page: Page, label: string): Promise<void> {
  const screenshot = await page.screenshot({ fullPage: true });

  // Attach to Playwright HTML report (visible in show-report)
  await test.info().attach(label, {
    body: screenshot,
    contentType: "image/png",
  });

  // Save to disk in the test's output directory (visible in test-results/ folder)
  try {
    const outPath = test.info().outputPath(`${label}.png`);
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, screenshot);
  } catch {
    // Non-critical — report attachment is the primary output
  }
}
