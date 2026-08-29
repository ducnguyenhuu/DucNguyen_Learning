/**
 * tests/unit/reporting/run-report.test.ts — T060
 *
 * Unit tests for run report generation.
 *
 * Tests cover:
 *  - Metrics aggregation: linesAdded/linesRemoved summed from filesChanged
 *  - Duration computed from startedAt / completedAt
 *  - totalTokens and estimatedCostUsd taken from the Run
 *  - prUrl passed through (or null when omitted)
 *  - status / task / branch / runId mapped from the Run
 *  - nodeResults forwarded unchanged
 *  - Edge cases: empty filesChanged, completedAt = null, zero-cost run
 */

import { describe, it, expect } from "vitest";
import type { Run, FileChange, TestResult, NodeResult } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { generateRunReport } from "../../../src/reporting/run-report.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const START = new Date("2026-03-13T14:00:00.000Z");
const END   = new Date("2026-03-13T14:00:35.000Z"); // 35 s later

const BASE_FILE_CHANGES: FileChange[] = [
  { path: "src/services/user_service.ts", action: "modified", linesAdded: 12, linesRemoved: 3 },
  { path: "tests/email-validation.test.ts", action: "created", linesAdded: 25, linesRemoved: 0 },
  { path: "src/old.ts", action: "deleted", linesAdded: 0, linesRemoved: 10 },
];

const BASE_TEST_RESULTS: TestResult = {
  passed: 10,
  failed: 0,
  skipped: 1,
  duration: 4200,
};

const BASE_NODE_RESULTS: NodeResult[] = [
  { nodeId: "setup",        type: "deterministic", status: "passed", duration: 500,   tokensUsed: 0 },
  { nodeId: "context",      type: "agent",         status: "passed", duration: 8000,  tokensUsed: 5000 },
  { nodeId: "implement",    type: "agent",         status: "passed", duration: 20000, tokensUsed: 11300 },
];

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "2026-03-13T14-00-00",
    task: {
      description: "Add email validation to user endpoint",
      slug: "add-email-validation-to-user-endpoint",
      timestamp: "2026-03-13T14:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
    },
    status: "succeeded",
    branch: "agent/add-email-validation-to-user-endpoint-1710331200",
    startedAt: START,
    completedAt: END,
    nodes: BASE_NODE_RESULTS,
    totalTokens: 16_300,
    totalCostUsd: 0.12,
    artifactsDir: "runs/2026-03-13T14-00-00",
    ...overrides,
  };
}

// ─── Identity & mapping ────────────────────────────────────────────────────────

describe("generateRunReport() — identity and field mapping", () => {
  it("maps runId from run.id", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.runId).toBe("2026-03-13T14-00-00");
  });

  it("maps status from run.status", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.status).toBe("succeeded");
  });

  it("maps task from run.task.description", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.task).toBe("Add email validation to user endpoint");
  });

  it("maps branch from run.branch", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.branch).toBe("agent/add-email-validation-to-user-endpoint-1710331200");
  });

  it("forwards filesChanged array unchanged", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.filesChanged).toEqual(BASE_FILE_CHANGES);
  });

  it("forwards testResults unchanged", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.testResults).toEqual(BASE_TEST_RESULTS);
  });

  it("forwards nodeResults unchanged from run.nodes", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.nodeResults).toEqual(BASE_NODE_RESULTS);
  });

  it("maps lintClean from the lintClean parameter — true", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.lintClean).toBe(true);
  });

  it("maps lintClean from the lintClean parameter — false", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, false);
    expect(report.lintClean).toBe(false);
  });
});

// ─── Computed metrics ─────────────────────────────────────────────────────────

