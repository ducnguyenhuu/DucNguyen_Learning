# Tasks: One-Shot End-to-End Coding Agent

**Input**: Design documents from `/specs/001-one-shot-coding-agent/`  
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cli-contract.md, quickstart.md  
**Branch**: `001-one-shot-coding-agent`

**Tests**: Every implementation task MUST include corresponding unit tests and a summary of what was implemented (Constitution Principle II). Tests are MANDATORY for all code tasks — write tests FIRST (red), then implement (green), then refactor.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project layout per plan.md:

- Source: `src/` at repository root
- Tests: `tests/unit/`, `tests/integration/`, `tests/extensions/`
- Extensions: `extensions/`
- Prompts: `prompts/`
- Skills: `skills/`
- Scripts: `scripts/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, and dependency installation. No code logic — just scaffolding.

- [X] T001 Create project directory structure per plan.md: src/ (cli, orchestrator, types, config, adapters/, steps/, blueprints/, context/, security/, reporting/), extensions/, prompts/, skills/, scripts/, tests/ (unit/, integration/, extensions/), runs/
- [X] T002 Initialize TypeScript project with package.json, tsconfig.json, and vitest.config.ts
- [X] T003 [P] Install all dependencies per plan.md Technical Context: @mariozechner/pi-coding-agent@0.57.1, commander, simple-git, pino, @octokit/rest, vectra, web-tree-sitter, js-tiktoken, @xenova/transformers (dependencies) and typescript, vitest, @types/node (devDependencies) in package.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, configuration, adapter, orchestrator, and security infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Write unit tests for shared type guards and validation helpers in tests/unit/types.test.ts
- [X] T005 Create all shared TypeScript interfaces and types in src/types.ts — AgentConfig, Task, Run, RunStatus, Blueprint, BlueprintNode, StepResult, RunContext, Session, RunReport, PRSummary, TokenBudget, LayerBudgets, FileChange, TestResult, NodeResult (per data-model.md)
- [X] T006 [P] Write unit tests for configuration loading and validation in tests/unit/config.test.ts
- [X] T007 [P] Implement configuration loading from pi-agent.config.ts with validation rules in src/config.ts — validate maxTokensPerRun > 0, timeoutSeconds > 0, non-empty testCommand/lintCommand, supported provider (FR-018, per data-model.md AgentConfig entity)
- [X] T008 [P] Write unit tests for Pi SDK adapter in tests/unit/adapters/pi-sdk.test.ts — test session creation, prompt execution, token usage extraction
- [X] T009 [P] Implement Pi SDK adapter layer wrapping createAgentSession, session.prompt, and session.tokenUsage in src/adapters/pi-sdk.ts (FR-012, Architecture Decision D2)
- [X] T010 Write unit tests for BlueprintRunner orchestrator in tests/unit/orchestrator.test.ts — test node sequencing, conditional routing, error propagation
- [X] T011 Implement BlueprintRunner orchestrator class with addNode and run methods in src/orchestrator.ts (Architecture Decision D1 — deterministic + agent node sequencing via next() routing)
- [X] T012 [P] Write unit tests for path validation in tests/unit/security/path-validator.test.ts — test allowed paths, directory traversal rejection, symlink handling
- [X] T013 [P] Implement path validation module restricting file I/O to repo directory in src/security/path-validator.ts (FR-019)
- [X] T014 [P] Write unit tests for token budget manager in tests/unit/context/token-budget.test.ts — test per-layer allocation, consumption tracking, graceful degradation threshold
- [X] T015 [P] Implement token budget manager with per-layer allocation (L0: 5%, L1: 15%, L2: 40%, L3: 10%, reserved: 30%) and graceful degradation in src/context/token-budget.ts (FR-013, data-model.md TokenBudget entity)

**Checkpoint**: Foundation ready — all shared types, config, adapter, orchestrator, path validation, and token budget are working with passing tests. User story implementation can now begin.

---

## Phase 3: User Story 1 — Run a Coding Task End-to-End (Priority: P1) 🎯 MVP

**Goal**: Accept a plain-text task via CLI, run the 9-node blueprint (setup → context_gather → plan → implement → lint_and_format → test → fix_failures → commit_and_push → report), and produce a committed branch with passing lint and tests. This phase uses basic implementations of agent steps — no extensions, no enhanced context.

**Independent Test**: Run the agent with a simple task against a test repository. Verify it creates a branch, makes code changes, runs lint + tests, and commits. The resulting branch should have zero lint errors and all tests passing.

### Tests for User Story 1 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**
> **Each completed task MUST include a summary: what was built, what tests verify, known limitations.**

- [X] T016 [P] [US1] Write unit tests for CLI run command parsing and option handling in tests/unit/cli.test.ts
- [X] T017 [P] [US1] Write unit tests for setup step (branch creation, task parsing) in tests/unit/steps/setup.test.ts
- [X] T018 [P] [US1] Write unit tests for lint-and-format step (command execution, auto-fix detection) in tests/unit/steps/lint-format.test.ts
- [X] T019 [P] [US1] Write unit tests for test step (command execution, pass/fail parsing) in tests/unit/steps/test.test.ts
- [X] T020 [P] [US1] Write unit tests for commit-and-push step (git operations, branch push) in tests/unit/steps/commit-push.test.ts
- [X] T021 [P] [US1] Write unit tests for report step (summary formatting, metrics output) in tests/unit/steps/report.test.ts
- [X] T079 [P] [US1] Write unit tests for context-gather step (adapter mock, prompt construction, relevant file output parsing) in tests/unit/steps/context-gather.test.ts
- [X] T080 [P] [US1] Write unit tests for plan step (read-only tool verification, structured plan output parsing) in tests/unit/steps/plan.test.ts
- [X] T081 [P] [US1] Write unit tests for implement step (write tool access verification, file change tracking) in tests/unit/steps/implement.test.ts
- [X] T082 [P] [US1] Write unit tests for standard blueprint routing logic (test pass → commit, test fail → fix_failures, retry cap enforcement) in tests/unit/blueprints/standard.test.ts

### Implementation for User Story 1

- [X] T022 [US1] Implement CLI entry point with run command accepting task description and all options (--config, --provider, --model, --dry-run, --max-retries, --max-tokens, --timeout, --verbose, --output-dir) in src/cli.ts (FR-001, FR-012, per contracts/cli-contract.md)
- [X] T023 [P] [US1] Implement setup step — create git branch, parse task slug, load AGENTS.md, initialize RunContext in src/steps/setup.ts (FR-002, FR-016)
- [X] T024 [P] [US1] Implement context-gather step — basic Pi session with read/grep/find/ls tools, output relevant files and understanding in src/steps/context-gather.ts (FR-003, FR-017)
- [X] T025 [P] [US1] Implement plan step — Pi session with read-only tools, output structured change plan in src/steps/plan.ts (FR-004, FR-017)
- [X] T026 [P] [US1] Implement implement step — Pi session with read/write/edit/bash/grep/find tools, execute code changes following the plan in src/steps/implement.ts (FR-005, FR-017)
- [X] T027 [P] [US1] Implement lint-and-format step — run configured lint/format/type-check commands via shell, capture output in src/steps/lint-format.ts (FR-006)
- [X] T028 [P] [US1] Implement test step — run configured test command via shell, parse pass/fail counts, return status in src/steps/test.ts (FR-007)
- [X] T029 [US1] Implement fix-failures step — basic Pi session receiving error output, attempts fix with read/write/edit/bash/grep tools in src/steps/fix-failures.ts (FR-008)
- [X] T030 [P] [US1] Implement commit-and-push step — stage changes, commit with prefix, push branch using simple-git in src/steps/commit-push.ts (FR-009)
- [X] T031 [P] [US1] Implement report step — basic console summary with files changed, test results, tokens, cost, time in src/steps/report.ts (FR-014)
- [X] T032 [P] [US1] Create system prompt templates for each agent node in prompts/context-gather.md, prompts/plan.md, prompts/implement.md, and prompts/fix-failures.md (per initial_requirement.md Section 7 system prompt strategy)
- [X] T033 [US1] Wire all 9 steps into standard blueprint with conditional routing (test pass → commit, test fail → fix_failures → retry) in src/blueprints/standard.ts (FR-017)
- [X] T034 [US1] Write integration test for full blueprint execution against a test fixture repo in tests/integration/blueprint-runner.test.ts — include edge cases: LLM API error mid-run, ambiguous/too-broad task, new files in non-existent directories

**Checkpoint**: User Story 1 complete — the agent can accept a task, run the full 9-node blueprint with basic context gathering, and produce a committed branch. This is the MVP.

---

## Phase 4: User Story 2 — Intelligent Context Gathering (Priority: P1)

**Goal**: Enhance the context-gathering step with Pi Extensions for repo map generation (tree-sitter), semantic search (vectra + embeddings), symbol navigation, and dependency graph analysis. This upgrades the basic context-gather from US1 to a multi-signal retrieval system.

**Independent Test**: Run the context-gathering step in isolation. Verify it produces a repo map with symbol counts, identifies relevant files for a given task via semantic search, and traces dependency relationships. Confirm the context window stays within token budget.

### Tests for User Story 2 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T035 [P] [US2] Write unit tests for repo map generator (tree-sitter parsing, symbol extraction, token limiting) in tests/unit/context/repo-map.test.ts
- [X] T036 [P] [US2] Write unit tests for code chunker (AST-based splitting at function/class boundaries) in tests/unit/context/chunker.test.ts
- [X] T037 [P] [US2] Write unit tests for embeddings module (indexing, querying, vectra integration) in tests/unit/context/embeddings.test.ts
- [X] T038 [P] [US2] Write unit tests for dependency graph builder (import parsing, importer/importee resolution) in tests/unit/context/dep-graph.test.ts
- [X] T039 [P] [US2] Write extension integration tests for context-tools Pi Extension in tests/extensions/context-tools.test.ts
- [X] T083 [P] [US2] Write unit tests for symbol navigation module (definition lookup, reference finding, tree-sitter integration) in tests/unit/context/symbol-nav.test.ts

### Implementation for User Story 2

- [X] T040 [P] [US2] Implement repo map generator with web-tree-sitter — parse files, extract function/class signatures, respect maxTokens budget in src/context/repo-map.ts (Research Decision R3)
- [X] T041 [P] [US2] Implement AST-based code chunker — split files at function/class boundaries using tree-sitter in src/context/chunker.ts
- [X] T042 [P] [US2] Implement symbol navigation module — go-to-definition and find-references using tree-sitter in src/context/symbol-nav.ts
- [X] T043 [P] [US2] Implement dependency graph builder — parse import/require/from statements, resolve importers and importees in src/context/dep-graph.ts
- [X] T044 [US2] Implement embedding indexing with vectra and @xenova/transformers — index code chunks, support cosine similarity queries in src/context/embeddings.ts (Research Decision R2)
- [X] T045 [US2] Implement context-tools Pi Extension registering repo_map, semantic_search, symbol_nav, and dependency_graph tools in extensions/context-tools.ts
- [X] T046 [US2] Update context-gather step to load context-tools extension and use multi-signal retrieval (keyword + semantic + dependency) in src/steps/context-gather.ts
- [X] T047 [P] [US2] Create pre-warm script that builds repo map and embeddings index in scripts/warm-cache.sh

**Checkpoint**: User Story 2 complete — the agent now gathers intelligent, multi-signal context using repo maps, semantic search, symbol navigation, and dependency tracing. Context stays within token budget.

---

## Phase 5: User Story 3 — Shift-Left Quality Feedback Loop (Priority: P2)

**Goal**: Enhance the retry loop with structured error parsing, oscillation detection (same error repeating), and quality-tools Pi Extensions that provide structured test/lint output to the fix-failures agent. Ensures the agent catches and fixes its own mistakes before committing.

**Independent Test**: Introduce a deliberate lint error or test failure in the agent's output, then verify the shift-left loop detects the failure and triggers a fix cycle. Verify oscillation detection aborts after detecting repeated identical failures.

### Tests for User Story 3 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T048 [P] [US3] Write unit tests for enhanced fix-failures step (oscillation detection, structured error parsing) in tests/unit/steps/fix-failures.test.ts
- [X] T049 [P] [US3] Write extension tests for quality-tools Pi Extension (run_test, run_lint structured output) in tests/extensions/quality-tools.test.ts

### Implementation for User Story 3

- [X] T050 [US3] Implement quality-tools Pi Extension registering run_test and run_lint tools with structured PASSED/FAILED output in extensions/quality-tools.ts
- [X] T051 [US3] Enhance fix-failures step with oscillation detection (track error hashes across retries), structured error injection into Pi session prompt, and configurable max retries in src/steps/fix-failures.ts (FR-008, FR-010, Risk R3)
- [X] T052 [US3] Enhance standard blueprint retry loop — load quality-tools extension for fix_failures node, enforce retry cap from config in src/blueprints/standard.ts
- [X] T053 [US3] Write integration test for retry loop — simulate lint failure → fix → pass, and oscillation → abort scenarios in tests/integration/retry-loop.test.ts

**Checkpoint**: User Story 3 complete — the agent has a robust shift-left feedback loop with oscillation detection, structured error parsing, and quality-tools extensions. Max 2 retries enforced.

---

## Phase 6: User Story 4 — Isolated Execution Environment (Priority: P2)

**Goal**: Build the Docker devbox with full isolation, tinyproxy domain allowlist, and web_fetch extension. Ensures the agent cannot damage host systems or exfiltrate data.

**Independent Test**: Launch the devbox container independently. Verify the repo is cloned inside, tools are available (Node.js, linters, test runners), changes do not affect the host, and outbound connections to non-allowlisted domains are blocked.

### Tests for User Story 4 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T054 [P] [US4] Write unit tests for domain allowlist configuration module in tests/unit/security/domain-allowlist.test.ts

### Implementation for User Story 4

- [X] T055 [P] [US4] Implement domain allowlist configuration module — load allowed domains from config, validate URLs against allowlist in src/security/domain-allowlist.ts (FR-020, Research Decision R5)
- [X] T056 [US4] Create Dockerfile.devbox with node:20-slim base, Pi global install, tinyproxy with domain allowlist, agent copy, repo clone, dependency install, and pre-warm step in Dockerfile.devbox (FR-011, per initial_requirement.md Section 10)
- [X] T057 [P] [US4] Create docker-compose.yml with proxy network configuration and environment variable passthrough in docker-compose.yml
- [X] T058 [US4] Implement web-tools Pi Extension registering web_fetch tool with domain allowlist enforcement in extensions/web-tools.ts
- [X] T059 [US4] Write Docker integration test validating container isolation (filesystem boundary), tinyproxy domain filtering, and pre-warm artifacts in tests/integration/docker.test.ts — include edge cases: container OOM/disk exhaustion, non-allowlisted domain access attempt

**Checkpoint**: User Story 4 complete — the agent runs inside an isolated Docker container with domain-restricted networking. All file operations are path-validated, all network requests are proxy-filtered.

---

## Phase 7: User Story 5 — Run Reporting and Observability (Priority: P3)

**Goal**: Full reporting pipeline — run report with all metrics, PR summary generation via Octokit, session transcript saving, and run artifact management. The PR is the agent's primary deliverable.

**Independent Test**: After a successful run, verify the report includes all required metrics (files changed, test results, token count, cost, duration). Verify session transcripts are saved as JSONL. Verify the PR body matches the contract in cli-contract.md.

### Tests for User Story 5 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T060 [P] [US5] Write unit tests for run report generation (metrics aggregation, status formatting) in tests/unit/reporting/run-report.test.ts
- [X] T061 [P] [US5] Write unit tests for PR summary generation (body template, changes table, Octokit API call) in tests/unit/reporting/pr-summary.test.ts
- [X] T084 [P] [US5] Write unit tests for session transcript saving (JSONL format, directory creation, file naming) in tests/unit/reporting/transcript.test.ts

### Implementation for User Story 5

- [X] T062 [P] [US5] Implement run report generation — aggregate NodeResults, compute totals, format summary per RunReport entity in src/reporting/run-report.ts (FR-014, data-model.md Entity 9)
- [X] T063 [P] [US5] Implement session transcript saving — save Pi session JSONL files to runs/{timestamp}/ directory in src/reporting/transcript.ts (FR-015)
- [X] T064 [US5] Implement PR summary generation with Octokit — create PR with structured body (changes table, test results, agent run details) per cli-contract.md PR body template in src/reporting/pr-summary.ts (FR-009, Research Decision R4, data-model.md Entity 10)
- [X] T065 [US5] Update commit-and-push step to create GitHub PR via Octokit after push in src/steps/commit-push.ts (Architecture Decision D5)
- [X] T066 [US5] Update report step to output full metrics, save report.json and metrics.json to run artifacts directory in src/steps/report.ts
- [X] T067 [US5] Write integration test for full reporting pipeline — run → report.json + metrics.json + session JSONL + PR creation in tests/integration/reporting.test.ts

**Checkpoint**: User Story 5 complete — every run produces a comprehensive report, saves session transcripts, and creates a GitHub PR with a structured summary.

---

## Phase 8: User Story 6 — Configurable Agent Behavior (Priority: P3)

**Goal**: Full configuration flexibility — `init` command for new target repos, AGENTS.md template generation, multi-provider switching without code changes. Makes the agent reusable across different projects.

**Independent Test**: Create two different config files pointing to different repos with different test/lint commands. Verify the agent respects each config. Verify `init` generates a valid config file.

### Tests for User Story 6 (MANDATORY per Constitution Principle II)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T068 [P] [US6] Write integration tests for CLI init command (language detection, config generation, AGENTS.md creation) in tests/integration/cli-init.test.ts

### Implementation for User Story 6

- [X] T069 [US6] Implement init CLI command — detect language from package.json/pyproject.toml/go.mod, detect test/lint commands, generate pi-agent.config.ts, create AGENTS.md if missing in src/cli.ts (per contracts/cli-contract.md init command)
- [X] T070 [P] [US6] Create AGENTS.md template file for target repos with coding conventions, testing rules, file editing strategy, and Do Not rules in src/templates/AGENTS.md (per initial_requirement.md Section 8)
- [X] T071 [US6] Write integration test for multi-config scenario — two configs with different providers and commands, verify correct execution in tests/integration/config-switch.test.ts

**Checkpoint**: User Story 6 complete — the agent can be configured for any target repo via a single config file. `init` generates sensible defaults. AGENTS.md template provides project rules to Pi sessions.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Reliability improvements, documentation, and benchmarking that affect multiple user stories.

- [X] T072 [P] Implement graceful error handling with try/catch at every blueprint node — capture errors, log failure context, continue to report step on failure in src/orchestrator.ts — handle edge cases: LLM API errors, missing test/lint config, git merge conflicts on target branch
- [X] T073 [P] Implement per-node and per-run timeout management — configurable timeouts, AbortController integration in src/orchestrator.ts
- [X] T074 [P] Add dry-run mode — show plan without executing changes, wire --dry-run flag to skip implement/lint/test/commit steps in src/cli.ts and src/blueprints/standard.ts
- [X] T075 [P] Create Pi Skills with SKILL.md instruction files in skills/explore-codebase/SKILL.md, skills/implement-feature/SKILL.md, and skills/fix-failures/SKILL.md
- [X] T076 Implement benchmark script — run agent against 10 known tasks, measure success rate, token usage, cost, and timing in scripts/benchmark.ts (validates SC-001, SC-002, SC-005, SC-009, SC-010, SC-011, SC-012, SC-013)
- [X] T077 Write project README.md with installation, usage examples, architecture overview, configuration guide, and troubleshooting in README.md
- [X] T078 Run quickstart.md validation — verify all 5 setup steps from quickstart.md work end-to-end on a fresh environment

---

## Dependencies & Execution Order

> **Note**: Task phases are organized by **user story** (US1-US6) rather than by technology layer as in plan.md. This restructuring enables independent story delivery and testing. Plan.md phases map to task phases: Plan Phase 1 (Foundation) → Tasks Phases 1-3, Plan Phase 2 (Pi SDK) → Tasks Phase 3, Plan Phase 3 (Extensions & Context) → Tasks Phases 4-5, Plan Phase 4 (PR & Reporting) → Tasks Phase 7, Plan Phase 5 (Security & Docker) → Tasks Phase 6, Plan Phase 6 (Polish) → Tasks Phase 9.

### Phase Dependencies

```
Phase 1: Setup ────────────► Phase 2: Foundational ────┬──► Phase 3: US1 (P1) MVP
                                                        │
                                                        ├──► Phase 4: US2 (P1)
                                                        │        (can start after Phase 2,
                                                        │         but US1 provides working
                                                        │         context-gather to enhance)
                                                        │
                                                        ├──► Phase 5: US3 (P2)
                                                        │        (requires US1 fix_failures step)
                                                        │
                                                        ├──► Phase 6: US4 (P2)
                                                        │        (can start after Phase 2)
                                                        │
                                                        ├──► Phase 7: US5 (P3)
                                                        │        (requires US1 commit-push + report)
                                                        │
                                                        └──► Phase 8: US6 (P3)
                                                                 (requires US1 CLI run command)

