/**
 * src/reporting/run-report.ts — Run report generation (FR-014)
 *
 * Aggregates node results, file changes, and test outcomes into a structured
 * RunReport that can be serialised to report.json (data-model.md Entity 9).
 *
 * Implementation task: T062
 */

import type { Run, RunReport, FileChange, TestResult } from "../types.js";

/**
 * Generate a RunReport from a completed Run plus the additional metrics that
 * are accumulated during execution (file diffs, test results, lint status, PR URL).
 *
 * @param run          - The completed Run object.
 * @param filesChanged - Git diff breakdown per file.
 * @param testResults  - Aggregated test pass/fail counts.
 * @param lintClean    - Whether the lint step passed without errors.
 * @param prUrl        - GitHub PR URL (null if the run failed before creating a PR).
 */
export function generateRunReport(
  run: Run,
  filesChanged: FileChange[],
  testResults: TestResult,
  lintClean: boolean,
  prUrl: string | null = null,
): RunReport {
  const linesAdded = filesChanged.reduce((sum, f) => sum + f.linesAdded, 0);
  const linesRemoved = filesChanged.reduce((sum, f) => sum + f.linesRemoved, 0);

  const durationMs =
    run.completedAt != null
      ? run.completedAt.getTime() - run.startedAt.getTime()
      : 0;
  const durationSeconds = Math.floor(durationMs / 1000);

  return {
    runId: run.id,
    status: run.status,
    task: run.task.description,
    branch: run.branch,
    prUrl,
    filesChanged,
    linesAdded,
    linesRemoved,
    testResults,
    lintClean,
    totalTokens: run.totalTokens,
    estimatedCostUsd: run.totalCostUsd,
    durationSeconds,
    nodeResults: run.nodes,
  };
}
