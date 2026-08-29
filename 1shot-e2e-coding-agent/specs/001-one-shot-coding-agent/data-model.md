# Data Model: One-Shot End-to-End Coding Agent

**Date**: 2026-03-13  
**Spec**: [spec.md](spec.md)  
**Plan**: [plan.md](plan.md)

## Entity Relationship Overview

```
┌──────────┐     1:N      ┌──────────┐     1:N     ┌──────────────┐
│  Config  │─────────────►│   Run    │────────────►│   Session    │
│          │              │          │              │ (Pi SDK)     │
└──────────┘              └────┬─────┘              └──────┬───────┘
                               │                           │
                          1:1  │                      1:N  │
                               ▼                           ▼
                          ┌──────────┐              ┌──────────────┐
                          │ Blueprint│              │  Tool Call   │
                          │          │              │              │
                          └────┬─────┘              └──────────────┘
                               │
                          1:N  │
                               ▼
                          ┌──────────┐
                          │   Node   │
                          │(Step)    │
                          └──────────┘
```

## Entities

### 1. AgentConfig

The root configuration object loaded from `pi-agent.config.ts`. Defines all agent behavior.

**Why this exists**: A single configuration object makes the agent reusable across different target repositories without code changes (FR-018, SC-008).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent.name` | string | yes | Human-readable agent name |
| `agent.maxTokensPerRun` | number | yes | Token budget ceiling (FR-013). Default: 200,000 |
| `agent.maxCostPerRunUsd` | number | yes | Cost ceiling. Default: 2.00 |
| `agent.timeoutSeconds` | number | yes | Max run duration. Default: 600 |
| `provider.default` | string | yes | LLM provider ID: "anthropic" \| "openai" |
| `provider.anthropicModel` | string | no | Anthropic model name. Default: "claude-sonnet-4-20250514" |
| `provider.openaiModel` | string | no | OpenAI model name. Default: "gpt-4.1" |
| `repo.path` | string | yes | Path to target repo inside container. Default: "/workspace" |
| `repo.language` | string | yes | Primary language: "python" \| "typescript" \| "javascript" \| "go" \| "java" |
| `repo.testCommand` | string | yes | Command to run tests (e.g., "pytest", "vitest run") |
| `repo.lintCommand` | string | yes | Command to run linter (e.g., "ruff check --fix", "eslint --fix") |
| `repo.formatCommand` | string | no | Command to format code (e.g., "ruff format", "prettier --write") |
| `repo.typeCheckCommand` | string | no | Command to type-check (e.g., "mypy", "tsc --noEmit") |
| `context.repoMapMaxTokens` | number | no | Token budget for repo map. Default: 5,000 |
| `context.searchResultsMaxTokens` | number | no | Token budget for search results. Default: 15,000 |
| `context.embeddingModel` | string | no | Local embedding model. Default: "all-MiniLM-L6-v2" |
| `shiftLeft.maxRetries` | number | no | Max retry cycles (FR-008). Default: 2 |
| `shiftLeft.runLintBeforePush` | boolean | no | Default: true |
| `shiftLeft.runTypeCheckBeforePush` | boolean | no | Default: true |
| `shiftLeft.runTargetedTests` | boolean | no | Default: true |
| `git.branchPrefix` | string | no | Branch naming prefix. Default: "agent/" |
| `git.commitMessagePrefix` | string | no | Commit message prefix. Default: "[agent]" |
| `git.autoPush` | boolean | no | Auto-push on success. Default: true |
| `git.baseBranch` | string | no | Base branch for PR. Default: "main" |
| `fileEditing.writeThresholdLines` | number | no | Files ≤ N lines use write; above use edit. Default: 250 |
| `security.domainAllowlist` | string[] | no | Allowed outbound domains (FR-020) |
| `extensions.contextTools` | string | no | Path to context-tools extension |
| `extensions.qualityTools` | string | no | Path to quality-tools extension |
| `extensions.webTools` | string | no | Path to web-tools extension |

**Validation rules**:
- `agent.maxTokensPerRun` must be > 0
- `agent.timeoutSeconds` must be > 0
- `repo.testCommand` and `repo.lintCommand` must not be empty
- `provider.default` must be one of the supported providers

---

### 2. Task

A plain-text description of the coding work to perform. The atomic input to the system.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | yes | Plain-text task description from the user (FR-001) |
| `slug` | string | derived | URL-safe slug derived from description (for branch naming) |
| `timestamp` | string | derived | ISO 8601 timestamp when the task was received |

**Validation rules**:
- `description` must not be empty
- `description` max length: 500 characters

**State transitions**: None — a Task is immutable once created.

---

### 3. Run

A single execution of the agent against a task. The top-level runtime entity.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | derived | Unique run ID: `{timestamp}` (e.g., "2026-03-13T14-30-00") |
| `task` | Task | yes | The task being executed |
| `config` | AgentConfig | yes | Resolved configuration for this run |
| `status` | RunStatus | derived | Current run status |
| `branch` | string | derived | Git branch name: `{branchPrefix}{task.slug}-{timestamp}` |
| `startedAt` | Date | derived | Run start time |
| `completedAt` | Date \| null | derived | Run completion time (null if in progress) |
| `nodes` | NodeResult[] | derived | Results from each executed blueprint node |
| `totalTokens` | number | derived | Sum of tokens across all sessions |
| `totalCostUsd` | number | derived | Estimated cost based on token usage |
| `artifactsDir` | string | derived | Path to run artifacts: `runs/{id}/` |

**RunStatus** (enum):
- `pending` — Run created but not started
- `running` — Currently executing blueprint nodes
- `succeeded` — All nodes completed, PR created
- `failed` — Aborted due to exhausted retries or error
- `timeout` — Exceeded `agent.timeoutSeconds`

**State transitions**:
```
pending → running → succeeded
                  → failed
                  → timeout
