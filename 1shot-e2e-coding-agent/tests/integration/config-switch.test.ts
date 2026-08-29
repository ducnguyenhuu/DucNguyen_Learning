/**
 * tests/integration/config-switch.test.ts — T071
 *
 * Integration tests for the multi-config scenario (US6).
 *
 * Validates that two AgentConfig objects with fundamentally different settings
 * (provider, language, test/lint commands, retry counts) can coexist, are
 * correctly merged over DEFAULT_CONFIG, and that CLI overrides layer correctly
 * on top of each config without bleeding across configs.
 *
 * Config A — TypeScript / anthropic / vitest + eslint
 * Config B — Python    / openai   / pytest + ruff
 *
 * Tests run entirely in-process — no disk I/O required.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { DEFAULT_CONFIG, mergeCliOverrides } from "../../src/config.js";
import type { AgentConfig } from "../../src/types.js";

// ─── Synthetic configs (what loadConfig would return after deep-merge) ────────

/** Config A  — TypeScript / anthropic / vitest + eslint */
const CONFIG_A: AgentConfig = {
  ...DEFAULT_CONFIG,
  provider: {
    ...DEFAULT_CONFIG.provider,
    default: "anthropic",
    anthropicModel: "claude-opus-4",
  },
  repo: {
    ...DEFAULT_CONFIG.repo,
    language: "typescript",
    path: "/repos/app-a",
    testCommand: "vitest run",
    lintCommand: "eslint .",
  },
  shiftLeft: { ...DEFAULT_CONFIG.shiftLeft, maxRetries: 3 },
};

/** Config B  — Python / openai / pytest + ruff */
const CONFIG_B: AgentConfig = {
  ...DEFAULT_CONFIG,
  provider: {
    ...DEFAULT_CONFIG.provider,
    default: "openai",
    openaiModel: "gpt-4.1",
  },
  repo: {
    ...DEFAULT_CONFIG.repo,
    language: "python",
    path: "/repos/app-b",
    testCommand: "pytest",
    lintCommand: "ruff check --fix",
  },
  shiftLeft: { ...DEFAULT_CONFIG.shiftLeft, maxRetries: 1 },
};

// ─── 1. Config A baseline ─────────────────────────────────────────────────────

describe("Config A (TypeScript / anthropic / vitest)", () => {
  it("has the correct provider", () => {
    expect(CONFIG_A.provider.default).toBe("anthropic");
  });

  it("has the correct anthropic model", () => {
    expect(CONFIG_A.provider.anthropicModel).toBe("claude-opus-4");
  });

  it("has the correct repo language", () => {
    expect(CONFIG_A.repo.language).toBe("typescript");
  });

  it("has the correct test command", () => {
    expect(CONFIG_A.repo.testCommand).toBe("vitest run");
  });

  it("has the correct lint command", () => {
    expect(CONFIG_A.repo.lintCommand).toBe("eslint .");
  });

  it("has the configured max retries", () => {
    expect(CONFIG_A.shiftLeft.maxRetries).toBe(3);
  });
});

// ─── 2. Config B baseline ─────────────────────────────────────────────────────

describe("Config B (Python / openai / pytest + ruff)", () => {
  it("has the correct provider", () => {
    expect(CONFIG_B.provider.default).toBe("openai");
  });

  it("has the correct openai model", () => {
    expect(CONFIG_B.provider.openaiModel).toBe("gpt-4.1");
  });

  it("has the correct repo language", () => {
    expect(CONFIG_B.repo.language).toBe("python");
  });

  it("has the correct test command", () => {
    expect(CONFIG_B.repo.testCommand).toBe("pytest");
  });

  it("has the correct lint command", () => {
    expect(CONFIG_B.repo.lintCommand).toBe("ruff check --fix");
  });

  it("has the configured max retries", () => {
    expect(CONFIG_B.shiftLeft.maxRetries).toBe(1);
  });
});

// ─── 3. Config isolation — A and B are independent ───────────────────────────

describe("Config isolation — A and B are independent", () => {
  it("configs have different providers", () => {
    expect(CONFIG_A.provider.default).not.toBe(CONFIG_B.provider.default);
  });

  it("configs have different languages", () => {
    expect(CONFIG_A.repo.language).not.toBe(CONFIG_B.repo.language);
  });

  it("configs have different test commands", () => {
    expect(CONFIG_A.repo.testCommand).not.toBe(CONFIG_B.repo.testCommand);
  });

  it("configs have different lint commands", () => {
    expect(CONFIG_A.repo.lintCommand).not.toBe(CONFIG_B.repo.lintCommand);
  });

  it("applying an override on A does not mutate A or affect B", () => {
    const overridden = mergeCliOverrides(CONFIG_A, { provider: "openai" });
    expect(CONFIG_A.provider.default).toBe("anthropic"); // original unchanged
    expect(CONFIG_B.provider.default).toBe("openai");    // B unchanged
    expect(overridden.provider.default).toBe("openai");  // only result changed
  });
});

// ─── 4. Provider switch via CLI overrides ────────────────────────────────────

