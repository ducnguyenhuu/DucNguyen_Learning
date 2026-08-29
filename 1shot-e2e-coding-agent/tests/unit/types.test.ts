/**
 * Unit tests for shared type guards and validation helpers.
 *
 * These tests define the CONTRACT for src/types.ts.
 * They are written first (TDD) and will fail until T005 creates the implementation.
 *
 * What is tested:
 *  - RunStatus type guard and enum values
 *  - Provider type guard and allowed values
 *  - Language type guard and allowed values
 *  - AgentConfig validation rules (from data-model.md)
 *  - Task validation and slug derivation
 *  - createLayerBudgets: per-layer % allocation from maxTokens
 */

import { describe, it, expect } from "vitest";
import {
  isRunStatus,
  isProvider,
  isLanguage,
  validateAgentConfig,
  validateTask,
  createTaskSlug,
  createLayerBudgets,
  RUN_STATUS,
  PROVIDERS,
  LANGUAGES,
  type RunStatus,
  type AgentConfig,
  type Task,
  type LayerBudgets,
} from "../../src/types.js";

// ─── RunStatus ───────────────────────────────────────────────────────────────

describe("RUN_STATUS", () => {
  it("contains the five expected values", () => {
    expect(RUN_STATUS).toEqual(
      expect.arrayContaining(["pending", "running", "succeeded", "failed", "timeout"]),
    );
    expect(RUN_STATUS).toHaveLength(5);
  });
});

describe("isRunStatus()", () => {
  it("returns true for all valid statuses", () => {
    const valid: string[] = ["pending", "running", "succeeded", "failed", "timeout"];
    for (const s of valid) {
      expect(isRunStatus(s), `expected ${s} to be valid`).toBe(true);
    }
  });

  it("returns false for unknown strings", () => {
    expect(isRunStatus("done")).toBe(false);
    expect(isRunStatus("complete")).toBe(false);
    expect(isRunStatus("")).toBe(false);
  });

  it("returns false for non-string inputs", () => {
    expect(isRunStatus(null)).toBe(false);
    expect(isRunStatus(undefined)).toBe(false);
    expect(isRunStatus(42)).toBe(false);
    expect(isRunStatus({})).toBe(false);
  });
});

// ─── Provider ────────────────────────────────────────────────────────────────

describe("PROVIDERS", () => {
  it("contains anthropic and openai", () => {
    expect(PROVIDERS).toContain("anthropic");
    expect(PROVIDERS).toContain("openai");
  });
});

describe("isProvider()", () => {
  it("returns true for supported providers", () => {
    expect(isProvider("anthropic")).toBe(true);
    expect(isProvider("openai")).toBe(true);
  });

  it("returns false for unsupported providers", () => {
    expect(isProvider("gemini")).toBe(false);
    expect(isProvider("")).toBe(false);
    expect(isProvider(null)).toBe(false);
  });
});

// ─── Language ─────────────────────────────────────────────────────────────────

describe("LANGUAGES", () => {
  it("contains the five declared repo languages", () => {
    expect(LANGUAGES).toEqual(
      expect.arrayContaining(["python", "typescript", "javascript", "go", "java"]),
    );
    expect(LANGUAGES).toHaveLength(5);
  });
});

describe("isLanguage()", () => {
  it("returns true for all supported languages", () => {
    for (const lang of ["python", "typescript", "javascript", "go", "java"]) {
      expect(isLanguage(lang), `${lang} should be valid`).toBe(true);
    }
  });

  it("returns false for unsupported languages", () => {
    expect(isLanguage("rust")).toBe(false);
    expect(isLanguage("")).toBe(false);
    expect(isLanguage(null)).toBe(false);
  });
});

// ─── AgentConfig validation ──────────────────────────────────────────────────

/** Minimal valid config to build variations from. */
function makeValidConfig(): AgentConfig {
  return {
    agent: {
      name: "test-agent",
      maxTokensPerRun: 200_000,
      maxCostPerRunUsd: 2.0,
      timeoutSeconds: 600,
    },
    provider: {
      default: "anthropic",
    },
    repo: {
      path: "/workspace",
      language: "typescript",
      testCommand: "vitest run",
      lintCommand: "eslint --fix",
    },
    shiftLeft: { maxRetries: 2, runLintBeforePush: true, runTypeCheckBeforePush: true, runTargetedTests: true },
    git: { branchPrefix: "agent/", commitMessagePrefix: "[agent]", autoPush: true, baseBranch: "main" },
    fileEditing: { writeThresholdLines: 250 },
    security: { domainAllowlist: [] },
    extensions: {},
    context: {},
  };
}

