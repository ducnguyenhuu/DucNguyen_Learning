/**
 * src/types.ts — All shared TypeScript interfaces, types, constants, and helpers.
 *
 * This is the single source of truth for the data model (see specs/data-model.md).
 * Every other module imports from here — nothing else re-exports these types.
 *
 * Also exports:
 *  - Type guard functions (isRunStatus, isProvider, isLanguage)
 *  - Validation helpers  (validateAgentConfig, validateTask)
 *  - Derivation helpers  (createTaskSlug, createLayerBudgets)
 */

// ─── Constants (used by type guards and validation) ───────────────────────────

/** All valid RunStatus values. Used by isRunStatus() and exhaustiveness checks. */
export const RUN_STATUS = ["pending", "running", "succeeded", "failed", "timeout"] as const;

/** All supported LLM provider identifiers. */
export const PROVIDERS = ["anthropic", "openai"] as const;

/** All supported target-repository languages. */
export const LANGUAGES = ["python", "typescript", "javascript", "go", "java"] as const;

// ─── Primitive types ──────────────────────────────────────────────────────────

export type RunStatus = (typeof RUN_STATUS)[number];
export type Provider = (typeof PROVIDERS)[number];
export type Language = (typeof LANGUAGES)[number];

// ─── Type guards ──────────────────────────────────────────────────────────────

export function isRunStatus(value: unknown): value is RunStatus {
  return typeof value === "string" && (RUN_STATUS as readonly string[]).includes(value);
}

export function isProvider(value: unknown): value is Provider {
  return typeof value === "string" && (PROVIDERS as readonly string[]).includes(value);
}

export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && (LANGUAGES as readonly string[]).includes(value);
}

// ─── AgentConfig (root configuration object) ──────────────────────────────────

export interface AgentConfig {
  agent: {
    name: string;
    /** Token budget ceiling. Must be > 0. Default: 200_000 */
    maxTokensPerRun: number;
    /** Cost ceiling in USD. Default: 2.00 */
    maxCostPerRunUsd: number;
    /** Max run duration in seconds. Must be > 0. Default: 600 */
    timeoutSeconds: number;
  };
  provider: {
    /** LLM provider ID — must be one of PROVIDERS. */
    default: Provider;
    anthropicModel?: string;
    openaiModel?: string;
  };
  repo: {
    /** Path to target repo inside the container. Default: "/workspace" */
    path: string;
    language: Language;
    /** Command to run tests — must not be empty. */
    testCommand: string;
    /** Command to run linter — must not be empty. */
    lintCommand: string;
    formatCommand?: string;
    typeCheckCommand?: string;
  };
  shiftLeft?: {
    maxRetries?: number;
    runLintBeforePush?: boolean;
    runTypeCheckBeforePush?: boolean;
    runTargetedTests?: boolean;
  };
  git?: {
    branchPrefix?: string;
    commitMessagePrefix?: string;
    autoPush?: boolean;
    baseBranch?: string;
  };
  fileEditing?: {
    writeThresholdLines?: number;
  };
  security?: {
    domainAllowlist?: string[];
  };
  context?: {
    repoMapMaxTokens?: number;
    searchResultsMaxTokens?: number;
    embeddingModel?: string;
  };
  extensions?: {
    contextTools?: string;
    qualityTools?: string;
    webTools?: string;
  };
}

// ─── Task ─────────────────────────────────────────────────────────────────────

/** A plain-text description of the coding work to perform. Immutable after creation. */
export interface Task {
  /** Plain-text task description (max 500 chars). */
  description: string;
  /** URL-safe slug derived from description — used for branch naming. */
  slug: string;
  /** ISO 8601 timestamp when the task was received. */
  timestamp: string;
}

// ─── Supporting types ─────────────────────────────────────────────────────────

export interface FileChange {
  path: string;
  action: "modified" | "created" | "deleted";
  linesAdded: number;
  linesRemoved: number;
}

export interface TestResult {
  passed: number;
  failed: number;
  skipped: number;
  /** Duration in milliseconds. */
  duration: number;
}

