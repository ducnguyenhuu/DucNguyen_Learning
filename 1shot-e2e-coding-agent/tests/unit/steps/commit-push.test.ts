/**
 * tests/unit/steps/commit-push.test.ts — T020
 *
 * Tests the commit-and-push step: staging changes, commit message formatting,
 * branch push, and edge cases (nothing to commit, push failure).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const { mockAdd, mockCommit, mockPush, mockStatus, mockGitInstance } = vi.hoisted(() => {
  const mockAdd = vi.fn().mockResolvedValue(undefined);
  const mockCommit = vi.fn().mockResolvedValue({ commit: "abc123def456" });
  const mockPush = vi.fn().mockResolvedValue(undefined);
  const mockStatus = vi.fn().mockResolvedValue({
    files: [{ path: "src/auth.ts" }, { path: "tests/auth.test.ts" }],
    isClean: () => false,
  });
  const mockGitInstance = { add: mockAdd, commit: mockCommit, push: mockPush, status: mockStatus };
  return { mockAdd, mockCommit, mockPush, mockStatus, mockGitInstance };
});

vi.mock("simple-git", () => ({
  default: vi.fn(() => mockGitInstance),
  simpleGit: vi.fn(() => mockGitInstance),
}));

import { commitPushStep } from "../../../src/steps/commit-push.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "Fix login bug in auth module",
      slug: "fix-login-bug-in-auth-module",
      timestamp: "2026-03-16T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
      git: {
        branchPrefix: "agent/",
        commitMessagePrefix: "[agent]",
        autoPush: true,
        baseBranch: "main",
      },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/fix-login-bug-in-auth-module",
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

describe("commitPushStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStatus.mockResolvedValue({
      files: [{ path: "src/auth.ts" }],
      isClean: () => false,
    });
    mockCommit.mockResolvedValue({ commit: "abc123def456" });
  });

  // ─── Status ──────────────────────────────────────────────────────────────

  it("returns passed status on success", async () => {
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns error status when commit fails", async () => {
    mockCommit.mockRejectedValueOnce(new Error("gpg signing failed"));
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/gpg signing failed/i);
  });

  it("returns error status when push fails", async () => {
    mockPush.mockRejectedValueOnce(new Error("remote: Permission denied"));
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/permission denied/i);
  });

  // ─── Staging ─────────────────────────────────────────────────────────────

  it("stages all changes with git add", async () => {
    await commitPushStep(makeCtx());
    expect(mockAdd).toHaveBeenCalledWith(".");
  });

  // ─── Commit message ───────────────────────────────────────────────────────

  it("includes the commitMessagePrefix in the commit message", async () => {
    await commitPushStep(makeCtx());
    const commitMsg = mockCommit.mock.calls[0]![0] as string;
    expect(commitMsg).toMatch(/^\[agent\]/);
  });

  it("includes the task description in the commit message", async () => {
    await commitPushStep(makeCtx());
    const commitMsg = mockCommit.mock.calls[0]![0] as string;
    expect(commitMsg).toContain("Fix login bug in auth module");
  });

  it("uses default '[agent]' prefix when commitMessagePrefix is not configured", async () => {
    const ctx = makeCtx();
    ctx.config.git = { ...ctx.config.git, commitMessagePrefix: undefined };
    await commitPushStep(ctx);
    const commitMsg = mockCommit.mock.calls[0]![0] as string;
    expect(commitMsg).toMatch(/^\[agent\]/);
  });

  // ─── Push ─────────────────────────────────────────────────────────────────

  it("pushes to origin with the current branch", async () => {
    await commitPushStep(makeCtx());
    expect(mockPush).toHaveBeenCalledWith(
      "origin",
      "agent/fix-login-bug-in-auth-module",
      expect.anything(),
    );
  });

  it("skips push when autoPush is false", async () => {
    const ctx = makeCtx();
    ctx.config.git = { ...ctx.config.git, autoPush: false };
    await commitPushStep(ctx);
    expect(mockPush).not.toHaveBeenCalled();
  });

  // ─── Result data ──────────────────────────────────────────────────────────

  it("includes branch in result data", async () => {
    const result = await commitPushStep(makeCtx());
    expect(result.data?.branch).toBe("agent/fix-login-bug-in-auth-module");
  });

  it("includes commit SHA in result data", async () => {
    const result = await commitPushStep(makeCtx());
    expect(result.data?.sha).toBe("abc123def456");
  });

  // ─── Nothing to commit ────────────────────────────────────────────────────

  it("returns passed with noop notice when there are no changes to commit", async () => {
    mockStatus.mockResolvedValueOnce({ files: [], isClean: () => true });
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("passed");
    expect(result.data?.noop).toBe(true);
  });
});
