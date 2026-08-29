# Feature Specification: One-Shot End-to-End Coding Agent

**Feature Branch**: `001-one-shot-coding-agent`  
**Created**: 2025-07-15  
**Status**: Draft  
**Input**: User description: "Build a one-shot end-to-end coding agent using Pi SDK as the agent harness"

## Clarifications

### Session 2026-03-12

- Q: Should functional requirements reference Pi SDK, TypeScript, and Pi Extensions explicitly (Pi-specific) or remain technology-agnostic? → A: Pi-specific — reference Pi SDK, TypeScript, and Pi Extensions directly in requirements.
- Q: Should the spec include an explicit Non-Goals section, and what is the agent's terminal output? → A: Yes, add non-goals. The agent's downstream output is a PR with a summary of all changes and why.
- Q: Should quantitative success metrics (one-shot success rate, token limit, run time, retry rate, partial success) be added to success criteria? → A: Yes, add all 5 quantitative targets.
- Q: Should the spec add explicit security boundary requirements (path validation, domain allowlist) beyond container isolation? → A: Yes, add both path validation and domain allowlist as new FRs.
- Q: Should the spec include a Risks & Mitigations section? → A: Yes, add the top 6 highest-impact risks from the initial requirement.

## Non-Goals (Out of Scope)

- **No multi-repo orchestration** — the agent operates on a single target repository per run.
- **No CI/CD replacement** — the agent does not replace or manage CI/CD pipelines; it creates a PR and lets existing CI run.
- **No autonomous merge** — the agent creates a PR for human review; it never merges its own output.
- **No production deployment** — the agent does not deploy code; its terminal output is a PR-ready branch with a PR.
- **No non-git repository support** — the agent assumes a git-based repository with a remote.

## Technology Decisions

- **Agent Harness**: Pi SDK — provides the workflow engine (graph-based blueprint), session management, built-in tools, and extension mechanism.
- **Language**: TypeScript — all agent code, extensions, and orchestration logic are written in TypeScript.
- **Custom Tools**: Pi Extensions — custom tools (e.g., `repo_map`, `semantic_search`, `run_test`) are registered as Pi Extensions.
- **LLM Integration**: Via Pi SDK's provider abstraction layer, supporting Anthropic Claude and OpenAI GPT.
- **Justification**: Pi SDK provides deterministic workflow orchestration, per-step tool scoping, session isolation, and a proven extension model — reducing boilerplate and enabling a graph-based blueprint that mixes deterministic and agent-driven nodes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Coding Task End-to-End (Priority: P1)

As a developer, I want to give the agent a plain-text task description (e.g., "Add email validation to the create_user endpoint") and have it autonomously produce a pull request — with code changes, passing linter, passing tests, and a PR summary explaining all changes and reasoning — in one shot with no human interaction during execution.

**Why this priority**: This is the core value proposition. Without this end-to-end flow, the agent has no purpose. Every other feature builds on this capability.

**Independent Test**: Run the agent with a simple task against a brownfield test repository. Verify it creates a branch, makes code changes, runs lint + tests, and commits. The resulting branch should have zero lint errors and all tests passing.

**Acceptance Scenarios**:

1. **Given** a configured target repository with existing tests and linting, **When** the user runs the CLI with a task description, **Then** the agent creates a new branch, makes code changes, runs lint and tests, commits, and opens a pull request — all without human intervention.
2. **Given** the agent completes a run, **When** the user inspects the pull request, **Then** the PR includes a summary of all changes made and the reasoning behind each change, and all existing tests still pass (no regressions) with the linter reporting zero errors.
3. **Given** a task that requires modifying multiple files, **When** the agent executes, **Then** the changes are coherent, logically consistent, and address the stated task.

---

### User Story 2 - Intelligent Context Gathering (Priority: P1)

As a developer, I want the agent to automatically explore and understand my codebase before making changes — building a repository map, searching for relevant symbols, tracing dependencies — so that it makes informed edits rather than blind guesses.

**Why this priority**: Context engineering is what separates a useful coding agent from one that hallucinates. Without good context gathering, the agent cannot produce correct code changes. This is equally critical as the end-to-end flow.

**Independent Test**: Run the context-gathering step in isolation. Verify it produces a repo map with symbol counts, identifies relevant files for a given task, and traces dependency relationships. Confirm the context window stays within token budget.

**Acceptance Scenarios**:

1. **Given** a target repository, **When** the context-gathering step runs, **Then** it generates a repository map capturing key symbols (functions, classes, exports) and their locations.
2. **Given** a task description mentioning specific functionality, **When** context gathering runs, **Then** it identifies the relevant files and dependencies related to that functionality.
3. **Given** a large repository exceeding context limits, **When** context gathering runs, **Then** it stays within the configured token budget by prioritizing the most relevant files.

