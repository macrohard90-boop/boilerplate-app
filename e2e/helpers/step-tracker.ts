/**
 * StepTracker — wraps test steps with progress logging and failure context.
 * Tracks which steps passed/failed and captures screenshots at failure points.
 */

import { test } from "@playwright/test";
import { Page } from "@playwright/test";
import { writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";
import { snap } from "./screenshot";

interface StepResult {
  step: number;
  label: string;
  status: "passed" | "failed" | "skipped";
  error?: string;
  durationMs: number;
}

export class StepTracker {
  private steps: StepResult[] = [];
  private currentStep = 0;
  private testName: string;
  private page: Page;

  constructor(page: Page, testName: string) {
    this.page = page;
    this.testName = testName;
  }

  /** Run a named step with automatic progress tracking and failure screenshots. */
  async run(label: string, fn: () => Promise<void>): Promise<void> {
    this.currentStep++;
    const stepNum = this.currentStep;
    const padded = String(stepNum).padStart(2, "0");
    const start = Date.now();

    try {
      await fn();
      const duration = Date.now() - start;
      this.steps.push({
        step: stepNum,
        label,
        status: "passed",
        durationMs: duration,
      });

      // Take step screenshot
      await snap(this.page, `${padded}-${label}`);
    } catch (err) {
      const duration = Date.now() - start;
      const errorMsg = err instanceof Error ? err.message : String(err);
      this.steps.push({
        step: stepNum,
        label,
        status: "failed",
        error: errorMsg,
        durationMs: duration,
      });

      // Capture failure screenshot with context
      try {
        await snap(this.page, `${padded}-FAILED-${label}`);
      } catch {
        // Page might be in a bad state
      }

      // Write progress summary before re-throwing
      this.writeSummary();

      throw err;
    }
  }

  /** Skip a step (log it but don't execute). */
  skip(label: string): void {
    this.currentStep++;
    this.steps.push({
      step: this.currentStep,
      label,
      status: "skipped",
      durationMs: 0,
    });
  }

  /** Write a progress summary to the test output directory. */
  writeSummary(): void {
    const lines: string[] = [];
    lines.push(`# Test Progress: ${this.testName}`);
    lines.push(`Date: ${new Date().toISOString()}`);
    lines.push("");

    const passed = this.steps.filter((s) => s.status === "passed").length;
    const failed = this.steps.filter((s) => s.status === "failed").length;
    const skipped = this.steps.filter((s) => s.status === "skipped").length;
    lines.push(
      `## Summary: ${passed} passed, ${failed} failed, ${skipped} skipped`,
    );
    lines.push("");

    for (const s of this.steps) {
      const icon =
        s.status === "passed"
          ? "PASS"
          : s.status === "failed"
            ? "FAIL"
            : "SKIP";
      const duration =
        s.durationMs > 0 ? ` (${(s.durationMs / 1000).toFixed(1)}s)` : "";
      lines.push(
        `${icon}  Step ${String(s.step).padStart(2, "0")}: ${s.label}${duration}`,
      );
      if (s.error) {
        lines.push(`       Error: ${s.error.split("\n")[0]}`);
      }
    }

    try {
      const outPath = test.info().outputPath("progress.md");
      mkdirSync(dirname(outPath), { recursive: true });
      writeFileSync(outPath, lines.join("\n"));
    } catch {
      // Fallback: log to console
      console.log(lines.join("\n"));
    }

    // Also attach to the HTML report
    test
      .info()
      .attach("progress-summary", {
        body: Buffer.from(lines.join("\n")),
        contentType: "text/markdown",
      })
      .catch(() => {});
  }

  /** Get the list of completed steps for assertions. */
  getResults(): StepResult[] {
    return [...this.steps];
  }
}