```

---

### 4. Blueprint

A Pi SDK graph-based workflow defining the execution flow as an ordered sequence of nodes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Blueprint identifier (e.g., "standard") |
| `entryNodeId` | string | yes | ID of the first node to execute |
| `nodes` | Map<string, BlueprintNode> | yes | All nodes in the blueprint |
| `maxRetries` | number | yes | From config: `shiftLeft.maxRetries` |

**Standard blueprint**: 9 nodes in this sequence:
```
setup → context_gather → plan → implement → lint_and_format → test
                                                                ↓
                                         commit_and_push ← ─ ─ ┤ (if passed)
                                                                ↓
                                         fix_failures ← ─ ─ ─ ─┘ (if failed)
                                              ↓
                                         lint_and_format (retry loop, max N)
```

---

### 5. BlueprintNode (Step/Node)

An individual unit of work within a blueprint.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique node ID within the blueprint |
| `type` | "deterministic" \| "agent" | yes | Whether this node uses an LLM session |
| `execute` | `(ctx: RunContext) => Promise<StepResult>` | yes | The function that performs the work |
| `next` | `(result: StepResult) => string \| null` | yes | Routing function returning next node ID or null |

**Tool scoping per node** (from spec FR-017):

| Node ID | Type | Pi Built-in Tools | Pi Extensions |
|---------|------|-------------------|---------------|
| `setup` | deterministic | — | — |
| `context_gather` | agent | read, grep, find, ls | repo_map, semantic_search, symbol_nav, dependency_graph |
| `plan` | agent | read | (none) |
| `implement` | agent | read, write, edit, bash, grep, find | (none) |
| `lint_and_format` | deterministic | — | — |
| `test` | deterministic | — | — |
| `fix_failures` | agent | read, write, edit, bash, grep | run_test, run_lint |
| `commit_and_push` | deterministic | — | — |
| `report` | deterministic | — | — |

---

### 6. StepResult

The output of a single node execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | "passed" \| "failed" \| "error" | yes | Outcome of this step |
| `tokensUsed` | number | no | Tokens consumed (agent nodes only) |
| `data` | Record<string, any> | no | Arbitrary data to pass to subsequent nodes |
| `error` | string | no | Error message if status is "error" |

---

### 7. RunContext

Shared mutable state passed through all blueprint nodes during a run.

| Field | Type | Description |
|-------|------|-------------|
| `task` | Task | The task being executed |
| `config` | AgentConfig | Resolved configuration |
| `workspacePath` | string | Path to cloned repo in container |
| `branch` | string | Git branch name for this run |
| `repoMap` | string | Generated repo map (populated by setup) |
| `relevantFiles` | string[] | Files relevant to task (populated by context_gather) |
| `understanding` | string | Agent's understanding of the codebase (populated by context_gather) |
| `plan` | string | Generated change plan (populated by plan node) |
| `retryCount` | number | Current retry iteration (0-based) |
| `tokenBudget` | TokenBudget | Remaining token budget tracker |
| `logger` | Logger | Structured logger (pino) |

---

### 8. Session (Pi SDK Session)

An LLM conversation context for an agent-driven node.

**Why this is a Pi SDK object, not our own**: Pi SDK manages session lifecycle, tool dispatch, auto-compaction, and JSONL transcript saving. We configure and invoke it, but don't own the internal state.

| Field | Type | Description |
|-------|------|-------------|
| `systemPrompt` | string | Instructions specific to this node's role |
| `tools` | string[] | Allowed Pi built-in tools |
| `extensions` | string[] | Paths to Pi Extension files to load |
| `provider` | string | LLM provider (from config) |
| `model` | string | Model name (from config) |
| `tokenUsage` | { total: number } | Tokens used in this session |

---

### 9. RunReport

The summary output of a run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `runId` | string | yes | Run identifier |
| `status` | RunStatus | yes | Final run status |
| `task` | string | yes | Original task description |
| `branch` | string | yes | Git branch name |
| `prUrl` | string \| null | yes | Pull request URL (null if failed before PR) |
| `filesChanged` | FileChange[] | yes | List of files changed |
| `linesAdded` | number | yes | Total lines added |
| `linesRemoved` | number | yes | Total lines removed |
| `testResults` | TestResult | yes | Test pass/fail counts |
| `lintClean` | boolean | yes | Whether lint passed |
| `totalTokens` | number | yes | Total tokens consumed |
| `estimatedCostUsd` | number | yes | Estimated cost |
| `durationSeconds` | number | yes | Total wall-clock time |
| `nodeResults` | NodeResult[] | yes | Per-node timing and status |

---

### 10. PRSummary

The description body of the pull request created by the agent.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | yes | PR title: `[agent] {task description}` |
| `body` | string | yes | Structured markdown body |
| `baseBranch` | string | yes | Target branch (from config: `git.baseBranch`) |
| `headBranch` | string | yes | Source branch (run's branch) |

**Body structure**:
```markdown
## Summary
{task description}