---

### User Story 3 - Shift-Left Quality Feedback Loop (Priority: P2)

As a developer, I want the agent to catch and fix its own mistakes locally (lint errors, type errors, test failures) before committing — with an automatic retry loop — so that the output branch is clean and ready for review.

**Why this priority**: Delivering broken code defeats the purpose. The shift-left loop is what makes the agent output trustworthy. It's secondary only because it depends on the core flow (P1) being functional first.

**Independent Test**: Introduce a deliberate lint error or test failure in the agent's output, then verify the shift-left loop detects the failure and triggers a fix cycle that resolves it.

**Acceptance Scenarios**:

1. **Given** the agent produces code with a lint error, **When** the lint step runs, **Then** the agent detects the error and attempts an auto-fix cycle.
2. **Given** the agent's changes cause a test failure, **When** the test step runs, **Then** the agent re-enters a fix step to address the failure before committing.
3. **Given** the fix step cannot resolve the issue within the configured retry limit, **When** retries are exhausted, **Then** the agent aborts cleanly, reports the failure with details, and does not push broken code.

---

### User Story 4 - Isolated Execution Environment (Priority: P2)

As a developer, I want the agent to run inside an isolated container (devbox) with pre-installed tools and a cloned copy of my repo, so that it cannot damage my local environment or the production codebase.

**Why this priority**: Safety and reproducibility. The agent runs arbitrary code (shell commands, tests) so isolation is non-negotiable for real use. But it depends on the core agent flow working first.

**Independent Test**: Launch the devbox container independently. Verify the repo is cloned inside, tools are available (Node.js, linters, test runners), and changes inside the container do not affect the host filesystem.

**Acceptance Scenarios**:

1. **Given** the agent is invoked, **When** it starts execution, **Then** it operates inside an isolated Docker container with the target repository cloned.
2. **Given** the container is running, **When** the agent executes shell commands, **Then** those commands affect only the container's filesystem, not the host.
3. **Given** the container is pre-built (warm cache), **When** the agent starts, **Then** startup time is under 10 seconds (excluding LLM API latency).

---

### User Story 5 - Run Reporting and Observability (Priority: P3)

As a developer, I want to see a clear summary after each agent run — files changed, tests passed/failed, tokens used, cost, timing — and be able to review the full session transcripts for debugging or learning.

**Why this priority**: Observability is critical for learning and debugging, but the agent must work first. This is a polish feature that makes the agent practical for repeated daily use.

**Independent Test**: After a successful run, verify the report includes all required metrics (files changed, test results, token count, cost, duration). Verify session transcripts are saved and readable.

**Acceptance Scenarios**:

1. **Given** the agent completes a run (success or failure), **When** the run finishes, **Then** a summary report is displayed showing: files changed, lines added/removed, test results, lint status, token usage, estimated cost, and total time.
2. **Given** a completed run, **When** the user inspects the run artifacts directory, **Then** they find session transcripts, the code diff, and a metrics file.
3. **Given** a failed run, **When** the user reviews the report, **Then** the failure point and error details are clearly identified.

---

### User Story 6 - Configurable Agent Behavior (Priority: P3)

As a developer, I want to configure the agent via a single config file — specifying the LLM provider/model, target repo settings (test command, lint command), token budgets, and git behavior — so I can adapt it to different projects.

**Why this priority**: Configuration flexibility is what makes the agent reusable across different repos. But a hardcoded-for-one-repo version is useful enough initially.

**Independent Test**: Create two different config files pointing to different repos with different test/lint commands. Verify the agent respects each config and runs the correct commands for each.

**Acceptance Scenarios**:

1. **Given** a configuration file specifying a target repo, LLM provider, and quality commands, **When** the agent runs, **Then** it uses the specified provider and runs the specified lint/test commands.
2. **Given** a configuration with a token budget limit, **When** the agent runs, **Then** it does not exceed the configured token budget.
3. **Given** the user changes the LLM provider in the config, **When** the agent runs, **Then** it uses the new provider without code changes.

---

### Edge Cases

