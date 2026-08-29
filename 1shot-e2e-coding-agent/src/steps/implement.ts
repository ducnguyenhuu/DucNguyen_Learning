/**
 * src/steps/implement.ts — Implement step (FR-005, FR-017)
 *
 * Fourth node in the standard blueprint. Responsible for:
 *  1. Creating a Pi session with FULL tool access (read/write/edit/bash/grep/find)
 *  2. Injecting ctx.plan from the plan step into the prompt
 *  3. Letting the LLM execute the plan — making actual file changes on disk
 *
 * The LLM manages its own execution order internally (not a programmatic loop).
 * It reads the plan, decides the order, calls write/edit/bash as needed, and
 * stops when it believes all changes are complete.
 *
 * Returns a StepResult with:
 *  - data.summary — full LLM response (what it did)
 *  - tokensUsed   — cumulative tokens consumed in this session
 */

import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import {
  createSession,
  runPrompt,
  getTokensUsed,
} from "../adapters/pi-sdk.js";
import type { RunContext, StepResult } from "../types.js";

// ─── Embedded system prompt ───────────────────────────────────────────────────

/**
 * Default system prompt for the implement node.
 * Used as fallback when skills/implement-feature/SKILL.md cannot be read.
 */
const DEFAULT_SYSTEM_PROMPT = `You are a software implementation agent. Your job is to execute a
structured change plan by making precise modifications to source code files.

You will be given:
- A task description
- A workspace path
- A change plan specifying exactly which files to modify and how

Use the provided tools to implement all changes in the plan:
- read / grep / find  — inspect files before editing
- write               — create new files or overwrite small files entirely
- edit                — make targeted changes to specific lines in existing files
- bash                — run commands if needed (e.g. to verify syntax)

Follow the plan precisely. Do not make changes outside the scope of the plan.
When all changes are complete, write a brief summary of what you did.`.trim();

// ─── Skill loader ───────────────────────────────────────────────────────────────

async function loadSkill(skillDir: string): Promise<string> {
  const skillPath = resolve(dirname(fileURLToPath(import.meta.url)), "../../skills", skillDir, "SKILL.md");
  try {
    return (await readFile(skillPath, "utf-8")).trim();
  } catch {
    return DEFAULT_SYSTEM_PROMPT;
  }
}

// ─── implementStep ────────────────────────────────────────────────────────────

export async function implementStep(ctx: RunContext): Promise<StepResult> {
  // ── 0. Load skill instructions ─────────────────────────────────────────────
  const systemPrompt = await loadSkill("implement-feature");

  // ── 1. Resolve model from config ───────────────────────────────────────────
  const provider = ctx.config.provider.default;
  const model =
    provider === "anthropic"
      ? (ctx.config.provider.anthropicModel ?? "claude-sonnet-4-20250514")
      : (ctx.config.provider.openaiModel ?? "gpt-4.1");

  // ── 2. Build user prompt — inject the plan ─────────────────────────────────
  const planSection = ctx.plan
    ? `\n\n## Change Plan\n${ctx.plan}`
    : "";

  const userPrompt =
    `## Task\n${ctx.task.description}\n\n` +
    `## Workspace\n${ctx.workspacePath}` +
    planSection +
    `\n\nImplement all changes described in the plan. ` +
    `Use write/edit for file changes, bash for any verification commands. ` +
    `When done, provide a brief summary of what you changed.`;

  // ── 3. Create Pi session with full tool access ─────────────────────────────
  let handle;
  try {
    handle = await createSession(
      {
        systemPrompt,
        tools: ["read", "write", "edit", "bash", "grep", "find"],
        extensions: [],
        provider,
        model,
      },
      { cwd: ctx.workspacePath },
    );
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 4. Run prompt — LLM executes the plan via tool calls ──────────────────
  let output: string;
  try {
    output = await runPrompt(handle, userPrompt);
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 5. Record token usage ──────────────────────────────────────────────────
  const tokensUsed = getTokensUsed(handle);

  return {
    status: "passed",
    tokensUsed,
    data: {
      summary: output,
    },
  };
}
