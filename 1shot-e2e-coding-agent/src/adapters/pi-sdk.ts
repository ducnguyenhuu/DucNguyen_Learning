/**
 * src/adapters/pi-sdk.ts — Pi SDK adapter layer (Architecture Decision D2)
 *
 * All Pi SDK interactions go through this file.
 * No other module imports from @mariozechner/pi-coding-agent directly.
 *
 * Why: Pi SDK is pre-v1.0. If its API changes, only this file needs updating.
 *
 * Exports:
 *  - createSession(config, options?)  — creates an AgentSession from our SessionConfig
 *  - runPrompt(handle, text)          — sends a prompt, returns the assistant's response text
 *  - getTokensUsed(handle)            — returns cumulative token count for the session
 *
 * The returned SessionHandle is an opaque object — callers should not access .session directly
 * beyond what the adapter exports.
 */

import {
  createAgentSession,
  SessionManager,
  readTool,
  grepTool,
  findTool,
  lsTool,
  bashTool,
  editTool,
  writeTool,
  type CreateAgentSessionOptions,
} from "@mariozechner/pi-coding-agent";
import { getModel } from "@mariozechner/pi-ai";
import type { AgentSession } from "@mariozechner/pi-coding-agent";
import type { SessionConfig, Provider } from "../types.js";

// ─── Tool name → Tool object mapping ─────────────────────────────────────────

/** Maps Pi SDK built-in tool names to their tool objects. */
const TOOL_MAP: Record<string, unknown> = {
  read: readTool,
  grep: grepTool,
  find: findTool,
  ls: lsTool,
  bash: bashTool,
  edit: editTool,
  write: writeTool,
};

function resolveTools(names: string[]): unknown[] {
  return names
    .map((name) => TOOL_MAP[name])
    .filter((t): t is NonNullable<typeof t> => t !== undefined);
}

// ─── Model resolution ─────────────────────────────────────────────────────────

const ANTHROPIC_DEFAULT = "claude-sonnet-4-20250514";
const OPENAI_DEFAULT = "gpt-4.1";

function resolveModel(provider: Provider, modelName: string) {
  try {
    if (provider === "anthropic") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return getModel("anthropic", modelName as any);
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return getModel("openai", modelName as any);
  } catch {
    // Fall back to safe defaults if the model name isn't in the registry
    if (provider === "anthropic") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return getModel("anthropic", ANTHROPIC_DEFAULT as any);
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return getModel("openai", OPENAI_DEFAULT as any);
  }
}

// ─── SessionHandle (opaque) ───────────────────────────────────────────────────

/**
 * Opaque handle returned by createSession().
 * Callers must use the adapter functions — they should not call session methods directly.
 */
export interface SessionHandle {
  /** Exposed for advanced use (e.g. attaching event listeners in step implementations). */
  readonly session: AgentSession;
}

// ─── createSession ────────────────────────────────────────────────────────────

export interface CreateSessionOptions {
  /** Working directory for project-local Pi SDK discovery. Default: process.cwd() */
  cwd?: string;
}

/**
 * Create a Pi AgentSession from our SessionConfig.
 *
 * Uses an in-memory SessionManager (no session files written to disk).
 * The session starts fresh on every call — no state is reused across runs.
 */
export async function createSession(
  config: SessionConfig,
  options?: CreateSessionOptions,
): Promise<SessionHandle> {
  const cwd = options?.cwd ?? process.cwd();
  const tools = resolveTools(config.tools);
  const model = resolveModel(config.provider, config.model);

  const sdkOptions: CreateAgentSessionOptions = {
    cwd,
    sessionManager: SessionManager.inMemory(cwd),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    model: model as any,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tools: tools as any,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...(config.customTools?.length ? { customTools: config.customTools as any } : {}),
  };

  const { session } = await createAgentSession(sdkOptions);

  return { session };
}

// ─── runPrompt ────────────────────────────────────────────────────────────────

/**
 * Send a prompt to the agent and return the assistant's response text.
 *
 * `session.prompt()` returns Promise<void> — the response is retrieved via
 * `session.getLastAssistantText()` after the promise resolves.
 *
 * Returns an empty string if the session produced no text output.
 */
export async function runPrompt(
  handle: SessionHandle,
  text: string,
): Promise<string> {
  await handle.session.prompt(text);
  return handle.session.getLastAssistantText() ?? "";
}

// ─── getTokensUsed ────────────────────────────────────────────────────────────

/**
 * Return the cumulative token count for this session.
 * Reads from session.getSessionStats().tokens.total.
 * Returns 0 if stats are unavailable (e.g. session not yet started).
 */
export function getTokensUsed(handle: SessionHandle): number {
  try {
    return handle.session.getSessionStats()?.tokens.total ?? 0;
  } catch {
    return 0;
  }
}
