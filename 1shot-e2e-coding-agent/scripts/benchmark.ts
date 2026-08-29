#!/usr/bin/env node
/**
 * scripts/benchmark.ts — Agent benchmark harness (T076)
 *
 * Validates success-criteria metrics from spec.md:
 *  SC-001  Task completable in under 5 minutes
 *  SC-002  80%+ partial success rate (passing test suite)
 *  SC-005  Cost < $2.00 per run
 *  SC-009  ≥50% one-shot success rate (no retries)
 *  SC-010  ≥80% partial success rate (code compiles, most tests pass)
 *  SC-011  < 200K tokens per run
 *  SC-012  Average run < 10 minutes
 *  SC-013  Retry rate < 30%
 *
 * Usage:
 *   npx tsx scripts/benchmark.ts [--report-dir <dir>] [--dry-run]
 *
 * In --dry-run mode the agent is NOT invoked; synthetic results are used so
 * the script can be validated without LLM API credentials.
 *
 * Output:
 *   - Console table of per-task results
 *   - Summary table of SC metrics (PASS / FAIL)
 *   - benchmark-results.json written to --report-dir (default: ./runs/benchmark/)
 */

import { parseArgs } from "node:util";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";

// ─── Benchmark task definitions ───────────────────────────────────────────────

/**
 * Representative tasks covering typical 1-3 file changes.
 * In a live run these would be handed to runAgent().
 * Difficulty ratings guide expected complexity:
 *   easy   — single-file, pure logic change
 *   medium — 2-3 files, needs context-gather
 *   hard   — cross-cutting, multi-file, may need retries
 */
interface BenchmarkTask {
  id: string;
  description: string;
  difficulty: "easy" | "medium" | "hard";
  expectedFiles: number;
}

const BENCHMARK_TASKS: BenchmarkTask[] = [
  {
    id: "BT-001",
    description: "Add input validation to the createUser endpoint — reject empty name and invalid email",
    difficulty: "easy",
    expectedFiles: 1,
  },
  {
    id: "BT-002",
    description: "Fix off-by-one error in the pagination helper — last page returns one extra item",
    difficulty: "easy",
    expectedFiles: 1,
  },
  {
    id: "BT-003",
    description: "Add a unit test for the formatCurrency utility covering negative values and zero",
    difficulty: "easy",
    expectedFiles: 1,
  },
  {
    id: "BT-004",
    description: "Rename the internal config field 'max_retries' to 'maxRetries' across the codebase",
    difficulty: "medium",
    expectedFiles: 2,
  },
  {
    id: "BT-005",
    description: "Add request logging middleware that captures method, path, status code, and latency",
    difficulty: "medium",
    expectedFiles: 2,
  },
  {
    id: "BT-006",
    description: "Add TypeScript type annotations to the three untyped utility functions in utils/strings.ts",
    difficulty: "easy",
    expectedFiles: 1,
  },
  {
    id: "BT-007",
    description: "Implement rate limiting on the /api/search endpoint using an in-memory token bucket",
    difficulty: "medium",
    expectedFiles: 3,
  },
  {
    id: "BT-008",
    description: "Fix the broken integration test in tests/api/auth.test.ts — mock the external OAuth call",
    difficulty: "medium",
    expectedFiles: 2,
  },
  {
    id: "BT-009",
    description: "Extract duplicate database connection setup into a shared helper and update all callers",
    difficulty: "hard",
    expectedFiles: 3,
  },
  {
    id: "BT-010",
    description: "Add health-check endpoint /api/health that returns version, uptime, and DB connectivity",
    difficulty: "medium",
    expectedFiles: 2,
  },
];

// ─── Result types ─────────────────────────────────────────────────────────────

interface TaskResult {
  taskId: string;
  description: string;
  difficulty: "easy" | "medium" | "hard";
  status: "succeeded" | "failed" | "partial";
  /** Did it succeed on the first attempt with no fix-failures retries? */
  oneShot: boolean;
  /** Number of fix-failures cycles used. */
  retryCount: number;
  /** Tokens consumed (all nodes combined). */
  tokensUsed: number;
  /** Estimated cost in USD. */
  estimatedCostUsd: number;
  /** Wall-clock duration in seconds. */
  durationSeconds: number;
  /** Whether lint passed. */
  lintClean: boolean;
  /** Whether all tests passed. */
  testsPass: boolean;
}

interface BenchmarkSummary {
  totalTasks: number;
  succeededCount: number;
  oneShotCount: number;
  retryCount: number;
  avgTokensUsed: number;
  avgCostUsd: number;
  avgDurationSeconds: number;
  maxDurationSeconds: number;
  successRate: number;
  oneShotRate: number;
  retryRate: number;
}

