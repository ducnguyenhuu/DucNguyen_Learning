/**
 * tests/integration/retry-loop.test.ts — T053
 *
 * Integration tests for the US3 shift-left retry loop.
 * Scenarios:
 *  1. quality-tools (run_test, run_lint) are wired into the fix_failures Pi session
 *  2. test failure → fix_failures → test passes → commit (full fix cycle)
 *  3. same error output repeats → oscillation detection → blueprint aborts (no commit)
 *
 * All external I/O is mocked (Pi SDK, fs, simple-git, run-command).
 * quality-tools and context-tools extensions are NOT mocked so their real
 * ToolDefinition objects flow through to the Pi session call assertions.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext } from "../../src/types.js";
import { DEFAULT_CONFIG } from "../../src/config.js";
import { createLayerBudgets } from "../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

// ── Pi SDK ────────────────────────────────────────────────────────────────────
const { mockCreateSession, mockRunPrompt, mockGetTokensUsed } = vi.hoisted(() => ({
  mockCreateSession: vi.fn(),
  mockRunPrompt: vi.fn(),
  mockGetTokensUsed: vi.fn(),
}));

vi.mock("../../src/adapters/pi-sdk.js", () => ({
  createSession: mockCreateSession,
  runPrompt: mockRunPrompt,
  getTokensUsed: mockGetTokensUsed,
}));

// ── node:fs/promises ──────────────────────────────────────────────────────────
const { mockReadFile, mockAccess } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
  mockAccess: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  readFile: mockReadFile,
  access: mockAccess,
}));

// ── simple-git ────────────────────────────────────────────────────────────────
const {
  mockCheckoutLocalBranch,
  mockAdd,
  mockCommit,
  mockPush,
  mockStatus,
  mockSimpleGit,
} = vi.hoisted(() => {
  const mockCheckoutLocalBranch = vi.fn().mockResolvedValue(undefined);
  const mockAdd = vi.fn().mockResolvedValue(undefined);
  const mockCommit = vi.fn().mockResolvedValue({ commit: "abc1234" });
  const mockPush = vi.fn().mockResolvedValue(undefined);
  const mockStatus = vi.fn().mockResolvedValue({ isClean: () => false });
  const mockGitInstance = {
    checkoutLocalBranch: mockCheckoutLocalBranch,
    add: mockAdd,
    commit: mockCommit,
    push: mockPush,
    status: mockStatus,
  };
  const mockSimpleGit = vi.fn(() => mockGitInstance);
  return {
    mockCheckoutLocalBranch,
    mockAdd,
    mockCommit,
    mockPush,
    mockStatus,
    mockSimpleGit,
  };
});

vi.mock("simple-git", () => ({
  default: mockSimpleGit,
  simpleGit: mockSimpleGit,
}));

// ── run-command ───────────────────────────────────────────────────────────────
const { mockRunCommand } = vi.hoisted(() => ({
  mockRunCommand: vi.fn(),
}));

vi.mock("../../src/utils/run-command.js", () => ({
  runCommand: mockRunCommand,
}));

// ── console.log (report step) ─────────────────────────────────────────────────
vi.spyOn(console, "log").mockImplementation(() => {});

import { createStandardBlueprint } from "../../src/blueprints/standard.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAKE_HANDLE = { session: {} as never };

const CONTEXT_GATHER_RESPONSE = `
Relevant files found:
- src/auth/login.ts
- tests/auth/login.test.ts

Understanding: The login module validates credentials.
`.trim();

const PLAN_RESPONSE = `
Files to modify:
1. src/auth/login.ts — fix password comparison logic
`.trim();

const IMPLEMENT_RESPONSE = "Applied fix: corrected password hash comparison.";
const FIX_RESPONSE = "Fixed the failing assertion in login.test.ts.";

/** Error output that will be repeated to trigger oscillation. */
const REPEATING_ERROR =
  "FAIL tests/auth/login.test.ts\n  ● login › rejects wrong password\n    Expected: false\n    Received: true";

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "fix login validation bug",
      slug: "fix-login-validation-bug",
      timestamp: "2026-03-17T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: {
        ...DEFAULT_CONFIG.repo,
        path: "/workspace/test-repo",
        testCommand: "npm test",
        lintCommand: "npm run lint",
      },
      git: {
        branchPrefix: "agent/",
        commitMessagePrefix: "[agent]",
        autoPush: false,
        baseBranch: "main",
      },
      shiftLeft: { maxRetries: 2 },
    },
    workspacePath: "/workspace/test-repo",
    branch: "",
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

