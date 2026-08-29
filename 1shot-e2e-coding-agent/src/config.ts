/**
 * src/config.ts — Configuration loading, defaulting, and validation.
 *
 * Exports:
 *  - DEFAULT_CONFIG: Sensible defaults for all optional AgentConfig fields
 *  - loadConfig(configPath): Dynamically imports a pi-agent.config file,
 *    deep-merges with defaults, validates, and throws on error.
 *  - mergeCliOverrides(config, overrides): Returns a new config with CLI flags applied.
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { validateAgentConfig } from "./types.js";
import type { AgentConfig } from "./types.js";

// ─── Defaults ─────────────────────────────────────────────────────────────────

export const DEFAULT_CONFIG: AgentConfig = {
  agent: {
    name: "1shot-agent",
    maxTokensPerRun: 200_000,
    maxCostPerRunUsd: 2.0,
    timeoutSeconds: 600,
  },
  provider: {
    default: "anthropic",
    anthropicModel: "claude-sonnet-4-20250514",
    openaiModel: "gpt-4.1",
  },
  repo: {
    path: "/workspace",
    language: "typescript",
    testCommand: "",
    lintCommand: "",
  },
  shiftLeft: {
    maxRetries: 2,
    runLintBeforePush: true,
    runTypeCheckBeforePush: true,
    runTargetedTests: true,
  },
  git: {
    branchPrefix: "agent/",
    commitMessagePrefix: "[agent]",
    autoPush: true,
    baseBranch: "main",
  },
  fileEditing: {
    writeThresholdLines: 250,
  },
  security: {
    domainAllowlist: [],
  },
  context: {
    repoMapMaxTokens: 5_000,
    searchResultsMaxTokens: 15_000,
    embeddingModel: "all-MiniLM-L6-v2",
  },
  extensions: {},
};

// ─── Deep merge helper ────────────────────────────────────────────────────────

function deepMerge<T extends Record<string, unknown>>(
  base: T,
  override: Partial<T>,
): T {
  const result = { ...base };
  for (const key of Object.keys(override) as (keyof T)[]) {
    const ov = override[key];
    const bv = base[key];
    if (
      ov !== null &&
      typeof ov === "object" &&
      !Array.isArray(ov) &&
      bv !== null &&
      typeof bv === "object" &&
      !Array.isArray(bv)
    ) {
      result[key] = deepMerge(
        bv as Record<string, unknown>,
        ov as Record<string, unknown>,
      ) as T[keyof T];
    } else if (ov !== undefined) {
      result[key] = ov as T[keyof T];
    }
  }
  return result;
}

// ─── loadConfig ───────────────────────────────────────────────────────────────

/**
 * Dynamically import a pi-agent.config file (`.ts` via tsx, or `.mjs`),
 * deep-merge with DEFAULT_CONFIG, validate, and return the final AgentConfig.
 *
 * Throws if:
 *  - The file does not exist
 *  - The file has no default export
 *  - Any validation rule is violated (all errors joined in one message)
 */
export async function loadConfig(configPath: string): Promise<AgentConfig> {
  const absPath = resolve(configPath);

  if (!existsSync(absPath)) {
    throw new Error(`Config file not found: ${absPath} (ENOENT)`);
  }

  // Dynamic import via file URL works for both .mjs and .ts (when tsx is the loader)
  const fileUrl = pathToFileURL(absPath).href;
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  const mod = await import(fileUrl);
  // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
  const userConfig = (mod.default ?? mod) as Partial<AgentConfig>;

  if (!userConfig || typeof userConfig !== "object") {
    throw new Error(
      `Config file must export a default object: ${absPath}`,
    );
  }

  // Deep-merge user config over defaults
  const merged = deepMerge(DEFAULT_CONFIG as unknown as Record<string, unknown>, userConfig as unknown as Record<string, unknown>) as unknown as AgentConfig;

  // Validate and throw if there are any errors
  const errors = validateAgentConfig(merged);
  if (errors.length > 0) {
    throw new Error(
      `Invalid configuration in ${absPath}:\n  - ${errors.join("\n  - ")}`,
    );
  }

  return merged;
}

// ─── CLI override shape ───────────────────────────────────────────────────────

export interface CliOverrides {
  provider?: string;
  model?: string;
  maxTokens?: number;
  maxRetries?: number;
  timeout?: number;
}

// ─── mergeCliOverrides ────────────────────────────────────────────────────────

/**
 * Apply CLI flag overrides on top of a loaded AgentConfig.
 * Returns a new config object — the original is never mutated.
 */
export function mergeCliOverrides(
  config: AgentConfig,
  overrides: CliOverrides,
): AgentConfig {
  // Shallow-clone top-level sections that we might modify
  const result: AgentConfig = {
    ...config,
    agent: { ...config.agent },
    provider: { ...config.provider },
    shiftLeft: { ...config.shiftLeft },
  };

  if (overrides.provider !== undefined) {
    result.provider.default = overrides.provider as AgentConfig["provider"]["default"];
  }

  if (overrides.model !== undefined) {
    if ((overrides.provider ?? result.provider.default) === "openai") {
      result.provider.openaiModel = overrides.model;
    } else {
      result.provider.anthropicModel = overrides.model;
    }
  }

  if (overrides.maxTokens !== undefined) {
    result.agent.maxTokensPerRun = overrides.maxTokens;
  }

  if (overrides.maxRetries !== undefined) {
    result.shiftLeft = { ...result.shiftLeft, maxRetries: overrides.maxRetries };
  }

  if (overrides.timeout !== undefined) {
    result.agent.timeoutSeconds = overrides.timeout;
  }

  return result;
}
