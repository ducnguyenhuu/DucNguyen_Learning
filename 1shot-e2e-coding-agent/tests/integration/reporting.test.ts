/**
 * tests/integration/reporting.test.ts — T067
 *
 * Integration tests for the full US5 reporting pipeline. All disk I/O, Pi SDK,
 * simple-git, and Octokit calls are mocked — the tests validate the
 * end-to-end wiring between:
 *
 *  1. generateRunReport()  — aggregates metrics into a RunReport
 *  2. saveTranscript()     — saves session messages as JSONL
 *  3. reportStep()         — writes report.json + metrics.json & logs to console
 *  4. generatePRSummary()  — builds PR title + structured markdown body
 *  5. createGitHubPR()     — posts the PR via Octokit, returns html_url
 *  6. commitPushStep()     — propagates prUrl in result.data when GITHUB_TOKEN set
 *
 * Scenarios covered:
 *  A. Full pipeline: run → run report aggregation → JSONL transcript → artifacts
 *  B. PR summary body contract: all required sections present
 *  C. PR creation: Octokit called with correct fields; prUrl returned
 *  D. Transcript: each session produces its own JSONL file
 *  E. report.json + metrics.json: correct keys and values
 *  F. Edge: no GITHUB_TOKEN → no PR created, prUrl absent from result
 *  G. Edge: completedAt = null → durationSeconds = 0, all else still works
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Run, RunContext, FileChange, TestResult, NodeResult } from "../../src/types.js";
import { DEFAULT_CONFIG } from "../../src/config.js";
import { createLayerBudgets } from "../../src/types.js";

// ─── Mocks — node:fs/promises ─────────────────────────────────────────────────

const { mkdirMock, writeFileMock, readFileMock, accessMock } = vi.hoisted(() => ({
  mkdirMock:     vi.fn().mockResolvedValue(undefined),
  writeFileMock: vi.fn().mockResolvedValue(undefined),
  readFileMock:  vi.fn().mockResolvedValue(""),
  accessMock:    vi.fn().mockResolvedValue(undefined),
}));

vi.mock("node:fs/promises", () => ({
  mkdir:     mkdirMock,
  writeFile: writeFileMock,
  readFile:  readFileMock,
  access:    accessMock,
}));

// ─── Mocks — Octokit ─────────────────────────────────────────────────────────

const { octokitCreatePR } = vi.hoisted(() => ({
  octokitCreatePR: vi.fn().mockResolvedValue({
    data: { html_url: "https://github.com/owner/repo/pull/99", number: 99 },
  }),
}));

vi.mock("@octokit/rest", () => ({
  Octokit: vi.fn().mockImplementation(() => ({
    rest: { pulls: { create: octokitCreatePR } },
  })),
}));

// ─── Mocks — simple-git (for commitPushStep PR creation path) ────────────────

const { mockGitRemote, mockGitInstance } = vi.hoisted(() => {
  const mockGitRemote  = vi.fn().mockResolvedValue("https://github.com/owner/repo.git\n");
  const mockStatus     = vi.fn().mockResolvedValue({ isClean: () => false });
  const mockAdd        = vi.fn().mockResolvedValue(undefined);
  const mockCommit     = vi.fn().mockResolvedValue({ commit: "deadbeef" });
  const mockPush       = vi.fn().mockResolvedValue(undefined);
  const mockGitInstance = {
    status: mockStatus,
    add: mockAdd,
    commit: mockCommit,
    push: mockPush,
    remote: mockGitRemote,
    checkoutLocalBranch: vi.fn().mockResolvedValue(undefined),
  };
  return { mockGitRemote, mockGitInstance };
});

vi.mock("simple-git", () => ({
  default: vi.fn(() => mockGitInstance),
  simpleGit: vi.fn(() => mockGitInstance),
}));

// ─── Suppress console output ──────────────────────────────────────────────────

vi.spyOn(console, "log").mockImplementation(() => {});

// ─── Import modules under test (after mocks are registered) ──────────────────

import { generateRunReport } from "../../src/reporting/run-report.js";
import { generatePRSummary, createGitHubPR } from "../../src/reporting/pr-summary.js";
import { saveTranscript } from "../../src/reporting/transcript.js";
import { reportStep } from "../../src/steps/report.js";
import { commitPushStep } from "../../src/steps/commit-push.js";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const START = new Date("2026-03-13T14:00:00.000Z");
const END   = new Date("2026-03-13T14:00:35.000Z");
const OUTPUT_DIR = "/agent/runs/2026-03-13T14-00-00";

const FILE_CHANGES: FileChange[] = [
  { path: "src/auth/login.ts",             action: "modified", linesAdded: 10, linesRemoved: 2 },
  { path: "tests/auth/login.test.ts",      action: "created",  linesAdded: 20, linesRemoved: 0 },
];

const TEST_RESULTS: TestResult = { passed: 8, failed: 0, skipped: 0, duration: 3200 };

const NODE_RESULTS: NodeResult[] = [
  { nodeId: "setup",     type: "deterministic", status: "passed", duration: 600,   tokensUsed: 0 },
  { nodeId: "context",   type: "agent",         status: "passed", duration: 9000,  tokensUsed: 4500 },
  { nodeId: "implement", type: "agent",         status: "passed", duration: 18000, tokensUsed: 9000 },
];

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "2026-03-13T14-00-00",
    task: {
      description: "Fix login validation bug",
      slug: "fix-login-validation-bug",
      timestamp: "2026-03-13T14:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
      git: { ...DEFAULT_CONFIG.git, baseBranch: "main" },
    },
    status: "succeeded",
    branch: "agent/fix-login-validation-bug-1710331200",
    startedAt: START,
    completedAt: END,
    nodes: NODE_RESULTS,
    totalTokens: 13_500,
    totalCostUsd: 0.09,
    artifactsDir: OUTPUT_DIR,
    ...overrides,
  };
}

function makeCtx(overrides: Partial<RunContext> = {}): RunContext {
  return {
    task: {
      description: "Fix login validation bug",
      slug: "fix-login-validation-bug",
      timestamp: "2026-03-13T14:00:00.000Z",
    },
    config: {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
      git: { branchPrefix: "agent/", commitMessagePrefix: "[agent]", autoPush: true, baseBranch: "main" },
    },
    workspacePath: "/workspace/test-repo",
    branch: "agent/fix-login-validation-bug-1710331200",
    repoMap: "",
    relevantFiles: [],
    understanding: "",
    plan: "",
    retryCount: 0,
    errorHashes: [],
    tokenBudget: {
      maxTokens: 200_000,
      consumed: 13_500,
      remaining: 186_500,
      layerBudgets: createLayerBudgets(200_000),
    },
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
    ...overrides,
  };
}

// ─── A. Full pipeline: generateRunReport → JSONL → reportStep artifacts ───────

describe("Full reporting pipeline — run report aggregation", () => {
  it("generateRunReport produces correct runId, status, task, branch", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true, "https://github.com/owner/repo/pull/99");
    expect(report.runId).toBe("2026-03-13T14-00-00");
    expect(report.status).toBe("succeeded");
    expect(report.task).toBe("Fix login validation bug");
    expect(report.branch).toBe("agent/fix-login-validation-bug-1710331200");
  });

  it("generateRunReport aggregates linesAdded from filesChanged", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true);
    expect(report.linesAdded).toBe(30); // 10 + 20
    expect(report.linesRemoved).toBe(2);
  });

  it("generateRunReport computes durationSeconds from startedAt→completedAt", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true);
    expect(report.durationSeconds).toBe(35);
  });

  it("generateRunReport passes through totalTokens and estimatedCostUsd", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true);
    expect(report.totalTokens).toBe(13_500);
    expect(report.estimatedCostUsd).toBeCloseTo(0.09, 5);
  });

  it("generateRunReport passes prUrl through correctly", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true, "https://github.com/owner/repo/pull/99");
    expect(report.prUrl).toBe("https://github.com/owner/repo/pull/99");
  });

  it("generateRunReport forwards nodeResults from run.nodes", () => {
    const report = generateRunReport(makeRun(), FILE_CHANGES, TEST_RESULTS, true);
    expect(report.nodeResults).toEqual(NODE_RESULTS);
  });
});

// ─── B. PR summary body contract ────────────────────────────────────────────────

describe("Full reporting pipeline — PR summary body contract", () => {
  const run = makeRun();
  const report = generateRunReport(run, FILE_CHANGES, TEST_RESULTS, true, "https://github.com/owner/repo/pull/99");

  it("PR title is '[agent] {task description}'", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.title).toBe("[agent] Fix login validation bug");
  });

  it("PR body contains ## Summary section", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.body).toContain("## Summary");
    expect(summary.body).toContain("Fix login validation bug");
  });

  it("PR body contains ## Changes section with file paths", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.body).toContain("## Changes");
    expect(summary.body).toContain("src/auth/login.ts");
    expect(summary.body).toContain("tests/auth/login.test.ts");
  });

  it("PR body contains ## Test Results section", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.body).toContain("## Test Results");
    expect(summary.body).toContain("8");
  });

  it("PR body contains ## Agent Run Details section with provider and model", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.body).toMatch(/## Agent Run/i);
    expect(summary.body).toContain("anthropic");
    expect(summary.body).toContain("claude-sonnet-4-20250514");
  });

  it("PR body contains attribution footer", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.body).toMatch(/generated by/i);
  });

  it("PR summary baseBranch is taken from config.git.baseBranch", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.baseBranch).toBe("main");
  });

  it("PR summary headBranch matches the run branch", () => {
    const summary = generatePRSummary(report, run.config, run.branch, "anthropic", "claude-sonnet-4-20250514", 0);
    expect(summary.headBranch).toBe("agent/fix-login-validation-bug-1710331200");
  });
});

// ─── C. PR creation via Octokit ──────────────────────────────────────────────

describe("Full reporting pipeline — createGitHubPR via Octokit", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the PR html_url from Octokit", async () => {
    const summary = {
      title: "[agent] Fix login validation bug",
      body: "## Summary\nFix login validation bug",
      baseBranch: "main",
      headBranch: "agent/fix-login-validation-bug",
    };
    const url = await createGitHubPR(summary, "ghp_token", "owner", "repo");
    expect(url).toBe("https://github.com/owner/repo/pull/99");
  });

  it("calls Octokit pulls.create with owner, repo, title, head, base", async () => {
    const summary = {
      title: "[agent] Fix login validation bug",
      body: "## Summary\nFix login validation bug",
      baseBranch: "main",
      headBranch: "agent/fix-login-validation-bug",
    };
    await createGitHubPR(summary, "ghp_token", "owner", "repo");
    expect(octokitCreatePR).toHaveBeenCalledWith(
      expect.objectContaining({
        owner: "owner",
        repo: "repo",
        title: "[agent] Fix login validation bug",
        head: "agent/fix-login-validation-bug",
        base: "main",
      }),
    );
  });
});

// ─── D. Session transcript JSONL ─────────────────────────────────────────────

describe("Full reporting pipeline — session transcript JSONL", () => {
  beforeEach(() => vi.clearAllMocks());

  it("context session transcript is written to session-context.jsonl", async () => {
    const messages = [{ role: "user", content: "Explore the repo" }, { role: "assistant", content: "Done" }];
    await saveTranscript("context", messages, OUTPUT_DIR);
    const [writtenPath] = writeFileMock.mock.calls[0] as [string, ...unknown[]];
    expect(writtenPath).toContain("session-context.jsonl");
  });

  it("implement session transcript is written to session-implement.jsonl", async () => {
    const messages = [{ role: "user", content: "Implement the plan" }];
    await saveTranscript("implement", messages, OUTPUT_DIR);
    const [writtenPath] = writeFileMock.mock.calls[0] as [string, ...unknown[]];
    expect(writtenPath).toContain("session-implement.jsonl");
  });

  it("each message is a valid JSON line in the file", async () => {
    const messages = [
      { role: "user", content: "Fix tests", tokens: 5 },
      { role: "assistant", content: "Fixed.", tokens: 12 },
    ];
    await saveTranscript("fix", messages, OUTPUT_DIR);
    const [, content] = writeFileMock.mock.calls[0] as [string, string];
    const lines = content.split("\n").filter((l) => l.trim().length > 0);
    expect(lines).toHaveLength(2);
    lines.forEach((l) => expect(() => JSON.parse(l)).not.toThrow());
  });

  it("multiple sessions write independently and don't overwrite each other", async () => {
    await saveTranscript("context", [{ role: "user", content: "ctx" }], OUTPUT_DIR);
    await saveTranscript("plan",    [{ role: "user", content: "plan" }], OUTPUT_DIR);
    const paths = writeFileMock.mock.calls.map((c) => (c as [string, ...unknown[]])[0]);
    expect(paths[0]).toContain("session-context.jsonl");
    expect(paths[1]).toContain("session-plan.jsonl");
  });

  it("outputDir is created with { recursive: true } for each session", async () => {
    await saveTranscript("context", [], OUTPUT_DIR);
    expect(mkdirMock).toHaveBeenCalledWith(OUTPUT_DIR, expect.objectContaining({ recursive: true }));
  });
});

// ─── E. report.json + metrics.json ───────────────────────────────────────────

describe("Full reporting pipeline — reportStep artifact files", () => {
  beforeEach(() => vi.clearAllMocks());

  it("reportStep creates the outputDir with recursive: true", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    expect(mkdirMock).toHaveBeenCalledWith(OUTPUT_DIR, expect.objectContaining({ recursive: true }));
  });

  it("reportStep writes report.json to the outputDir", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const paths = writeFileMock.mock.calls.map((c) => (c as [string, ...unknown[]])[0]);
    expect(paths.some((p) => p.endsWith("report.json"))).toBe(true);
  });

  it("reportStep writes metrics.json to the outputDir", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const paths = writeFileMock.mock.calls.map((c) => (c as [string, ...unknown[]])[0]);
    expect(paths.some((p) => p.endsWith("metrics.json"))).toBe(true);
  });

  it("report.json is valid JSON containing task description", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const reportCall = writeFileMock.mock.calls.find((c) =>
      (c as [string, ...unknown[]])[0].endsWith("report.json"),
    ) as [string, string] | undefined;
    const parsed = JSON.parse(reportCall![1]);
    expect(parsed.task).toBe("Fix login validation bug");
  });

  it("report.json contains the branch", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const reportCall = writeFileMock.mock.calls.find((c) =>
      (c as [string, ...unknown[]])[0].endsWith("report.json"),
    ) as [string, string] | undefined;
    const parsed = JSON.parse(reportCall![1]);
    expect(parsed.branch).toBe("agent/fix-login-validation-bug-1710331200");
  });

  it("report.json contains totalTokens equal to tokenBudget.consumed", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const reportCall = writeFileMock.mock.calls.find((c) =>
      (c as [string, ...unknown[]])[0].endsWith("report.json"),
    ) as [string, string] | undefined;
    const parsed = JSON.parse(reportCall![1]);
    expect(parsed.totalTokens).toBe(13_500);
  });

  it("metrics.json is valid JSON containing totalTokens", async () => {
    await reportStep(makeCtx(), { outputDir: OUTPUT_DIR });
    const metricsCall = writeFileMock.mock.calls.find((c) =>
      (c as [string, ...unknown[]])[0].endsWith("metrics.json"),
    ) as [string, string] | undefined;
    const parsed = JSON.parse(metricsCall![1]);
    expect(parsed.totalTokens).toBe(13_500);
  });

  it("report.json includes prUrl when provided in accumulatedData", async () => {
    await reportStep(makeCtx(), {
      outputDir: OUTPUT_DIR,
      prUrl: "https://github.com/owner/repo/pull/99",
    });
    const reportCall = writeFileMock.mock.calls.find((c) =>
      (c as [string, ...unknown[]])[0].endsWith("report.json"),
    ) as [string, string] | undefined;
    const parsed = JSON.parse(reportCall![1]);
    expect(parsed.prUrl).toBe("https://github.com/owner/repo/pull/99");
  });

  it("reportStep still returns passed status when no outputDir is given", async () => {
    const result = await reportStep(makeCtx());
    expect(result.status).toBe("passed");
    expect(writeFileMock).not.toHaveBeenCalled();
  });
});

// ─── F. No GITHUB_TOKEN → no PR created ─────────────────────────────────────

describe("Full reporting pipeline — PR creation gated on GITHUB_TOKEN", () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => {
    delete process.env.GITHUB_TOKEN;
  });

  it("commitPushStep does not call createGitHubPR when GITHUB_TOKEN is absent", async () => {
    delete process.env.GITHUB_TOKEN;
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("passed");
    expect(octokitCreatePR).not.toHaveBeenCalled();
    expect(result.data?.prUrl).toBeUndefined();
  });

  it("commitPushStep includes prUrl in result.data when GITHUB_TOKEN is set", async () => {
    process.env.GITHUB_TOKEN = "ghp_fake_token";
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("passed");
    expect(octokitCreatePR).toHaveBeenCalledOnce();
    expect(result.data?.prUrl).toBe("https://github.com/owner/repo/pull/99");
  });

  it("commitPushStep swallows Octokit error and still returns passed", async () => {
    process.env.GITHUB_TOKEN = "ghp_fake_token";
    octokitCreatePR.mockRejectedValueOnce(new Error("HTTP 422"));
    const result = await commitPushStep(makeCtx());
    expect(result.status).toBe("passed");
    expect(result.data?.prUrl).toBeUndefined();
  });
});

// ─── G. Edge: completedAt = null ─────────────────────────────────────────────

describe("Full reporting pipeline — edge case: completedAt = null", () => {
  it("generateRunReport yields durationSeconds = 0 when completedAt is null", () => {
    const run = makeRun({ completedAt: null });
    const report = generateRunReport(run, FILE_CHANGES, TEST_RESULTS, true);
    expect(report.durationSeconds).toBe(0);
  });

  it("generateRunReport still produces valid output when completedAt is null", () => {
    const run = makeRun({ completedAt: null });
    const report = generateRunReport(run, FILE_CHANGES, TEST_RESULTS, true);
    expect(report.status).toBe("succeeded");
    expect(report.linesAdded).toBe(30);
  });
});