export interface NodeResult {
  nodeId: string;
  type: "deterministic" | "agent";
  status: "passed" | "failed" | "error" | "skipped";
  /** Duration in milliseconds. */
  duration: number;
  tokensUsed: number;
}

// ─── LayerBudgets + TokenBudget ───────────────────────────────────────────────

/**
 * Per-layer token allocation derived from maxTokens.
 *
 *  L0 repoMap       —  5%  — repo map + agent rules + task description (setup)
 *  L1 searchResults — 15%  — keyword search, symbol nav, dep graph (context gather)
 *  L2 fullFiles     — 40%  — full content of files to modify (implement)
 *  L3 supplementary — 10%  — git blame, co-change history, examples (if budget remains)
 *  reserved         — 30%  — system prompts, chain-of-thought, output generation
 */
export interface LayerBudgets {
  repoMap: number;
  searchResults: number;
  fullFiles: number;
  supplementary: number;
  reserved: number;
}

export interface TokenBudget {
  maxTokens: number;
  consumed: number;
  /** Derived: maxTokens - consumed */
  remaining: number;
  layerBudgets: LayerBudgets;
}

// ─── StepResult ───────────────────────────────────────────────────────────────

export interface StepResult {
  status: "passed" | "failed" | "error";
  /** Tokens consumed (agent nodes only). */
  tokensUsed?: number;
  /** Arbitrary data forwarded to subsequent nodes. */
  data?: Record<string, unknown>;
  error?: string;
}

// ─── RunContext ────────────────────────────────────────────────────────────────

/**
 * Shared mutable state threaded through all blueprint nodes during a run.
 * Each node reads from it and may append to it.
 */
export interface RunContext {
  task: Task;
  config: AgentConfig;
  workspacePath: string;
  branch: string;
  repoMap: string;
  relevantFiles: string[];
  /** Agent's understanding of the codebase (populated by context_gather). */
  understanding: string;
  /** Generated change plan (populated by plan node). */
  plan: string;
  retryCount: number;
  /**
   * Hashes of error outputs seen in previous fix-failures attempts.
   * Used for oscillation detection — if the same hash appears again, abort.
   */
  errorHashes: string[];
  tokenBudget: TokenBudget;
  /** Structured logger (pino). Using unknown here to avoid coupling to pino types. */
  logger: unknown;
  /**
   * AbortSignal for per-run cancellation.
   * Set by BlueprintRunner.run() from config.agent.timeoutSeconds (T073).
   * Step functions may check this to bail out early.
   */
  abortSignal?: AbortSignal;
  /**
   * When true, destructive steps (implement / lint / test / commit) are skipped.
   * Populated by the CLI --dry-run flag (T074).
   */
  dryRun?: boolean;
}

// ─── Blueprint types ──────────────────────────────────────────────────────────

export interface BlueprintNode {
  id: string;
  type: "deterministic" | "agent";
  execute: (ctx: RunContext) => Promise<StepResult>;
  /** Returns next node ID or null to end the run. */
  next: (result: StepResult) => string | null;
}

export interface Blueprint {
  name: string;
  entryNodeId: string;
  nodes: Map<string, BlueprintNode>;
  maxRetries: number;
}

// ─── Run ──────────────────────────────────────────────────────────────────────

export interface Run {
  /** Unique run ID: ISO 8601 timestamp e.g. "2026-03-13T14-30-00" */
  id: string;
  task: Task;
  config: AgentConfig;
  status: RunStatus;
  branch: string;
  startedAt: Date;
  completedAt: Date | null;
  nodes: NodeResult[];
  totalTokens: number;
  totalCostUsd: number;
  /** Path to run artifacts directory: runs/{id}/ */
  artifactsDir: string;
}

// ─── RunReport ────────────────────────────────────────────────────────────────