interface SCMetric {
  id: string;
  description: string;
  threshold: string;
  measured: string;
  pass: boolean;
}

interface BenchmarkReport {
  runAt: string;
  dryRun: boolean;
  tasks: TaskResult[];
  summary: BenchmarkSummary;
  metrics: SCMetric[];
}

// ─── Synthetic result generator (dry-run mode) ───────────────────────────────

/**
 * Generate realistic synthetic results that model expected agent performance.
 * Used when --dry-run is set so the script runs without LLM API credentials.
 *
 * Models:
 *  - 80% overall success rate
 *  - 55% one-shot rate (no retries)
 *  - Hard tasks more likely to need retries
 *  - Token usage 40-120K depending on difficulty
 *  - Cost $0.40-$1.60 (well under $2 threshold)
 *  - Duration 90-280s (well under 5-minute threshold)
 */
function syntheticResult(task: BenchmarkTask): TaskResult {
  // Deterministic pseudo-random via task ID hash so results are reproducible
  const seed = task.id.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const rand = (min: number, max: number): number =>
    min + ((seed * 1103515245 + 12345) & 0x7fffffff) % (max - min + 1);

  const failChance = task.difficulty === "hard" ? 20 : task.difficulty === "medium" ? 10 : 5;
  const succeeded = rand(0, 99) >= failChance;
  const needsRetry = !succeeded || (rand(0, 99) < (task.difficulty === "hard" ? 40 : task.difficulty === "medium" ? 20 : 10));
  const retryCount = needsRetry ? rand(1, task.difficulty === "hard" ? 2 : 1) : 0;
  const oneShot = succeeded && retryCount === 0;

  const baseTokens = task.difficulty === "easy" ? 45_000 : task.difficulty === "medium" ? 75_000 : 110_000;
  const tokensUsed = baseTokens + rand(0, 20_000) + retryCount * 15_000;

  // Cost model: anthropic claude-sonnet ~$3/MTok input + $15/MTok output ≈ avg $4/MTok blended
  const estimatedCostUsd = Math.round(tokensUsed * 0.000004 * 100) / 100;

  const baseDuration = task.difficulty === "easy" ? 90 : task.difficulty === "medium" ? 150 : 220;
  const durationSeconds = baseDuration + rand(0, 60) + retryCount * 45;

  return {
    taskId: task.id,
    description: task.description,
    difficulty: task.difficulty,
    status: succeeded ? "succeeded" : (rand(0, 99) < 60 ? "partial" : "failed"),
    oneShot,
    retryCount,
    tokensUsed,
    estimatedCostUsd,
    durationSeconds,
    lintClean: succeeded || rand(0, 99) < 80,
    testsPass: succeeded || rand(0, 99) < 60,
  };
}

// ─── Live agent runner (real mode) ────────────────────────────────────────────

/**
 * Run a single benchmark task against the real agent.
 * Requires ANTHROPIC_API_KEY or OPENAI_API_KEY in environment.
 *
 * NOTE: runAgent() is a stub (T033 not wired yet) — calling this will throw.
 * Use --dry-run for offline benchmarking.
 */
async function liveResult(task: BenchmarkTask, configPath: string): Promise<TaskResult> {
  const { createProgram } = await import("../src/cli.js");
  const start = Date.now();

  let status: TaskResult["status"] = "failed";
  let retryCount = 0;

  try {
    // Parse as if user ran: duc-e2e-agent run "<task>" --config <path>
    await createProgram().parseAsync([
      "node", "duc-e2e-agent",
      "run", task.description,
      "--config", configPath,
      "--output-dir", `./runs/benchmark/${task.id}/`,
    ]);
    status = "succeeded";
  } catch {
    status = "failed";
  }

  const durationSeconds = Math.round((Date.now() - start) / 1000);

  return {
    taskId: task.id,
    description: task.description,
    difficulty: task.difficulty,
    status,
    oneShot: status === "succeeded" && retryCount === 0,
    retryCount,
    tokensUsed: 0,       // would be read from report.json artifacts in T033
    estimatedCostUsd: 0,
    durationSeconds,
    lintClean: status === "succeeded",
    testsPass: status === "succeeded",
  };
}

// ─── SC metric evaluators ─────────────────────────────────────────────────────

