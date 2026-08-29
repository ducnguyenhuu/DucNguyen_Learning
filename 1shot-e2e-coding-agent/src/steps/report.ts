/**
 * src/steps/report.ts — Report step (FR-014)
 *
 * Summarises the completed run to the console and writes machine-readable
 * artifacts to the run artifacts directory (when outputDir is provided):
 *  - report.json  — full run report with all metrics
 *  - metrics.json — token usage, cost, and timing snapshot
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { RunContext, StepResult, TestResult } from "../types.js";

// ─── File helpers ──────────────────────────────────────────────────────────────

async function saveArtifacts(
  outputDir: string,
  ctx: RunContext,
  accumulatedData: Record<string, unknown>,
  totalTokens: number,
): Promise<void> {
  await mkdir(outputDir, { recursive: true });

  const report = {
    task: ctx.task.description,
    branch: ctx.branch,
    status: "succeeded",
    totalTokens,
    prUrl: accumulatedData.prUrl ?? null,
    testResults: accumulatedData.testResult ?? null,
    lintClean: accumulatedData.lintClean ?? null,
    filesChanged: accumulatedData.filesChanged ?? [],
    durationMs: accumulatedData.durationMs ?? null,
  };

  const metrics = {
    totalTokens,
    estimatedCostUsd: accumulatedData.estimatedCostUsd ?? null,
    durationMs: accumulatedData.durationMs ?? null,
    prUrl: accumulatedData.prUrl ?? null,
  };

  await Promise.all([
    writeFile(join(outputDir, "report.json"), JSON.stringify(report, null, 2), "utf-8"),
    writeFile(join(outputDir, "metrics.json"), JSON.stringify(metrics, null, 2), "utf-8"),
  ]);
}

// ─── Step ─────────────────────────────────────────────────────────────────────

export async function reportStep(
  ctx: RunContext,
  accumulatedData?: Record<string, unknown>,
): Promise<StepResult> {
  const { task, branch, tokenBudget } = ctx;
  const totalTokens = tokenBudget.consumed;
  const data = accumulatedData ?? {};

  console.log("=== 1-Shot Coding Agent — Run Report ===");
  console.log(`Task   : ${task.description}`);
  console.log(`Branch : ${branch}`);
  console.log(`Tokens : ${totalTokens.toLocaleString()}`);

  if (data.testResult) {
    const tr = data.testResult as TestResult;
    console.log(`Tests  : ${tr.passed} passed, ${tr.failed} failed, ${tr.skipped} skipped (${tr.duration}ms)`);
  }

  if (data.prUrl) {
    console.log(`PR     : ${data.prUrl}`);
  }

  // Save machine-readable artifacts when an output directory is provided
  if (typeof data.outputDir === "string" && data.outputDir.length > 0) {
    await saveArtifacts(data.outputDir, ctx, data, totalTokens);
  }

  return {
    status: "passed",
    data: { totalTokens, branch, ...(data.prUrl ? { prUrl: data.prUrl } : {}) },
  };
}

