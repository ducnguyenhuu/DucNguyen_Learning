/**
 * Unit tests for the Pi SDK adapter — tests/unit/adapters/pi-sdk.test.ts
 *
 * These tests define the CONTRACT for src/adapters/pi-sdk.ts.
 * Written TDD-first — will fail until T009 creates the implementation.
 *
 * The adapter wraps three Pi SDK operations:
 *  1. createAgentSession()  → our createSession()
 *  2. session.prompt()      → our runPrompt()
 *  3. session.getSessionStats().tokens.total  → our getTokensUsed()
 *
 * @mariozechner/pi-coding-agent is mocked entirely — no real LLM calls.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SessionConfig } from "../../../src/types.js";

// ─── Mock Pi SDK ──────────────────────────────────────────────────────────────
// We mock the entire module so tests never touch the real Pi SDK.

const mockPrompt = vi.fn<[string], Promise<void>>();
const mockGetLastAssistantText = vi.fn<[], string | undefined>();
const mockGetSessionStats = vi.fn();
const mockSubscribe = vi.fn(() => () => {}); // returns unsubscribe noop

const mockSession = {
  prompt: mockPrompt,
  getLastAssistantText: mockGetLastAssistantText,
  getSessionStats: mockGetSessionStats,
  subscribe: mockSubscribe,
};

const mockCreateAgentSession = vi.fn();

vi.mock("@mariozechner/pi-coding-agent", () => ({
  createAgentSession: mockCreateAgentSession,
  SessionManager: { inMemory: vi.fn(() => ({})) },
  readTool: { name: "read" },
  grepTool: { name: "grep" },
  findTool: { name: "find" },
  lsTool: { name: "ls" },
  bashTool: { name: "bash" },
  editTool: { name: "edit" },
  writeTool: { name: "write" },
  readOnlyTools: [{ name: "read" }],
  codingTools: [{ name: "read" }, { name: "bash" }, { name: "edit" }, { name: "write" }],
  createReadOnlyTools: vi.fn(() => [{ name: "read" }]),
  createCodingTools: vi.fn(() => [{ name: "read" }, { name: "bash" }]),
}));

vi.mock("@mariozechner/pi-ai", () => ({
  getModel: vi.fn(() => ({ id: "claude-sonnet-4-20250514", provider: "anthropic" })),
}));

// Import adapter AFTER mock is set up
const { createSession, runPrompt, getTokensUsed } = await import(
  "../../../src/adapters/pi-sdk.js"
);

// ─── Shared test config ───────────────────────────────────────────────────────

const baseConfig: SessionConfig = {
  systemPrompt: "You are a coding agent.",
  tools: ["read", "grep", "find", "ls"],
  extensions: [],
  provider: "anthropic",
  model: "claude-sonnet-4-20250514",
};

// ─── createSession() ──────────────────────────────────────────────────────────

describe("createSession()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateAgentSession.mockResolvedValue({
      session: mockSession,
      extensionsResult: { extensions: [] },
    });
  });

  it("calls createAgentSession from Pi SDK", async () => {
    await createSession(baseConfig);
    expect(mockCreateAgentSession).toHaveBeenCalledOnce();
  });

  it("returns a handle containing the Pi SDK session", async () => {
    const handle = await createSession(baseConfig);
    expect(handle).toBeDefined();
    expect(handle.session).toBe(mockSession);
  });

  it("passes cwd option when provided", async () => {
    await createSession(baseConfig, { cwd: "/workspace" });
    expect(mockCreateAgentSession).toHaveBeenCalledWith(
      expect.objectContaining({ cwd: "/workspace" }),
    );
  });

  it("throws when createAgentSession rejects", async () => {
    mockCreateAgentSession.mockRejectedValue(new Error("no credentials"));
    await expect(createSession(baseConfig)).rejects.toThrow(/no credentials/);
  });
});

// ─── runPrompt() ─────────────────────────────────────────────────────────────

describe("runPrompt()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateAgentSession.mockResolvedValue({
      session: mockSession,
      extensionsResult: { extensions: [] },
    });
    mockPrompt.mockResolvedValue(undefined);
  });

  it("calls session.prompt() with the provided text", async () => {
    const handle = await createSession(baseConfig);
    mockGetLastAssistantText.mockReturnValue("I have implemented the feature.");

    await runPrompt(handle, "Implement the feature");

    expect(mockPrompt).toHaveBeenCalledOnce();
    expect(mockPrompt).toHaveBeenCalledWith("Implement the feature");
  });

  it("returns the assistant response text after the prompt resolves", async () => {
    const handle = await createSession(baseConfig);
    mockGetLastAssistantText.mockReturnValue("Done! I created the file.");

    const response = await runPrompt(handle, "Create the file");

    expect(response).toBe("Done! I created the file.");
  });

  it("returns an empty string when getLastAssistantText() returns undefined", async () => {
    const handle = await createSession(baseConfig);
    mockGetLastAssistantText.mockReturnValue(undefined);

    const response = await runPrompt(handle, "Do something");

    expect(response).toBe("");
  });

  it("awaits session.prompt() before reading the response", async () => {
    const handle = await createSession(baseConfig);
    const callOrder: string[] = [];

    mockPrompt.mockImplementation(async () => {
      callOrder.push("prompt");
    });
    mockGetLastAssistantText.mockImplementation(() => {
      callOrder.push("getLastAssistantText");
      return "response";
    });

    await runPrompt(handle, "some task");

    expect(callOrder).toEqual(["prompt", "getLastAssistantText"]);
  });

  it("propagates errors thrown by session.prompt()", async () => {
    const handle = await createSession(baseConfig);
    mockPrompt.mockRejectedValue(new Error("LLM API timeout"));

    await expect(runPrompt(handle, "task")).rejects.toThrow(/LLM API timeout/);
  });
});

// ─── getTokensUsed() ─────────────────────────────────────────────────────────

describe("getTokensUsed()", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateAgentSession.mockResolvedValue({
      session: mockSession,
      extensionsResult: { extensions: [] },
    });
  });

  it("returns the total token count from session stats", async () => {
    const handle = await createSession(baseConfig);
    mockGetSessionStats.mockReturnValue({
      tokens: { input: 500, output: 200, cacheRead: 0, cacheWrite: 0, total: 700 },
      cost: 0.02,
    });

    expect(getTokensUsed(handle)).toBe(700);
  });

  it("returns 0 when session stats are not available", async () => {
    const handle = await createSession(baseConfig);
    mockGetSessionStats.mockReturnValue(undefined);

    expect(getTokensUsed(handle)).toBe(0);
  });

  it("returns 0 when getSessionStats throws", async () => {
    const handle = await createSession(baseConfig);
    mockGetSessionStats.mockImplementation(() => {
      throw new Error("stats unavailable");
    });

    expect(getTokensUsed(handle)).toBe(0);
  });

  it("reflects updated token count after multiple prompts", async () => {
    const handle = await createSession(baseConfig);

    mockGetSessionStats.mockReturnValueOnce({
      tokens: { input: 100, output: 50, cacheRead: 0, cacheWrite: 0, total: 150 },
    });
    expect(getTokensUsed(handle)).toBe(150);

    mockGetSessionStats.mockReturnValueOnce({
      tokens: { input: 300, output: 150, cacheRead: 0, cacheWrite: 0, total: 450 },
    });
    expect(getTokensUsed(handle)).toBe(450);
  });
});
