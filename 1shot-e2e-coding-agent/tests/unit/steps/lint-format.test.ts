/**
 * tests/unit/steps/lint-format.test.ts — T018
 *
 * Tests the lint-and-format step: command execution, pass/fail detection,
 * auto-fix via formatCommand, and output capture.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const { mockRunCommand } = vi.hoisted(() => ({
  mockRunCommand: vi.fn(),
}));

vi.mock("../../../src/utils/run-command.js", () => ({
  runCommand: mockRunCommand,
}));

import { lintFormatStep } from "../../../src/steps/lint-format.js";

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
      repo: {
        ...DEFAULT_CONFIG.repo,
        testCommand: "npm test",
        lintCommand: "npm run lint",
        formatCommand: undefined,
      },
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

describe("lintFormatStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── Lint command execution ───────────────────────────────────────────────

  it("runs the configured lintCommand", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const ctx = makeCtx();
    await lintFormatStep(ctx);
    expect(mockRunCommand).toHaveBeenCalledWith(
      "npm run lint",
      "/workspace/test-repo",
    );
  });

  it("runs lintCommand in workspacePath", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const ctx = makeCtx({ workspacePath: "/tmp/my-repo" });
    await lintFormatStep(ctx);
    expect(mockRunCommand).toHaveBeenCalledWith(
      expect.any(String),
      "/tmp/my-repo",
    );
  });

  // ─── Exit code → status ───────────────────────────────────────────────────

  it("returns passed when lint exits with code 0", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const result = await lintFormatStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns failed when lint exits with non-zero code", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "2 errors found",
      stderr: "",
      exitCode: 1,
    });
    const result = await lintFormatStep(makeCtx());
    expect(result.status).toBe("failed");
  });

  it("returns error when runCommand throws", async () => {
    mockRunCommand.mockRejectedValue(new Error("command not found: eslint"));
    const result = await lintFormatStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/command not found/i);
  });

  // ─── Output capture ───────────────────────────────────────────────────────

  it("captures lint stdout in result data", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "All files passed lint checks",
      stderr: "",
      exitCode: 0,
    });
    const result = await lintFormatStep(makeCtx());
    expect(result.data?.lintOutput).toBe("All files passed lint checks");
  });

  it("captures lint stderr in result data", async () => {
    mockRunCommand.mockResolvedValue({
      stdout: "",
      stderr: "Warning: use strict",
      exitCode: 0,
    });
    const result = await lintFormatStep(makeCtx());
    // stderr is included in output (either merged or separate)
    const output = String(result.data?.lintOutput ?? "");
    expect(output).toContain("Warning: use strict");
  });

  // ─── formatCommand ────────────────────────────────────────────────────────

  it("does not run formatCommand when not configured", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const ctx = makeCtx(); // formatCommand: undefined
    await lintFormatStep(ctx);
    expect(mockRunCommand).toHaveBeenCalledTimes(1); // only lint
  });

  it("runs formatCommand when configured", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const ctx = makeCtx();
    ctx.config.repo.formatCommand = "npm run format";
    await lintFormatStep(ctx);
    expect(mockRunCommand).toHaveBeenCalledWith(
      "npm run format",
      "/workspace/test-repo",
    );
  });

  it("runs formatCommand after lintCommand", async () => {
    const calls: string[] = [];
    mockRunCommand.mockImplementation(async (cmd: string) => {
      calls.push(cmd);
      return { stdout: "", stderr: "", exitCode: 0 };
    });
    const ctx = makeCtx();
    ctx.config.repo.formatCommand = "npm run format";
    await lintFormatStep(ctx);
    expect(calls).toEqual(["npm run lint", "npm run format"]);
  });

  it("includes autoFixed: true in data when formatCommand runs", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const ctx = makeCtx();
    ctx.config.repo.formatCommand = "npm run format";
    const result = await lintFormatStep(ctx);
    expect(result.data?.autoFixed).toBe(true);
  });

  it("includes autoFixed: false when no formatCommand configured", async () => {
    mockRunCommand.mockResolvedValue({ stdout: "", stderr: "", exitCode: 0 });
    const result = await lintFormatStep(makeCtx());
    expect(result.data?.autoFixed).toBe(false);
  });

  it("still returns lint status even if formatCommand fails", async () => {
    mockRunCommand
      .mockResolvedValueOnce({ stdout: "", stderr: "", exitCode: 0 }) // lint passes
      .mockResolvedValueOnce({ stdout: "", stderr: "format error", exitCode: 1 }); // format fails
    const ctx = makeCtx();
    ctx.config.repo.formatCommand = "npm run format";
    const result = await lintFormatStep(ctx);
    // lint passed, so overall result is passed (format is advisory)
    expect(result.status).toBe("passed");
  });
});
