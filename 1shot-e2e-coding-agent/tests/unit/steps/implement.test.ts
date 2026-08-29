/**
 * tests/unit/steps/implement.test.ts — T081
 *
 * Tests the implement step: Pi session with full write tool access,
 * plan injection into prompt, ctx mutation, and token tracking.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunContext } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import { createLayerBudgets } from "../../../src/types.js";

// ─── Mocks ────────────────────────────────────────────────────────────────────

const { mockCreateSession, mockRunPrompt, mockGetTokensUsed } = vi.hoisted(() => ({
  mockCreateSession: vi.fn(),
  mockRunPrompt: vi.fn(),
  mockGetTokensUsed: vi.fn(),
}));

vi.mock("../../../src/adapters/pi-sdk.js", () => ({
  createSession: mockCreateSession,
  runPrompt: mockRunPrompt,
  getTokensUsed: mockGetTokensUsed,
}));

import { implementStep } from "../../../src/steps/implement.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAKE_HANDLE = { session: {} as never };

const SAMPLE_PLAN = `
## Change Plan

1. src/auth/login.ts — swap bcrypt.compare arguments on line 42
2. tests/auth/login.test.ts — add "should reject wrong password" test case
`.trim();

const LLM_IMPLEMENT_RESPONSE = `
I have completed the implementation:

- Modified src/auth/login.ts: swapped bcrypt.compare(raw, hash) to bcrypt.compare(hash, raw)
- Modified tests/auth/login.test.ts: added test case for wrong password rejection

All changes have been applied successfully.
`.trim();

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "fix the login bug in auth module",
      slug: "fix-the-login-bug-in-auth-module",
      timestamp: "2026-03-16T00:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      provider: {
        default: "anthropic",
        anthropicModel: "claude-sonnet-4-20250514",
        openaiModel: "gpt-4.1",
      },
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/fix-the-login-bug-in-auth-module",
    repoMap: "",
    relevantFiles: ["src/auth/login.ts", "tests/auth/login.test.ts"],
    understanding: "The login function has a bug in bcrypt.compare argument order.",
    plan: SAMPLE_PLAN,
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

describe("implementStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue(FAKE_HANDLE);
    mockRunPrompt.mockResolvedValue(LLM_IMPLEMENT_RESPONSE);
    mockGetTokensUsed.mockReturnValue(8000);
  });

  // ─── Status ─────────────────────────────────────────────────────────────────

  it("returns passed status on success", async () => {
    const result = await implementStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns error status when createSession throws", async () => {
    mockCreateSession.mockRejectedValueOnce(new Error("API key missing"));
    const result = await implementStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/API key missing/i);
  });

  it("returns error status when runPrompt throws", async () => {
    mockRunPrompt.mockRejectedValueOnce(new Error("context window exceeded"));
    const result = await implementStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/context window exceeded/i);
  });

  // ─── Session config — write tool access ─────────────────────────────────────

  it("creates session with write tools: read, write, edit, bash, grep, find", async () => {
    await implementStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ tools: string[] }];
    expect(sessionConfig.tools).toEqual(["read", "write", "edit", "bash", "grep", "find"]);
  });

  it("creates session with write tool enabled (not read-only)", async () => {
    await implementStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ tools: string[] }];
    expect(sessionConfig.tools).toContain("write");
    expect(sessionConfig.tools).toContain("edit");
    expect(sessionConfig.tools).toContain("bash");
  });

  it("creates session with provider from ctx.config", async () => {
    await implementStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ provider: string }];
    expect(sessionConfig.provider).toBe("anthropic");
  });

  it("creates session with anthropic model from ctx.config", async () => {
    await implementStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("claude-sonnet-4-20250514");
  });

  it("creates session with openai model when provider is openai", async () => {
    const ctx = makeCtx();
    ctx.config.provider = { default: "openai", openaiModel: "gpt-4.1" };
    await implementStep(ctx);
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("gpt-4.1");
  });

  it("passes workspacePath as cwd to createSession", async () => {
    await implementStep(makeCtx());
    const [, options] = mockCreateSession.mock.calls[0] as [unknown, { cwd: string }];
    expect(options?.cwd).toBe("/workspace/test-repo");
  });

  // ─── Prompt construction — plan injection ────────────────────────────────────

  it("user prompt contains ctx.plan from plan step", async () => {
    await implementStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain(SAMPLE_PLAN);
  });

  it("user prompt contains task description", async () => {
    await implementStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("fix the login bug in auth module");
  });

  it("user prompt contains workspace path", async () => {
    await implementStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("/workspace/test-repo");
  });

  it("user prompt works when ctx.plan is empty", async () => {
    const ctx = makeCtx({ plan: "" });
    const result = await implementStep(ctx);
    expect(result.status).toBe("passed");
  });

  // ─── Token usage ─────────────────────────────────────────────────────────────

  it("returns tokensUsed from getTokensUsed", async () => {
    const result = await implementStep(makeCtx());
    expect(result.tokensUsed).toBe(8000);
  });

  // ─── Result data ─────────────────────────────────────────────────────────────

  it("includes summary in result data", async () => {
    const result = await implementStep(makeCtx());
    expect(result.data?.summary).toBe(LLM_IMPLEMENT_RESPONSE);
  });
});
