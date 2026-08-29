# One-Shot End-to-End Coding Agent — Project Spec

> A personal experiment to build a small-scale, Stripe Minions-inspired unattended coding agent that can one-shot tasks on a brownfield repository: from task intake to PR-ready branch — no human in the loop.

---

## Table of Contents

- [1. Vision & Goals](#1-vision--goals)
- [2. Key Concepts (Borrowed from Stripe Minions)](#2-key-concepts-borrowed-from-stripe-minions)
- [3. Scope & Constraints](#3-scope--constraints)
- [4. Architecture Overview](#4-architecture-overview)
- [5. Tech Stack](#5-tech-stack)
- [6. The Blueprint (Workflow Engine)](#6-the-blueprint-workflow-engine)
- [7. Agent Design](#7-agent-design)
- [8. Context Engineering](#8-context-engineering)
- [9. MCP Tools](#9-mcp-tools)
- [10. Devbox (Isolated Environment)](#10-devbox-isolated-environment)
- [11. Shift-Left Feedback Loop](#11-shift-left-feedback-loop)
- [12. Implementation Phases](#12-implementation-phases)
- [13. Success Metrics](#13-success-metrics)
- [14. Risks & Mitigations](#14-risks--mitigations)
- [15. Future Extensions](#15-future-extensions)

---

## 1. Vision & Goals

### What

Build a **personal-scale "Minion"**: an unattended coding agent that takes a task description (e.g., "Add input validation to the /users endpoint"), operates on an existing brownfield codebase inside an isolated environment, produces a code change, runs linters and tests, and delivers a PR-ready branch — all in one shot with no human interaction during execution.

### Why

- Learn the end-to-end mechanics of building a production-*flavored* coding agent
- Understand the interplay between **blueprints** (deterministic workflow), **agent loops** (LLM-driven), **context engineering**, and **shift-left feedback**
- Create a reusable personal tool for automating repetitive coding tasks on side projects
- Build intuition on what makes agents succeed or fail at scale

### Non-Goals (for v1)

- Multi-repo or monorepo support
- Slack/web UI for task intake (CLI is fine)
- Multi-user or team use
- Production-grade security hardening
- Custom model training/fine-tuning

---

## 2. Key Concepts (Borrowed from Stripe Minions)

| Stripe Concept | Our Adaptation |
|---|---|
| **Devbox** — isolated EC2 instances with pre-warmed code/services | Docker container or Devcontainer with repo + tools pre-loaded |
| **Blueprint** — state machine mixing deterministic nodes + agent nodes | Python workflow engine: ordered steps, some run code, some invoke LLM |
| **Agent harness** — forked goose agent with Stripe customizations | Microsoft Agent Framework `AIAgent` with custom providers for direct Anthropic + OpenAI API calls |
| **Rule files** — `.cursorrules`, `AGENTS.md`, scoped to subdirectories | `AGENTS.md` / `CLAUDE.md` / `.cursorrules` loaded contextually |
| **Toolshed (MCP)** — centralized MCP server with ~500 tools | Local MCP server with 10-15 curated tools for a single repo |
| **Shift-left feedback** — lint locally before pushing, max 2 CI rounds | Local lint + test → push → CI check → one retry loop |
| **One-shot** — from task to PR with no human in the loop | Same: task → branch → code → lint → test → PR-ready branch |

---

## 3. Scope & Constraints

### Target Repository

Pick **one brownfield repo** you actively work on. Ideal characteristics:

- **Language:** Python (easiest tooling ecosystem) or TypeScript (good LSP support)
- **Size:** 5K–50K LOC (small enough to reason about, large enough to need context management)
- **Has tests:** At least some existing test suite (pytest, jest, etc.)
- **Has linting:** Configured linter (ruff/flake8, eslint, etc.)
- **Has CI:** GitHub Actions or similar

### Task Types the Agent Should Handle (v1)

| Task Type | Example | Difficulty |
|---|---|---|
| Bug fix with error message | "Fix TypeError in `parse_config` when config is empty" | Easy |
| Add simple feature | "Add a `--verbose` flag to the CLI" | Medium |
| Refactor | "Extract the validation logic from `create_user` into a separate function" | Medium |
| Write tests | "Add tests for the `auth/service.py` module" | Medium |
| Fix lint/type errors | "Fix all mypy errors in `src/api/`" | Easy |

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                         │
│  $ agent run "Add input validation to POST /users"              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BLUEPRINT ENGINE                           │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │  Setup   │──►│ Context  │──►│ Implement│──►│  Lint &  │   │
│  │(determin)│   │ Gather   │   │  (agent) │   │  Format  │   │
│  │          │   │ (agent)  │   │          │   │(determin)│   │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   │
│       │                                             │          │
│       │              ┌──────────┐   ┌──────────┐    │          │
│       │              │  Test    │──►│  CI Push │    │          │
│       │              │  (mixed) │   │(determin)│    │          │
│       │              └──────────┘   └──────────┘    │          │
│       │                    │              │         │          │
│       │                    ▼              ▼         │          │
│       │              ┌──────────┐   ┌──────────┐   │          │
│       │              │ Fix      │──►│  Final   │   │          │
│       │              │ Failures │   │  Report  │   │          │
│       │              │ (agent)  │   │(determin)│   │          │
│       │              └──────────┘   └──────────┘   │          │
│       │                                             │          │
└───────┼─────────────────────────────────────────────┼──────────┘
        │                                             │
        ▼                                             ▼
┌──────────────┐                            ┌──────────────────┐
│   DEVBOX     │                            │   MCP TOOLS      │
│  (Docker)    │                            │                  │
│              │                            │ • file_read      │
│ • Git repo   │                            │ • file_write     │
│ • Linters    │                            │ • grep_search    │
│ • Test suite │                            │ • symbol_nav     │
│ • Language   │                            │ • run_command    │
│   server     │                            │ • git_ops        │
│              │                            │ • test_runner    │
└──────────────┘                            │ • lint_runner    │
                                            │ • web_search     │
                                            │ • repo_map       │
                                            └──────────────────┘
```

---

## 5. Tech Stack

### Core

| Component | Technology | Why |
|---|---|---|
| **Language** | Python 3.12+ | Rich ecosystem for AI agents, easy prototyping |
| **LLM** | Claude 4 Sonnet (via Anthropic API) | Strong coding, tool-use, long context. Swap to GPT-4.1 / Gemini as needed. |
| **Agent framework** | Microsoft Agent Framework (`agent-framework` on PyPI) | Graph-based workflows, executors, edges, built-in OpenTelemetry, streaming, checkpointing. Custom providers for Anthropic + OpenAI. |
| **Blueprint engine** | AF Workflows (`WorkflowBuilder` + Executors + Edges) | Directed graph with deterministic executors + AI agent nodes, conditional routing, superstep execution model |
| **CLI** | `click` or `typer` | Task intake, config, dry-run mode |

### Devbox / Environment

| Component | Technology | Why |
|---|---|---|
| **Container runtime** | Docker + Docker Compose | Isolated, reproducible, disposable |
| **Devcontainer** | `.devcontainer/devcontainer.json` | Standard spec, works with VS Code, GitHub Codespaces |
| **Base image** | `python:3.12-slim` or language-specific | Pre-install linters, test frameworks, language server |
| **Pre-warm script** | `setup.sh` | Clone repo, install deps, warm caches, start language server |

### MCP & Tools

| Component | Technology | Why |
|---|---|---|
| **MCP server** | Python (`mcp` SDK) or `fastmcp` | Host tools locally, standard protocol |
| **MCP transport** | stdio (for local) | Simplest for single-machine setup. AF has native Local MCP Tools support. |
| **Tool definitions** | Python functions decorated as MCP tools | Each tool = one focused capability. AF `AIAgent` consumes MCP tools directly. |

### Context Engineering

| Component | Technology | Why |
|---|---|---|
| **Repo map** | `tree-sitter` + custom skeleton generator | Layer 0 context (file list + signatures) |
| **Keyword search** | `ripgrep` (subprocess) | Fast exact-match search |
| **Semantic search** | ChromaDB + `nomic-embed-text` (local) | Meaning-based code retrieval, zero API cost |
| **Code chunking** | tree-sitter AST-based splitter | Chunk at function/class boundaries |
| **Token counting** | `tiktoken` or Anthropic's tokenizer | Budget management |

### Shift-Left / Quality

| Component | Technology | Why |
|---|---|---|
| **Linter** | `ruff` (Python) / `eslint` (TS) | Fast, auto-fixable |
| **Type checker** | `mypy` or `pyright` (Python) / `tsc` (TS) | Catch type errors before CI |
| **Test runner** | `pytest` (Python) / `jest` (TS) | Run targeted tests |
| **Test selection** | `pytest-testmon` or convention-based | Only run affected tests |
| **Formatter** | `ruff format` / `prettier` | Deterministic formatting |
| **Git** | `gitpython` or subprocess | Branch management, commits, push |

### Observability

| Component | Technology | Why |
|---|---|---|
| **Logging** | `structlog` | Structured JSON logs for every step |
| **Step tracing** | AF built-in OpenTelemetry + structlog | Distributed tracing per-executor, monitoring, debugging. Token usage via custom middleware. |
| **Cost tracking** | Token counting per LLM call | Track API spend per run |
| **Run artifacts** | Save full conversation + diffs to `runs/` directory | Post-mortem analysis |

---

## 6. The Blueprint (Workflow Engine)

The blueprint is the core orchestration primitive — a **directed graph** (built with Microsoft Agent Framework's Workflow system) that sequences **deterministic executors** (just run code) and **agent executors** (invoke LLM with tools).

### Blueprint Definition (Using AF Workflows)

The blueprint is implemented using Microsoft Agent Framework's **Workflow** system. **Executors** handle individual processing steps (either deterministic functions or AI agents). **Edges** define the flow between them, with optional conditions for branching.

```python
# blueprints/standard.py — Standard minion blueprint using AF Workflows
from agent_framework.workflows import WorkflowBuilder
from agent.executors import setup, lint_and_format, test, commit_and_push, report
from agent.agents import context_agent, plan_agent, implement_agent, fix_agent


def build_standard_blueprint():
    """Build the 9-node standard minion workflow."""
    workflow = (
        WorkflowBuilder(setup)                                # 1. SETUP [deterministic]
        .add_edge(setup, context_agent)                       # 2. CONTEXT GATHER [agent]
        .add_edge(context_agent, plan_agent)                  # 3. PLAN [agent]
        .add_edge(plan_agent, implement_agent)                # 4. IMPLEMENT [agent]
        .add_edge(implement_agent, lint_and_format)           # 5. LINT & FORMAT [deterministic]
        .add_edge(lint_and_format, test)                      # 6. TEST [deterministic]
        .add_edge(test, commit_and_push, condition=passed)    # 7. → COMMIT [deterministic]
        .add_edge(test, fix_agent, condition=failed)          # 7. → FIX [agent] (max 2 retries)
        .add_edge(fix_agent, lint_and_format)                 #    retry loop back to lint
        .add_edge(commit_and_push, report)                    # 8-9. REPORT [deterministic]
        .build()
    )
    return workflow
```

### Key AF Workflow Concepts

| AF Concept | Maps To | Description |
|---|---|---|
| **Executor** | Blueprint node | Processing unit — deterministic function or AI agent |
| **Edge** | `on_success` / `on_failure` | Connection between executors with optional conditions |
| **WorkflowBuilder** | Blueprint graph | Fluent API for constructing the directed execution graph |
| **Superstep** | Node execution round | BSP execution model — all triggered executors run, then barrier |
| **AIAgent** | Agent node | LLM-powered executor with tools, instructions, and a provider |

### The Standard Minion Blueprint

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌────────────────┐                                        │
│  │ 1. SETUP       │  [DETERMINISTIC]                       │
│  │                │  • Create branch from main              │
│  │                │  • Load agent rule files                │
│  │                │  • Parse task description               │
│  │                │  • Pre-fetch linked context (URLs, etc) │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐                                        │
│  │ 2. CONTEXT     │  [AGENT]                               │
│  │    GATHER      │  • Build repo map                      │
│  │                │  • Search for relevant code             │
│  │                │  • Navigate symbols/dependencies        │
│  │                │  • Produce: list of files to modify     │
│  │                │    + understanding of current behavior   │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐                                        │
│  │ 3. PLAN        │  [AGENT]                               │
│  │                │  • Given context, produce a plan:       │
│  │                │    - Which files to modify              │
│  │                │    - What changes to make               │
│  │                │    - Which tests to add/update          │
│  │                │  • Output: structured change plan       │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐                                        │
│  │ 4. IMPLEMENT   │  [AGENT]                               │
│  │                │  • Read files before editing             │
│  │                │  • ≤250 lines: file_write (full rewrite) │
│  │                │  • >250 lines: file_patch (surgical)     │
│  │                │  • Write/update tests (file_write)       │
│  │                │  • Tools: file_read, file_write,         │
│  │                │    file_patch, grep, symbol_nav          │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐                                        │
│  │ 5. LINT &      │  [DETERMINISTIC]                       │
│  │    FORMAT      │  • Run ruff/eslint with --fix           │
│  │                │  • Run formatter (ruff format/prettier) │
│  │                │  • Run type checker (mypy/pyright/tsc)  │
│  │                │  • Auto-apply fixable issues            │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐       ┌────────────────┐               │
│  │ 6. TEST        │  [DET]│ 7. FIX FAILURES│  [AGENT]      │
│  │                │──fail─►│                │               │
│  │ • Run affected │       │ • Read errors   │               │
│  │   tests only   │       │ • Fix code      │               │
│  │                │       │ • Re-lint       │               │
│  │                │       │ • Re-test       │               │
│  └───────┬────────┘       └───────┬────────┘               │
│          │ pass                    │                         │
│          ▼                        │ (max 2 retries)         │
│  ┌────────────────┐               │                         │
│  │ 8. COMMIT &    │◄──────────────┘                         │
│  │    PUSH        │  [DETERMINISTIC]                        │
│  │                │  • git add + commit with message        │
│  │                │  • git push to feature branch           │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐                                        │
│  │ 9. REPORT      │  [DETERMINISTIC]                       │
│  │                │  • Generate summary of changes          │
│  │                │  • Log token usage + cost               │
│  │                │  • Output: branch name, diff, status    │
│  └────────────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Why This Matters

As Stripe discovered: **"putting LLMs into contained boxes" compounds into system-wide reliability.** Running linters and formatters deterministically (not via LLM) saves tokens and eliminates a class of mistakes. The blueprint ensures that even if the LLM gets confused, the run always lints, always formats, always commits properly.

---

## 7. Agent Design

### Custom LLM Providers (No Azure Foundry)

Microsoft Agent Framework is Azure/OpenAI-centric by default. We implement **custom providers** to call **Anthropic and OpenAI APIs directly** — no Azure Foundry dependency. Each provider translates between the framework's internal format and each API's native tool-use protocol.

```python
# agent/providers/anthropic_provider.py
from agent_framework.providers import AgentProvider, ProviderResponse
import anthropic


class AnthropicProvider(AgentProvider):
    """Custom provider for direct Anthropic API calls (Claude)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, messages, tools=None, **kwargs) -> ProviderResponse:
        # Translate AF tool definitions → Anthropic tool-use format
        anthropic_tools = [self._convert_tool(t) for t in (tools or [])]
        response = await self.client.messages.create(
            model=self.model,
            messages=self._convert_messages(messages),
            tools=anthropic_tools,
            max_tokens=kwargs.get("max_tokens", 16384),
        )
        return self._convert_response(response)

    # ... conversion helpers for messages, tools, and responses
```

```python
# agent/providers/openai_provider.py
from agent_framework.providers import AgentProvider, ProviderResponse
import openai


class OpenAIProvider(AgentProvider):
    """Custom provider for direct OpenAI API calls."""

    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, messages, tools=None, **kwargs) -> ProviderResponse:
        # Translate AF tool definitions → OpenAI function-calling format
        openai_tools = [self._convert_tool(t) for t in (tools or [])]
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self._convert_messages(messages),
            tools=openai_tools,
        )
        return self._convert_response(response)

    # ... conversion helpers for messages, tools, and responses
```

### Agent Nodes (AIAgent per Blueprint Step)

Each **agent node** in the workflow is an `AIAgent` configured with its own provider, instructions, and tool subset. The framework handles the tool-use loop internally (prompt → tool calls → observe → repeat).

```python
# agent/agents.py — Agent node definitions
import os
from agent_framework.agents import AIAgent
from agent.providers.anthropic_provider import AnthropicProvider
from agent.tools import (
    repo_map, file_read, file_write, file_patch,
    grep_search, semantic_search, symbol_nav,
    dependency_graph, run_command, run_test, run_lint,
)

provider = AnthropicProvider(api_key=os.environ["ANTHROPIC_API_KEY"])

context_agent = AIAgent(
    name="context_gather",
    instructions="You are a code exploration agent...",  # see System Prompts below
    tools=[repo_map, grep_search, semantic_search, file_read, symbol_nav, dependency_graph],
    provider=provider,
)

plan_agent = AIAgent(
    name="plan",
    instructions="You are a software architect...",
    tools=[file_read],  # read-only — no writes during planning
    provider=provider,
)

implement_agent = AIAgent(
    name="implement",
    instructions="You are a senior developer...",
    tools=[file_read, file_write, file_patch, grep_search, symbol_nav, run_command],
    provider=provider,
)

fix_agent = AIAgent(
    name="fix_failures",
    instructions="You are a debugging expert...",
    tools=[file_read, file_write, file_patch, grep_search, run_test, run_lint],
    provider=provider,
)
```

### Tool Scoping Per Node

Different blueprint nodes get different tool subsets:

| Blueprint Node | Available Tools |
|---|---|
| Context Gather | `repo_map`, `grep_search`, `semantic_search`, `file_read`, `symbol_nav`, `dependency_graph` |
| Plan | `file_read` (read-only — planning only, no writes) |
| Implement | `file_read`, `file_write`, `file_patch`, `grep_search`, `symbol_nav`, `run_command` |
| Fix Failures | `file_read`, `file_write`, `file_patch`, `grep_search`, `run_test`, `run_lint` |

### System Prompt Strategy

Each `AIAgent` gets a **focused `instructions` string** that constrains its behavior:

- **Context Gather:** "You are a code exploration agent. Your job is to understand the codebase and identify files relevant to the task. Do NOT modify any files."
- **Plan:** "You are a software architect. Given context about a codebase and a task, produce a detailed change plan. Do NOT write code."
- **Implement:** "You are a senior developer operating as an unattended one-shot agent — there is no human to fix your mistakes. Reliability > token efficiency. Follow the plan. Write clean, idiomatic code. Follow existing conventions. Write tests for new behavior. For new files or files ≤250 lines: use file_write with COMPLETE content — include every original line, do not skip anything. For existing files >250 lines: use file_patch with old_string/new_string and 5+ lines of context. Always read a file before editing. Do NOT fix formatting — the linter handles that automatically."
- **Fix Failures:** "You are a debugging expert operating as an unattended agent. Read the test/lint failures, diagnose the issue, and fix the code. Make minimal changes. For small files (≤250 lines), rewrite with file_write. For large files, use file_patch. Read the file back after file_patch to verify."

---

## 8. Context Engineering

This is where your existing context management research directly applies. The agent's effectiveness depends on getting the **right 1-8% of the codebase** into context.

### Layered Context Loading (Applied to Blueprint)

| Layer | When Loaded | What | Token Budget |
|---|---|---|---|
| **Layer 0** | Always (Setup node) | Repo map (file list + signatures), agent rules, task description | ~5K tokens (5%) |
| **Layer 1** | Context Gather node | Keyword search results, symbol navigation, dependency graph neighbors | ~15K tokens (15%) |
| **Layer 2** | Implement node | Full content of files to modify + direct dependencies + relevant tests | ~40K tokens (40%) |
| **Layer 3** | If budget remains | Git blame, co-change history, docstrings, similar code examples | ~10K tokens (10%) |
| Reserved | — | System prompts, chain-of-thought, output generation | ~30K tokens (30%) |

### Repo Map Generation

Built at setup time, always in context:

```
project/
├── src/
│   ├── api/
│   │   ├── routes.py
│   │   │   ├── class UserRouter
│   │   │   │   ├── def create_user(request: CreateUserRequest) -> UserResponse
│   │   │   │   ├── def get_user(user_id: int) -> UserResponse
│   │   │   │   └── def delete_user(user_id: int) -> None
│   │   │   └── class AuthRouter
│   │   │       ├── def login(request: LoginRequest) -> TokenResponse
│   │   │       └── def logout() -> None
│   │   └── middleware.py
│   │       └── def auth_middleware(request, call_next) -> Response
│   ├── services/
│   │   ├── user_service.py
│   │   │   └── class UserService
│   │   │       ├── def create(data: CreateUserRequest) -> User
│   │   │       └── def get_by_id(user_id: int) -> User | None
│   │   └── auth_service.py
│   │       └── class AuthService
│   │           ├── def authenticate(email: str, password: str) -> User
│   │           └── def generate_token(user: User) -> str
│   └── models/
│       └── user.py
│           └── class User(BaseModel)
│               ├── id: int
│               ├── email: str
│               └── is_active: bool
├── tests/
│   ├── test_user_routes.py (5 tests)
│   ├── test_auth_routes.py (3 tests)
│   └── test_user_service.py (4 tests)
├── pyproject.toml (ruff, mypy, pytest configured)
└── README.md
```

### Multi-Signal Retrieval

For the Context Gather agent node, combine:

1. **Keyword search** (ripgrep): extract identifiers from task → search
2. **Semantic search** (ChromaDB): embed task description → find similar code chunks
3. **Dependency graph**: for each found file, include its imports and importers
4. **Rank & deduplicate**: weighted scoring, then load top files within token budget

---

## 9. MCP Tools

A curated set of tools exposed to the agent via Model Context Protocol.

### Tool Inventory

| # | Tool | Category | Description | Agent Nodes |
|---|---|---|---|---|
| 1 | `repo_map` | Context | Generate file skeleton with signatures | Context Gather |
| 2 | `file_read` | File I/O | Read file contents (full or line range). Returns line count + editing strategy hint. | All |
| 3 | `file_write` | File I/O | Write complete file contents. **Primary edit tool** for new files and files ≤250 lines. | Implement, Fix |
| 4 | `file_patch` | File I/O | Surgical search & replace edit. **Fallback** for existing files >250 lines. | Implement, Fix |
| 5 | `grep_search` | Search | Ripgrep wrapper — exact text/regex search | Context, Implement, Fix |
| 6 | `semantic_search` | Search | Vector search over code embeddings | Context |
| 7 | `symbol_nav` | Code Intel | Go-to-definition, find-references (via LSP or ctags) | Context, Implement |
| 8 | `dependency_graph` | Code Intel | Show imports/importers for a file | Context |
| 9 | `run_command` | Shell | Run arbitrary shell command (sandboxed) | Implement |
| 10 | `run_test` | Quality | Run specific test file or test name | Fix |
| 11 | `run_lint` | Quality | Run linter on specific files | Fix |
| 12 | `git_diff` | Git | Show current uncommitted changes | Implement, Fix |
| 13 | `git_log` | Git | Show recent commit history | Context |
| 14 | `web_fetch` | External | Fetch a URL (docs, issue tracker) — restricted allowlist | Context |

### File Editing Strategy (One-Shot Optimized)

In an unattended one-shot agent, **every failed tool call is expensive** — there is no human to retry or fix a bad edit. This changes the default editing strategy compared to interactive agents (Cursor, Claude Code).

#### Why `file_write` Is the Default

| Factor | `file_patch` (search & replace) | `file_write` (whole-file rewrite) |
|---|---|---|
| **Failure mode** | Silent corruption or "old_string not found" error + retry loop | Cannot fail — always produces a complete file |
| **Self-consistency** | Multiple patches can conflict or leave half-edited state | File is always internally consistent |
| **Whitespace sensitivity** | Exact match required — tabs vs spaces break it | Not an issue |
| **Multiple edits** | N sequential calls, each can fail, lines shift between calls | Single atomic call |
| **Token cost** | Lower when it works; **much higher** when retries happen | Predictable, consistent |

One failed `file_patch` retry costs 20-50x more tokens than a whole-file rewrite.

#### Size-Based Decision Rule

```
                    ┌─────────────────────┐
                    │   Need to edit a     │
                    │   file?              │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  New file?           │
                    │  (doesn't exist yet) │
                    └──────┬─────┬────────┘
                      YES  │     │  NO
                           ▼     ▼
                    file_write   │
                                 │
                    ┌────────────▼────────┐
                    │  File ≤ 250 lines?  │
                    └──────┬─────┬────────┘
                      YES  │     │  NO
                           ▼     ▼
                    file_write   file_patch
```

**Why 250 lines?** Empirically, LLMs start dropping content (missing functions, altered unchanged lines) when reproducing files above ~250 lines. Below that threshold, `file_write` has near-zero failure rate and eliminates match errors entirely.

#### `file_read` Hints the Editing Strategy

`file_read` returns a line count and a hint to guide the LLM:

```python
@mcp.tool()
def file_read(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read file contents. Returns content with line count and editing hint."""
    content = resolve_and_validate_path(path).read_text()
    line_count = len(content.splitlines())
    hint = ("Use file_write for this file."
            if line_count <= 250
            else "This file is large. Use file_patch for surgical edits.")
    return f"[{line_count} lines — {hint}]\n{content}"
```

#### The Deterministic Safety Net

The LLM doesn't need to produce perfect formatting — the blueprint's deterministic lint/format node fixes it:

```
LLM writes code (file_write/file_patch)
  → ruff format (auto-fix formatting)
  → ruff check --fix (auto-fix lint issues)
  → mypy (report type errors)
```

This is Stripe's blueprint philosophy: **let the LLM focus on logic, let deterministic tools handle formatting.**

### MCP Server Implementation

```python
# tools/server.py — Local MCP server using fastmcp
from fastmcp import FastMCP

mcp = FastMCP("coding-agent-tools")

FILE_WRITE_THRESHOLD = 250  # lines — above this, use file_patch

@mcp.tool()
def repo_map(path: str = ".") -> str:
    """Generate a skeleton of the repository with file paths and function signatures."""
    ...

@mcp.tool()
def file_read(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read file contents. Returns line count and editing strategy hint."""
    content = resolve_and_validate_path(path).read_text()
    line_count = len(content.splitlines())
    hint = ("Use file_write for this file."
            if line_count <= FILE_WRITE_THRESHOLD
            else "This file is large. Use file_patch for surgical edits.")
    # Apply line range if specified
    lines = content.splitlines(keepends=True)
    if end_line:
        lines = lines[start_line - 1:end_line]
    else:
        lines = lines[start_line - 1:]
    return f"[{line_count} lines — {hint}]\n{''.join(lines)}"

@mcp.tool()
def file_write(path: str, content: str) -> str:
    """Write complete file content. Use for new files or existing files ≤250 lines.
    For existing files >250 lines, use file_patch instead."""
    resolved = resolve_and_validate_path(path)
    resolved.write_text(content)
    return f"Wrote {path} ({len(content.splitlines())} lines)"

@mcp.tool()
def file_patch(path: str, old_string: str, new_string: str) -> str:
    """Replace exact occurrence of old_string with new_string in a file.
    Use for existing files >250 lines. Include 5+ lines of context for uniqueness.
    old_string must match exactly one location."""
    resolved = resolve_and_validate_path(path)
    content = resolved.read_text()
    count = content.count(old_string)
    if count == 0:
        return f"ERROR: old_string not found in {path}. Read the file again with file_read and retry."
    if count > 1:
        return f"ERROR: old_string matches {count} locations. Add more surrounding context lines."
    resolved.write_text(content.replace(old_string, new_string, 1))
    return f"Patched {path}"

@mcp.tool()
def grep_search(pattern: str, path: str = ".", file_glob: str = "") -> str:
    """Search for text/regex pattern in files using ripgrep."""
    ...

# ... etc.
```

### Security Boundaries

Even in a personal project, practice good hygiene:

- `run_command` is sandboxed: no network access, no `rm -rf /`, time-limited
- `file_write` / `file_patch` only operate within the repo directory (path traversal blocked)
- `file_read` returns editing strategy hints to guide the LLM toward the right tool
- `web_fetch` uses an allowlist of domains (GitHub, docs sites)
- All tool calls are logged with input/output for post-mortem

---

## 10. Devbox (Isolated Environment)

### Docker-Based Devbox

```dockerfile
# Dockerfile.devbox
FROM python:3.12-slim

# System tools
RUN apt-get update && apt-get install -y \
    git ripgrep universal-ctags curl jq \
    && rm -rf /var/lib/apt/lists/*

# Python tools
RUN pip install --no-cache-dir \
    ruff mypy pytest pytest-testmon \
    tree-sitter tree-sitter-python \
    chromadb tiktoken structlog \
    fastmcp anthropic

# Pre-warm: clone the target repo
ARG REPO_URL
ARG REPO_BRANCH=main
RUN git clone --depth=50 ${REPO_URL} /workspace
WORKDIR /workspace

# Install repo dependencies
RUN pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true

# Pre-warm: build repo map + embeddings index
COPY scripts/warm_cache.sh /scripts/warm_cache.sh
RUN bash /scripts/warm_cache.sh

# Entry point: the agent CLI
COPY agent/ /agent/
ENTRYPOINT ["python", "-m", "agent"]
```

### Lifecycle

```
1. BUILD (once, or when repo changes significantly)
   $ docker build -t agent-devbox --build-arg REPO_URL=... .

2. RUN (per task — disposable)
   $ docker run --rm agent-devbox \
       run "Add input validation to POST /users"

3. EXTRACT (get the branch out)
   - Agent pushes to remote from inside container
   - Or mount a volume to extract the git repo
```

### Why Docker, Not Just Local

| Concern | Local | Docker Devbox |
|---|---|---|
| Isolation | Agent has full access to your system | Sandboxed filesystem and network |
| Reproducibility | "Works on my machine" | Identical every time |
| Parallelism | File conflicts if running multiple agents | Each container is independent |
| Cleanup | Manual | `docker run --rm` = auto cleanup |
| Blast radius | Mistakes affect your real repo | Mistakes are discarded with container |

---

## 11. Shift-Left Feedback Loop

Stripe's key insight: **"If we know an automated check will fail CI, it's best to enforce it in the IDE and present it immediately."**

### Feedback Layers (Fastest to Slowest)

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: INLINE (during code generation)            │
│  • Agent's system prompt includes linting rules      │
│  • Agent rule files (.cursorrules) loaded in context │
│  • Token cost: near zero. Latency: 0 seconds.       │
├─────────────────────────────────────────────────────┤
│  Layer 2: LOCAL LINT (deterministic blueprint node)   │
│  • ruff check --fix + ruff format                    │
│  • mypy / pyright type check                         │
│  • Auto-fix what's fixable, report what isn't        │
│  • Latency: 1-5 seconds                             │
├─────────────────────────────────────────────────────┤
│  Layer 3: LOCAL TEST (targeted)                      │
│  • pytest-testmon: only tests affected by changes    │
│  • Or convention-based: changed src/auth/service.py  │
│    → run tests/test_auth_service.py                  │
│  • Latency: 5-30 seconds                            │
├─────────────────────────────────────────────────────┤
│  Layer 4: CI (full suite)                            │
│  • Push branch → GitHub Actions runs full tests      │
│  • If fail: feed errors back to agent, one retry     │
│  • Latency: 2-10 minutes                            │
└─────────────────────────────────────────────────────┘
```

### Retry Policy

Following Stripe's approach: **at most 2 CI runs**.

```
Attempt 1:
  → Agent writes code
  → Local lint (auto-fix)
  → Local test (targeted)
  → Push
  → CI runs

If CI fails:
  → Feed failure logs to "Fix Failures" agent node
  → Agent fixes code
  → Local lint again
  → Local test again
  → Push (attempt 2)
  → CI runs

If CI fails again:
  → Report: "Partial completion — needs human review"
  → Human takes over from the branch
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Skeleton that can run a deterministic-only workflow on your target repo.

- [ ] Set up project structure (`agent/`, `tools/`, `blueprints/`, `scripts/`)
- [ ] Install Microsoft Agent Framework (`pip install agent-framework --pre`)
- [ ] Build deterministic executors: Setup, Lint, Format, Test, Commit, Push, Report
- [ ] Wire executors into a `WorkflowBuilder` graph (deterministic-only blueprint)
- [ ] CLI entry point: `python -m agent run "task description"`
- [ ] Structured logging with `structlog` + OpenTelemetry integration
- [ ] Docker devbox: Dockerfile + `warm_cache.sh`
- [ ] Test: run workflow that just lints + tests + commits (no LLM yet)

### Phase 2: MCP Tools (Week 2-3)

**Goal:** Local MCP server with core tools working.

- [ ] Set up `fastmcp` server
- [ ] Implement tools: `file_read`, `file_write`, `file_patch`, `grep_search`
- [ ] Implement tools: `run_command`, `run_test`, `run_lint`, `git_diff`
- [ ] Implement `repo_map` using tree-sitter
- [ ] Test each tool independently with unit tests
- [ ] Security: path validation, command sandboxing

### Phase 3: Context Engine (Week 3-4)

**Goal:** Multi-signal context retrieval system.

- [ ] Repo map generator (tree-sitter skeleton)
- [ ] Keyword search tool (ripgrep wrapper)
- [ ] Semantic search: embed codebase with ChromaDB + nomic-embed
- [ ] Code chunking with tree-sitter (function/class boundaries)
- [ ] Token budget manager
- [ ] Dependency graph builder (parse import statements)
- [ ] Agent rule file loader (`.cursorrules`, `AGENTS.md`, `CLAUDE.md`)

### Phase 4: Agent Integration (Week 4-5)

**Goal:** LLM-powered AIAgent nodes integrated into workflow.

- [ ] Custom `AnthropicProvider` (translate AF format ↔ Anthropic tool-use API)
- [ ] Custom `OpenAIProvider` (translate AF format ↔ OpenAI function-calling API)
- [ ] Provider integration tests (verify tool calls round-trip correctly)
- [ ] Define `AIAgent` nodes: Context Gather, Plan, Implement, Fix Failures
- [ ] System prompts (`instructions`) for each agent node
- [ ] Tool scoping per node (restrict available tools via `AIAgent` constructor)
- [ ] Wire agent nodes into workflow alongside deterministic executors
- [ ] Conversation logging (save full transcript per run)
- [ ] Token usage tracking and cost reporting

### Phase 5: Shift-Left Integration (Week 5-6)

**Goal:** Full feedback loop working end-to-end.

- [ ] Lint node: run linter, auto-fix, report unfixable
- [ ] Type check node: run type checker, report errors
- [ ] Test node: run targeted tests, capture failure output
- [ ] Retry loop: failures → Fix agent → re-lint → re-test (max 2)
- [ ] CI integration: push branch → poll GitHub Actions → capture results
- [ ] End-to-end test: task → PR-ready branch (on a test repo)

### Phase 6: Harden & Polish (Week 6-8)

**Goal:** Reliable enough for regular personal use.

- [ ] Error handling: graceful failure at every blueprint node
- [ ] Timeout management: per-node and per-run timeouts
- [ ] Run artifacts: save full run to `runs/{timestamp}/` (transcript, diffs, logs)
- [ ] Dry-run mode: show plan without executing changes
- [ ] Configuration file: `agent.toml` for repo-specific settings
- [ ] Documentation: README, examples, common issues
- [ ] Benchmark: run against 10 known tasks, measure success rate
- [ ] Iterate on prompts and tool descriptions based on failures

---

## 13. Success Metrics

### Quantitative

| Metric | Target (v1) | How to Measure |
|---|---|---|
| One-shot success rate | ≥50% on target task types | Task passes lint + tests without human edits |
| Partial success rate | ≥80% | Produces meaningful changes, human finishes |
| Average tokens per run | <200K | Log token usage per LLM call |
| Average cost per run | <$2 | Calculate from token usage × API pricing |
| Average run time | <10 minutes | Wall clock from start to branch push |
| Retry rate (2nd CI run needed) | <30% | Track how often first push passes |

### Qualitative

- Agent follows existing code conventions (naming, patterns, structure)
- Agent writes idiomatic code (not "AI-looking" boilerplate)
- Agent commits are reviewable (clean diff, good commit message)
- Debug-ability: when it fails, the logs tell you why

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Context window too small for complex tasks | Agent misses critical code, makes wrong changes | Aggressive context filtering, iterative deepening, summarization |
| LLM hallucinates non-existent APIs | Broken code, test failures | Repo map + type info in context, local lint catches errors fast |
| LLM drops lines in file_write for large files | Missing functions/code in output | Size-based strategy: file_write ≤250 lines, file_patch above; file_read hints the correct tool |
| file_patch old_string mismatch | Wasted retry tokens, cascading failures | Fallback only for >250-line files; 5+ context lines required; read-back verification |
| Agent enters infinite retry loop | Token burn, wasted time | Hard max on iterations per node + total run timeout |
| Docker overhead slows iteration | Slow dev cycle when building the agent itself | Develop agent locally first, Docker for final integration |
| Semantic search index stale | Agent retrieves outdated code | Rebuild index on each run (fast for small repos) |
| API cost spirals | Expensive experiment | Token budget cap per run, use cheaper models for simple nodes |
| Over-engineering the framework | Never ships | Phases are scoped; ship Phase 1-4 first, polish later |

---

## 15. Future Extensions

Once v1 works reliably:

| Extension | Description |
|---|---|
| **Web UI** | Simple web dashboard showing run status, transcript, diffs |
| **Slack/Discord intake** | Trigger agent from a chat message (like Stripe's Slack integration) |
| **Multi-language support** | Add TypeScript/Go/Rust support to tools and context engine |
| **Custom blueprints** | Define task-specific blueprints (migration, dependency update, etc.) |
| **GitHub PR creation** | Auto-create PR with description, not just push branch |
| **Review feedback loop** | Feed PR review comments back to agent for revisions |
| **Parallel agents** | Run multiple agents on different tasks simultaneously |
| **Fine-tuned embeddings** | Train code embeddings on your specific codebase for better RAG |
| **Local LLM** | Run with Ollama/llama.cpp for zero API cost (quality tradeoff) |
| **Metrics dashboard** | Track success rate, cost, and common failure modes over time |

---

## Appendix A: Project Directory Structure

```
1shot-e2e-coding-agent/
├── agent/                      # Core agent code
│   ├── __init__.py
│   ├── __main__.py             # CLI entry point
│   ├── providers/              # Custom LLM providers (AF AgentProvider)
│   │   ├── __init__.py
│   │   ├── anthropic_provider.py  # Direct Anthropic API (Claude)
│   │   └── openai_provider.py     # Direct OpenAI API (GPT-4.1)
│   ├── agents.py               # AIAgent definitions (per blueprint node)
│   ├── executors.py            # Deterministic executor functions
│   ├── config.py               # Configuration loading (agent.toml)
│   └── models.py               # Data models (message types, run state, etc.)
│
├── blueprints/                 # Workflow definitions (AF WorkflowBuilder)
│   ├── __init__.py
│   └── standard.py             # Standard minion workflow (9 nodes)
│
├── tools/                      # MCP tools
│   ├── __init__.py
│   ├── server.py               # FastMCP server definition
│   ├── file_tools.py           # file_read, file_write, file_patch
│   ├── search_tools.py         # grep_search, semantic_search
│   ├── code_intel.py           # repo_map, symbol_nav, dependency_graph
│   ├── quality_tools.py        # run_test, run_lint
│   ├── git_tools.py            # git_diff, git_log, git_commit, git_push
│   └── sandbox.py              # Command sandboxing utilities
│
├── context/                    # Context engineering
│   ├── __init__.py
│   ├── repo_map.py             # Tree-sitter skeleton generator
│   ├── embeddings.py           # Embedding + ChromaDB indexing
│   ├── chunker.py              # AST-based code chunking
│   ├── token_budget.py         # Token budget manager
│   └── rule_loader.py          # Load .cursorrules, AGENTS.md, etc.
│
├── scripts/                    # Utility scripts
│   ├── warm_cache.sh           # Pre-warm devbox (index, embed, cache)
│   └── benchmark.py            # Run agent against known tasks
│
├── runs/                       # Run artifacts (gitignored)
│   └── 2026-03-10T14-30-00/
│       ├── transcript.json     # Full LLM conversation
│       ├── diff.patch          # Final code diff
│       ├── metrics.json        # Token usage, cost, timing
│       └── logs.jsonl          # Structured logs
│
├── tests/                      # Tests for the agent itself
│   ├── test_blueprint.py
│   ├── test_tools.py
│   ├── test_context.py
│   └── test_agent_loop.py
│
├── Dockerfile.devbox           # Devbox container definition
├── docker-compose.yml          # Compose file for devbox + MCP server
├── agent.toml                  # Agent configuration
├── pyproject.toml              # Python project config
├── README.md                   # Project documentation
│
├── SPEC.md                     # ← This file
├── context-management-strategies.md
└── common-context-management-strategies.md
```

## Appendix B: Example `agent.toml`

```toml
[agent]
name = "one-shot-agent"
framework = "agent-framework"  # Microsoft Agent Framework
max_tokens_per_run = 200000
max_cost_per_run_usd = 2.00
timeout_seconds = 600

[provider]
# Custom providers — call Anthropic/OpenAI APIs directly (no Azure Foundry)
default = "anthropic"
anthropic_model = "claude-sonnet-4-20250514"
openai_model = "gpt-4.1"
# API keys read from environment: ANTHROPIC_API_KEY, OPENAI_API_KEY

[repo]
path = "/workspace"
language = "python"
test_command = "pytest"
lint_command = "ruff check --fix"
format_command = "ruff format"
type_check_command = "mypy"

[context]
repo_map_max_tokens = 5000
search_results_max_tokens = 15000
full_file_max_tokens = 40000
embedding_model = "nomic-embed-text"
vector_db = "chromadb"

[shift_left]
run_lint_before_push = true
run_type_check_before_push = true
run_targeted_tests = true
max_ci_retries = 1

[git]
branch_prefix = "agent/"
commit_message_prefix = "[agent]"
auto_push = true

[file_editing]
file_write_threshold_lines = 250  # Files ≤ this → file_write; above → file_patch

[mcp]
transport = "stdio"
tools = [
    "repo_map", "file_read", "file_write", "file_patch",
    "grep_search", "semantic_search", "symbol_nav",
    "dependency_graph", "run_command", "run_test",
    "run_lint", "git_diff", "git_log",
]
```

## Appendix C: Example Run (End-to-End)

```
$ python -m agent run "Add email validation to the create_user endpoint"

[14:30:01] BLUEPRINT START: standard_minion
[14:30:01] NODE 1/9: setup [DETERMINISTIC]
           → Created branch: agent/add-email-validation-1710012601
           → Loaded 3 rule files
           → Task parsed: modify create_user, add validation

[14:30:02] NODE 2/9: context_gather [AGENT]
           → Built repo map (127 symbols, 4,832 tokens)
           → Keyword search: "create_user" → 3 files
           → Keyword search: "email" → 5 files
           → Semantic search: "email validation" → 2 chunks
           → Dependency graph: routes.py → service.py → models.py
           → Selected 6 files for context (18,432 tokens)
           [3 tool calls, 2,100 tokens used]

[14:30:08] NODE 3/9: plan [AGENT]
           → Plan: modify src/api/routes.py (add validation)
                   modify src/services/user_service.py (validate in create)
                   add tests/test_email_validation.py
           [1 tool call, 1,800 tokens used]

[14:30:12] NODE 4/9: implement [AGENT]
           → Modified: src/services/user_service.py (+12 lines)
           → Modified: src/api/routes.py (+3 lines)
           → Created: tests/test_email_validation.py (5 tests)
           [8 tool calls, 12,400 tokens used]

[14:30:25] NODE 5/9: lint_and_format [DETERMINISTIC]
           → ruff check --fix: 1 issue fixed (unused import)
           → ruff format: 2 files formatted
           → mypy: 0 errors ✓

[14:30:27] NODE 6/9: test [DETERMINISTIC]
           → pytest tests/test_email_validation.py: 5/5 passed ✓
           → pytest tests/test_user_routes.py: 5/5 passed ✓ (regression)

[14:30:33] NODE 7/9: (skipped — no failures)

[14:30:33] NODE 8/9: commit_and_push [DETERMINISTIC]
           → Committed: "[agent] Add email validation to create_user endpoint"
           → Pushed to: origin/agent/add-email-validation-1710012601

[14:30:36] NODE 9/9: report [DETERMINISTIC]
           ┌─────────────────────────────┐
           │ ✓ RUN COMPLETE              │
           │ Branch: agent/add-email-... │
           │ Files changed: 3            │
           │ Lines added: 47             │
           │ Tests: 10/10 passed         │
           │ Lint: 0 errors              │
           │ Tokens: 16,300 total        │
           │ Cost: $0.12                 │
           │ Time: 35 seconds            │
           └─────────────────────────────┘

[14:30:36] BLUEPRINT COMPLETE ✓
           Run artifacts saved to: runs/2026-03-10T14-30-01/
```
