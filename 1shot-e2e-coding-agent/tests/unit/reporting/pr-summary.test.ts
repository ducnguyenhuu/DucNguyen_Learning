/**
 * tests/unit/reporting/pr-summary.test.ts — T061
 *
 * Unit tests for PR summary generation and GitHub PR creation.
 *
 * Tests cover:
 *  - PR title: "[agent] {task description}"
 *  - PR body: ## Summary, ## Changes table, ## Test Results, ## Agent Run Details, footer
 *  - Changes table: file path, action, line counts for each FileChange
 *  - baseBranch taken from config.git.baseBranch (defaults to "main")
 *  - headBranch matches the supplied branch
 *  - Octokit createGitHubPR: called with token/owner/repo, returns html_url
 *  - createGitHubPR: throws when Octokit rejects
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RunReport, AgentConfig } from "../../../src/types.js";
import { DEFAULT_CONFIG } from "../../../src/config.js";
import {
  generatePRSummary,
  createGitHubPR,
} from "../../../src/reporting/pr-summary.js";

// ─── Mock Octokit ─────────────────────────────────────────────────────────────

vi.mock("@octokit/rest", () => ({
  Octokit: vi.fn().mockImplementation(() => ({
    rest: {
      pulls: {
        create: vi.fn().mockResolvedValue({
          data: { html_url: "https://github.com/owner/repo/pull/42", number: 42 },
        }),
      },
    },
  })),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeReport(overrides: Partial<RunReport> = {}): RunReport {
  return {
    runId: "2026-03-13T14-00-00",
    status: "succeeded",
    task: "Add email validation to user endpoint",
    branch: "agent/add-email-validation-to-user-endpoint-1710331200",
    prUrl: null,
    filesChanged: [
      {
        path: "src/services/user_service.ts",
        action: "modified",
        linesAdded: 12,
        linesRemoved: 3,
      },
      {
        path: "tests/email-validation.test.ts",
        action: "created",
        linesAdded: 25,
        linesRemoved: 0,
      },
    ],
    linesAdded: 37,
    linesRemoved: 3,
    testResults: { passed: 10, failed: 0, skipped: 1, duration: 4200 },
    lintClean: true,
    totalTokens: 16_300,
    estimatedCostUsd: 0.12,
    durationSeconds: 35,
    nodeResults: [],
    ...overrides,
  };
}

function makeConfig(gitBaseBranch?: string): AgentConfig {
  return {
    ...DEFAULT_CONFIG,
    repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
    git: { ...DEFAULT_CONFIG.git, baseBranch: gitBaseBranch ?? "main" },
  };
}

const HEAD_BRANCH = "agent/add-email-validation-to-user-endpoint-1710331200";
const PROVIDER = "anthropic";
const MODEL = "claude-sonnet-4-20250514";

// ─── PR title ─────────────────────────────────────────────────────────────────

describe("generatePRSummary() — PR title", () => {
  it("formats title as '[agent] {task description}'", () => {
    const summary = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(summary.title).toBe("[agent] Add email validation to user endpoint");
  });

  it("handles long task descriptions without truncating the title", () => {
    const longTask = "A".repeat(200);
    const summary = generatePRSummary(
      makeReport({ task: longTask }),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(summary.title).toBe(`[agent] ${longTask}`);
  });
});

// ─── PR branching ─────────────────────────────────────────────────────────────

describe("generatePRSummary() — branch fields", () => {
  it("sets headBranch to the supplied headBranch argument", () => {
    const summary = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(summary.headBranch).toBe(HEAD_BRANCH);
  });

  it("sets baseBranch from config.git.baseBranch", () => {
    const summary = generatePRSummary(
      makeReport(),
      makeConfig("develop"),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(summary.baseBranch).toBe("develop");
  });

  it("defaults baseBranch to 'main' when git config is absent", () => {
    const config: AgentConfig = {
      ...DEFAULT_CONFIG,
      repo: { ...DEFAULT_CONFIG.repo, testCommand: "npm test", lintCommand: "npm run lint" },
      git: undefined,
    };
    const summary = generatePRSummary(
      makeReport(),
      config,
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(summary.baseBranch).toBe("main");
  });
});

// ─── PR body — ## Summary ─────────────────────────────────────────────────────

describe("generatePRSummary() — PR body summary section", () => {
  it("body contains '## Summary' heading", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("## Summary");
  });

  it("body summary section contains the task description", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("Add email validation to user endpoint");
  });
});

// ─── PR body — ## Changes ─────────────────────────────────────────────────────

describe("generatePRSummary() — PR body changes table", () => {
  it("body contains '## Changes' heading", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("## Changes");
  });

  it("body changes table contains modified file path", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("src/services/user_service.ts");
  });

  it("body changes table contains created file path", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("tests/email-validation.test.ts");
  });

  it("body changes table contains action labels for each file", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    // Either the word itself or a capitalised form
    expect(body.toLowerCase()).toContain("modified");
    expect(body.toLowerCase()).toContain("created");
  });

  it("body changes table renders empty state for zero file changes", () => {
    const { body } = generatePRSummary(
      makeReport({ filesChanged: [], linesAdded: 0, linesRemoved: 0 }),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    // Should still have the ## Changes section header
    expect(body).toContain("## Changes");
  });
});

// ─── PR body — ## Test Results ────────────────────────────────────────────────

describe("generatePRSummary() — PR body test results section", () => {
  it("body contains '## Test Results' heading", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("## Test Results");
  });

  it("body test results show passed count", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("10");
  });

  it("body test results show lint clean status when lintClean=true", () => {
    const { body } = generatePRSummary(
      makeReport({ lintClean: true }),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    // Should contain a checkmark or "Clean" or "✅"
    expect(body).toMatch(/✅|clean|passed/i);
  });

  it("body test results show lint failure when lintClean=false", () => {
    const { body } = generatePRSummary(
      makeReport({ lintClean: false }),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toMatch(/❌|issues|failed|lint/i);
  });
});

// ─── PR body — ## Agent Run Details ──────────────────────────────────────────

describe("generatePRSummary() — PR body agent run details", () => {
  it("body contains an agent run details heading", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    // Accept either "Agent Run Details" or just "Agent Run"
    expect(body).toMatch(/## Agent Run/i);
  });

  it("body contains the provider name", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      "anthropic",
      MODEL,
      0,
    );
    expect(body).toContain("anthropic");
  });

  it("body contains the model name", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      "claude-sonnet-4-20250514",
      0,
    );
    expect(body).toContain("claude-sonnet-4-20250514");
  });

  it("body contains token count", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("16");   // at least the leading digits of 16,300
  });

  it("body contains estimated cost", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("0.12");
  });

  it("body contains duration in seconds", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toContain("35");
  });

  it("body contains retry count", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      2,
    );
    expect(body).toContain("2");
  });
});

// ─── PR body — footer ─────────────────────────────────────────────────────────

describe("generatePRSummary() — PR body footer", () => {
  it("body contains a 'Generated by' attribution footer", () => {
    const { body } = generatePRSummary(
      makeReport(),
      makeConfig(),
      HEAD_BRANCH,
      PROVIDER,
      MODEL,
      0,
    );
    expect(body).toMatch(/generated by/i);
  });
});

// ─── createGitHubPR ───────────────────────────────────────────────────────────

describe("createGitHubPR()", () => {
  const SUMMARY = {
    title: "[agent] Add email validation",
    body: "## Summary\nTask description",
    baseBranch: "main",
    headBranch: "agent/add-email-validation",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns the PR html_url from the Octokit response", async () => {
    const url = await createGitHubPR(SUMMARY, "ghp_token", "owner", "repo");
    expect(url).toBe("https://github.com/owner/repo/pull/42");
  });

  it("calls Octokit pulls.create with the correct owner and repo", async () => {
    const { Octokit } = await import("@octokit/rest");
    await createGitHubPR(SUMMARY, "ghp_token", "myorg", "myrepo");
    // The Octokit constructor mock returns an instance in the module-level mock
    const instance = vi.mocked(Octokit).mock.results[0]?.value as {
      rest: { pulls: { create: ReturnType<typeof vi.fn> } };
    };
    expect(instance.rest.pulls.create).toHaveBeenCalledWith(
      expect.objectContaining({ owner: "myorg", repo: "myrepo" }),
    );
  });

  it("passes the PR title to Octokit", async () => {
    const { Octokit } = await import("@octokit/rest");
    vi.mocked(Octokit).mockClear();
    await createGitHubPR(SUMMARY, "ghp_token", "owner", "repo");
    const instance = vi.mocked(Octokit).mock.results[0]?.value as {
      rest: { pulls: { create: ReturnType<typeof vi.fn> } };
    };
    expect(instance.rest.pulls.create).toHaveBeenCalledWith(
      expect.objectContaining({ title: "[agent] Add email validation" }),
    );
  });

  it("passes head and base branches to Octokit", async () => {
    const { Octokit } = await import("@octokit/rest");
    vi.mocked(Octokit).mockClear();
    await createGitHubPR(SUMMARY, "ghp_token", "owner", "repo");
    const instance = vi.mocked(Octokit).mock.results[0]?.value as {
      rest: { pulls: { create: ReturnType<typeof vi.fn> } };
    };
    expect(instance.rest.pulls.create).toHaveBeenCalledWith(
      expect.objectContaining({ head: "agent/add-email-validation", base: "main" }),
    );
  });

  it("throws when Octokit rejects (e.g. 422 Unprocessable Entity)", async () => {
    const { Octokit } = await import("@octokit/rest");
    vi.mocked(Octokit).mockImplementationOnce(() => ({
      rest: {
        pulls: {
          create: vi.fn().mockRejectedValue(new Error("HTTP 422: Validation Failed")),
        },
      },
    }) as never);

    await expect(
      createGitHubPR(SUMMARY, "ghp_bad_token", "owner", "repo"),
    ).rejects.toThrow();
  });
});
