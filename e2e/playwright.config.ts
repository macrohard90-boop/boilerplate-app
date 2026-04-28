import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://34.30.88.59";

export default defineConfig({
  globalSetup: "./global-setup.ts",
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  retries: 2,
  workers: 2,
  fullyParallel: true,
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
      testIgnore: "01-register.spec.ts",
    },
  ],
  reporter: [["html", { open: "never" }], ["list"], ["json", { outputFile: "test-results/results.json" }]],
});