export interface RunReport {
  runId: string;
  status: RunStatus;
  task: string;
  branch: string;
  prUrl: string | null;
  filesChanged: FileChange[];
  linesAdded: number;
  linesRemoved: number;
  testResults: TestResult;
  lintClean: boolean;
  totalTokens: number;
  estimatedCostUsd: number;
  durationSeconds: number;
  nodeResults: NodeResult[];
}

// ─── PRSummary ────────────────────────────────────────────────────────────────

export interface PRSummary {
  /** PR title: "[agent] {task description}" */
  title: string;
  /** Structured markdown body (see cli-contract.md). */
  body: string;
  baseBranch: string;
  headBranch: string;
}

// ─── Session (Pi SDK) ─────────────────────────────────────────────────────────

/**
 * Configuration bag passed to createAgentSession().
 * The runtime session object is owned by Pi SDK — we only configure it.
 */
export interface SessionConfig {
  systemPrompt: string;
  tools: string[];
  extensions: string[];
  provider: Provider;
  model: string;
  /** Custom Pi SDK ToolDefinition objects (e.g. from context-tools extension). */
  customTools?: unknown[];
}

// ─── Validation helpers ───────────────────────────────────────────────────────

/**
 * Validate an AgentConfig object.
 * Returns an array of human-readable error strings.
 * An empty array means the config is valid.
 */
export function validateAgentConfig(config: AgentConfig): string[] {
  const errors: string[] = [];

  if (config.agent.maxTokensPerRun <= 0) {
    errors.push(
      `agent.maxTokensPerRun must be > 0, got ${config.agent.maxTokensPerRun}`,
    );
  }

  if (config.agent.timeoutSeconds <= 0) {
    errors.push(
      `agent.timeoutSeconds must be > 0, got ${config.agent.timeoutSeconds}`,
    );
  }

  if (!config.repo.testCommand || config.repo.testCommand.trim() === "") {
    errors.push("repo.testCommand must not be empty");
  }

  if (!config.repo.lintCommand || config.repo.lintCommand.trim() === "") {
    errors.push("repo.lintCommand must not be empty");
  }

  if (!isProvider(config.provider.default)) {
    errors.push(
      `provider.default must be one of [${PROVIDERS.join(", ")}], got "${String(config.provider.default)}"`,
    );
  }

  return errors;
}

/**
 * Validate a task description string.
 * Returns an array of human-readable error strings.
 */
export function validateTask(description: string): string[] {
  const errors: string[] = [];

  if (!description || description.trim() === "") {
    errors.push("Task description must not be empty");
  }

  if (description.length > 500) {
    errors.push(
      `Task description must not exceed 500 characters (got ${description.length})`,
    );
  }

  return errors;
}

// ─── Derivation helpers ───────────────────────────────────────────────────────

/**
 * Derive a URL-safe git-branch slug from a task description.
 *
 * Rules:
 *  - Lowercase
 *  - Alphanumerics and hyphens only
 *  - Multiple non-alphanumeric runs → single hyphen
 *  - No leading or trailing hyphens
 *  - Maximum 60 characters
 */
export function createTaskSlug(description: string): string {
  return description
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-") // non-alphanumeric runs → hyphen
    .replace(/^-+|-+$/g, "")      // strip leading/trailing hyphens
    .slice(0, 60)
    .replace(/-+$/, "");          // strip trailing hyphen introduced by slice
}

/**
 * Compute per-layer token budgets from a maxTokens ceiling.
 *
 * Allocations (per data-model.md):
 *  L0 repoMap        5%
 *  L1 searchResults 15%
 *  L2 fullFiles     40%
 *  L3 supplementary 10%
 *  reserved         30%
 *
 * Uses Math.floor to guarantee total never exceeds maxTokens.
 */
export function createLayerBudgets(maxTokens: number): LayerBudgets {
  return {
    repoMap: Math.floor(maxTokens * 0.05),
    searchResults: Math.floor(maxTokens * 0.15),
    fullFiles: Math.floor(maxTokens * 0.40),
    supplementary: Math.floor(maxTokens * 0.10),
    reserved: Math.floor(maxTokens * 0.30),
  };
}
