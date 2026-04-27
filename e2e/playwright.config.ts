import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://34.30.88.59";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  retries: 1,
  workers: 6,
  fullyParallel: true,
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: "01-register.spec.ts",
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
      testIgnore: "01-register.spec.ts",
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
      dependencies: ["setup"],
      testMatch: [
        "04-single-buyers.spec.ts",
        "02-window-shoppers.spec.ts",
      ],
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
      dependencies: ["setup"],
      testMatch: [
        "04-single-buyers.spec.ts",
        "03-cart-abandoners.spec.ts",
      ],
    },
  ],
  reporter: [["html", { open: "never" }], ["list"]],
});
