/**
 * tests/unit/steps/report.test.ts — T021
 *
 * Tests the report step: summary formatting, console output,
 * metrics inclusion, and consistent passed return status.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext, TestResult } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// Spy on console output — report step writes there
const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});

import { reportStep } from "../../../src/steps/report.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "Add email validation to user endpoint",
      slug: "add-email-validation-to-user-endpoint",
      timestamp: "2026-03-16T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/add-email-validation-to-user-endpoint",
    repoMap: "",
    relevantFiles: [],
    understanding: "",
    plan: "",
    retryCount: 0,
    errorHashes: [],
    tokenBudget: {
      maxTokens: 200_000,
      consumed: 12_500,
      remaining: 187_500,
      layerBudgets: createLayerBudgets(200_000),
    },
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
    ...overrides,
  };
}

function getFullOutput(): string {
  return consoleSpy.mock.calls.flat().join("\n");
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("reportStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Status ──────────────────────────────────────────────────────────────

  it("always returns passed status", async () => {
    const result = await reportStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  // ─── Console output ───────────────────────────────────────────────────────

  it("outputs the task description", async () => {
    await reportStep(makeCtx());
    expect(getFullOutput()).toContain("Add email validation to user endpoint");
  });

  it("outputs the branch name", async () => {
    await reportStep(makeCtx());
    expect(getFullOutput()).toContain("agent/add-email-validation-to-user-endpoint");
  });

  it("outputs the token count", async () => {
    await reportStep(makeCtx());
    expect(getFullOutput()).toMatch(/12[,_]?500|12500/);
  });

  it("outputs a summary even when branch is empty string", async () => {
    const ctx = makeCtx({ branch: "" });
    const result = await reportStep(ctx);
    expect(result.status).toBe("passed");
    // should not throw
  });

  // ─── Metrics in result data ───────────────────────────────────────────────

  it("includes totalTokens in result data", async () => {
    const result = await reportStep(makeCtx());
    expect(result.data?.totalTokens).toBe(12_500);
  });

  it("includes branch in result data", async () => {
    const result = await reportStep(makeCtx());
    expect(result.data?.branch).toBe("agent/add-email-validation-to-user-endpoint");
  });

  // ─── Test results integration ─────────────────────────────────────────────

  it("outputs test result summary when testResult is provided in data", async () => {
    const testResult: TestResult = { passed: 10, failed: 0, skipped: 0, duration: 3200 };
    const result = await reportStep(
      makeCtx(),
      { testResult } as Record<string, unknown>,
    );
    expect(getFullOutput()).toMatch(/10.*passed|passed.*10/i);
    expect(result.status).toBe("passed");
  });

  it("outputs failed count when tests failed", async () => {
    const testResult: TestResult = { passed: 7, failed: 3, skipped: 0, duration: 2100 };
    await reportStep(makeCtx(), { testResult } as Record<string, unknown>);
    expect(getFullOutput()).toMatch(/3.*fail|fail.*3/i);
  });

  it("handles missing testResult gracefully", async () => {
    const result = await reportStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  // ─── PR URL ───────────────────────────────────────────────────────────────

  it("outputs PR URL when provided in accumulated data", async () => {
    await reportStep(
      makeCtx(),
      { prUrl: "https://github.com/user/repo/pull/42" } as Record<string, unknown>,
    );
    expect(getFullOutput()).toContain("https://github.com/user/repo/pull/42");
  });

  it("handles absent PR URL gracefully", async () => {
    const result = await reportStep(makeCtx());
    expect(result.status).toBe("passed");
  });
});
