/**
 * tests/unit/steps/setup.test.ts — T017
 *
 * Tests the setup step: git branch creation, task slug parsing,
 * AGENTS.md loading, and RunContext initialisation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const { mockCheckoutLocalBranch, mockGitDefault, mockSimpleGit } = vi.hoisted(() => {
  const mockCheckoutLocalBranch = vi.fn().mockResolvedValue(undefined);
  const mockGitInstance = { checkoutLocalBranch: mockCheckoutLocalBranch };
  const mockGitDefault = vi.fn(() => mockGitInstance);
  const mockSimpleGit = vi.fn(() => mockGitInstance);
  return { mockCheckoutLocalBranch, mockGitDefault, mockSimpleGit };
});

vi.mock("simple-git", () => ({
  default: mockGitDefault,
  simpleGit: mockSimpleGit,
}));

const { mockReadFile, mockAccess } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
  mockAccess: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  readFile: mockReadFile,
  access: mockAccess,
}));

import { setupStep } from "../../../src/steps/setup.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "fix the login bug in auth module",
      slug: "fix-the-login-bug-in-auth-module",
      timestamp: "2026-03-16T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
      git: { branchPrefix: "agent/", commitMessagePrefix: "[agent]", autoPush: true, baseBranch: "main" },
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

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("setupStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAccess.mockRejectedValue(new Error("ENOENT")); // no AGENTS.md by default
  });

  // ─── Status ──────────────────────────────────────────────────────────────

  it("returns passed status on success", async () => {
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.status).toBe("passed");
  });

  it("returns error status when git branch creation fails", async () => {
    mockCheckoutLocalBranch.mockRejectedValueOnce(new Error("branch already exists"));
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/branch already exists/i);
  });

  // ─── Branch creation ─────────────────────────────────────────────────────

  it("creates a branch with branchPrefix + slug", async () => {
    const ctx = makeCtx();
    await setupStep(ctx);
    expect(mockCheckoutLocalBranch).toHaveBeenCalledWith(
      "agent/fix-the-login-bug-in-auth-module",
    );
  });

  it("sets ctx.branch to the created branch name", async () => {
    const ctx = makeCtx();
    await setupStep(ctx);
    expect(ctx.branch).toBe("agent/fix-the-login-bug-in-auth-module");
  });

  it("includes branch name in result data", async () => {
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.data?.branch).toBe("agent/fix-the-login-bug-in-auth-module");
  });

  it("uses default 'agent/' prefix when branchPrefix is not configured", async () => {
    const ctx = makeCtx();
    ctx.config.git = { ...ctx.config.git, branchPrefix: undefined };
    await setupStep(ctx);
    expect(mockCheckoutLocalBranch).toHaveBeenCalledWith(
      expect.stringMatching(/^agent\//),
    );
  });

  it("creates git instance pointing at workspacePath", async () => {
    const ctx = makeCtx();
    await setupStep(ctx);
    expect(mockSimpleGit).toHaveBeenCalledWith("/workspace/test-repo");
  });

  // ─── AGENTS.md ───────────────────────────────────────────────────────────

  it("stores empty string in result data when AGENTS.md is absent", async () => {
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.data?.agentsMd).toBe("");
  });

  it("reads and stores AGENTS.md content when the file exists", async () => {
    mockAccess.mockResolvedValueOnce(undefined); // file exists
    mockReadFile.mockResolvedValueOnce("# AGENTS\nDo not modify vendor/");
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.data?.agentsMd).toBe("# AGENTS\nDo not modify vendor/");
  });

  it("reads AGENTS.md from workspacePath", async () => {
    mockAccess.mockResolvedValueOnce(undefined);
    mockReadFile.mockResolvedValueOnce("content");
    const ctx = makeCtx();
    await setupStep(ctx);
    expect(mockReadFile).toHaveBeenCalledWith(
      expect.stringContaining("AGENTS.md"),
      "utf-8",
    );
  });

  it("still succeeds if AGENTS.md read fails unexpectedly", async () => {
    mockAccess.mockResolvedValueOnce(undefined);
    mockReadFile.mockRejectedValueOnce(new Error("permission denied"));
    const ctx = makeCtx();
    const result = await setupStep(ctx);
    expect(result.status).toBe("passed");
    expect(result.data?.agentsMd).toBe("");
  });
});
