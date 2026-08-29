/**
 * Unit tests for configuration loading and validation — tests/unit/config.test.ts
 *
 * These tests define the CONTRACT for src/config.ts.
 * Written first (TDD) — will fail until T007 creates the implementation.
 *
 * What is tested:
 *  - loadConfig(): reads and returns a pi-agent.config.ts file
 *  - loadConfig(): applies defaults for optional fields
 *  - loadConfig(): throws on validation errors (invalid field values)
 *  - loadConfig(): throws with a clear message when the file is missing
 *  - mergeCliOverrides(): CLI flags override config file values
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { loadConfig, mergeCliOverrides, DEFAULT_CONFIG } from "../../src/config.js";
import type { AgentConfig } from "../../src/types.js";

// ─── Helpers ───────────────────────────────────────────────────────────────────

/** Write a pi-agent.config.ts that does `export default { ... }` */
async function writeConfigFile(dir: string, config: Partial<AgentConfig> & Record<string, unknown>): Promise<string> {
  const configPath = join(dir, "pi-agent.config.ts");
  // Use JSON-serialisable subset — real configs use TS but we only test the
  // loadConfig() loading path; the object literal is eval'd via dynamic import.
  // We write a .mjs with `export default` so Node can import it directly.
  const mjsPath = join(dir, "pi-agent.config.mjs");
  await writeFile(mjsPath, `export default ${JSON.stringify(config, null, 2)};\n`);
  return mjsPath;
}

// ─── DEFAULT_CONFIG ──────────────────────────────────────────────────────────

describe("DEFAULT_CONFIG", () => {
  it("provides sensible defaults for all optional fields", () => {
    expect(DEFAULT_CONFIG.agent.maxTokensPerRun).toBe(200_000);
    expect(DEFAULT_CONFIG.agent.maxCostPerRunUsd).toBe(2.0);
    expect(DEFAULT_CONFIG.agent.timeoutSeconds).toBe(600);
    expect(DEFAULT_CONFIG.provider.default).toBe("anthropic");
    expect(DEFAULT_CONFIG.provider.anthropicModel).toBeDefined();
    expect(DEFAULT_CONFIG.provider.openaiModel).toBeDefined();
    expect(DEFAULT_CONFIG.repo.path).toBe("/workspace");
    expect(DEFAULT_CONFIG.shiftLeft?.maxRetries).toBe(2);
    expect(DEFAULT_CONFIG.git?.branchPrefix).toBe("agent/");
    expect(DEFAULT_CONFIG.git?.commitMessagePrefix).toBe("[agent]");
    expect(DEFAULT_CONFIG.git?.autoPush).toBe(true);
    expect(DEFAULT_CONFIG.git?.baseBranch).toBe("main");
    expect(DEFAULT_CONFIG.fileEditing?.writeThresholdLines).toBe(250);
  });
});

// ─── loadConfig() ─────────────────────────────────────────────────────────────