function evaluateMetrics(results: TaskResult[], summary: BenchmarkSummary): SCMetric[] {
  const maxTokens = Math.max(...results.map((r) => r.tokensUsed));
  const maxCost = Math.max(...results.map((r) => r.estimatedCostUsd));
  const maxDuration = summary.maxDurationSeconds;

  return [
    {
      id: "SC-001",
      description: "Task completable in under 5 minutes",
      threshold: "max duration < 300s",
      measured: `${maxDuration}s`,
      pass: maxDuration < 300,
    },
    {
      id: "SC-002",
      description: "Code passes existing test suite ≥80% of the time",
      threshold: "testsPass rate ≥ 80%",
      measured: `${Math.round(results.filter((r) => r.testsPass).length / results.length * 100)}%`,
      pass: results.filter((r) => r.testsPass).length / results.length >= 0.8,
    },
    {
      id: "SC-005",
      description: "Cost < $2.00 per run",
      threshold: "max cost < $2.00",
      measured: `$${maxCost.toFixed(2)}`,
      pass: maxCost < 2.0,
    },
    {
      id: "SC-009",
      description: "≥50% one-shot success rate",
      threshold: "oneShot rate ≥ 50%",
      measured: `${Math.round(summary.oneShotRate * 100)}%`,
      pass: summary.oneShotRate >= 0.5,
    },
    {
      id: "SC-010",
      description: "≥80% partial success rate",
      threshold: "succeeded + partial rate ≥ 80%",
      measured: `${Math.round(summary.successRate * 100)}%`,
      pass: summary.successRate >= 0.8,
    },
    {
      id: "SC-011",
      description: "< 200K tokens per run",
      threshold: "max tokens < 200,000",
      measured: `${maxTokens.toLocaleString()}`,
      pass: maxTokens < 200_000,
    },
    {
      id: "SC-012",
      description: "Average run time < 10 minutes",
      threshold: "avg duration < 600s",
      measured: `${Math.round(summary.avgDurationSeconds)}s`,
      pass: summary.avgDurationSeconds < 600,
    },
    {
      id: "SC-013",
      description: "Retry rate < 30%",
      threshold: "retry rate < 30%",
      measured: `${Math.round(summary.retryRate * 100)}%`,
      pass: summary.retryRate < 0.3,
    },
  ];
}

// ─── Summary computation ──────────────────────────────────────────────────────

function computeSummary(results: TaskResult[]): BenchmarkSummary {
  const n = results.length;
  const succeeded = results.filter((r) => r.status === "succeeded" || r.status === "partial");
  const retried = results.filter((r) => r.retryCount > 0);

  return {
    totalTasks: n,
    succeededCount: results.filter((r) => r.status === "succeeded").length,
    oneShotCount: results.filter((r) => r.oneShot).length,
    retryCount: retried.length,
    avgTokensUsed: Math.round(results.reduce((s, r) => s + r.tokensUsed, 0) / n),
    avgCostUsd: Math.round(results.reduce((s, r) => s + r.estimatedCostUsd, 0) / n * 100) / 100,
    avgDurationSeconds: Math.round(results.reduce((s, r) => s + r.durationSeconds, 0) / n),
    maxDurationSeconds: Math.max(...results.map((r) => r.durationSeconds)),
    successRate: succeeded.length / n,
    oneShotRate: results.filter((r) => r.oneShot).length / n,
    retryRate: retried.length / n,
  };
}

// ─── Console output helpers ───────────────────────────────────────────────────

const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";

function statusColor(status: string): string {
  if (status === "succeeded") return `${GREEN}succeeded${RESET}`;
  if (status === "partial") return `${YELLOW}partial  ${RESET}`;
  return `${RED}failed   ${RESET}`;
}

function passIcon(pass: boolean): string {
  return pass ? `${GREEN}✓ PASS${RESET}` : `${RED}✗ FAIL${RESET}`;
}

function printTaskTable(results: TaskResult[]): void {
  console.log(`\n${BOLD}── Benchmark Results (per task) ──────────────────────────────────────────${RESET}`);
  console.log(
    `${"ID".padEnd(7)} ${"Diff".padEnd(7)} ${"Status".padEnd(11)} ${"1Shot".padEnd(6)} ${"Retries".padEnd(8)} ${"Tokens".padEnd(9)} ${"Cost".padEnd(7)} ${"Dur(s)"}`,
  );
  console.log("─".repeat(80));

  for (const r of results) {
    const oneShot = r.oneShot ? `${GREEN}yes${RESET}` : `${DIM}no ${RESET}`;
    console.log(
      `${r.taskId.padEnd(7)} ${r.difficulty.padEnd(7)} ${statusColor(r.status)} ${oneShot}   ${String(r.retryCount).padEnd(8)} ${r.tokensUsed.toLocaleString().padEnd(9)} $${r.estimatedCostUsd.toFixed(2).padEnd(6)} ${r.durationSeconds}s`,
    );
  }
}

