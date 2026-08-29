/**
 * tests/unit/steps/context-gather.test.ts — T079, T046
 *
 * Tests the context-gather step: Pi session creation with read-only tools,
 * context-tools extension loading (multi-signal retrieval), prompt construction,
 * relevant file output parsing, and ctx mutation.
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

const { mockReadFile } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  readFile: mockReadFile,
}));

const FAKE_TOOL_DEFINITIONS = [
  { name: "repo_map" },
  { name: "semantic_search" },
  { name: "symbol_nav" },
  { name: "dependency_graph" },
];

const { mockCreateContextToolsExtension } = vi.hoisted(() => ({
  mockCreateContextToolsExtension: vi.fn(),
}));

vi.mock("../../../extensions/context-tools.js", () => ({
  createContextToolsExtension: mockCreateContextToolsExtension,
}));

import { contextGatherStep } from "../../../src/steps/context-gather.js";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FAKE_HANDLE = { session: {} as never };

const LLM_RESPONSE_WITH_FILES = `
I have explored the repository and identified the following relevant files:

- src/auth/login.ts
- src/auth/user.ts
- tests/auth/login.test.ts

Understanding: The login functionality is implemented in src/auth/login.ts. It uses a user model
defined in src/auth/user.ts. The bug is likely in the validateCredentials function.
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

describe("contextGatherStep()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue(FAKE_HANDLE);
    mockRunPrompt.mockResolvedValue(LLM_RESPONSE_WITH_FILES);
    mockGetTokensUsed.mockReturnValue(1500);
    // Default: reject all readFile calls (covers both skill loading and AGENTS.md)
    mockReadFile.mockRejectedValue(new Error("ENOENT"));
    mockCreateContextToolsExtension.mockReturnValue({
      name: "context-tools",
      tools: ["repo_map", "semantic_search", "symbol_nav", "dependency_graph"],
      toolDefinitions: FAKE_TOOL_DEFINITIONS,
    });
  });

  // ─── Status ────────────────────────────────────────────────────────────────

  it("returns passed status on success", async () => {
    const result = await contextGatherStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  it("returns error status when createSession throws", async () => {
    mockCreateSession.mockRejectedValueOnce(new Error("API key missing"));
    const result = await contextGatherStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/API key missing/i);
  });

  it("returns error status when runPrompt throws", async () => {
    mockRunPrompt.mockRejectedValueOnce(new Error("rate limit exceeded"));
    const result = await contextGatherStep(makeCtx());
    expect(result.status).toBe("error");
    expect(result.error).toMatch(/rate limit exceeded/i);
  });

  // ─── Session config ─────────────────────────────────────────────────────────

  it("creates session with read-only tools: read, grep, find, ls", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ tools: string[] }];
    expect(sessionConfig.tools).toEqual(["read", "grep", "find", "ls"]);
  });

  it("creates session with provider from ctx.config", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ provider: string }];
    expect(sessionConfig.provider).toBe("anthropic");
  });

  it("creates session with anthropic model from ctx.config", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("claude-sonnet-4-20250514");
  });

  it("creates session with openai model when provider is openai", async () => {
    const ctx = makeCtx();
    ctx.config.provider = { default: "openai", openaiModel: "gpt-4.1" };
    await contextGatherStep(ctx);
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ model: string }];
    expect(sessionConfig.model).toBe("gpt-4.1");
  });

  it("passes workspacePath as cwd to createSession", async () => {
    await contextGatherStep(makeCtx());
    const [, options] = mockCreateSession.mock.calls[0] as [unknown, { cwd: string }];
    expect(options?.cwd).toBe("/workspace/test-repo");
  });

  // ─── Prompt construction ───────────────────────────────────────────────────

  it("user prompt contains task description", async () => {
    await contextGatherStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("fix the login bug in auth module");
  });

  it("user prompt contains workspace path", async () => {
    await contextGatherStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("/workspace/test-repo");
  });

  it("includes AGENTS.md content in prompt when file is available", async () => {
    // First readFile call is loadSkill() — let it fail so it uses DEFAULT_SYSTEM_PROMPT.
    // Second readFile call is AGENTS.md — resolve with content.
    mockReadFile.mockRejectedValueOnce(new Error("ENOENT"));
    mockReadFile.mockResolvedValueOnce("# Agent Rules\n- Always test before commit");
    await contextGatherStep(makeCtx());
    const [, userPrompt] = mockRunPrompt.mock.calls[0] as [unknown, string];
    expect(userPrompt).toContain("# Agent Rules");
  });

  it("proceeds without AGENTS.md when file is absent", async () => {
    mockReadFile.mockRejectedValueOnce(new Error("ENOENT"));
    const result = await contextGatherStep(makeCtx());
    expect(result.status).toBe("passed");
  });

  // ─── Output parsing ────────────────────────────────────────────────────────

  it("parses relevant file paths from LLM response", async () => {
    const result = await contextGatherStep(makeCtx());
    const relevantFiles = result.data?.relevantFiles as string[];
    expect(relevantFiles).toContain("src/auth/login.ts");
    expect(relevantFiles).toContain("src/auth/user.ts");
    expect(relevantFiles).toContain("tests/auth/login.test.ts");
  });

  it("sets ctx.relevantFiles from parsed LLM output", async () => {
    const ctx = makeCtx();
    await contextGatherStep(ctx);
    expect(ctx.relevantFiles).toContain("src/auth/login.ts");
    expect(ctx.relevantFiles).toContain("src/auth/user.ts");
  });

  it("sets ctx.understanding to the LLM response", async () => {
    const ctx = makeCtx();
    await contextGatherStep(ctx);
    expect(ctx.understanding).toBe(LLM_RESPONSE_WITH_FILES);
  });

  // ─── Token usage ───────────────────────────────────────────────────────────

  it("returns tokensUsed from getTokensUsed", async () => {
    const result = await contextGatherStep(makeCtx());
    expect(result.tokensUsed).toBe(1500);
  });

  // ─── Result data ───────────────────────────────────────────────────────────

  it("includes relevantFiles in result data", async () => {
    const result = await contextGatherStep(makeCtx());
    expect(result.data?.relevantFiles).toBeDefined();
    expect(Array.isArray(result.data?.relevantFiles)).toBe(true);
  });

  it("includes understanding in result data", async () => {
    const result = await contextGatherStep(makeCtx());
    expect(result.data?.understanding).toBe(LLM_RESPONSE_WITH_FILES);
  });

  // ─── Context-tools extension (T046) ───────────────────────────────────────

  it("creates context-tools extension with workspacePath", async () => {
    await contextGatherStep(makeCtx());
    expect(mockCreateContextToolsExtension).toHaveBeenCalledWith(
      expect.objectContaining({ workspacePath: "/workspace/test-repo" }),
    );
  });

  it("creates context-tools extension with default index path under workspacePath", async () => {
    await contextGatherStep(makeCtx());
    expect(mockCreateContextToolsExtension).toHaveBeenCalledWith(
      expect.objectContaining({ embeddingsIndexPath: "/workspace/test-repo/.index" }),
    );
  });

  it("uses extensions.contextTools as embeddingsIndexPath when configured", async () => {
    const ctx = makeCtx();
    ctx.config.extensions = { contextTools: "/custom/index/path" };
    await contextGatherStep(ctx);
    expect(mockCreateContextToolsExtension).toHaveBeenCalledWith(
      expect.objectContaining({ embeddingsIndexPath: "/custom/index/path" }),
    );
  });

  it("passes embeddingModel from ctx.config.context to the extension", async () => {
    const ctx = makeCtx();
    ctx.config.context = { ...ctx.config.context, embeddingModel: "Xenova/all-MiniLM-L6-v2" };
    await contextGatherStep(ctx);
    expect(mockCreateContextToolsExtension).toHaveBeenCalledWith(
      expect.objectContaining({ embeddingModel: "Xenova/all-MiniLM-L6-v2" }),
    );
  });

  it("creates session with customTools from context-tools extension", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ customTools: unknown[] }];
    expect(sessionConfig.customTools).toEqual(FAKE_TOOL_DEFINITIONS);
  });

  it("system prompt mentions repo_map tool", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ systemPrompt: string }];
    expect(sessionConfig.systemPrompt).toContain("repo_map");
  });

  it("system prompt mentions semantic_search tool", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ systemPrompt: string }];
    expect(sessionConfig.systemPrompt).toContain("semantic_search");
  });

  it("system prompt mentions symbol_nav tool", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ systemPrompt: string }];
    expect(sessionConfig.systemPrompt).toContain("symbol_nav");
  });

  it("system prompt mentions dependency_graph tool", async () => {
    await contextGatherStep(makeCtx());
    const [sessionConfig] = mockCreateSession.mock.calls[0] as [{ systemPrompt: string }];
    expect(sessionConfig.systemPrompt).toContain("dependency_graph");
  });
});