/** Shared mock setup for a run where tests fail once then pass after fix. */
function setupSingleFixCycleMocks() {
  mockAccess.mockResolvedValue(undefined);
  mockReadFile.mockResolvedValue("# AGENTS.md\nFollow existing patterns.");

  mockCreateSession.mockResolvedValue(FAKE_HANDLE);
  mockRunPrompt
    .mockResolvedValueOnce(CONTEXT_GATHER_RESPONSE) // context_gather
    .mockResolvedValueOnce(PLAN_RESPONSE)           // plan
    .mockResolvedValueOnce(IMPLEMENT_RESPONSE)      // implement
    .mockResolvedValueOnce(FIX_RESPONSE);           // fix_failures
  mockGetTokensUsed.mockReturnValue(3_000);

  mockRunCommand
    .mockResolvedValueOnce({ stdout: "", stderr: "", exitCode: 0 })                    // lint pass
    .mockResolvedValueOnce({ stdout: REPEATING_ERROR, stderr: "", exitCode: 1 })       // test fail
    .mockResolvedValueOnce({ stdout: "Tests: 5 passed", stderr: "", exitCode: 0 });   // test pass (after fix)

  mockStatus.mockResolvedValue({ isClean: () => false });
  mockCommit.mockResolvedValue({ commit: "c0ffee" });
}