Phase 9: Polish ◄──── All desired user stories complete
```

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) only — no dependencies on other stories. **Start here.**
- **US2 (P1)**: Depends on Phase 2. Enhances US1's context-gather step. Can start in parallel with US1 if working on different files, but integration (T046) requires US1's T024.
- **US3 (P2)**: Depends on Phase 2. Enhances US1's fix-failures step and blueprint. T051 requires US1's T029 (fix-failures) and T052 requires US1's T033 (standard blueprint).
- **US4 (P2)**: Depends on Phase 2 only. Dockerization is independent of agent logic. Can start in parallel with US1.
- **US5 (P3)**: Depends on US1's commit-push (T030) and report (T031) steps. T065 updates commit-push, T066 updates report.
- **US6 (P3)**: Depends on US1's CLI (T022). T069 adds init command to the same CLI module.

### Within Each User Story

1. Tests MUST be written and FAIL before implementation begins
2. Models/types before services/logic
3. Core modules before Pi Extensions
4. Pi Extensions before step integration
5. Individual steps before blueprint wiring
6. Unit tests before integration tests

### Parallel Opportunities per Phase

**Phase 2 (Foundational)**:
- T004 + T006 + T008 + T012 + T014 (all test tasks — different files)
- T007 + T009 + T013 + T015 (all implementation tasks — different files, after their paired tests)

**Phase 3 (US1)**:
- T016-T021, T079-T082 (all test tasks — different files)
- T023 + T024 + T025 + T026 + T027 + T028 + T030 + T031 + T032 (step implementations — different files)

**Phase 4 (US2)**:
- T035-T039, T083 (all test tasks — different files)
- T040 + T041 + T042 + T043 (context modules — different files)

**Phase 5 (US3)**:
- T048 + T049 (test tasks — different files)

**Phase 6 (US4)**:
- T054 (test) + T055 + T057 (different files)

**Phase 7 (US5)**:
- T060 + T061 + T084 (test tasks — different files)
- T062 + T063 (reporting modules — different files)

---

## Parallel Example: User Story 1

```bash
# Step 1: Launch all US1 test tasks in parallel (they write to different test files):
T016: "Unit tests for CLI in tests/unit/cli.test.ts"
T017: "Unit tests for setup step in tests/unit/steps/setup.test.ts"
T018: "Unit tests for lint-format step in tests/unit/steps/lint-format.test.ts"
T019: "Unit tests for test step in tests/unit/steps/test.test.ts"
T020: "Unit tests for commit-push step in tests/unit/steps/commit-push.test.ts"
T021: "Unit tests for report step in tests/unit/steps/report.test.ts"
T079: "Unit tests for context-gather step in tests/unit/steps/context-gather.test.ts"
T080: "Unit tests for plan step in tests/unit/steps/plan.test.ts"
T081: "Unit tests for implement step in tests/unit/steps/implement.test.ts"
T082: "Unit tests for standard blueprint routing in tests/unit/blueprints/standard.test.ts"

