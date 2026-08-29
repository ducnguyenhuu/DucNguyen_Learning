/**
 * src/steps/lint-format.ts — Lint & Format step (FR-006)
 *
 * Fifth node in the standard blueprint. Responsible for:
 *  1. Running the configured lintCommand in the workspace
 *  2. Optionally running formatCommand (auto-fix) if configured
 *  3. Returning passed/failed/error based on lintCommand exit code
 *
 * The format step is advisory — its exit code does not affect the overall status.
 * The lint exit code drives the result:
 *   exitCode 0  → passed
 *   exitCode >0 → failed
 *   spawn error → error
 *
 * Returns a StepResult with:
 *  - data.lintOutput  — combined stdout + stderr from lintCommand
 *  - data.autoFixed   — true if formatCommand was run
 */

import { runCommand } from "../utils/run-command.js";
import type { RunContext, StepResult } from "../types.js";

export async function lintFormatStep(ctx: RunContext): Promise<StepResult> {
  const { lintCommand, formatCommand } = ctx.config.repo;
  const cwd = ctx.workspacePath;

  // ── 1. Run lint command ────────────────────────────────────────────────────
  let lintOutput: string;
  let lintExitCode: number;

  try {
    const result = await runCommand(lintCommand, cwd);
    lintExitCode = result.exitCode;
    // Merge stdout + stderr into one output string
    lintOutput = [result.stdout, result.stderr].filter(Boolean).join("\n");
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 2. Run format command (advisory — non-fatal) ───────────────────────────
  let autoFixed = false;
  if (formatCommand) {
    try {
      await runCommand(formatCommand, cwd);
    } catch {
      // Format failure is non-fatal
    }
    autoFixed = true;
  }

  // ── 3. Return result based on lint exit code ───────────────────────────────
  const status = lintExitCode === 0 ? "passed" : "failed";

  return {
    status,
    data: {
      lintOutput,
      autoFixed,
    },
  };
}
