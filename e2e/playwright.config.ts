import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://34.30.88.59";

/**
 * Test profile — controls which journey files run.
 *
 *   TEST_PROFILE=smoke   → 20 users, 1 worker, sequential (default)
 *   TEST_PROFILE=full    → 50 users, 2 workers, parallel
 *
 * Usage:
 *   TEST_PROFILE=smoke npx playwright test
 *   TEST_PROFILE=full  npx playwright test
 */
const profile = process.env.TEST_PROFILE || "smoke";

const isFull = profile === "full";

export default defineConfig({
  globalSetup: "./global-setup.ts",
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  retries: isFull ? 2 : 1,
  workers: isFull ? 2 : 1,
  fullyParallel: isFull,
  preserveOutput: "always",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "on",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: "01-register.spec.ts",
      timeout: 180_000,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
      // smoke = 20 users files; full = all journey + validation files
      testMatch: isFull
        ? ["0[2-9]-*.spec.ts", "1[0-4]-*.spec.ts", "99-*.spec.ts"]
        : [
            "02-users-001-005.spec.ts",
            "03-users-006-010.spec.ts",
            "04-users-011-015.spec.ts",
            "05-users-016-020.spec.ts",
          ],
      testIgnore: "01-register.spec.ts",
    },
  ],
  reporter: [
    ["html", { open: "never" }],
    ["list"],
    ["json", { outputFile: "test-results/results.json" }],
  ],
});