describe("Provider switching via mergeCliOverrides", () => {
  it("Config A — switch to openai provider", () => {
    const result = mergeCliOverrides(CONFIG_A, { provider: "openai" });
    expect(result.provider.default).toBe("openai");
  });

  it("Config B — switch to anthropic provider", () => {
    const result = mergeCliOverrides(CONFIG_B, { provider: "anthropic" });
    expect(result.provider.default).toBe("anthropic");
  });

  it("Config A — no override preserves anthropic", () => {
    const result = mergeCliOverrides(CONFIG_A, {});
    expect(result.provider.default).toBe("anthropic");
  });

  it("Config B — no override preserves openai", () => {
    const result = mergeCliOverrides(CONFIG_B, {});
    expect(result.provider.default).toBe("openai");
  });
});

// ─── 5. Model override ────────────────────────────────────────────────────────

describe("Model override via mergeCliOverrides", () => {
  it("Config A — override anthropicModel when provider stays anthropic", () => {
    const result = mergeCliOverrides(CONFIG_A, { model: "claude-sonnet-4-20250514" });
    expect(result.provider.anthropicModel).toBe("claude-sonnet-4-20250514");
  });

  it("Config B — override openaiModel when provider stays openai", () => {
    const result = mergeCliOverrides(CONFIG_B, { model: "o4-mini" });
    expect(result.provider.openaiModel).toBe("o4-mini");
  });

  it("Config A — override model + switch to openai updates openaiModel", () => {
    const result = mergeCliOverrides(CONFIG_A, { provider: "openai", model: "gpt-4o" });
    expect(result.provider.default).toBe("openai");
    expect(result.provider.openaiModel).toBe("gpt-4o");
  });

  it("Config B — override model + switch to anthropic updates anthropicModel", () => {
    const result = mergeCliOverrides(CONFIG_B, { provider: "anthropic", model: "claude-haiku-3-5" });
    expect(result.provider.default).toBe("anthropic");
    expect(result.provider.anthropicModel).toBe("claude-haiku-3-5");
  });
});

// ─── 6. maxRetries override ───────────────────────────────────────────────────

describe("maxRetries override via mergeCliOverrides", () => {
  it("Config A — override maxRetries replaces configured value", () => {
    const result = mergeCliOverrides(CONFIG_A, { maxRetries: 5 });
    expect(result.shiftLeft.maxRetries).toBe(5);
  });

  it("Config B — override maxRetries replaces configured value", () => {
    const result = mergeCliOverrides(CONFIG_B, { maxRetries: 4 });
    expect(result.shiftLeft.maxRetries).toBe(4);
  });

  it("maxRetries override on A does not affect B's maxRetries", () => {
    mergeCliOverrides(CONFIG_A, { maxRetries: 99 });
    expect(CONFIG_B.shiftLeft.maxRetries).toBe(1);
  });
});

// ─── 7. Timeout and token overrides ──────────────────────────────────────────

describe("Timeout and token overrides via mergeCliOverrides", () => {
  it("Config A — timeout override updates timeoutSeconds", () => {
    const result = mergeCliOverrides(CONFIG_A, { timeout: 300 });
    expect(result.agent.timeoutSeconds).toBe(300);
  });

  it("Config B — timeout override updates timeoutSeconds", () => {
    const result = mergeCliOverrides(CONFIG_B, { timeout: 120 });
    expect(result.agent.timeoutSeconds).toBe(120);
  });

  it("Config A — maxTokens override updates maxTokensPerRun", () => {
    const result = mergeCliOverrides(CONFIG_A, { maxTokens: 100_000 });
    expect(result.agent.maxTokensPerRun).toBe(100_000);
  });

  it("Config B — maxTokens override updates maxTokensPerRun", () => {
    const result = mergeCliOverrides(CONFIG_B, { maxTokens: 50_000 });
    expect(result.agent.maxTokensPerRun).toBe(50_000);
  });
});

// ─── 8. Repo fields preserved across overrides ───────────────────────────────

describe("Repo commands preserved through CLI overrides", () => {
  it("Config A repo fields are unaffected by provider override", () => {
    const result = mergeCliOverrides(CONFIG_A, { provider: "openai" });
    expect(result.repo.testCommand).toBe("vitest run");
    expect(result.repo.lintCommand).toBe("eslint .");
    expect(result.repo.language).toBe("typescript");
  });

  it("Config B repo fields are unaffected by provider override", () => {
    const result = mergeCliOverrides(CONFIG_B, { provider: "anthropic" });
    expect(result.repo.testCommand).toBe("pytest");
    expect(result.repo.lintCommand).toBe("ruff check --fix");
    expect(result.repo.language).toBe("python");
  });

  it("Config A repo fields are unaffected by model + timeout + maxTokens overrides", () => {
    const result = mergeCliOverrides(CONFIG_A, {
      provider: "openai",
      model: "gpt-4o",
      timeout: 300,
      maxTokens: 80_000,
      maxRetries: 2,
    });
    expect(result.repo.testCommand).toBe("vitest run");
    expect(result.repo.lintCommand).toBe("eslint .");
    expect(result.repo.language).toBe("typescript");
    expect(result.repo.path).toBe("/repos/app-a");
  });

  it("Config B repo fields are unaffected by all overrides", () => {
    const result = mergeCliOverrides(CONFIG_B, {
      provider: "anthropic",
      model: "claude-opus-4",
      timeout: 600,
      maxTokens: 200_000,
      maxRetries: 5,
    });
    expect(result.repo.testCommand).toBe("pytest");
    expect(result.repo.lintCommand).toBe("ruff check --fix");
    expect(result.repo.language).toBe("python");
    expect(result.repo.path).toBe("/repos/app-b");
  });
});
