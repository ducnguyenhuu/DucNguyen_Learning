/**
 * src/steps/setup.ts — Setup step (FR-002, FR-016)
 *
 * The first node in the standard blueprint. Responsible for:
 *  1. Creating a git branch from branchPrefix + task.slug
 *  2. Loading AGENTS.md from the workspace root (if present)
 *  3. Setting ctx.branch so downstream nodes know which branch they're on
 *
 * Returns a StepResult with:
 *  - data.branch    — full branch name
 *  - data.agentsMd  — AGENTS.md content (empty string if absent)
 */

import { join } from "node:path";
import { access, readFile } from "node:fs/promises";
import { simpleGit } from "simple-git";
import type { RunContext, StepResult } from "../types.js";

const DEFAULT_BRANCH_PREFIX = "agent/";

export async function setupStep(ctx: RunContext): Promise<StepResult> {
  const prefix = ctx.config.git?.branchPrefix ?? DEFAULT_BRANCH_PREFIX;
  const branchName = `${prefix}${ctx.task.slug}`;

  // ── 1. Create git branch ───────────────────────────────────────────────────
  try {
    const git = simpleGit(ctx.workspacePath);
    await git.checkoutLocalBranch(branchName);
    ctx.branch = branchName;
  } catch (err) {
    return {
      status: "error",
      error: err instanceof Error ? err.message : String(err),
    };
  }

  // ── 2. Load AGENTS.md (advisory — failure is non-fatal) ───────────────────
  let agentsMd = "";
  const agentsMdPath = join(ctx.workspacePath, "AGENTS.md");
  try {
    await access(agentsMdPath);
    agentsMd = await readFile(agentsMdPath, "utf-8");
  } catch {
    // File absent or unreadable — continue with empty string
  }

  return {
    status: "passed",
    data: {
      branch: branchName,
      agentsMd,
    },
  };
}