- What happens when the LLM provider API is unreachable or returns an error mid-run?
- What happens when the target repository has no tests or no linter configured?
- What happens when the task description is ambiguous or too broad for a single PR?
- What happens when the codebase is too large to fit meaningful context within token limits?
- What happens when the agent's code changes conflict with concurrent changes on the target branch?
- What happens when the Docker container runs out of memory or disk space during execution?
- What happens when the agent needs to create new files in directories that don't exist yet?
- What happens when the retry loop cycles between two different failures (oscillation)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a plain-text task description via CLI and execute the full coding workflow autonomously (no human prompts during execution).
- **FR-002**: System MUST create a dedicated git branch for each task run, following a configurable naming convention (e.g., `agent/<task-slug>-<timestamp>`).
- **FR-003**: System MUST gather codebase context before planning — using Pi SDK agent sessions with read-only tool scoping — including a repository map of symbols (via `repo_map` Pi Extension), relevant file identification via search, and dependency tracing.
- **FR-004**: System MUST generate a structured plan (files to modify, approach) before writing any code, using a dedicated Pi SDK planning session with read-only tools.
- **FR-005**: System MUST implement code changes following the plan, using Pi SDK agent sessions with full tool access and appropriate file editing strategies (full write for small files, targeted edits for large files).
- **FR-006**: System MUST run configured lint and format commands after code changes, auto-fixing where possible.
- **FR-007**: System MUST run configured test commands after code changes, including both targeted tests (for new/changed code) and regression tests (existing suite).
- **FR-008**: System MUST attempt to fix lint errors and test failures in an automated retry loop, with a configurable maximum retry count (default: 2 retries).
- **FR-009**: System MUST commit and push changes to the branch only when lint passes and tests pass, then create a pull request with a summary describing all changes made and the reasoning behind each change.
- **FR-010**: System MUST abort cleanly and report detailed failure context when the retry limit is exhausted without resolution.
- **FR-011**: System MUST execute all operations inside an isolated Docker container, with the target repository cloned inside.
- **FR-012**: System MUST support multiple LLM providers (at minimum: Anthropic Claude and OpenAI GPT) selectable via configuration, using Pi SDK's provider abstraction layer.
- **FR-013**: System MUST respect a configurable token budget per run, stopping or degrading gracefully if the budget is exhausted.
- **FR-014**: System MUST produce a run report upon completion containing: files changed, lines added/removed, test results, lint status, token usage, estimated cost, and total time.
- **FR-015**: System MUST save session transcripts (full LLM conversation logs) for each agent-driven step, enabling post-run review and debugging.
- **FR-016**: System MUST load project-level rules and conventions (via AGENTS.md or equivalent) into each Pi SDK agent session's system prompt automatically.
- **FR-017**: System MUST scope the available tools per workflow step using Pi SDK's per-node tool configuration — e.g., the planning step should be read-only (no file writes), while the implementation step has full tool access.
- **FR-018**: System MUST support configurable target repository settings: test command, lint command, format command, type-check command, and language.
- **FR-019**: System MUST enforce path validation — all file read/write operations by the agent MUST be restricted to the cloned repository directory inside the container. Any attempt to access paths outside the repo root MUST be blocked and logged.
- **FR-020**: System MUST enforce a domain allowlist for outbound network access — restricting connections to approved endpoints only (LLM provider API, git remote, package registry). All other outbound connections MUST be blocked.

### Key Entities

