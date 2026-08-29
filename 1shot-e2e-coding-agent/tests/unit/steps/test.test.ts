/**
 * tests/unit/steps/test.test.ts — T019
 *
 * Tests the test step: command execution, pass/fail count parsing,
 * duration tracking, and status determination.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext, TestResult } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const { mockRunCommand } = vi.hoisted(() => ({
  mockRunCommand: vi.fn(),
}));

vi.mock("../../../src/utils/run-command.js", () => ({
  runCommand: mockRunCommand,
}));

import { testStep } from "../../../src/steps/test.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "fix the login bug",
      slug: "fix-the-login-bug",
      timestamp: "2026-03-16T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/fix-the-login-bug",
    repoMap: "",
    relevantFiles: [],
    understanding: "",
    plan: "",
    retryCount: 0,
    errorHashes: [],
    tokenBudget: {
      maxTokens: 200_000,
      consumed: 0,
      remaining: 200_000,
      layerBudgets: createLayerBudgets(200_000),
    },
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
    ...overrides,
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("testStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Command execution ────────────────────────────────────────────────────

  it("runs the configured testCommand", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    await testStep(makeCtx());
    expect(mockRunCommand).toHaveBeenCalledWith("npm test", "/workspace/test-repo");
  });

  it("runs testCommand in workspacePath", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    await testStep(makeCtx({ workspacePath: "/tmp/other-repo" }));
    expect(mockRunCommand).toHaveBeenCalledWith(expect.any(String), "/tmp/other-repo");
  });

  // ─── Exit code → status ───────────────────────────────────────────────────

  it("returns passed when test command exits 0", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "All tests passed", stderr: "", exitCode: 0 });
    const result = await testStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns failed when test command exits non-zero", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "3 tests failed",
      stderr: "",
      exitCode: 1,
    });
    const result = await testStep(makeCtx());
    expect(result.status).toBe("failed");
  });

  it("returns error when runCommand throws", async () => {
    mockRunCommand.mockRejectedValue(new Error("jest: command not found"));
    const result = await testStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/command not found/i);
  });

  // ─── Pass/fail count parsing ──────────────────────────────────────────────

  it("parses vitest/jest style: 'Tests: 8 passed, 2 failed'", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "Tests: 8 passed, 2 failed, 10 total",
      stderr: "",
      exitCode: 1,
    });
    const result = await testStep(makeCtx());
    const tr = result.data?.testResult as TestResult;
    expect(tr.passed).toBe(8);
    expect(tr.failed).toBe(2);
  });

  it("parses 'X passed' style with no failures", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "10 passed (10)",
      stderr: "",
      exitCode: 0,
    });
    const result = await testStep(makeCtx());
    const tr = result.data?.testResult as TestResult;
    expect(tr.passed).toBe(10);
    expect(tr.failed).toBe(0);
  });

  it("sets passed=0, failed=0 when counts cannot be parsed", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "ok",
      stderr: "",
      exitCode: 0,
    });
    const result = await testStep(makeCtx());
    const tr = result.data?.testResult as TestResult;
    expect(tr.passed).toBe(0);
    expect(tr.failed).toBe(0);
  });

  it("infers all failed when exit non-zero and no counts found", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "something went wrong",
      stderr: "",
      exitCode: 1,
    });
    const result = await testStep(makeCtx());
    const tr = result.data?.testResult as TestResult;
    expect(tr.failed).toBeGreaterThanOrEqual(1);
  });

  // ─── Output capture ───────────────────────────────────────────────────────

  it("captures test output in result data", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "Tests: 5 passed",
      stderr: "",
      exitCode: 0,
    });
    const result = await testStep(makeCtx());
    expect(result.data?.output).toContain("Tests: 5 passed");
  });

  // ─── Duration ─────────────────────────────────────────────────────────────

  it("records a non-negative duration in TestResult", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const result = await testStep(makeCtx());
    const tr = result.data?.testResult as TestResult;
    expect(tr.duration).toBeGreaterThanOrEqual(0);
  });

  // ─── TestResult shape ─────────────────────────────────────────────────────

  it("always returns a testResult object in data", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const result = await testStep(makeCtx());
    expect(result.data?.testResult).toMatchObject({
      passed: expect.any(Number),
      failed: expect.any(Number),
      skipped: expect.any(Number),
      duration: expect.any(Number),
    });
  });
});
