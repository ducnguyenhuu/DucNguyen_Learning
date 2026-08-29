/**
 * src/steps/test.ts — Test step (FR-007)
 *
 * Sixth node in the standard blueprint. Responsible for:
 *  1. Running the configured testCommand in the workspace
 *  2. Parsing pass/fail/skipped counts from output (vitest/jest style)
 *  3. Returning passed/failed/error based on exit code
 *
 * The exit code drives the result:
 *   exitCode 0  → passed
 *   exitCode >0 → failed
 *   spawn error → error
 *
 * Returns a StepResult with:
 *  - data.testResult — { passed, failed, skipped, duration }
 *  - data.output     — combined stdout + stderr
 */

import { runCommand } from "../utils/run-command.js";
import type { RunContext, StepResult, TestResult } from "../types.js";

// ─── Output parsers ───────────────────────────────────────────────────────────

/**
 * Parse pass/fail/skipped counts from vitest/jest style output.
 *
 * Handles patterns like:
 *   "Tests: 8 passed, 2 failed, 10 total"
 *   "10 passed (10)"
 *   "✓ 5 passed"
 */
function parseTestCounts(output: string): Pick<TestResult, "passed" | "failed" | "skipped"> {
  // vitest/jest: "Tests: 8 passed, 2 failed"
  const passFail = output.match(/Tests?:.*?(\d+)\s+passed.*?(\d+)\s+failed/i);
  if (passFail) {
    return {
      passed: parseInt(passFail[1]!, 10),
      failed: parseInt(passFail[2]!, 10),
      skipped: 0,
    };
  }

  // vitest/jest: "Tests: 2 failed, 8 passed"  (order reversed)
  const failPass = output.match(/Tests?:.*?(\d+)\s+failed.*?(\d+)\s+passed/i);
  if (failPass) {
    return {
      passed: parseInt(failPass[2]!, 10),
      failed: parseInt(failPass[1]!, 10),
      skipped: 0,
    };
  }

  // "8 passed" with no failures
  const passedOnly = output.match(/(\d+)\s+passed/i);
  if (passedOnly) {
    return {
      passed: parseInt(passedOnly[1]!, 10),
      failed: 0,
      skipped: 0,
    };
  }

  // "2 failed" with no pass count found
  const failedOnly = output.match(/(\d+)\s+failed/i);
  if (failedOnly) {
    return {
      passed: 0,
      failed: parseInt(failedOnly[1]!, 10),
      skipped: 0,
    };
  }

  return { passed: 0, failed: 0, skipped: 0 };
}

// ─── testStep ─────────────────────────────────────────────────────────────────

export async function testStep(ctx: RunContext): Promise<StepResult> {
  const { testCommand } = ctx.config.repo;
  const cwd = ctx.workspacePath;

  const start = Date.now();

  let output: string;
  let exitCode: number;

  try {
    const result = await runCommand(testCommand, cwd);
    exitCode = result.exitCode;
    output = [result.stdout, result.stderr].filter(Boolean).join("\n");
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  const duration = Date.now() - start;
  const counts = parseTestCounts(output);

  // If exit non-zero and no counts parsed, signal at least 1 failure
  if (exitCode !== 0 && counts.passed === 0 && counts.failed === 0) {
    counts.failed = 1;
  }

  const testResult: TestResult = {
    passed: counts.passed,
    failed: counts.failed,
    skipped: counts.skipped,
    duration,
  };

  return {
    status: exitCode === 0 ? "passed" : "failed",
    data: {
      testResult,
      output,
    },
  };
}