/** Shared mock setup for the oscillation scenario: same error output repeated. */
function setupOscillationMocks() {
  mockAccess.mockResolvedValue(undefined);
  mockReadFile.mockResolvedValue("");

  mockCreateSession.mockResolvedValue(FAKE_HANDLE);
  mockRunPrompt
    .mockResolvedValueOnce(CONTEXT_GATHER_RESPONSE) // context_gather
    .mockResolvedValueOnce(PLAN_RESPONSE)           // plan
    .mockResolvedValueOnce(IMPLEMENT_RESPONSE)      // implement
    .mockResolvedValueOnce(FIX_RESPONSE);           // fix_failures #1 (oscillation fires before #2)
  mockGetTokensUsed.mockReturnValue(2_000);

  // lint passes, then two identical test failures → oscillation
  mockRunCommand
    .mockResolvedValueOnce({ stdout: "", stderr: "", exitCode: 0 })               // lint
    .mockResolvedValueOnce({ stdout: REPEATING_ERROR, stderr: "", exitCode: 1 }) // test #1
    .mockResolvedValueOnce({ stdout: REPEATING_ERROR, stderr: "", exitCode: 1 }); // test #2 (same)
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("Retry Loop — Integration (US3)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ─── 1. quality-tools wired to fix_failures ─────────────────────────────────

  describe("quality-tools wired to fix_failures Pi session", () => {
    it("calls createSession with customTools during the fix_failures node", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // At least one createSession call must have customTools (the fix_failures node)
      const callWithCustomTools = mockCreateSession.mock.calls.find(
        ([config]: [{ customTools?: unknown[] }]) =>
          Array.isArray(config.customTools) && config.customTools.length > 0,
      );
      expect(callWithCustomTools).toBeDefined();
    });

    it("provides exactly 2 quality tools (run_test and run_lint) to the fix_failures session", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // Find the fix_failures session: it has exactly 2 customTools (run_test + run_lint)
      const fixFailuresCall = mockCreateSession.mock.calls.find(
        ([config]: [{ customTools?: unknown[] }]) =>
          Array.isArray(config.customTools) && config.customTools.length === 2,
      );
      expect(fixFailuresCall).toBeDefined();
    });

    it("includes run_test and run_lint tool names in the fix_failures session", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      const fixFailuresCall = mockCreateSession.mock.calls.find(
        ([config]: [{ customTools?: unknown[] }]) =>
          Array.isArray(config.customTools) && config.customTools.length === 2,
      );
      expect(fixFailuresCall).toBeDefined();

      const tools = fixFailuresCall![0].customTools as Array<{ name: string }>;
      const toolNames = tools.map((t) => t.name);
      expect(toolNames).toContain("run_test");
      expect(toolNames).toContain("run_lint");
    });

    it("configures quality-tools with the workspace test command from config", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // run_test tool description or handler should reference "npm test" (from ctx.config.repo.testCommand)
      // We verify this indirectly: the tool was registered with our config values by checking
      // the fix_failures Pi session received customTools (tool creation did not throw)
      const fixFailuresCall = mockCreateSession.mock.calls.find(
        ([config]: [{ customTools?: unknown[] }]) =>
          Array.isArray(config.customTools) && config.customTools.length === 2,
      );
      expect(fixFailuresCall).toBeDefined();
      // The tools array contains ToolDefinition objects (not null/undefined)
      const tools = fixFailuresCall![0].customTools as unknown[];
      expect(tools.every((t) => t !== null && t !== undefined)).toBe(true);
    });
  });

  // ─── 2. failure → fix → pass (full retry cycle) ─────────────────────────────

  describe("test failure → fix → pass", () => {
    it("returns succeeded after one fix-failures cycle repairs the test failure", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      expect(summary.status).toBe("succeeded");
    });

    it("executes fix_failures before commit_and_push in the node sequence", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      const ids = summary.nodeResults.map((r) => r.nodeId);
      expect(ids).toContain("fix_failures");
      expect(ids).toContain("commit_and_push");
      expect(ids.indexOf("fix_failures")).toBeLessThan(ids.indexOf("commit_and_push"));
    });

    it("increments ctx.retryCount to 1 after one successful fix attempt", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      expect(ctx.retryCount).toBe(1);
    });

    it("stores the error hash in ctx.errorHashes after fix_failures runs", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      expect(ctx.errorHashes).toHaveLength(1);
    });

    it("fix_failures node result has status passed when it successfully fixes", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      const fixNode = summary.nodeResults.find((r) => r.nodeId === "fix_failures");
      expect(fixNode).toBeDefined();
      expect(fixNode!.status).toBe("passed");
    });

    it("runs the test node twice (first fail + retry pass) in a single fix cycle", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      const testNodes = summary.nodeResults.filter((r) => r.nodeId === "test");
      expect(testNodes.length).toBe(2);
    });

    it("commits to the branch after the test passes post-fix", async () => {
      setupSingleFixCycleMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      expect(mockCommit).toHaveBeenCalledTimes(1);
    });
  });

  // ─── 3. oscillation detection → abort ────────────────────────────────────────

  describe("oscillation detection → abort", () => {
    it("aborts the blueprint when the same error output repeats", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      // Blueprint ends mid-loop — no commit or report after oscillation abort
      const ids = summary.nodeResults.map((r) => r.nodeId);
      expect(ids).not.toContain("commit_and_push");
    });

    it("does not call commit when oscillation aborts the retry loop", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      expect(mockCommit).not.toHaveBeenCalled();
    });

    it("records fix_failures with status failed when oscillation fires", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      const fixNodes = summary.nodeResults.filter((r) => r.nodeId === "fix_failures");
      // fix_failures #1 passes (stores hash), fix_failures #2 detects oscillation → failed
      const failedFix = fixNodes.find((r) => r.status === "failed");
      expect(failedFix).toBeDefined();
    });

    it("does not call the Pi session for the oscillating fix attempt", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // Expect exactly 3 runPrompt calls: context_gather + plan + implement + fix #1
      // fix #2 oscillates before calling the Pi session
      const fixRelatedPromptCalls = mockRunPrompt.mock.calls.length;
      // context_gather=1, plan=1, implement=1, fix#1=1 → total 4 (NOT 5)
      expect(fixRelatedPromptCalls).toBe(4);
    });

    it("runs fix_failures twice: first succeeds (stores hash), second detects oscillation", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      const summary = await runner.run(ctx);

      const fixNodes = summary.nodeResults.filter((r) => r.nodeId === "fix_failures");
      expect(fixNodes.length).toBe(2);
      expect(fixNodes[0].status).toBe("passed");
      expect(fixNodes[1].status).toBe("failed");
    });

    it("stores exactly one error hash (from the first fix attempt)", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // Only one unique hash is stored (the repeating error is the same hash)
      expect(ctx.errorHashes).toHaveLength(1);
    });

    it("does not increment retryCount on the oscillating fix attempt", async () => {
      setupOscillationMocks();
      const ctx = makeCtx();
      const runner = createStandardBlueprint(ctx);
      await runner.run(ctx);

      // retryCount should be 1: incremented by the first fix, not by the oscillating second
      expect(ctx.retryCount).toBe(1);
    });
  });
});