describe("generateRunReport() — computed metrics aggregation", () => {
  it("sums linesAdded across all file changes", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    // 12 + 25 + 0 = 37
    expect(report.linesAdded).toBe(37);
  });

  it("sums linesRemoved across all file changes", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    // 3 + 0 + 10 = 13
    expect(report.linesRemoved).toBe(13);
  });

  it("copies totalTokens from run.totalTokens", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.totalTokens).toBe(16_300);
  });

  it("copies estimatedCostUsd from run.totalCostUsd", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.estimatedCostUsd).toBeCloseTo(0.12, 5);
  });

  it("computes durationSeconds from startedAt to completedAt", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    // START → END = 35 000 ms = 35 s
    expect(report.durationSeconds).toBe(35);
  });

  it("rounds durationSeconds to whole seconds", () => {
    const run = makeRun({
      startedAt: new Date("2026-03-13T14:00:00.000Z"),
      completedAt: new Date("2026-03-13T14:00:12.600Z"), // 12.6 s → floors to 12
    });
    const report = generateRunReport(run, BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.durationSeconds).toBe(12);
  });
});

// ─── PR URL ───────────────────────────────────────────────────────────────────

describe("generateRunReport() — PR URL", () => {
  it("sets prUrl to the provided URL string", () => {
    const report = generateRunReport(
      makeRun(),
      BASE_FILE_CHANGES,
      BASE_TEST_RESULTS,
      true,
      "https://github.com/user/repo/pull/42",
    );
    expect(report.prUrl).toBe("https://github.com/user/repo/pull/42");
  });

  it("defaults prUrl to null when omitted", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.prUrl).toBeNull();
  });

  it("accepts explicit null for prUrl (failed before PR creation)", () => {
    const report = generateRunReport(makeRun(), BASE_FILE_CHANGES, BASE_TEST_RESULTS, true, null);
    expect(report.prUrl).toBeNull();
  });
});

// ─── Edge cases ───────────────────────────────────────────────────────────────

describe("generateRunReport() — edge cases", () => {
  it("handles empty filesChanged array — linesAdded = 0", () => {
    const report = generateRunReport(makeRun(), [], BASE_TEST_RESULTS, true);
    expect(report.linesAdded).toBe(0);
  });

  it("handles empty filesChanged array — linesRemoved = 0", () => {
    const report = generateRunReport(makeRun(), [], BASE_TEST_RESULTS, true);
    expect(report.linesRemoved).toBe(0);
  });

  it("handles empty filesChanged array — filesChanged is empty array", () => {
    const report = generateRunReport(makeRun(), [], BASE_TEST_RESULTS, true);
    expect(report.filesChanged).toHaveLength(0);
  });

  it("handles completedAt = null — durationSeconds = 0", () => {
    const run = makeRun({ completedAt: null });
    const report = generateRunReport(run, BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.durationSeconds).toBe(0);
  });

  it("handles zero-cost run — estimatedCostUsd = 0", () => {
    const run = makeRun({ totalCostUsd: 0 });
    const report = generateRunReport(run, BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.estimatedCostUsd).toBe(0);
  });

  it("handles zero tokens — totalTokens = 0", () => {
    const run = makeRun({ totalTokens: 0 });
    const report = generateRunReport(run, BASE_FILE_CHANGES, BASE_TEST_RESULTS, true);
    expect(report.totalTokens).toBe(0);
  });

  it("handles failed run status", () => {
    const run = makeRun({ status: "failed" });
    const report = generateRunReport(run, [], BASE_TEST_RESULTS, false);
    expect(report.status).toBe("failed");
  });

  it("handles timeout status", () => {
    const run = makeRun({ status: "timeout" });
    const report = generateRunReport(run, [], BASE_TEST_RESULTS, false);
    expect(report.status).toBe("timeout");
  });

  it("handles a single modified file with no lines added", () => {
    const files: FileChange[] = [
      { path: "src/foo.ts", action: "modified", linesAdded: 0, linesRemoved: 5 },
    ];
    const report = generateRunReport(makeRun(), files, BASE_TEST_RESULTS, true);
    expect(report.linesAdded).toBe(0);
    expect(report.linesRemoved).toBe(5);
  });
});
