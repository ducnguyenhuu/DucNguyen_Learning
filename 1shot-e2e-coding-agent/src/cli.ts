/**
 * src/cli.ts — CLI entry point (FR-001, FR-012, FR-018)
 *
 * Exposes two commands:
 *  - `run`  — execute a coding task end-to-end (FR-001, FR-012)
 *  - `init` — detect language, generate pi-agent.config.ts, create AGENTS.md (FR-018)
 *
 * Exports `createProgram()` so tests can instantiate a fresh Commander instance
 * without triggering process.exit (exitOverride() makes it throw instead).
 */

import { Command } from "commander";
import { access, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { runAgent } from "./runner.js";
import type { Language } from "./types.js";

// ─── Option types ─────────────────────────────────────────────────────────────

export interface CliOptions {
  config: string;
  provider?: string;
  model?: string;
  dryRun: boolean;
  maxRetries?: number;
  maxTokens?: number;
  timeout?: number;
  verbose: boolean;
  outputDir: string;
}

export interface InitOptions {
  language?: Language;
  output: string;
}

// ─── init helpers ──────────────────────────────────────────────────────────────

/** Detect the primary language from well-known project files in cwd. */
async function detectLanguage(cwd: string): Promise<Language> {
  // TypeScript — package.json with typescript devDependency
  try {
    const src = await readFile(join(cwd, "package.json"), "utf-8");
    const pkg = JSON.parse(src) as {
      devDependencies?: Record<string, string>;
      dependencies?: Record<string, string>;
    };
    const hasTs =
      pkg.devDependencies?.["typescript"] !== undefined ||
      pkg.dependencies?.["typescript"] !== undefined;
    return hasTs ? "typescript" : "javascript";
  } catch {
    // not a Node.js project — continue probing
  }

  try { await access(join(cwd, "pyproject.toml")); return "python"; } catch { /* noop */ }
  try { await access(join(cwd, "go.mod")); return "go"; } catch { /* noop */ }
  try { await access(join(cwd, "pom.xml")); return "java"; } catch { /* noop */ }
  try { await access(join(cwd, "build.gradle")); return "java"; } catch { /* noop */ }

  return "typescript"; // sensible fallback
}

/** Read test/lint commands from package.json scripts when present. */
async function detectNodeCommands(cwd: string): Promise<{ test: string; lint: string }> {
  try {
    const src = await readFile(join(cwd, "package.json"), "utf-8");
    const pkg = JSON.parse(src) as { scripts?: Record<string, string> };
    return {
      test: pkg.scripts?.["test"] ?? "npm test",
      lint: pkg.scripts?.["lint"] ?? "eslint .",
    };
  } catch {
    return { test: "npm test", lint: "eslint ." };
  }
}

/** Return sensible default test/lint commands for each language. */
function defaultCommandsForLanguage(lang: Language): { test: string; lint: string } {
  switch (lang) {
    case "python":     return { test: "pytest",          lint: "ruff check --fix" };
    case "go":         return { test: "go test ./...",   lint: "golangci-lint run" };
    case "java":       return { test: "mvn test",        lint: "mvn checkstyle:check" };
    case "typescript": return { test: "vitest run",      lint: "eslint ." };
    case "javascript": return { test: "npm test",        lint: "eslint ." };
  }
}

function generateConfig(lang: Language, testCommand: string, lintCommand: string): string {
  return `import type { AgentConfig } from "@1shot/agent";

const config: AgentConfig = {
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
    language: "${lang}",
    testCommand: "${testCommand}",
    lintCommand: "${lintCommand}",
  },
  shiftLeft: {
    maxRetries: 2,
    runLintBeforePush: true,
    runTypeCheckBeforePush: true,
  },
  git: {
    branchPrefix: "agent/",
    commitMessagePrefix: "[agent]",
    autoPush: true,
    baseBranch: "main",
  },
};

export default config;
`;
}

const AGENTS_MD_TEMPLATE = `# AGENTS.md — Coding Agent Rules

## Coding Conventions
- Follow existing code style and patterns in the repository
- Keep changes minimal and focused on the requested task
- Add comments only where logic is non-obvious

## Testing Rules
- Write tests for every new function or changed behaviour
- Run the full test suite before committing
- Tests must pass before creating a PR

## File Editing Strategy
- Prefer editing existing files over creating new ones
- Use the smallest possible diff to achieve the goal

## Do Not
- Do not modify unrelated files
- Do not add dependencies without explicit instruction
- Do not commit secrets, tokens, or credentials
`;

async function runInit(opts: InitOptions, cwd: string): Promise<void> {
  const lang: Language = opts.language ?? await detectLanguage(cwd);

  let testCommand: string;
  let lintCommand: string;

  if (lang === "typescript" || lang === "javascript") {
    const cmds = await detectNodeCommands(cwd);
    testCommand = cmds.test;
    lintCommand = cmds.lint;
  } else {
    const cmds = defaultCommandsForLanguage(lang);
    testCommand = cmds.test;
    lintCommand = cmds.lint;
  }

  // Write pi-agent.config.ts
  const configPath = resolve(opts.output);
  await writeFile(configPath, generateConfig(lang, testCommand, lintCommand), "utf-8");
  console.log(`✓ Created ${configPath}`);

  // Create AGENTS.md only if it doesn't already exist
  const agentsPath = join(cwd, "AGENTS.md");
  let agentsExists = false;
  try { await access(agentsPath); agentsExists = true; } catch { /* absent */ }

  if (!agentsExists) {
    await writeFile(agentsPath, AGENTS_MD_TEMPLATE, "utf-8");
    console.log(`✓ Created ${agentsPath}`);
  } else {
    console.log(`  AGENTS.md already exists — skipping`);
  }
}

// ─── Program factory ──────────────────────────────────────────────────────────

/**
 * Build and return a configured Commander program.
 * Calls `.exitOverride()` so Commander throws on errors instead of calling
 * `process.exit()` — this makes the CLI unit-testable.
 */
export function createProgram(): Command {
  const program = new Command();

  program
    .name("duc-e2e-agent")
    .description("One-shot end-to-end coding agent powered by Pi SDK")
    .exitOverride();

  program
    .command("run")
    .description("Execute a coding task end-to-end")
    .argument("<task>", "Plain-text description of the coding task")
    .option("-c, --config <path>", "Path to configuration file", "./pi-agent.config.ts")
    .option("-p, --provider <provider>", "LLM provider override (anthropic | openai)")
    .option("-m, --model <model>", "Model name override")
    .option("--dry-run", "Show plan without executing changes", false)
    .option("--max-retries <n>", "Override max retry count", (v) => parseInt(v, 10))
    .option("--max-tokens <n>", "Override token budget", (v) => parseInt(v, 10))
    .option("--timeout <n>", "Override timeout in seconds", (v) => parseInt(v, 10))
    .option("-v, --verbose", "Enable verbose logging", false)
    .option("--output-dir <dir>", "Directory for run artifacts", "./runs/")
    .exitOverride()
    .action(async (task: string, opts: CliOptions) => {
      await runAgent(task, opts);
    });

  program
    .command("init")
    .description("Initialize pi-agent.config.ts and AGENTS.md for the target repository")
    .option("-l, --language <lang>", "Target repo language (typescript|javascript|python|go|java)")
    .option("-o, --output <path>", "Config output path", "./pi-agent.config.ts")
    .exitOverride()
    .action(async (opts: InitOptions) => {
      await runInit(opts, process.cwd());
    });

  return program;
}

// ─── Entry point ──────────────────────────────────────────────────────────────

// Only parse when run directly (not imported by tests)
const isMain =
  typeof process !== "undefined" &&
  process.argv[1] !== undefined &&
  (process.argv[1].endsWith("duc-e2e-agent.js") ||
   process.argv[1].endsWith("cli.js") ||
   process.argv[1].endsWith("cli.ts"));

if (isMain) {
  createProgram()
    .parseAsync(process.argv)
    .catch((err: unknown) => {
      if (err instanceof Error) {
        console.error(err.message);
      }
      process.exit(1);
    });
}
