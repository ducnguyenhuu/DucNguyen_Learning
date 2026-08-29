/**
 * tests/unit/steps/plan.test.ts — T080
 *
 * Tests the plan step: Pi session creation with read-only tools,
 * prompt construction (injecting relevantFiles + understanding from ctx),
 * structured plan output stored in ctx.plan.
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

import { planStep } from "../../../src/steps/plan.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAKE_HANDLE = { session: {} as never };

const LLM_PLAN_RESPONSE = `
## Change Plan

### Files to modify
1. src/auth/login.ts — fix validateCredentials() argument order (line 42)
2. tests/auth/login.test.ts — add test case for wrong password rejection

### Approach
1. In src/auth/login.ts, swap the arguments to bcrypt.compare():
   - Before: bcrypt.compare(raw, hash)
   - After:  bcrypt.compare(hash, raw)
2. In tests/auth/login.test.ts, add:
   - it("should reject wrong password", ...)
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
    relevantFiles: ["src/auth/login.ts", "src/auth/user.ts", "tests/auth/login.test.ts"],
    understanding: "The login function calls validateCredentials in user.ts. Bug is in bcrypt.compare args.",
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

describe("planStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue(FAKE_HANDLE);
    mockRunPrompt.mockResolvedValue(LLM_PLAN_RESPONSE);
    mockGetTokensUsed.mockReturnValue(2000);
  });

  // ─── Status ─────────────────────────────────────────────────────────────────

  it("returns passed status on success", async () => {
    const result = await planStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns error status when createSession throws", async () => {
    mockCreateSession.mockRejectedValueOnce(new Error("API key missing"));
    const result = await planStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/API key missing/i);
  });

  it("returns error status when runPrompt throws", async () => {
    mockRunPrompt.mockRejectedValueOnce(new Error("rate limit exceeded"));
    const result = await planStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/rate limit exceeded/i);
  });

  // ─── Session config ─────────────────────────────────────────────────────────

  it("creates session with read-only tools: read, grep, find, ls", async () => {
    await planStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ tools: string[] }];
    expect(sessionConfig.tools).toEqual(["read", "grep", "find", "ls"]);
  });

  it("creates session with provider from ctx.config", async () => {
    await planStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ provider: string }];
    expect(sessionConfig.provider).toBe("anthropic");
  });

  it("creates session with anthropic model from ctx.config", async () => {
    await planStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("claude-sonnet-4-20250514");
  });

  it("creates session with openai model when provider is openai", async () => {
    const ctx = makeCtx();
    ctx.config.provider = { default: "openai", openaiModel: "gpt-4.1" };
    await planStep(ctx);
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("gpt-4.1");
  });

  it("passes workspacePath as cwd to createSession", async () => {
    await planStep(makeCtx());
    const [, options] = mockCreateSession.mock.calls[0] as [unknown, { cwd: string }];
    expect(options?.cwd).toBe("/workspace/test-repo");
  });

  // ─── Prompt construction — context injection ─────────────────────────────────

  it("user prompt contains task description", async () => {
    await planStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("fix the login bug in auth module");
  });

  it("user prompt contains ctx.understanding from context_gather", async () => {
    await planStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("The login function calls validateCredentials");
  });

  it("user prompt contains each relevant file from ctx.relevantFiles", async () => {
    await planStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("src/auth/login.ts");
    expect(userPrompt).toContain("src/auth/user.ts");
    expect(userPrompt).toContain("tests/auth/login.test.ts");
  });

  it("user prompt works when ctx.relevantFiles is empty", async () => {
    const ctx = makeCtx({ relevantFiles: [] });
    const result = await planStep(ctx);
    expect(result.status).toBe("passed");
  });

  it("user prompt works when ctx.understanding is empty", async () => {
    const ctx = makeCtx({ understanding: "" });
    const result = await planStep(ctx);
    expect(result.status).toBe("passed");
  });

  // ─── ctx mutation ────────────────────────────────────────────────────────────

  it("sets ctx.plan to the LLM response", async () => {
    const ctx = makeCtx();
    await planStep(ctx);
    expect(ctx.plan).toBe(LLM_PLAN_RESPONSE);
  });

  // ─── Token usage ─────────────────────────────────────────────────────────────

  it("returns tokensUsed from getTokensUsed", async () => {
    const result = await planStep(makeCtx());
    expect(result.tokensUsed).toBe(2000);
  });

  // ─── Result data ─────────────────────────────────────────────────────────────

  it("includes plan in result data", async () => {
    const result = await planStep(makeCtx());
    expect(result.data?.plan).toBe(LLM_PLAN_RESPONSE);
  });
});