- **Task**: A plain-text description of the coding work to perform. The atomic input to the system.
- **Run**: A single execution of the agent against a task. Contains all session transcripts, artifacts, metrics, and the resulting code diff. Each run is timestamped and self-contained.
- **Blueprint**: A Pi SDK graph-based workflow defining the agent's execution flow as an ordered sequence of nodes. Mixes deterministic nodes (lint, test, git) with agent-driven nodes (context gather, plan, implement, fix). Defined in TypeScript using Pi SDK's workflow API.
- **Step/Node**: A Pi SDK workflow node — an individual unit of work within a blueprint. Each node is either deterministic (runs shell commands, always the same) or agent-driven (uses a Pi SDK session to reason and act). Nodes declare their own tool scoping.
- **Session**: A Pi SDK session — an LLM conversation context for an agent-driven node. Includes system prompt, scoped tool access, conversation history, and token accounting. Each agent-driven node gets its own isolated session.
- **Devbox**: The isolated Docker container where the agent executes. Contains the cloned repo, installed tools, and runtime environment.
- **Extension**: A Pi Extension — a custom tool registered with Pi SDK (e.g., `repo_map`, `semantic_search`, `run_test`). Pi Extensions extend the agent's capabilities beyond Pi's 7 built-in tools (read_file, write_file, shell, etc.).
- **Token Budget**: The maximum tokens allocated for context loading per run. Subdivided into per-layer allocations (L0-L3 + reserved). The system must prioritize and truncate context to stay within budget. (Named `TokenBudget` in data-model.md.)
- **Run Report**: The summary output of a run, including metrics and pass/fail status. Serves both as user feedback and as data for future agent improvement.
- **PR Summary**: The description body of the pull request created by the agent. Contains a structured summary of all files changed, what was changed in each, and the reasoning behind each change. This is the agent's primary deliverable to the human reviewer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The agent can complete a well-defined single-file coding task (e.g., "add input validation to endpoint X") on the target repo in under 5 minutes, producing a clean branch with passing lint and tests.
- **SC-002**: For tasks touching 1-3 files, the agent produces code changes that pass the existing test suite at least 80% of the time (no regressions).
- **SC-003**: The agent's context gathering correctly identifies the relevant files for a given task at least 90% of the time (measured by whether the plan references the right files).
- **SC-004**: The shift-left feedback loop catches and auto-fixes at least 70% of lint and test failures before the final commit (measured over 20 representative tasks).
- **SC-005**: Total token cost per successful run stays under $2.00 for typical tasks (1-3 files changed).
- **SC-006**: Run reports are complete and accurate — every completed run produces a report with all required metrics (files changed, test results, tokens, cost, time).
- **SC-007**: The agent runs reliably inside the isolated container — zero host filesystem modifications, zero data leaks outside the container.
- **SC-008**: A new developer can configure the agent for a different target repository by editing only the configuration file, with no code changes, in under 15 minutes.
- **SC-009**: The agent achieves a ≥50% one-shot success rate — completing the task with passing lint and tests on the first attempt (no retries), measured over 20 representative tasks.
- **SC-010**: The agent achieves a ≥80% partial success rate — code compiles and most tests pass even when full success is not reached, measured over 20 representative tasks.
- **SC-011**: Total token consumption per run stays under 200K tokens for typical tasks (1-3 files changed).
- **SC-012**: Average agent run time is under 10 minutes for typical tasks (excluding container build time).
- **SC-013**: The retry rate (runs requiring at least one fix cycle) stays below 30% across representative tasks.

## Risks & Mitigations

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| R1 | **LLM Hallucination** — agent generates plausible but incorrect code (wrong API usage, invented functions) | High | High | Shift-left feedback loop (lint + test after every change); regression test suite catches incorrect behavior; planning step uses read-only tools to verify APIs exist before coding |
| R2 | **Token Budget Blowout** — large repos or complex tasks consume excessive tokens, inflating cost and hitting provider limits | High | Medium | Configurable token budget per run (FR-013); layered context loading prioritizes relevant files; budget monitoring with graceful degradation when threshold reached |
| R3 | **Infinite Retry Loop / Oscillation** — fix cycle alternates between two different failures without converging | Medium | Medium | Hard retry cap (FR-008, default 2 retries); detect oscillation pattern (same error repeating); abort cleanly with detailed failure report (FR-010) |
| R4 | **Prompt Injection via Repo Content** — malicious code comments or file content in the target repo manipulate the agent's behavior | High | Low | Treat all repo content as untrusted data; system prompts include injection-resistance instructions; path validation (FR-019) prevents file access outside repo; domain allowlist (FR-020) blocks exfiltration |
| R5 | **Context Window Overflow** — codebase too large for meaningful context within token limits, causing the agent to miss critical files | Medium | High | Repo map + semantic search to identify relevant files (FR-003); configurable context budget per session; truncation strategy prioritizes files referenced in task description and dependency graph |
| R6 | **Flaky Test Misdiagnosis** — pre-existing flaky tests fail during agent run, causing the agent to waste retries fixing unrelated code or abort incorrectly | Medium | Medium | Baseline test run before agent changes (detect pre-existing failures); compare test results before/after to isolate agent-caused failures; configurable test flakiness tolerance |

## Assumptions

- The target repository has an existing test suite and linter configured and working before the agent is introduced.
- The developer has API keys for at least one supported LLM provider (Anthropic or OpenAI).
- Docker is available on the developer's machine for running the isolated devbox.
- The target repository is hosted on a git remote (e.g., GitHub) that the developer has push access to.
- Tasks given to the agent are scoped to single-PR-sized changes (not full feature rewrites or multi-day refactors).
- The developer is comfortable reviewing and merging the agent's output (the agent does not replace code review).
- Network access is available during execution for LLM API calls and git push operations.

## Dependencies

- An LLM provider API (Anthropic Claude or OpenAI GPT) with sufficient quota for development and testing.
- Docker runtime for building and running the devbox container.
- A brownfield target repository (5K-50K LOC) with working tests, linter, and CI pipeline.
- Git remote access (SSH or HTTPS) for branch creation and push operations.