function printSummaryTable(summary: BenchmarkSummary): void {
  console.log(`\n${BOLD}── Aggregate Summary ─────────────────────────────────────────────────────${RESET}`);
  const rows: [string, string][] = [
    ["Total tasks", String(summary.totalTasks)],
    ["Succeeded (full)", String(summary.succeededCount)],
    ["One-shot (no retries)", String(summary.oneShotCount)],
    ["Required retries", String(summary.retryCount)],
    ["Avg tokens / run", summary.avgTokensUsed.toLocaleString()],
    ["Avg cost / run", `$${summary.avgCostUsd.toFixed(2)}`],
    ["Avg duration", `${summary.avgDurationSeconds}s`],
    ["Max duration", `${summary.maxDurationSeconds}s`],
    ["Success rate", `${Math.round(summary.successRate * 100)}%`],
    ["One-shot rate", `${Math.round(summary.oneShotRate * 100)}%`],
    ["Retry rate", `${Math.round(summary.retryRate * 100)}%`],
  ];
  for (const [k, v] of rows) {
    console.log(`  ${k.padEnd(26)} ${v}`);
  }
}

function printMetricsTable(metrics: SCMetric[]): void {
  console.log(`\n${BOLD}── Success-Criteria Verification ─────────────────────────────────────────${RESET}`);
  console.log(`${"ID".padEnd(8)} ${"Threshold".padEnd(28)} ${"Measured".padEnd(14)} ${"Result"}`);
  console.log("─".repeat(70));
  for (const m of metrics) {
    console.log(
      `${m.id.padEnd(8)} ${m.threshold.padEnd(28)} ${m.measured.padEnd(14)} ${passIcon(m.pass)}`,
    );
  }

  const allPass = metrics.every((m) => m.pass);
  console.log();
  console.log(
    allPass
      ? `${GREEN}${BOLD}All success criteria PASS.${RESET}`
      : `${RED}${BOLD}Some success criteria FAIL — see table above.${RESET}`,
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      "report-dir": { type: "string" },
      "config": { type: "string" },
      "dry-run": { type: "boolean" },
    },
  });

  const reportDir = resolve(values["report-dir"] ?? "./runs/benchmark");
  const configPath = resolve(values["config"] ?? "./pi-agent.config.ts");
  const isDryRun = values["dry-run"] ?? false;

  console.log(`${BOLD}1-Shot Coding Agent — Benchmark${RESET}`);
  console.log(`Mode     : ${isDryRun ? `${YELLOW}dry-run (synthetic data)${RESET}` : `${GREEN}live (real agent)${RESET}`}`);
  console.log(`Config   : ${configPath}`);
  console.log(`Report   : ${reportDir}`);
  console.log(`Tasks    : ${BENCHMARK_TASKS.length}`);
  console.log();

  // ── Run tasks ───────────────────────────────────────────────────────────────
  const results: TaskResult[] = [];

  for (const task of BENCHMARK_TASKS) {
    process.stdout.write(`  ${task.id} [${task.difficulty}] ${task.description.slice(0, 55)}...`);

    const result = isDryRun
      ? syntheticResult(task)
      : await liveResult(task, configPath);

    results.push(result);

    const icon = result.status === "succeeded" ? "✓" : result.status === "partial" ? "~" : "✗";
    const color = result.status === "succeeded" ? GREEN : result.status === "partial" ? YELLOW : RED;
    console.log(` ${color}${icon}${RESET} (${result.durationSeconds}s)`);
  }

  // ── Compute metrics ─────────────────────────────────────────────────────────
  const summary = computeSummary(results);
  const metrics = evaluateMetrics(results, summary);

  // ── Console output ──────────────────────────────────────────────────────────
  printTaskTable(results);
  printSummaryTable(summary);
  printMetricsTable(metrics);

  // ── Write report ────────────────────────────────────────────────────────────
  const report: BenchmarkReport = {
    runAt: new Date().toISOString(),
    dryRun: isDryRun,
    tasks: results,
    summary,
    metrics,
  };

  await mkdir(reportDir, { recursive: true });
  const reportPath = join(reportDir, "benchmark-results.json");
  await writeFile(reportPath, JSON.stringify(report, null, 2), "utf-8");
  console.log(`\nReport written → ${reportPath}`);

  // Exit 1 if any SC metric fails
  if (!metrics.every((m) => m.pass)) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
