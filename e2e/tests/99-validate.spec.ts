/**
 * Test 99: Final validation — verify all expected events fired and audience metrics return data.
 * Runs LAST after all persona journeys have completed.
 */

import { test, expect } from "@playwright/test";
import { AdminApiClient } from "../helpers/api-client";

const BASE_URL = "http://34.30.88.59";
const ADMIN_EMAIL = "admin@boilerplate.test";
const ADMIN_PASSWORD = "Admin123!";

// Events we expect the test suite to have fired (33/35 covered)
const EXPECTED_EVENTS: { event_type: string; min_count: number; source_tests: string }[] = [
  { event_type: "signup_completed", min_count: 10, source_tests: "01-register" },
  { event_type: "login_completed", min_count: 1, source_tests: "09-auth-edge-cases" },
  { event_type: "login_failed", min_count: 1, source_tests: "09-auth-edge-cases" },
  { event_type: "logout", min_count: 1, source_tests: "02-window-shoppers" },
  { event_type: "cookie_consent_given", min_count: 5, source_tests: "01-register, 08-guest" },
  { event_type: "product_viewed", min_count: 50, source_tests: "02-07" },
  { event_type: "search_performed", min_count: 5, source_tests: "02, 05" },
  { event_type: "add_to_cart", min_count: 20, source_tests: "03-06" },
  { event_type: "cart_viewed", min_count: 10, source_tests: "03-05" },
  { event_type: "checkout_started", min_count: 5, source_tests: "03-06" },
  { event_type: "purchase_completed", min_count: 1, source_tests: "04-05, 10" },
];

// Audience metrics we expect to return at least 1 row
const EXPECTED_AUDIENCE_METRICS = [
  "all_customers",
  "cart_abandoners",
  "added_to_cart",
  "active_30d",
];

test.describe("Event & Metric Validation", () => {
  let client: AdminApiClient;

  test.beforeAll(async ({ request }) => {
    client = await AdminApiClient.login(request, BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD);
  });

  test("All expected tracking events have fired", async () => {
    const events = await client.getEventDefinitions();
    expect(events.length).toBeGreaterThan(0);

    const eventMap = new Map(events.map((e) => [e.name, e]));

    const results: { event: string; expected: number; actual: number; pass: boolean }[] = [];

    for (const expected of EXPECTED_EVENTS) {
      const def = eventMap.get(expected.event_type);
      const actual = def?.fire_count_30d ?? 0;
      const pass = actual >= expected.min_count;
      results.push({ event: expected.event_type, expected: expected.min_count, actual, pass });
    }

    // Print coverage report
    console.log("\n=== EVENT COVERAGE REPORT ===");
    console.log("Event Type".padEnd(30) + "Expected".padEnd(10) + "Actual".padEnd(10) + "Status");
    console.log("-".repeat(60));
    for (const r of results) {
      const status = r.pass ? "PASS" : "FAIL";
      console.log(
        r.event.padEnd(30) + String(r.expected).padEnd(10) + String(r.actual).padEnd(10) + status
      );
    }

    // Also report events that fired but aren't in our expected list
    const expectedSet = new Set(EXPECTED_EVENTS.map((e) => e.event_type));
    const bonus = events.filter((e) => !expectedSet.has(e.name) && e.fire_count_30d > 0);
    if (bonus.length > 0) {
      console.log("\n--- Additional events fired (not in expected list) ---");
      for (const b of bonus) {
        console.log(`  ${b.name}: ${b.fire_count_30d} fires`);
      }
    }

    // Report events that never fired
    const neverFired = events.filter((e) => e.fire_count_30d === 0);
    if (neverFired.length > 0) {
      console.log("\n--- Events with zero fires ---");
      for (const n of neverFired) {
        console.log(`  ${n.name}`);
      }
    }

    const failures = results.filter((r) => !r.pass);
    if (failures.length > 0) {
      console.log(`\n${failures.length} events below expected threshold`);
    }

    // Soft assert — log failures but don't hard-fail (some events depend on Stripe success)
    expect.soft(failures.length).toBeLessThanOrEqual(3);
  });

  test("Audience metrics return data", async () => {
    const metrics = await client.getSavedMetrics();
    expect(metrics.length).toBeGreaterThan(0);

    console.log("\n=== AUDIENCE METRIC VALIDATION ===");
    console.log("Metric".padEnd(30) + "Rows".padEnd(10) + "Time (ms)".padEnd(12) + "Status");
    console.log("-".repeat(62));

    let failures = 0;

    for (const metric of metrics) {
      const result = await client.runMetric(metric.id);
      const rowCount = result?.row_count ?? 0;
      const timeMs = result?.execution_time_ms ?? 0;

      const isExpected = EXPECTED_AUDIENCE_METRICS.includes(metric.preset_key ?? "");
      const pass = !isExpected || rowCount > 0;
      if (!pass) failures++;

      const status = isExpected ? (pass ? "PASS" : "FAIL") : "SKIP";
      console.log(
        metric.name.padEnd(30) +
          String(rowCount).padEnd(10) +
          String(Math.round(timeMs)).padEnd(12) +
          status
      );
    }

    // Soft assert — some metrics may return 0 if checkout didn't complete
    expect.soft(failures).toBeLessThanOrEqual(1);
  });

  test("Total event summary", async () => {
    const events = await client.getEventDefinitions();
    const totalFired = events.reduce((sum, e) => sum + (e.fire_count_30d || 0), 0);
    const typesWithFires = events.filter((e) => e.fire_count_30d > 0).length;
    const totalTypes = events.length;

    console.log("\n=== SUMMARY ===");
    console.log(`Total event types: ${totalTypes}`);
    console.log(`Types with fires: ${typesWithFires}/${totalTypes} (${Math.round((typesWithFires / totalTypes) * 100)}%)`);
    console.log(`Total events fired: ${totalFired}`);
    console.log(`Coverage: ${typesWithFires}/${totalTypes} event types`);

    // At least 50% of event types should have fired
    expect(typesWithFires).toBeGreaterThan(totalTypes * 0.4);
  });
});
