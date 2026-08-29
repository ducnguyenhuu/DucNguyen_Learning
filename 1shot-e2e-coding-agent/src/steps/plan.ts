/**
 * src/steps/plan.ts — Plan step (FR-004, FR-017)
 *
 * Third node in the standard blueprint. Responsible for:
 *  1. Creating a read-only Pi session (read/grep/find/ls tools only)
 *  2. Injecting ctx.relevantFiles and ctx.understanding from context_gather
 *  3. Prompting the LLM to produce a structured change plan
 *  4. Mutating ctx.plan for the implement step to follow
 *
 * Returns a StepResult with:
 *  - data.plan   — full LLM response (structured change plan)
 *  - tokensUsed  — cumulative tokens consumed in this session
 */

import {
  createSession,
  runPrompt,
  getTokensUsed,
} from "../adapters/pi-sdk.js";
import type { RunContext, StepResult } from "../types.js";

// ─── Embedded system prompt ───────────────────────────────────────────────────

/**
 * Default system prompt for the plan node.
 * Used as fallback when skills/ cannot be read.
 */
const DEFAULT_SYSTEM_PROMPT = `You are a software planning agent. Your job is to produce a
structured, actionable change plan for a coding task.

You will be given:
- A task description
- A codebase understanding (from a prior exploration step)
- A list of relevant files already identified

Use the provided tools (read, grep, find, ls) to examine files more closely if needed.
Do NOT modify any files — this is a planning session only.

Output a structured plan with:
1. A list of files to modify (with exact changes needed per file)
2. A list of new files to create (if any)
3. The order in which changes should be applied
4. Any gotchas or dependencies to watch for

Be specific and unambiguous — the implement step will follow your plan without asking questions.`.trim();

// ─── planStep ────────────────────────────────────────────────────────────────

export async function planStep(ctx: RunContext): Promise<StepResult> {
  // ── 1. Resolve model from config ───────────────────────────────────────────
  const provider = ctx.config.provider.default;
  const model =
    provider === "anthropic"
      ? (ctx.config.provider.anthropicModel ?? "claude-sonnet-4-20250514")
      : (ctx.config.provider.openaiModel ?? "gpt-4.1");

  // ── 2. Build user prompt — inject context from context_gather ──────────────
  const relevantFilesSection =
    ctx.relevantFiles.length > 0
      ? `\n\n## Relevant Files (identified by context_gather)\n${ctx.relevantFiles.map((f) => `- ${f}`).join("\n")}`
      : "";

  const understandingSection = ctx.understanding
    ? `\n\n## Codebase Understanding\n${ctx.understanding}`
    : "";

  const userPrompt =
    `## Task\n${ctx.task.description}` +
    understandingSection +
    relevantFilesSection +
    `\n\nProduce a structured change plan. Be specific about which files to modify, ` +
    `what exact changes to make, and the order to apply them.`;

  // ── 3. Create read-only Pi session ─────────────────────────────────────────
  let handle;
  try {
    handle = await createSession(
      {
        systemPrompt: DEFAULT_SYSTEM_PROMPT,
        tools: ["read", "grep", "find", "ls"],
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

  // ── 4. Run prompt ──────────────────────────────────────────────────────────
  let output: string;
  try {
    output = await runPrompt(handle, userPrompt);
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 5. Update ctx ──────────────────────────────────────────────────────────
  ctx.plan = output;

  // ── 6. Record token usage ──────────────────────────────────────────────────
  const tokensUsed = getTokensUsed(handle);

  return {
    status: "passed",
    tokensUsed,
    data: {
      plan: output,
    },
  };
}