describe("loadConfig()", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = join(tmpdir(), `config-test-${Date.now()}`);
    await mkdir(tmpDir, { recursive: true });
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it("loads a valid minimal config and fills defaults", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "my-agent", maxTokensPerRun: 100_000, maxCostPerRunUsd: 1.0, timeoutSeconds: 300 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    });

    const cfg = await loadConfig(configPath);

    // Required fields intact
    expect(cfg.agent.name).toBe("my-agent");
    expect(cfg.agent.maxTokensPerRun).toBe(100_000);
    expect(cfg.provider.default).toBe("anthropic");
    expect(cfg.repo.testCommand).toBe("vitest run");

    // Defaults applied for missing optional fields
    expect(cfg.git?.branchPrefix).toBe("agent/");
    expect(cfg.shiftLeft?.maxRetries).toBe(2);
    expect(cfg.fileEditing?.writeThresholdLines).toBe(250);
  });

  it("respects explicit values over defaults", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "custom-agent", maxTokensPerRun: 50_000, maxCostPerRunUsd: 0.5, timeoutSeconds: 120 },
      provider: { default: "openai" },
      repo: { path: "/code", language: "python", testCommand: "pytest", lintCommand: "ruff check" },
      git: { branchPrefix: "bot/", autoPush: false, baseBranch: "develop", commitMessagePrefix: "[bot]" },
      shiftLeft: { maxRetries: 5 },
    });

    const cfg = await loadConfig(configPath);

    expect(cfg.git?.branchPrefix).toBe("bot/");
    expect(cfg.git?.autoPush).toBe(false);
    expect(cfg.git?.baseBranch).toBe("develop");
    expect(cfg.shiftLeft?.maxRetries).toBe(5);
    expect(cfg.provider.default).toBe("openai");
  });

  it("throws when config file does not exist", async () => {
    await expect(loadConfig(join(tmpDir, "nonexistent.mjs"))).rejects.toThrow(/not found|no such file|ENOENT/i);
  });

  it("throws with a validation error when maxTokensPerRun is 0", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 0, maxCostPerRunUsd: 1.0, timeoutSeconds: 300 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/maxTokensPerRun/);
  });

  it("throws with a validation error when timeoutSeconds is 0", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 100_000, maxCostPerRunUsd: 1.0, timeoutSeconds: 0 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/timeoutSeconds/);
  });

  it("throws with a validation error when testCommand is empty", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 100_000, maxCostPerRunUsd: 1.0, timeoutSeconds: 300 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "", lintCommand: "eslint" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/testCommand/);
  });

  it("throws with a validation error when lintCommand is empty", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 100_000, maxCostPerRunUsd: 1.0, timeoutSeconds: 300 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/lintCommand/);
  });

  it("throws with a validation error when provider is unsupported", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 100_000, maxCostPerRunUsd: 1.0, timeoutSeconds: 300 },
      provider: { default: "gemini" },
      repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/provider/i);
  });

  it("includes all validation errors in the thrown message", async () => {
    const configPath = await writeConfigFile(tmpDir, {
      agent: { name: "bad", maxTokensPerRun: 0, maxCostPerRunUsd: 1.0, timeoutSeconds: 0 },
      provider: { default: "anthropic" },
      repo: { path: "/workspace", language: "typescript", testCommand: "", lintCommand: "" },
    });
    await expect(loadConfig(configPath)).rejects.toThrow(/maxTokensPerRun/);
  });
});

// ─── mergeCliOverrides() ──────────────────────────────────────────────────────

describe("mergeCliOverrides()", () => {
  const base: AgentConfig = {
    agent: { name: "base", maxTokensPerRun: 200_000, maxCostPerRunUsd: 2.0, timeoutSeconds: 600 },
    provider: { default: "anthropic", anthropicModel: "claude-sonnet-4-20250514" },
    repo: { path: "/workspace", language: "typescript", testCommand: "vitest run", lintCommand: "eslint" },
    shiftLeft: { maxRetries: 2 },
    git: { branchPrefix: "agent/", autoPush: true, baseBranch: "main", commitMessagePrefix: "[agent]" },
    fileEditing: { writeThresholdLines: 250 },
    security: { domainAllowlist: [] },
    extensions: {},
    context: {},
  };

  it("returns config unchanged when no overrides provided", () => {
    const result = mergeCliOverrides(base, {});
    expect(result.provider.default).toBe("anthropic");
    expect(result.agent.maxTokensPerRun).toBe(200_000);
  });

  it("overrides provider", () => {
    const result = mergeCliOverrides(base, { provider: "openai" });
    expect(result.provider.default).toBe("openai");
  });

  it("overrides model", () => {
    const result = mergeCliOverrides(base, { provider: "anthropic", model: "claude-3-haiku-20240307" });
    expect(result.provider.anthropicModel).toBe("claude-3-haiku-20240307");
  });

  it("overrides maxTokens", () => {
    const result = mergeCliOverrides(base, { maxTokens: 50_000 });
    expect(result.agent.maxTokensPerRun).toBe(50_000);
  });

  it("overrides maxRetries", () => {
    const result = mergeCliOverrides(base, { maxRetries: 5 });
    expect(result.shiftLeft?.maxRetries).toBe(5);
  });

  it("overrides timeout", () => {
    const result = mergeCliOverrides(base, { timeout: 120 });
    expect(result.agent.timeoutSeconds).toBe(120);
  });

  it("does not mutate the original config", () => {
    const original = base.agent.maxTokensPerRun;
    mergeCliOverrides(base, { maxTokens: 1 });
    expect(base.agent.maxTokensPerRun).toBe(original);
  });
});