describe("validateAgentConfig()", () => {
  it("returns no errors for a valid config", () => {
    expect(validateAgentConfig(makeValidConfig())).toHaveLength(0);
  });

  it("rejects maxTokensPerRun = 0", () => {
    const cfg = makeValidConfig();
    cfg.agent.maxTokensPerRun = 0;
    const errors = validateAgentConfig(cfg);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => /maxTokensPerRun/.test(e))).toBe(true);
  });

  it("rejects maxTokensPerRun < 0", () => {
    const cfg = makeValidConfig();
    cfg.agent.maxTokensPerRun = -1;
    expect(validateAgentConfig(cfg).length).toBeGreaterThan(0);
  });

  it("rejects timeoutSeconds = 0", () => {
    const cfg = makeValidConfig();
    cfg.agent.timeoutSeconds = 0;
    const errors = validateAgentConfig(cfg);
    expect(errors.some((e) => /timeoutSeconds/.test(e))).toBe(true);
  });

  it("rejects empty testCommand", () => {
    const cfg = makeValidConfig();
    cfg.repo.testCommand = "";
    const errors = validateAgentConfig(cfg);
    expect(errors.some((e) => /testCommand/.test(e))).toBe(true);
  });

  it("rejects empty lintCommand", () => {
    const cfg = makeValidConfig();
    cfg.repo.lintCommand = "";
    const errors = validateAgentConfig(cfg);
    expect(errors.some((e) => /lintCommand/.test(e))).toBe(true);
  });

  it("rejects unsupported provider.default", () => {
    const cfg = makeValidConfig();
    (cfg.provider as any).default = "gemini";
    const errors = validateAgentConfig(cfg);
    expect(errors.some((e) => /provider/.test(e))).toBe(true);
  });

  it("can report multiple errors at once", () => {
    const cfg = makeValidConfig();
    cfg.agent.maxTokensPerRun = 0;
    cfg.agent.timeoutSeconds = 0;
    cfg.repo.testCommand = "";
    expect(validateAgentConfig(cfg).length).toBeGreaterThanOrEqual(3);
  });
});

// ─── Task validation ─────────────────────────────────────────────────────────

describe("validateTask()", () => {
  it("accepts a normal task description", () => {
    expect(validateTask("Add email validation to the signup form")).toHaveLength(0);
  });

  it("rejects an empty description", () => {
    const errors = validateTask("");
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => /description/.test(e))).toBe(true);
  });

  it("rejects descriptions longer than 500 characters", () => {
    const long = "x".repeat(501);
    const errors = validateTask(long);
    expect(errors.some((e) => /500/.test(e) || /length/.test(e))).toBe(true);
  });

  it("accepts a description of exactly 500 characters", () => {
    expect(validateTask("a".repeat(500))).toHaveLength(0);
  });
});

// ─── Task slug derivation ─────────────────────────────────────────────────────

describe("createTaskSlug()", () => {
  it("lowercases the description", () => {
    expect(createTaskSlug("Add Email Validation")).toMatch(/^add-email-validation/);
  });

  it("replaces spaces with hyphens", () => {
    expect(createTaskSlug("fix the login bug")).toBe("fix-the-login-bug");
  });

  it("strips punctuation and special characters", () => {
    const slug = createTaskSlug("Fix login! (urgent) #123");
    expect(slug).not.toMatch(/[!()#]/);
  });

  it("collapses multiple separators into one hyphen", () => {
    const slug = createTaskSlug("add  email   validation");
    expect(slug).not.toMatch(/--/);
  });

  it("truncates to a maximum of 60 characters", () => {
    const long = "a ".repeat(50).trim(); // >60 chars
    expect(createTaskSlug(long).length).toBeLessThanOrEqual(60);
  });

  it("does not start or end with a hyphen", () => {
    const slug = createTaskSlug("  fix bug  ");
    expect(slug).not.toMatch(/^-|-$/);
  });
});

// ─── createLayerBudgets ───────────────────────────────────────────────────────

describe("createLayerBudgets()", () => {
  const budgets: LayerBudgets = createLayerBudgets(100_000);

  it("allocates 5% to repoMap (L0)", () => {
    expect(budgets.repoMap).toBe(5_000);
  });

  it("allocates 15% to searchResults (L1)", () => {
    expect(budgets.searchResults).toBe(15_000);
  });

  it("allocates 40% to fullFiles (L2)", () => {
    expect(budgets.fullFiles).toBe(40_000);
  });

  it("allocates 10% to supplementary (L3)", () => {
    expect(budgets.supplementary).toBe(10_000);
  });

  it("allocates 30% to reserved", () => {
    expect(budgets.reserved).toBe(30_000);
  });

  it("all layers sum to maxTokens", () => {
    const total =
      budgets.repoMap +
      budgets.searchResults +
      budgets.fullFiles +
      budgets.supplementary +
      budgets.reserved;
    expect(total).toBe(100_000);
  });

  it("scales correctly for different maxTokens values", () => {
    const b = createLayerBudgets(200_000);
    expect(b.repoMap).toBe(10_000);
    expect(b.fullFiles).toBe(80_000);
  });

  it("rounds down fractional tokens without going over budget", () => {
    const b = createLayerBudgets(99_999);
    const total =
      b.repoMap + b.searchResults + b.fullFiles + b.supplementary + b.reserved;
    expect(total).toBeLessThanOrEqual(99_999);
  });
});