# Step 2: Launch independent step implementations in parallel:
T023: "Setup step in src/steps/setup.ts"
T024: "Context-gather step in src/steps/context-gather.ts"
T025: "Plan step in src/steps/plan.ts"
T026: "Implement step in src/steps/implement.ts"
T027: "Lint-format step in src/steps/lint-format.ts"
T028: "Test step in src/steps/test.ts"
T030: "Commit-push step in src/steps/commit-push.ts"
T031: "Report step in src/steps/report.ts"
T032: "System prompts in prompts/"

# Step 3: Sequential — depends on all steps existing:
T022: "CLI entry point in src/cli.ts" (after tests T016)
T029: "Fix-failures step in src/steps/fix-failures.ts" (after T027, T028 — needs their output format)
T033: "Standard blueprint in src/blueprints/standard.ts" (after all steps)
T034: "Integration test in tests/integration/blueprint-runner.test.ts" (after T033)
```

## Parallel Example: User Story 2

```bash
# Step 1: Launch all US2 test tasks in parallel:
T035: "Unit tests for repo-map in tests/unit/context/repo-map.test.ts"
T036: "Unit tests for chunker in tests/unit/context/chunker.test.ts"
T037: "Unit tests for embeddings in tests/unit/context/embeddings.test.ts"
T038: "Unit tests for dep-graph in tests/unit/context/dep-graph.test.ts"
T083: "Unit tests for symbol-nav in tests/unit/context/symbol-nav.test.ts"