## Changes
| File | What Changed | Why |
|------|-------------|-----|
| path/to/file.ts | Added email validation | Task requirement |

## Test Results
- X tests passed, Y failed
- Lint: clean / N issues

## Agent Run
- Tokens: {total}
- Cost: ${estimated}
- Duration: {seconds}s
- Retries: {count}
```

---

### 11. TokenBudget

Tracks and enforces token consumption limits per run.

| Field | Type | Description |
|-------|------|-------------|
| `maxTokens` | number | From config: `agent.maxTokensPerRun` |
| `consumed` | number | Running total of tokens used |
| `remaining` | number | Derived: `maxTokens - consumed` |
| `layerBudgets` | LayerBudgets | Per-layer allocation (see below) |

**LayerBudgets** (derived from `maxTokens`):

| Layer | Field | Default % | Description |
|-------|-------|-----------|-------------|
| L0 | `repoMap` | 5% | Repo map + agent rules + task description (setup node) |
| L1 | `searchResults` | 15% | Keyword search, symbol nav, dependency graph (context gather node) |
| L2 | `fullFiles` | 40% | Full content of files to modify + dependencies (implement node) |
| L3 | `supplementary` | 10% | Git blame, co-change history, examples (if budget remains) |
| Reserved | `reserved` | 30% | System prompts, chain-of-thought, output generation |

**Why layered budgets**: Flat token counting would allow early steps (like context gathering) to consume the entire budget, leaving nothing for implementation. Per-layer allocation ensures each phase of the workflow has guaranteed capacity.

**State transitions**: Only increases (consumed goes up). When `remaining` drops below a threshold (10%), the system enters graceful degradation (shorter context, simpler prompts).

---

## Supporting Types

### FileChange
```typescript
interface FileChange {
  path: string;
  action: "modified" | "created" | "deleted";
  linesAdded: number;
  linesRemoved: number;
}
```

### TestResult
```typescript
interface TestResult {
  passed: number;
  failed: number;
  skipped: number;
  duration: number; // milliseconds
}
```

### NodeResult
```typescript
interface NodeResult {
  nodeId: string;
  type: "deterministic" | "agent";
  status: "passed" | "failed" | "error" | "skipped";
  duration: number; // milliseconds
  tokensUsed: number;
}
```
