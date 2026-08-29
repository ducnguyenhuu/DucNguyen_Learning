/**
 * src/steps/fix-failures.ts — Fix Failures step (FR-008, FR-010, T051)
 *
 * Seventh node in the standard blueprint (conditional — only reached on test failure).
 * Responsible for:
 *  1. Enforcing the max-retries cap (returns failed if retryCount >= maxRetries)
 *  2. Detecting oscillation — same error hash seen before → abort with failed
 *  3. Tracking error hashes in ctx.errorHashes across retries
 *  4. Creating a Pi session with write tool access (read/write/edit/bash/grep)
 *  5. Injecting the error output (from test/lint) and ctx.plan as context
 *  6. Letting the LLM diagnose and fix the failures
 *  7. Incrementing ctx.retryCount so the blueprint can enforce the retry cap
 *
 * After this step, the blueprint routes back to the test step.
 *
 * Signature: fixFailuresStep(ctx, errorOutput) — errorOutput is the
 * combined stdout+stderr from the failed test/lint step.
 *
 * Returns a StepResult with:
 *  - data.summary — LLM's description of what it fixed
 *  - tokensUsed   — cumulative tokens consumed in this session
 */

import { createHash } from "node:crypto";
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
 * Default system prompt for the fix-failures node.
 */
const DEFAULT_SYSTEM_PROMPT = `You are a software debugging agent. Your job is to fix failing
tests or lint errors by modifying source code.

You will be given:
- The original task description
- The change plan that was already executed
- The error output from a failed test or lint run

Analyze the errors carefully. Use the tools to read relevant files and understand
what went wrong. Then apply targeted fixes.

Use read/grep to investigate, write/edit to fix files, bash to verify locally.
Focus only on fixing the reported failures — do not make unrelated changes.
When done, briefly describe what you fixed and why.`.trim();

// ─── Skill loader ───────────────────────────────────────────────────────────────

async function loadSkill(skillDir: string): Promise<string> {
  const skillPath = resolve(dirname(fileURLToPath(import.meta.url)), "../../skills", skillDir, "SKILL.md");
  try {
    return (await readFile(skillPath, "utf-8")).trim();
  } catch {
    return DEFAULT_SYSTEM_PROMPT;
  }
}

// ─── Private helpers ──────────────────────────────────────────────────────────

/** Compute a short SHA-256 hash of a string for oscillation detection. */
function hashError(errorOutput: string): string {
  return createHash("sha256").update(errorOutput).digest("hex").slice(0, 16);
}

// ─── fixFailuresStep ──────────────────────────────────────────────────────────

export async function fixFailuresStep(
  ctx: RunContext,
  errorOutput: string,
  customTools?: unknown[],
): Promise<StepResult> {
  const maxRetries = ctx.config.shiftLeft?.maxRetries ?? 2;

  // ── 0. Load skill instructions ─────────────────────────────────────────────
  const systemPrompt = await loadSkill("fix-failures");

  // ── 1. Enforce max-retries cap ─────────────────────────────────────────────
  if (ctx.retryCount >= maxRetries) {
    return {
      status: "failed",
      error: `Retry limit reached: ${ctx.retryCount}/${maxRetries} retries exhausted. Aborting fix loop.`,
    };
  }

  // ── 2. Oscillation detection ───────────────────────────────────────────────
  const errorHash = hashError(errorOutput);
  if (ctx.errorHashes.includes(errorHash)) {
    return {
      status: "failed",
      error: `Oscillation detected: the same error (hash ${errorHash}) has been seen before. ` +
        `The fix loop is not converging — aborting to prevent infinite retries.`,
    };
  }

  // ── 3. Store error hash ────────────────────────────────────────────────────
  ctx.errorHashes.push(errorHash);

  // ── 4. Resolve model from config ───────────────────────────────────────────
  const provider = ctx.config.provider.default;
  const model =
    provider === "anthropic"
      ? (ctx.config.provider.anthropicModel ?? "claude-sonnet-4-20250514")
      : (ctx.config.provider.openaiModel ?? "gpt-4.1");

  // ── 5. Build user prompt — inject error output + plan ─────────────────────
  const planSection = ctx.plan
    ? `\n\n## Original Change Plan\n${ctx.plan}`
    : "";

  const errorSection = errorOutput
    ? `\n\n## Error Output\n\`\`\`\n${errorOutput}\n\`\`\``
    : "";

  const retryNote = ctx.retryCount > 0
    ? `\n\n_(Retry ${ctx.retryCount + 1} of ${maxRetries})_`
    : "";

  const userPrompt =
    `## Task\n${ctx.task.description}` +
    planSection +
    errorSection +
    retryNote +
    `\n\nDiagnose the failures and apply targeted fixes. ` +
    `Read the failing files first, then edit only what is necessary.`;

  // ── 6. Create Pi session with write tool access ────────────────────────────
  let handle;
  try {
    handle = await createSession(
      {
        systemPrompt,
        tools: ["read", "write", "edit", "bash", "grep"],
        extensions: [],
        provider,
        model,
        ...(customTools?.length ? { customTools } : {}),
      },
      { cwd: ctx.workspacePath },
    );
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 7. Run prompt — LLM diagnoses and fixes ────────────────────────────────
  let output: string;
  try {
    output = await runPrompt(handle, userPrompt);
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 8. Increment retry count ───────────────────────────────────────────────
  ctx.retryCount += 1;

  // ── 9. Record token usage ──────────────────────────────────────────────────
  const tokensUsed = getTokensUsed(handle);

  return {
    status: "passed",
    tokensUsed,
    data: {
      summary: output,
    },
  };
}