# Step 2: Launch independent context modules in parallel:
T040: "Repo map generator in src/context/repo-map.ts"
T041: "Code chunker in src/context/chunker.ts"
T042: "Symbol navigation in src/context/symbol-nav.ts"
T043: "Dependency graph in src/context/dep-graph.ts"
T047: "Pre-warm script in scripts/warm-cache.sh"

# Step 3: Sequential — depends on context modules:
T044: "Embeddings + vectra in src/context/embeddings.ts" (after T041 chunker)
T045: "Context-tools extension in extensions/context-tools.ts" (after T040-T044)
T046: "Update context-gather step in src/steps/context-gather.ts" (after T045)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete **Phase 1: Setup** (T001-T003) — project scaffolding
2. Complete **Phase 2: Foundational** (T004-T015) — core infrastructure
3. Complete **Phase 3: User Story 1** (T016-T034) — basic end-to-end flow
4. **STOP AND VALIDATE**: Run agent against a test repo with a simple task
5. If working → MVP is done. The agent can accept a task and produce a committed branch.

### Incremental Delivery

1. **Setup + Foundational** → Foundation ready
2. **+ US1** → Basic end-to-end agent (MVP!) — test independently
3. **+ US2** → Intelligent context gathering — agent finds relevant code better
4. **+ US3** → Robust retry loop — agent fixes its own mistakes
5. **+ US4** → Docker isolation — safe to run on real repos
6. **+ US5** → Full reporting + PR creation — agent creates proper PRs
7. **+ US6** → Configuration — agent works across different repos
8. **+ Polish** → Production-ready personal tool

Each user story adds value without breaking previous stories.

---

## Constitution Compliance

- [x] **Principle I**: All task descriptions use plain language; technical terms and acronyms (CLI, PR, LLM, SDK, AST, WASM, JSONL) defined in plan.md and quickstart.md
- [x] **Principle II**: Every code task has a paired test task written FIRST; task summaries planned per constitution requirement
- [x] **Principle III**: Tasks align with spec.md (20 FRs, 13 SCs), plan.md (project structure, architecture decisions), data-model.md (11 entities), and contracts/cli-contract.md (CLI commands, PR body); no contradictions
- [x] **Principle IV**: Tasks referencing design decisions link to justification — D1-D5 in plan.md, R1-R6 in research.md

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks within the same phase
- [Story] label (US1-US6) maps each task to a specific user story for traceability
- Each user story is independently completable and testable at its checkpoint
- Commit after each task or logical group of tasks
- Stop at any checkpoint to validate the story independently before proceeding
