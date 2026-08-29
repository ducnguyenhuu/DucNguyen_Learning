# 1-Shot End-to-End Coding Agent

A one-shot coding agent that takes a plain-text task description, autonomously explores your codebase, writes code, runs tests, and opens a pull request — all without human interaction during the run.

**Think of it like:** You write a Post-it note describing what you want changed, hand it to a robot developer, and get back a PR ready for review.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Extending the Agent](#extending-the-agent)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## How It Works

The agent follows a fixed **9-node Blueprint**:

```
setup → context-gather → plan → implement → lint → test ─► commit → report
                                                      ↑        │
                                                      └─ fix ◄─┘ (if tests fail, up to 2 retries)
```

| Step | Type | What It Does |
|------|------|-------------|
| **setup** | deterministic | Creates a git branch, loads `AGENTS.md` |
| **context-gather** | LLM | Explores the codebase, identifies relevant files |
| **plan** | LLM | Produces a structured change plan |
| **implement** | LLM | Writes code changes following the plan |
| **lint & format** | deterministic | Runs your configured linter |
| **test** | deterministic | Runs your configured test suite |
| **fix-failures** | LLM | Diagnoses and fixes failing tests (up to 2 retries) |
| **commit & push** | deterministic | Commits changes, pushes branch, opens a GitHub PR |
| **report** | deterministic | Writes `report.json` and `metrics.json` artifacts |

---

## Prerequisites

| Requirement | Minimum Version | Check | Install |
|-------------|----------------|-------|---------|
| Node.js | 20+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| Docker | any recent | `docker --version` | [docker.com](https://www.docker.com/) |
| Git | any recent | `git --version` | `brew install git` |
| Anthropic API key | — | — | [console.anthropic.com](https://console.anthropic.com/) |
| GitHub token (optional) | — | `gh auth status` | `gh auth login` |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-user/1shot-e2e-coding-agent.git
cd 1shot-e2e-coding-agent

# 2. Install dependencies
npm install

# 3. Set environment variables
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."          # optional — enables automatic PR creation
```

---

## Configuration

### Auto-generate a config

The `init` command detects your target repo's language and test/lint commands automatically:

```bash
npx duc-e2e-agent init
# or specify manually:
npx duc-e2e-agent init --language typescript --output ./pi-agent.config.ts
```

### Config file reference (`pi-agent.config.ts`)

```typescript
import type { AgentConfig } from "@1shot/agent";

const config: AgentConfig = {
  agent: {
    name: "1shot-agent",
    maxTokensPerRun: 200_000,   // Token budget ceiling (SC-011: stay under 200K)
    maxCostPerRunUsd: 2.0,      // Cost ceiling in USD (SC-005: stay under $2)
    timeoutSeconds: 600,        // 10-minute run timeout (SC-012)
  },

  provider: {
    default: "anthropic",                         // "anthropic" | "openai"
    anthropicModel: "claude-sonnet-4-20250514",
    openaiModel: "gpt-4.1",                       // used if default is "openai"
  },

  repo: {
    path: "/workspace",         // Path inside Docker (don't change)
    language: "typescript",     // "typescript" | "javascript" | "python" | "go" | "java"
    testCommand: "vitest run",  // Command to run your tests
    lintCommand: "eslint .",    // Command to run your linter
  },

  shiftLeft: {
    maxRetries: 2,              // Max fix-failures retry cycles (SC-013)
    runLintBeforePush: true,
    runTypeCheckBeforePush: true,
  },

  git: {
    branchPrefix: "agent/",
    commitMessagePrefix: "[agent]",
    autoPush: true,             // Set false to skip push + PR creation
    baseBranch: "main",
  },
};

export default config;
```

### Supported languages

| Language | Auto-detected from | Default test command | Default lint command |
|----------|-------------------|---------------------|---------------------|
| TypeScript | `package.json` + typescript devDep | `vitest run` | `eslint .` |
| JavaScript | `package.json` (no TS) | `npm test` | `eslint .` |
| Python | `pyproject.toml` | `pytest` | `ruff check --fix` |
| Go | `go.mod` | `go test ./...` | `golangci-lint run` |
| Java | `pom.xml` / `build.gradle` | `mvn test` | `mvn checkstyle:check` |

---

## Usage

### Basic run

```bash
npx duc-e2e-agent run "Add input validation to the createUser endpoint — reject empty name and invalid email"
```

### Common task patterns

```bash
# Bug fix
npx duc-e2e-agent run "Fix TypeError in parseConfig when config file is empty"

# Add a feature
npx duc-e2e-agent run "Add a health-check endpoint GET /api/health returning uptime and version"

# Write tests
npx duc-e2e-agent run "Add unit tests for the auth/token.ts module covering expiry edge cases"

# Refactor
npx duc-e2e-agent run "Extract duplicate DB connection setup into a shared helper in src/db/connection.ts"

# Type annotations
npx duc-e2e-agent run "Add TypeScript type annotations to all functions in src/utils/strings.ts"
```

### CLI flags

```
npx duc-e2e-agent run <task> [options]

Options:
  -c, --config <path>       Config file path (default: ./pi-agent.config.ts)
  -p, --provider <name>     LLM provider override: anthropic | openai
  -m, --model <name>        Model name override
  --dry-run                 Show plan without executing changes
  --max-retries <n>         Override shiftLeft.maxRetries
  --max-tokens <n>          Override agent.maxTokensPerRun
  --timeout <n>             Override agent.timeoutSeconds (seconds)
  -v, --verbose             Enable verbose logging
  --output-dir <dir>        Artifacts directory (default: ./runs/)
```

```
npx duc-e2e-agent init [options]

Options:
  -l, --language <lang>     Language override (auto-detected if omitted)
  -o, --output <path>       Config output path (default: ./pi-agent.config.ts)
```

### Dry-run mode

Preview what the agent plans to do without writing any code or pushing:

```bash
npx duc-e2e-agent run "Add logging to all API endpoints" --dry-run
```

### Switch providers

```bash
# Use OpenAI instead of Anthropic for this run
npx duc-e2e-agent run "Fix the pagination bug" --provider openai --model gpt-4.1
```

### Run artifacts

After each run, artifacts are written to `./runs/<timestamp>/`:

```
runs/
└── 2026-03-29T14-30-00/
    ├── report.json     ← full run report with metrics
    └── metrics.json    ← token usage, cost, duration, PR URL
```

---

## Architecture

### Directory structure

```
1shot-e2e-coding-agent/
├── src/
│   ├── cli.ts                 # CLI entry point (commander) — run + init commands
│   ├── runner.ts              # runAgent() — wires config + blueprint
│   ├── orchestrator.ts        # BlueprintRunner — sequences nodes with error fallback + timeout
│   ├── types.ts               # All shared TypeScript types
│   ├── config.ts              # loadConfig() + mergeCliOverrides()
│   ├── adapters/
│   │   └── pi-sdk.ts          # Pi SDK wrapper (createSession, runPrompt)
│   ├── blueprints/
│   │   └── standard.ts        # 9-node standard blueprint with dry-run support
│   ├── steps/                 # One file per blueprint node
│   ├── context/               # Repo map, embeddings, chunker, token budget
│   ├── reporting/             # run-report, pr-summary, transcript
│   └── security/              # Path validator, domain allowlist
├── extensions/                # Pi Extensions (custom LLM tools)
│   ├── context-tools.ts       # repo_map, semantic_search, symbol_nav, dep_graph
│   └── quality-tools.ts       # run_test, run_lint
├── prompts/                   # System prompt templates per agent node
├── skills/                    # Pi Skills (SKILL.md instruction files for the LLM)
│   ├── explore-codebase/
│   ├── implement-feature/
│   └── fix-failures/
├── scripts/
│   ├── benchmark.ts           # SC metrics benchmark (10 representative tasks)
│   └── warm-cache.ts          # Pre-warm embeddings index
├── src/templates/
│   └── AGENTS.md              # Template created by `init` in target repos
└── tests/                     # vitest test suite (unit + integration)
```

### Key design decisions

**BlueprintRunner** (`src/orchestrator.ts`) — simple while-loop over a `Map<id, node>`. No framework. Each node returns a `StepResult` and a `next()` function that decides routing. Error fallback routes any failing node to the `report` node so artifacts are always written.

**Deterministic vs agent nodes** — git/lint/test steps are plain async functions. Only context-gather, plan, implement, and fix-failures invoke the Pi SDK. This means failures in the reliable steps never require LLM retries.

**Shift-left feedback loop** — lint and test run *inside the container* before pushing. If tests fail, `fix-failures` runs (up to `maxRetries` cycles). Only when tests pass does the agent commit and push.

**Token budget** — hard ceiling at `maxTokensPerRun`. Each context layer (repo map, search results, full files) has a percentage allocation. The budget manager tracks consumption across all nodes.

**Security** — `PathValidator` restricts all file I/O to the workspace directory. A domain allowlist proxy gates outbound HTTP in agent nodes.

---

## Extending the Agent

### Add a custom Pi Extension (new LLM tool)

Create a new file in `extensions/`:

```typescript
// extensions/my-tool.ts
import type { ToolDefinition } from "../src/types.js";

export function createMyExtension() {
  const toolDefinitions: ToolDefinition[] = [
    {
      name: "my_tool",
      description: "Does something useful",
      inputSchema: { type: "object", properties: { input: { type: "string" } }, required: ["input"] },
      execute: async ({ input }) => ({ result: `processed: ${input}` }),
    },
  ];
  return { toolDefinitions };
}
```

Then pass `toolDefinitions` to the relevant step's `runPrompt()` call.

### Add a Pi Skill (LLM instruction file)

Create a `SKILL.md` in a new `skills/<name>/` directory following the pattern in `skills/explore-codebase/SKILL.md`. Skills are markdown instruction files that guide the LLM through a specific workflow.

### Add a new blueprint node

```typescript
runner.addNode({
  id: "my_node",
  type: "deterministic",            // or "agent" if it uses the Pi SDK
  execute: (ctx) => myStep(ctx),
  next: (result) => result.status === "passed" ? "next_node" : null,
});
```

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| `ANTHROPIC_API_KEY not set` | Missing env var | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Docker build fails | Docker not running | Start Docker Desktop |
| Tests fail in container | Commands differ from local | Check `repo.testCommand` in config |
| Agent loops without converging | Task too broad or ambiguous | Use a more specific task description |
| Token budget exceeded | Large codebase or complex task | Increase `agent.maxTokensPerRun` |
| PR not created | Missing `GITHUB_TOKEN` | `export GITHUB_TOKEN=ghp_...` |
| "unknown command 'init'" | Old build | `npm run build && npm link` |
| Run times out | Slow test suite | Increase `agent.timeoutSeconds` |

### Debug a run

```bash
# Verbose logs
npx duc-e2e-agent run "..." --verbose

# Check the last run's artifacts
cat runs/$(ls -t runs/ | head -1)/report.json | jq .

# Benchmark in dry-run mode (no API key needed)
npx tsx scripts/benchmark.ts --dry-run
```

---

## Development

### Run the test suite

```bash
npm test                   # run all 818 tests
npm test -- --watch        # watch mode
npm test -- <pattern>      # run matching tests only
```

### Project conventions

- **TDD**: tests are written before implementation — every source file has a corresponding test file in `tests/`
- **Imports**: use `.js` extensions in imports (Node.js ESM requirement)
- **Mocks**: use `vi.hoisted()` for mock variables referenced inside `vi.mock()` factories
- **No `process.exit()`**: CLI uses Commander's `exitOverride()` so tests can call `parseAsync()` without killing the process

### Run the benchmark

```bash
# Dry-run (synthetic data, no API key needed)
npx tsx scripts/benchmark.ts --dry-run

# Live (requires ANTHROPIC_API_KEY and a configured repo)
npx tsx scripts/benchmark.ts --config ./pi-agent.config.ts
```

### Pre-warm the embeddings index

```bash
./scripts/warm-cache.sh --workspace /path/to/your/repo
```

---

## Success Criteria

The agent is designed to meet these benchmarks over 20 representative tasks:

| Metric | Target |
|--------|--------|
| One-shot success rate | ≥ 50% |
| Test suite pass rate | ≥ 80% |
| Retry rate | < 30% |
| Tokens per run | < 200K |
| Cost per run | < $2.00 |
| Average run time | < 10 min |

Run `npx tsx scripts/benchmark.ts --dry-run` to check current metrics against these targets.

---

## License

MIT
