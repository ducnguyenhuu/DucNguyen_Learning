/**
 * src/runner.ts — Agent run orchestrator
 *
 * Wires together config loading, RunContext construction, and standard blueprint execution.
 * The CLI calls `runAgent(task, opts)` — this module is the glue between the CLI and the
 * BlueprintRunner + standard blueprint.
 */

import { resolve } from "node:path";
import pino from "pino";
import type { CliOptions } from "./cli.js";
import { loadConfig, mergeCliOverrides } from "./config.js";
import { createStandardBlueprint } from "./blueprints/standard.js";
import { createTaskSlug, createLayerBudgets } from "./types.js";
import type { RunContext } from "./types.js";

export interface RunResult {
  status: "succeeded" | "failed" | "error" | "timeout";
  error?: string;
}

/**
 * Execute a full agent run for the given task description.
 * Loads config, builds RunContext, runs the standard blueprint.
 *
 * @param task  Plain-text task description
 * @param opts  Parsed CLI options (overrides for config values)
 */
export async function runAgent(task: string, opts: CliOptions): Promise<RunResult> {
  // ── 1. Load + merge config ─────────────────────────────────────────────────
  let config = await loadConfig(opts.config);
  config = mergeCliOverrides(config, {
    provider: opts.provider,
    model: opts.model,
    maxTokens: opts.maxTokens,
    maxRetries: opts.maxRetries,
    timeout: opts.timeout,
  });

  // ── 2. Build logger ────────────────────────────────────────────────────────
  const logger = pino(
    { level: opts.verbose ? "debug" : "info" },
    pino.destination({ sync: false }),
  );

  // ── 3. Resolve workspace path ──────────────────────────────────────────────
  // config.repo.path is typically "/workspace" (Docker) but can be overridden.
  // When running locally (not in Docker), fall back to process.cwd().
  const workspacePath = resolve(
    config.repo.path !== "/workspace" ? config.repo.path : process.cwd(),
  );

  // ── 4. Build RunContext ────────────────────────────────────────────────────
  const maxTokens = config.agent.maxTokensPerRun;
  const ctx: RunContext = {
    task: {
      description: task,
      slug: createTaskSlug(task),
      timestamp: new Date().toISOString(),
    },
    config,
    workspacePath,
    branch: "",          // populated by setup node
    repoMap: "",         // populated by setup node
    relevantFiles: [],   // populated by context_gather node
    understanding: "",   // populated by context_gather node
    plan: "",            // populated by plan node
    retryCount: 0,
    errorHashes: [],
    tokenBudget: {
      maxTokens,
      consumed: 0,
      remaining: maxTokens,
      layerBudgets: createLayerBudgets(maxTokens),
    },
    logger,
    dryRun: opts.dryRun,
  };

  // ── 5. Run standard blueprint ──────────────────────────────────────────────
  const runner = createStandardBlueprint(ctx);
  const summary = await runner.run(ctx);

  return {
    status: summary.status === "succeeded" ? "succeeded" : "failed",
    error: summary.error,
  };
}
