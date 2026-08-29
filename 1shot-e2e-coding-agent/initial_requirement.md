# One-Shot End-to-End Coding Agent — Pi-Based Spec

> Same vision as the original SPEC.md — a Stripe Minions-inspired unattended one-shot coding agent — but rebuilt around [Pi](https://github.com/mariozechner/pi) as the agent harness instead of Microsoft Agent Framework.

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
- [9. Tools (Pi Extensions + Built-ins)](#9-tools-pi-extensions--built-ins)
- [10. Devbox (Isolated Environment)](#10-devbox-isolated-environment)
- [11. Shift-Left Feedback Loop](#11-shift-left-feedback-loop)
- [12. Implementation Phases](#12-implementation-phases)
- [13. Success Metrics](#13-success-metrics)
- [14. Risks & Mitigations](#14-risks--mitigations)
- [15. Future Extensions](#15-future-extensions)

---

## 1. Vision & Goals

### What

Build a **personal-scale "Minion"**: an unattended coding agent that takes a task description, operates on an existing brownfield codebase inside an isolated environment, produces a code change, runs linters and tests, and delivers a PR-ready branch — all in one shot with no human interaction during execution.

### Why (Same as Original)

- Learn the end-to-end mechanics of building a production-*flavored* coding agent
- Understand the interplay between **blueprints** (deterministic workflow), **agent loops** (LLM-driven), **context engineering**, and **shift-left feedback**
- Create a reusable personal tool for automating repetitive coding tasks on side projects
- Build intuition on what makes agents succeed or fail at scale

### Why Pi

Pi is chosen as the agent harness despite being a TypeScript-only interactive coding agent. The redesign embraces Pi's strengths:

- **15+ LLM providers** natively supported — no custom provider wrappers needed
- **Extension system** — register custom tools, commands, and event hooks in TypeScript
- **Skills system** — instruction-based capabilities via SKILL.md files
- **SDK for embedding** — `createAgentSession()` + `session.prompt()` for programmatic use
- **Built-in coding tools** — `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls` out of the box
- **MIT licensed**, actively developed, aggressively extensible

### What Changes

| Original Spec | Pi-Based Spec |
|---|---|
| Python 3.12+ | TypeScript (Node.js 20+) |
| Microsoft Agent Framework (WorkflowBuilder, Executors, Edges) | Custom TypeScript orchestrator driving Pi SDK sessions |
| Custom AnthropicProvider + OpenAIProvider classes | Pi's native multi-provider support (no wrappers) |
| FastMCP server with 14 MCP tools | Pi built-in tools (7) + Pi Extensions (~7 custom) |
| `agent.toml` config | `pi-agent.config.ts` + `.pi/settings.json` |
| `pyproject.toml` + ruff/mypy/pytest | `package.json` + tsconfig + vitest |

### Non-Goals (for v1)

- Multi-repo or monorepo support
- Slack/web UI for task intake (CLI is fine)
- Multi-user or team use
- Production-grade security hardening
- Custom model training/fine-tuning

---

## 2. Key Concepts (Borrowed from Stripe Minions)

| Stripe Concept | Our Adaptation (Pi-Based) |
|---|---|
| **Devbox** — isolated EC2 instances with pre-warmed code/services | Docker container with Node.js + Pi installed globally, repo + tools pre-loaded |
| **Blueprint** — state machine mixing deterministic nodes + agent nodes | Custom TypeScript orchestrator: sequences Pi SDK sessions + direct function calls |
| **Agent harness** — forked goose agent with Stripe customizations | Pi (`@mariozechner/pi-coding-agent`) with custom extensions for domain tools |
| **Rule files** — `.cursorrules`, `AGENTS.md`, scoped to subdirectories | `AGENTS.md` / `SYSTEM.md` loaded contextually by Pi + per-node system prompts |
| **Toolshed (MCP)** — centralized MCP server with ~500 tools | Pi built-in tools + Pi Extensions (TypeScript) for custom capabilities |
| **Shift-left feedback** — lint locally before pushing, max 2 CI rounds | Same: local lint + test → push → CI check → one retry loop |
| **One-shot** — from task to PR with no human in the loop | Same: task → branch → code → lint → test → PR-ready branch |

---

## 3. Scope & Constraints

### Target Repository

Pick **one brownfield repo** you actively work on. Ideal characteristics:

- **Language:** Python (easiest tooling) or TypeScript (natural Pi fit)
- **Size:** 5K–50K LOC
- **Has tests:** Existing test suite (pytest, jest, vitest, etc.)
- **Has linting:** Configured linter (ruff, eslint, biome, etc.)
- **Has CI:** GitHub Actions or similar

> **Note:** The agent itself is written in TypeScript (Pi's language). The *target repository* it operates on can be any language — the agent interacts via shell commands, not language-native APIs.

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
│  $ npx pi-agent run "Add input validation to POST /users"       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR (TypeScript)                          │
│          Drives Pi SDK sessions per blueprint node               │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │  Setup   │──►│ Context  │──►│ Implement│──►│  Lint &  │   │
│  │(TS func) │   │ Gather   │   │(Pi sess) │   │  Format  │   │
│  │          │   │(Pi sess) │   │          │   │ (TS func)│   │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   │
│       │                                             │          │
│       │              ┌──────────┐   ┌──────────┐    │          │
│       │              │  Test    │──►│  Commit  │    │          │
│       │              │(TS func) │   │ & Push   │    │          │
│       │              └──────────┘   │ (TS func)│    │          │
│       │                    │        └──────────┘    │          │
│       │                    ▼              │         │          │
│       │              ┌──────────┐   ┌──────────┐   │          │
│       │              │ Fix      │──►│  Final   │   │          │
│       │              │ Failures │   │  Report  │   │          │
│       │              │(Pi sess) │   │ (TS func)│   │          │
│       │              └──────────┘   └──────────┘   │          │
│       │                                             │          │
└───────┼─────────────────────────────────────────────┼──────────┘
        │                                             │
        ▼                                             ▼
┌──────────────┐                            ┌──────────────────┐
│   DEVBOX     │                            │  PI TOOLS        │
│(Docker+Node) │                            │                  │
│              │                            │  Built-in:       │
│ • Git repo   │                            │  • read          │
│ • Linters    │                            │  • write         │
│ • Test suite │                            │  • edit          │
│ • Pi CLI     │                            │  • bash          │
│   (global)   │                            │  • grep          │
│              │                            │  • find, ls      │
└──────────────┘                            │                  │
                                            │  Extensions:     │
                                            │  • repo_map      │
                                            │  • semantic_srch │
                                            │  • symbol_nav    │
                                            │  • dep_graph     │
                                            │  • run_test      │
                                            │  • run_lint      │
                                            │  • web_fetch     │
                                            └──────────────────┘
```

**Key difference from original:** There is no external MCP server. Pi's built-in tools cover file I/O, shell, and search. Custom capabilities are registered as Pi Extensions loaded per-session.

---

## 5. Tech Stack

### Core

| Component | Technology | Why |
|---|---|---|
| **Language** | TypeScript (Node.js 20+) | Pi is TypeScript-native; extensions, orchestrator, and config are all TS |
| **LLM** | Claude 4 Sonnet (via Pi's native Anthropic support) | Strong coding, tool-use, long context. Swap to GPT-4.1 / Gemini via Pi's 15+ providers. |
| **Agent harness** | Pi (`@mariozechner/pi-coding-agent`) | Built-in coding tools, extension system, SDK for embedding, multi-model support |
| **Orchestrator** | Custom TypeScript module (`src/orchestrator.ts`) | Sequences Pi SDK sessions per blueprint node, handles conditional routing and retries |
| **CLI** | `commander` or Pi's own CLI with custom commands | Task intake, config, dry-run mode |

### Devbox / Environment

| Component | Technology | Why |
|---|---|---|
| **Container runtime** | Docker + Docker Compose | Isolated, reproducible, disposable |
| **Base image** | `node:20-slim` | Pi requires Node.js; target repo tools installed separately |
| **Pre-warm script** | `scripts/warm-cache.sh` | Clone target repo, install deps, warm caches, build indexes |
| **Pi installation** | `npm install -g @mariozechner/pi-coding-agent` | Global Pi install in container |

### Tools

| Component | Technology | Why |
|---|---|---|
| **Built-in tools** | Pi's `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls` | Cover ~70% of tool needs out of the box, no MCP needed |
| **Custom tools** | Pi Extensions (`ExtensionAPI.registerTool()`) | TypeScript functions registered per-session for domain-specific capabilities |
| **Tool scoping** | `--tools <list>` and `--no-tools` + `--no-extensions -e <ext>` CLI flags | Restrict available tools per blueprint node |

### Context Engineering

| Component | Technology | Why |
|---|---|---|
| **Repo map** | `tree-sitter` (WASM bindings for Node.js) + custom skeleton generator | Layer 0 context (file list + signatures) |
| **Keyword search** | Pi's built-in `grep` tool (ripgrep-based) | Fast exact-match search, no custom tool needed |
| **Semantic search** | `chromadb` (Python sidecar) or `vectra` (native TS) + local embeddings | Meaning-based code retrieval, zero API cost |
| **Code chunking** | tree-sitter AST-based splitter (TS) | Chunk at function/class boundaries |
| **Token counting** | `tiktoken` (WASM) or Anthropic's tokenizer | Budget management |
| **Context files** | `AGENTS.md`, `SYSTEM.md`, SKILL.md files — all native to Pi | Pi auto-loads these for context |

### Shift-Left / Quality

| Component | Technology | Why |
|---|---|---|
| **Linter** | `ruff` (Python targets) / `eslint` (TS targets) — invoked via `bash` tool | Fast, auto-fixable |
| **Type checker** | `mypy`/`pyright` (Python) / `tsc` (TS) — invoked via `bash` tool | Catch type errors before CI |
| **Test runner** | `pytest` (Python) / `jest`/`vitest` (TS) — invoked via `bash` tool | Run targeted tests |
| **Formatter** | `ruff format` / `prettier` — invoked via `bash` tool | Deterministic formatting |
| **Git** | `simple-git` (Node.js) or shell commands via `bash` | Branch management, commits, push |

### Observability

| Component | Technology | Why |
|---|---|---|
| **Session logs** | Pi's native JSONL session files (tree-structured) | Full conversation transcript per node |
| **Step tracing** | Custom orchestrator logging (`pino` or `winston`) | Structured JSON logs for every blueprint step |
| **Cost tracking** | Token counting per Pi session | Track API spend per run |
| **Run artifacts** | Save sessions + diffs to `runs/` directory | Post-mortem analysis |

---

## 6. The Blueprint (Workflow Engine)

### The Challenge

Pi has **zero built-in workflow orchestration**. It's a single-session interactive agent. We must build the blueprint engine ourselves as a TypeScript orchestrator that drives Pi SDK sessions.

### Orchestrator Design

The orchestrator is a TypeScript module that replaces Microsoft Agent Framework's `WorkflowBuilder`. It defines a directed graph of **steps**, where each step is either a **deterministic function** (plain TypeScript) or an **agent session** (Pi SDK `createAgentSession`).

```typescript
// src/orchestrator.ts — Blueprint orchestrator driving Pi SDK sessions
import { createAgentSession, SessionManager, AuthStorage, ModelRegistry } from "@mariozechner/pi-coding-agent";
import { StepResult, BlueprintStep, BlueprintConfig } from "./types.js";

type StepFn = (ctx: RunContext) => Promise<StepResult>;
type NextFn = (result: StepResult) => string | null; // returns next step ID or null to end

interface BlueprintNode {
  id: string;
  type: "deterministic" | "agent";
  execute: StepFn;
  next: NextFn;
}

export class BlueprintRunner {
  private nodes = new Map<string, BlueprintNode>();
  private entryNode: string;

  constructor(entryNode: string) {
    this.entryNode = entryNode;
  }

  addNode(node: BlueprintNode): this {
    this.nodes.set(node.id, node);
    return this;
  }

  async run(ctx: RunContext): Promise<RunReport> {
    let currentId: string | null = this.entryNode;
    const report = new RunReport();

    while (currentId) {
      const node = this.nodes.get(currentId);
      if (!node) throw new Error(`Unknown node: ${currentId}`);

      ctx.logger.info({ node: currentId, type: node.type }, "executing node");
      const start = Date.now();

      const result = await node.execute(ctx);

      report.addStep({
        nodeId: currentId,
        type: node.type,
        duration: Date.now() - start,
        tokensUsed: result.tokensUsed ?? 0,
        status: result.status,
      });

      currentId = node.next(result);
    }

    return report;
  }
}
```

### Building the Standard Blueprint

```typescript
// src/blueprints/standard.ts — Standard minion blueprint (9 nodes)
import { BlueprintRunner } from "../orchestrator.js";
import { setupStep } from "../steps/setup.js";
import { contextGatherStep } from "../steps/context-gather.js";
import { planStep } from "../steps/plan.js";
import { implementStep } from "../steps/implement.js";
import { lintAndFormatStep } from "../steps/lint-format.js";
import { testStep } from "../steps/test.js";
import { fixFailuresStep } from "../steps/fix-failures.js";
import { commitAndPushStep } from "../steps/commit-push.js";
import { reportStep } from "../steps/report.js";

export function buildStandardBlueprint(maxRetries = 2): BlueprintRunner {
  let retryCount = 0;

  return new BlueprintRunner("setup")
    .addNode({
      id: "setup",
      type: "deterministic",
      execute: setupStep,
      next: () => "context_gather",
    })
    .addNode({
      id: "context_gather",
      type: "agent",
      execute: contextGatherStep,
      next: () => "plan",
    })
    .addNode({
      id: "plan",
      type: "agent",
      execute: planStep,
      next: () => "implement",
    })
    .addNode({
      id: "implement",
      type: "agent",
      execute: implementStep,
      next: () => "lint_and_format",
    })
    .addNode({
      id: "lint_and_format",
      type: "deterministic",
      execute: lintAndFormatStep,
      next: () => "test",
    })
    .addNode({
      id: "test",
      type: "deterministic",
      execute: testStep,
      next: (result) => result.status === "passed" ? "commit_and_push" : "fix_failures",
    })
    .addNode({
      id: "fix_failures",
      type: "agent",
      execute: fixFailuresStep,
      next: () => {
        retryCount++;
        return retryCount >= maxRetries ? "commit_and_push" : "lint_and_format";
      },
    })
    .addNode({
      id: "commit_and_push",
      type: "deterministic",
      execute: commitAndPushStep,
      next: () => "report",
    })
    .addNode({
      id: "report",
      type: "deterministic",
      execute: reportStep,
      next: () => null, // end
    });
}
```

### Key Orchestrator Concepts

| Concept | Maps To | Description |
|---|---|---|
| **BlueprintNode** | Blueprint step | Either a deterministic TS function or a Pi SDK agent session |
| **next function** | Edge / routing | Returns the next node ID, or `null` to end. Enables conditional branching. |
| **BlueprintRunner** | Blueprint graph | Holds nodes, executes them sequentially following the `next` chain |
| **RunContext** | Shared state | Carries task description, workspace path, accumulated context, config |
| **StepResult** | Node output | Contains status, token usage, any data to pass forward |

### Why This Matters

Same as the original spec: **"putting LLMs into contained boxes" compounds into system-wide reliability.** The orchestrator ensures deterministic steps always run — lint, format, commit — regardless of what the LLM does. The LLM handles reasoning (context gathering, planning, implementing); deterministic TypeScript handles everything else.

---

## 7. Agent Design

### No Custom Providers Needed

Unlike the original spec (which required custom `AnthropicProvider` and `OpenAIProvider` classes for Microsoft Agent Framework), **Pi natively supports 15+ LLM providers**. No wrapper code needed.

Provider selection is done via configuration or CLI flags:

```bash
# Use Anthropic Claude
pi --provider anthropic --model claude-sonnet-4-20250514

# Use OpenAI GPT-4.1
pi --provider openai --model gpt-4.1

# Use local Ollama
pi --provider ollama --model deepseek-coder-v2
```

### Agent Nodes via Pi SDK Sessions

Each **agent node** in the blueprint is a separate Pi SDK session with its own system prompt, tool restrictions, and extension set.

```typescript
// src/steps/context-gather.ts — Context Gather agent node
import { createAgentSession, SessionManager, AuthStorage, ModelRegistry } from "@mariozechner/pi-coding-agent";
import { RunContext, StepResult } from "../types.js";

export async function contextGatherStep(ctx: RunContext): Promise<StepResult> {
  const authStorage = AuthStorage.create();
  const modelRegistry = new ModelRegistry(authStorage);

  const { session } = await createAgentSession({
    sessionManager: SessionManager.inMemory(),
    authStorage,
    modelRegistry,
    // Per-node configuration
    systemPrompt: CONTEXT_GATHER_PROMPT,
    extensions: [ctx.config.extensionsDir + "/context-tools.ts"],
    tools: ["read", "grep", "find", "ls", "bash"],  // read-only built-ins
    provider: ctx.config.provider,
    model: ctx.config.model,
  });

  const result = await session.prompt(`
Task: ${ctx.task}

Workspace: ${ctx.workspacePath}

Repo Map:
${ctx.repoMap}

Instructions:
1. Search the codebase to find all files relevant to this task
2. Navigate symbols and dependencies to understand the code structure
3. Output a JSON summary: { "files": [...], "understanding": "..." }
  `);

  // Parse structured output from the agent
  const parsed = extractJSON(result);

  return {
    status: "passed",
    tokensUsed: session.tokenUsage?.total ?? 0,
    data: { relevantFiles: parsed.files, understanding: parsed.understanding },
  };
}

const CONTEXT_GATHER_PROMPT = `You are a code exploration agent. Your ONLY job is to understand the codebase and identify files relevant to the task.

Rules:
- Do NOT modify any files
- Use grep and find to search for relevant code
- Use read to examine file contents
- Use the repo_map and semantic_search extension tools for deeper analysis
- Output a JSON object with "files" (array of file paths) and "understanding" (string summary)
`;
```

```typescript
// src/steps/implement.ts — Implement agent node
import { createAgentSession, SessionManager, AuthStorage, ModelRegistry } from "@mariozechner/pi-coding-agent";
import { RunContext, StepResult } from "../types.js";

export async function implementStep(ctx: RunContext): Promise<StepResult> {
  const authStorage = AuthStorage.create();
  const modelRegistry = new ModelRegistry(authStorage);

  const { session } = await createAgentSession({
    sessionManager: SessionManager.inMemory(),
    authStorage,
    modelRegistry,
    systemPrompt: IMPLEMENT_PROMPT,
    extensions: [],  // no custom extensions needed — built-in tools suffice
    tools: ["read", "write", "edit", "bash", "grep", "find"],  // write-capable
    provider: ctx.config.provider,
    model: ctx.config.model,
  });

  const result = await session.prompt(`
Task: ${ctx.task}

Plan:
${ctx.plan}

Relevant Files:
${ctx.relevantFiles.map(f => `- ${f}`).join("\n")}

Instructions:
Follow the plan. Implement the changes. Write tests for new behavior.
For new files or files ≤250 lines: use 'write' with COMPLETE content.
For existing files >250 lines: use 'edit' for surgical edits.
Always read a file before editing it.
Do NOT fix formatting — the linter handles that automatically.
  `);

  return {
    status: "passed",
    tokensUsed: session.tokenUsage?.total ?? 0,
  };
}

const IMPLEMENT_PROMPT = `You are a senior developer operating as an unattended one-shot agent — there is no human to fix your mistakes. Reliability > token efficiency.

Follow the plan exactly. Write clean, idiomatic code. Follow existing conventions.
Write tests for new behavior.

File editing strategy:
- New files or files ≤250 lines: use 'write' to create complete file content
- Existing files >250 lines: use 'edit' for surgical search-and-replace
- Always 'read' a file before editing it
- Do NOT fix formatting — the deterministic linter handles that
`;
```

### Tool Scoping Per Node

Different blueprint nodes get different tool subsets, enforced via the Pi SDK session configuration:

| Blueprint Node | Pi Built-in Tools | Pi Extensions |
|---|---|---|
| Context Gather | `read`, `grep`, `find`, `ls` | `repo_map`, `semantic_search`, `symbol_nav`, `dependency_graph` |
| Plan | `read` | *(none — planning only, no writes)* |
| Implement | `read`, `write`, `edit`, `bash`, `grep`, `find` | *(none — built-ins suffice)* |
| Fix Failures | `read`, `write`, `edit`, `bash`, `grep` | `run_test`, `run_lint` |

#### How Tool Scoping Works in Pi

Pi supports per-session tool restriction:

```typescript
// Option 1: SDK session config (preferred for our orchestrator)
const { session } = await createAgentSession({
  tools: ["read", "grep", "find", "ls"],          // only these built-ins
  extensions: ["./extensions/context-tools.ts"],    // only these extensions
  // ...
});

// Option 2: CLI flags (if spawning Pi as a subprocess)
// pi --no-tools --tools read,grep,find,ls --no-extensions -e ./extensions/context-tools.ts -p "..."
```

### System Prompt Strategy

Each Pi session gets a **focused system prompt** via the `systemPrompt` parameter:

- **Context Gather:** "You are a code exploration agent. Your job is to understand the codebase and identify files relevant to the task. Do NOT modify any files."
- **Plan:** "You are a software architect. Given context about a codebase and a task, produce a detailed change plan. Do NOT write code."
- **Implement:** "You are a senior developer operating as an unattended one-shot agent — there is no human to fix your mistakes. Reliability > token efficiency. Follow the plan. Write clean, idiomatic code. For new files or files ≤250 lines: use write with COMPLETE content. For existing files >250 lines: use edit for surgical changes. Always read a file before editing. Do NOT fix formatting — the linter handles that automatically."
- **Fix Failures:** "You are a debugging expert operating as an unattended agent. Read the test/lint failures, diagnose the issue, and fix the code. Make minimal changes."

---

## 8. Context Engineering

### Pi-Native Context Mechanisms

Pi provides three native context mechanisms that replace some of the custom infrastructure from the original spec:

| Pi Mechanism | What It Does | Maps To |
|---|---|---|
| **AGENTS.md** | Auto-loaded when Pi enters a directory. Contains project rules, conventions, coding standards. | Rule files (`.cursorrules` equivalent) |
| **SYSTEM.md** | Appended to the system prompt. Global instructions. | Layer 0 "always-on" context |
| **SKILL.md** | Capability instructions that Pi can discover and follow. | Agent capability prompts |
| **Auto-compaction** | Pi automatically summarizes long conversations to stay within context window. | Token budget management (partial) |
| **Session files** | Tree-structured JSONL files that can be resumed. | Conversation history / checkpointing |

### Layered Context Loading (Applied to Blueprint)

Same layered approach as the original, but adapted for Pi's mechanisms:

| Layer | When Loaded | What | Token Budget | How (Pi-Based) |
|---|---|---|---|---|
| **Layer 0** | Always (Setup node) | Repo map, agent rules, task description | ~5K tokens (5%) | Generated by `repo_map` extension, injected into first prompt. `AGENTS.md` auto-loaded by Pi. |
| **Layer 1** | Context Gather node | Keyword search results, symbol navigation, dependency graph | ~15K tokens (15%) | Pi's built-in `grep`/`find` + custom `semantic_search`/`symbol_nav` extensions |
| **Layer 2** | Implement node | Full content of files to modify + direct dependencies + tests | ~40K tokens (40%) | Passed as context in the implement step's prompt (from context gather output) |
| **Layer 3** | If budget remains | Git blame, co-change history, docstrings, similar code examples | ~10K tokens (10%) | `bash` tool running `git log`, `git blame` |
| Reserved | — | System prompts, chain-of-thought, output generation | ~30K tokens (30%) | Pi's auto-compaction helps manage this |

### Repo Map Generation

Same as original — built at setup time using tree-sitter, exposed as a Pi Extension tool:

```typescript
// extensions/context-tools.ts
import { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { generateRepoMap } from "../src/context/repo-map.js";

export default function(pi: ExtensionAPI) {
  pi.registerTool({
    name: "repo_map",
    description: "Generate a skeleton of the repository with file paths and function/class signatures.",
    parameters: {
      path: { type: "string", description: "Root path to scan", default: "." },
      maxTokens: { type: "number", description: "Max tokens for the map", default: 5000 },
    },
    execute: async ({ path, maxTokens }) => {
      return await generateRepoMap(path, maxTokens);
    },
  });
}
```

### Multi-Signal Retrieval

For the Context Gather agent node, same strategy:

1. **Keyword search** (Pi's built-in `grep`): agent uses it directly — no wrapper needed
2. **Semantic search** (custom extension): embed task description → find similar code chunks
3. **Dependency graph** (custom extension): for each found file, include its imports and importers
4. **Rank & deduplicate**: handled by the context gather agent's reasoning

### AGENTS.md File (Project Rules)

Placed in the target repo root, auto-loaded by Pi:

```markdown
# AGENTS.md — Project Rules for AI Agents

## Coding Conventions
- Follow existing code patterns and naming conventions
- Use type annotations for all function parameters and return types
- Write docstrings for public functions

## Testing
- Every new feature must have corresponding tests
- Test file naming: `test_<module>.py` or `<module>.test.ts`
- Use pytest fixtures for test setup (Python)

## File Editing
- Files ≤250 lines: rewrite completely with `write`
- Files >250 lines: use `edit` for surgical changes
- Always read a file before editing it

## Do Not
- Do not modify configuration files unless explicitly asked
- Do not change import sorting — the formatter handles it
- Do not add print/console.log debugging statements
```

---

## 9. Tools (Pi Extensions + Built-ins)

### Tool Inventory

Pi's philosophy is **"No MCP — build CLI tools with READMEs."** Instead of an MCP server, we use Pi's built-in tools plus custom Extensions.

| # | Tool | Source | Description | Agent Nodes |
|---|---|---|---|---|
| 1 | `read` | Pi built-in | Read file contents (full or line range) | All |
| 2 | `write` | Pi built-in | Write complete file contents | Implement, Fix |
| 3 | `edit` | Pi built-in | Surgical search & replace edit | Implement, Fix |
| 4 | `bash` | Pi built-in | Run shell command | Implement, Fix |
| 5 | `grep` | Pi built-in | Ripgrep wrapper — text/regex search | Context, Implement, Fix |
| 6 | `find` | Pi built-in | Find files by name/pattern | Context, Implement |
| 7 | `ls` | Pi built-in | List directory contents | Context |
| 8 | `repo_map` | Extension | Generate file skeleton with signatures (tree-sitter) | Context |
| 9 | `semantic_search` | Extension | Vector search over code embeddings | Context |
| 10 | `symbol_nav` | Extension | Go-to-definition, find-references (ctags/tree-sitter) | Context |
| 11 | `dependency_graph` | Extension | Show imports/importers for a file | Context |
| 12 | `run_test` | Extension | Run specific test file or test name (wraps pytest/jest) | Fix |
| 13 | `run_lint` | Extension | Run linter on specific files (wraps ruff/eslint) | Fix |
| 14 | `web_fetch` | Extension | Fetch a URL (docs, issue tracker) — restricted allowlist | Context |

### File Editing Strategy (Same as Original)

The one-shot optimized editing strategy carries over unchanged:

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
                     write       │
                                 │
                    ┌────────────▼────────┐
                    │  File ≤ 250 lines?  │
                    └──────┬─────┬────────┘
                      YES  │     │  NO
                           ▼     ▼
                     write       edit
```

**Mapping to Pi's built-in tools:**
- Original `file_write` → Pi's `write` tool (writes complete file)
- Original `file_patch` → Pi's `edit` tool (surgical search & replace)
- Original `file_read` → Pi's `read` tool (reads file contents)

### Custom Extension Implementation

```typescript
// extensions/context-tools.ts — Custom tools for context gathering
import { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { generateRepoMap } from "../src/context/repo-map.js";
import { searchEmbeddings } from "../src/context/embeddings.js";
import { navigateSymbol } from "../src/context/symbol-nav.js";
import { buildDependencyGraph } from "../src/context/dep-graph.js";

export default function(pi: ExtensionAPI) {

  pi.registerTool({
    name: "repo_map",
    description: "Generate a skeleton of the repository with file paths and function/class signatures.",
    parameters: {
      path: { type: "string", description: "Root path to scan", default: "." },
    },
    execute: async ({ path }) => {
      return await generateRepoMap(path);
    },
  });

  pi.registerTool({
    name: "semantic_search",
    description: "Search code using semantic similarity. Returns code chunks most related to the query.",
    parameters: {
      query: { type: "string", description: "Natural language search query" },
      maxResults: { type: "number", description: "Max results to return", default: 5 },
    },
    execute: async ({ query, maxResults }) => {
      return await searchEmbeddings(query, maxResults);
    },
  });

  pi.registerTool({
    name: "symbol_nav",
    description: "Navigate to symbol definition or find all references. Uses ctags or tree-sitter.",
    parameters: {
      symbol: { type: "string", description: "Symbol name to look up" },
      action: { type: "string", description: "'definition' or 'references'", default: "definition" },
    },
    execute: async ({ symbol, action }) => {
      return await navigateSymbol(symbol, action);
    },
  });

  pi.registerTool({
    name: "dependency_graph",
    description: "Show imports and importers for a given file.",
    parameters: {
      filePath: { type: "string", description: "File to analyze" },
    },
    execute: async ({ filePath }) => {
      return await buildDependencyGraph(filePath);
    },
  });
}
```

```typescript
// extensions/quality-tools.ts — Custom tools for testing and linting
import { ExtensionAPI } from "@mariozechner/pi-coding-agent";

export default function(pi: ExtensionAPI) {

  pi.registerTool({
    name: "run_test",
    description: "Run specific tests. Wraps pytest (Python) or jest/vitest (TS).",
    parameters: {
      target: { type: "string", description: "Test file or test name to run" },
    },
    execute: async ({ target }) => {
      // Delegates to bash internally, but provides structured output
      const { execSync } = await import("child_process");
      try {
        const output = execSync(`pytest ${target} -v --tb=short 2>&1`, {
          cwd: process.env.WORKSPACE_PATH,
          timeout: 60_000,
          encoding: "utf-8",
        });
        return `PASSED\n${output}`;
      } catch (err: any) {
        return `FAILED\n${err.stdout ?? ""}\n${err.stderr ?? ""}`;
      }
    },
  });

  pi.registerTool({
    name: "run_lint",
    description: "Run linter on specific files. Wraps ruff (Python) or eslint (TS).",
    parameters: {
      files: { type: "string", description: "Space-separated file paths to lint" },
    },
    execute: async ({ files }) => {
      const { execSync } = await import("child_process");
      try {
        const output = execSync(`ruff check ${files} 2>&1`, {
          cwd: process.env.WORKSPACE_PATH,
          timeout: 30_000,
          encoding: "utf-8",
        });
        return `CLEAN\n${output}`;
      } catch (err: any) {
        return `ISSUES\n${err.stdout ?? ""}\n${err.stderr ?? ""}`;
      }
    },
  });
}
```

### Security Boundaries

Same hygiene as the original spec, enforced differently:

- Pi's `bash` tool runs commands directly — wrap sensitive operations in extensions with validation
- `write` / `edit` only operate within the repo directory (enforced by Docker mount + extension validation)
- `web_fetch` extension uses an allowlist of domains
- All Pi sessions log full JSONL transcripts for post-mortem
- No `--dangerously-skip-permissions` — not needed since Pi has no permission popups by design

---

## 10. Devbox (Isolated Environment)

### Docker-Based Devbox

```dockerfile
# Dockerfile.devbox
FROM node:20-slim

# System tools (for the target repo, not the agent)
RUN apt-get update && apt-get install -y \
    git ripgrep universal-ctags curl jq python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Pi globally
RUN npm install -g @mariozechner/pi-coding-agent

# Install agent orchestrator
COPY package.json package-lock.json /agent/
WORKDIR /agent
RUN npm ci --production

COPY src/ /agent/src/
COPY extensions/ /agent/extensions/
COPY skills/ /agent/skills/
COPY scripts/ /agent/scripts/

# Pre-warm: clone the target repo
ARG REPO_URL
ARG REPO_BRANCH=main
RUN git clone --depth=50 ${REPO_URL} /workspace

# Install target repo dependencies (Python or Node-based)
WORKDIR /workspace
RUN pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
RUN npm install 2>/dev/null || true

# Pre-warm: build repo map + embeddings index
RUN bash /agent/scripts/warm-cache.sh

# Entry point: the orchestrator CLI
WORKDIR /agent
ENTRYPOINT ["node", "src/cli.js"]
```

### Lifecycle

```
1. BUILD (once, or when repo changes significantly)
   $ docker build -t pi-agent-devbox --build-arg REPO_URL=... .

2. RUN (per task — disposable)
   $ docker run --rm \
       -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
       pi-agent-devbox \
       run "Add input validation to POST /users"

3. EXTRACT (get the branch out)
   - Agent pushes to remote from inside container
   - Or mount a volume to extract the git repo
```

### Why Docker (Same Reasoning)

| Concern | Local | Docker Devbox |
|---|---|---|
| Isolation | Agent has full access to your system | Sandboxed filesystem and network |
| Reproducibility | "Works on my machine" | Identical every time |
| Parallelism | File conflicts if running multiple agents | Each container is independent |
| Cleanup | Manual | `docker run --rm` = auto cleanup |
| Blast radius | Mistakes affect your real repo | Mistakes are discarded with container |

---

## 11. Shift-Left Feedback Loop

Identical to the original spec — the shift-left philosophy is framework-agnostic.

### Feedback Layers (Fastest to Slowest)

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: INLINE (during code generation)            │
│  • Agent's system prompt includes linting rules      │
│  • AGENTS.md auto-loaded by Pi for project rules     │
│  • Token cost: near zero. Latency: 0 seconds.       │
├─────────────────────────────────────────────────────┤
│  Layer 2: LOCAL LINT (deterministic blueprint node)   │
│  • ruff check --fix + ruff format (Python)           │
│  • eslint --fix + prettier (TypeScript)              │
│  • mypy / pyright / tsc type check                   │
│  • Auto-fix what's fixable, report what isn't        │
│  • Latency: 1-5 seconds                             │
├─────────────────────────────────────────────────────┤
│  Layer 3: LOCAL TEST (targeted)                      │
│  • pytest-testmon or convention-based (Python)       │
│  • Jest --changedSince or vitest related (TS)        │
│  • Only tests affected by changes                    │
│  • Latency: 5-30 seconds                            │
├─────────────────────────────────────────────────────┤
│  Layer 4: CI (full suite)                            │
│  • Push branch → GitHub Actions runs full tests      │
│  • If fail: feed errors back to agent, one retry     │
│  • Latency: 2-10 minutes                            │
└─────────────────────────────────────────────────────┘
```

### Retry Policy

At most 2 CI runs (same as original):

```
Attempt 1:
  → Agent writes code
  → Local lint (auto-fix)
  → Local test (targeted)
  → Push
  → CI runs

If CI fails:
  → Feed failure logs to "Fix Failures" agent node (Pi session)
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

**Goal:** Skeleton orchestrator that can run a deterministic-only workflow.

- [ ] Set up TypeScript project structure (`src/`, `extensions/`, `skills/`, `scripts/`)
- [ ] Install Pi SDK (`npm install @mariozechner/pi-coding-agent`)
- [ ] Install dev dependencies (`typescript`, `vitest`, `pino`, `simple-git`, `commander`)
- [ ] Build deterministic step functions: setup, lint-format, test, commit-push, report
- [ ] Build `BlueprintRunner` orchestrator class
- [ ] Wire steps into the standard blueprint (deterministic-only, no Pi sessions yet)
- [ ] CLI entry point: `npx pi-agent run "task description"`
- [ ] Structured logging with `pino`
- [ ] Docker devbox: Dockerfile with Node.js + Pi
- [ ] Test: run workflow that just lints + tests + commits (no LLM yet)

### Phase 2: Pi SDK Integration (Week 2-3)

**Goal:** Pi SDK sessions driving agent nodes.

- [ ] Verify Pi SDK `createAgentSession` + `session.prompt` API works
- [ ] Build `contextGatherStep` as first Pi SDK session
- [ ] Build `planStep` as Pi SDK session (read-only tools)
- [ ] Build `implementStep` as Pi SDK session (write tools)
- [ ] Build `fixFailuresStep` as Pi SDK session
- [ ] Per-node system prompts (instructions)
- [ ] Per-node tool scoping (restrict tools per session)
- [ ] Session transcript saving (JSONL) to `runs/` directory
- [ ] Token usage tracking and cost reporting

### Phase 3: Custom Extensions (Week 3-4)

**Goal:** Pi Extensions for capabilities beyond built-in tools.

- [ ] Implement `repo_map` extension (tree-sitter WASM for Node.js)
- [ ] Implement `semantic_search` extension (embeddings + vector store)
- [ ] Implement `symbol_nav` extension (ctags or tree-sitter-based)
- [ ] Implement `dependency_graph` extension (parse import statements)
- [ ] Implement `run_test` extension (structured test runner wrapper)
- [ ] Implement `run_lint` extension (structured lint wrapper)
- [ ] Implement `web_fetch` extension (URL fetch with domain allowlist)
- [ ] Unit tests for each extension
- [ ] Security: path validation in extensions, command sandboxing

### Phase 4: Context Engine (Week 4-5)

**Goal:** Multi-signal context retrieval system.

- [ ] Repo map generator (tree-sitter skeleton) — used by `repo_map` extension
- [ ] Semantic search: embed codebase with local vector store + embeddings
- [ ] Code chunking with tree-sitter (function/class boundaries)
- [ ] Token budget manager (count tokens, enforce budgets per layer)
- [ ] Dependency graph builder (parse import statements)
- [ ] `AGENTS.md` file template for target repos
- [ ] Pre-warm script (`warm-cache.sh`): build repo map, embed codebase

### Phase 5: Shift-Left Integration (Week 5-6)

**Goal:** Full feedback loop working end-to-end.

- [ ] Lint node: run linter via shell, auto-fix, capture unfixable errors
- [ ] Type check node: run type checker via shell, capture errors
- [ ] Test node: run targeted tests via shell, capture failure output
- [ ] Retry loop: test failures → fix_failures Pi session → re-lint → re-test (max 2)
- [ ] CI integration: push branch → poll GitHub Actions → capture results
- [ ] End-to-end test: task → PR-ready branch (on a test repo)

### Phase 6: Harden & Polish (Week 6-8)

**Goal:** Reliable enough for regular personal use.

- [ ] Error handling: graceful failure at every blueprint node
- [ ] Timeout management: per-node and per-run timeouts
- [ ] Run artifacts: save full run to `runs/{timestamp}/` (Pi session JSONL, diffs, logs)
- [ ] Dry-run mode: show plan without executing changes
- [ ] Configuration: `pi-agent.config.ts` for repo-specific settings
- [ ] Documentation: README, examples, common issues
- [ ] Benchmark: run against 10 known tasks, measure success rate
- [ ] Iterate on prompts and extension tool descriptions based on failures

---

## 13. Success Metrics

### Quantitative (Same Targets)

| Metric | Target (v1) | How to Measure |
|---|---|---|
| One-shot success rate | ≥50% on target task types | Task passes lint + tests without human edits |
| Partial success rate | ≥80% | Produces meaningful changes, human finishes |
| Average tokens per run | <200K | Track via Pi session token usage |
| Average cost per run | <$2 | Calculate from token usage × API pricing |
| Average run time | <10 minutes | Wall clock from start to branch push |
| Retry rate (2nd CI run needed) | <30% | Track how often first push passes |

### Qualitative

- Agent follows existing code conventions
- Agent writes idiomatic code
- Agent commits are reviewable (clean diff, good commit message)
- Debug-ability: Pi's JSONL session logs show exactly what happened

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Pi SDK API instability** | Breaking changes in Pi's embedding API (v0.57.x) | Pin exact Pi version, wrap SDK calls in adapter functions, monitor Pi releases |
| **No workflow engine in Pi** | Must build orchestration from scratch | Keep `BlueprintRunner` simple (~200 LOC); it's a linear sequencer with one conditional branch |
| **TypeScript overhead for Python targets** | Agent written in TS but target repo may be Python — extra complexity | Agent interacts via shell commands (bash tool), not language APIs. Language-agnostic by design. |
| **Pi's built-in tools may change** | Tool names, parameters, or behavior could shift between Pi versions | Abstract tool names in config; pin Pi version in Dockerfile |
| **Context window too small** | Agent misses critical code, makes wrong changes | Same as original: aggressive context filtering, iterative deepening, Pi auto-compaction helps |
| **LLM hallucinates non-existent APIs** | Broken code, test failures | Repo map + type info in context, local lint catches errors fast |
| **LLM drops lines in `write` for large files** | Missing functions/code | Same strategy: `write` ≤250 lines, `edit` above |
| **`edit` old_string mismatch** | Wasted retry tokens | Same: fallback only for >250-line files; context lines required |
| **Agent enters infinite retry loop** | Token burn, wasted time | Hard max on retries (2) + total run timeout |
| **Docker overhead** | Slow dev cycle | Develop locally first, Docker for final integration |
| **Pi extensions debugging** | TS extension errors hard to trace | Structured logging in extensions, unit test each extension independently |
| **No MCP means no standardized tool protocol** | Lock-in to Pi's extension API | Extensions are simple TS functions — easy to extract and wrap in MCP later if needed |

---

## 15. Future Extensions

| Extension | Description |
|---|---|
| **Pi Skills for common tasks** | Package reusable patterns as SKILL.md files (e.g., "add-tests", "fix-types") |
| **Pi Packages** | Publish extensions as npm packages for sharing (`pi install npm:@my/agent-tools`) |
| **Web UI** | Simple dashboard showing run status, session transcripts, diffs |
| **Slack/Discord intake** | Trigger agent via chat message |
| **Multi-language support** | Add Go/Rust/Java support to extensions and context engine |
| **Custom blueprints** | Define task-specific blueprints (migration, dependency update, etc.) |
| **GitHub PR creation** | Auto-create PR with description via GitHub API |
| **Review feedback loop** | Feed PR review comments back to agent for revisions |
| **Parallel agents** | Run multiple orchestrators on different tasks simultaneously (separate containers) |
| **Local LLM** | Use Pi's Ollama provider for zero API cost |
| **MCP bridge** | If Pi ever supports MCP, or build a Pi Extension that proxies to an MCP server |
| **Metrics dashboard** | Track success rate, cost, and common failure modes over time |

---

## Appendix A: Project Directory Structure

```
1shot-e2e-coding-agent/
├── src/                          # Core orchestrator code (TypeScript)
│   ├── cli.ts                    # CLI entry point (commander)
│   ├── orchestrator.ts           # BlueprintRunner — sequences steps
│   ├── types.ts                  # Shared types (RunContext, StepResult, etc.)
│   ├── config.ts                 # Configuration loading
│   │
│   ├── steps/                    # Blueprint step implementations
│   │   ├── setup.ts              # 1. Setup (deterministic)
│   │   ├── context-gather.ts     # 2. Context Gather (Pi session)
│   │   ├── plan.ts               # 3. Plan (Pi session)
│   │   ├── implement.ts          # 4. Implement (Pi session)
│   │   ├── lint-format.ts        # 5. Lint & Format (deterministic)
│   │   ├── test.ts               # 6. Test (deterministic)
│   │   ├── fix-failures.ts       # 7. Fix Failures (Pi session)
│   │   ├── commit-push.ts        # 8. Commit & Push (deterministic)
│   │   └── report.ts             # 9. Report (deterministic)
│   │
│   ├── blueprints/               # Blueprint definitions
│   │   └── standard.ts           # Standard minion workflow (9 nodes)
│   │
│   └── context/                  # Context engineering modules
│       ├── repo-map.ts           # Tree-sitter skeleton generator
│       ├── embeddings.ts         # Embedding + vector store indexing
│       ├── chunker.ts            # AST-based code chunking
│       ├── token-budget.ts       # Token budget manager
│       ├── symbol-nav.ts         # Symbol navigation (ctags/tree-sitter)
│       └── dep-graph.ts          # Dependency graph builder
│
├── extensions/                   # Pi Extensions (custom tools)
│   ├── context-tools.ts          # repo_map, semantic_search, symbol_nav, dependency_graph
│   ├── quality-tools.ts          # run_test, run_lint
│   └── web-tools.ts              # web_fetch (with domain allowlist)
│
├── skills/                       # Pi Skills (SKILL.md instruction files)
│   ├── explore-codebase/
│   │   └── SKILL.md              # Instructions for codebase exploration
│   ├── implement-feature/
│   │   └── SKILL.md              # Instructions for feature implementation
│   └── fix-failures/
│       └── SKILL.md              # Instructions for fixing test/lint failures
│
├── prompts/                      # System prompt templates per node
│   ├── context-gather.md
│   ├── plan.md
│   ├── implement.md
│   └── fix-failures.md
│
├── scripts/                      # Utility scripts
│   ├── warm-cache.sh             # Pre-warm devbox (index, embed, cache)
│   └── benchmark.ts              # Run agent against known tasks
│
├── runs/                         # Run artifacts (gitignored)
│   └── 2026-03-10T14-30-00/
│       ├── session-context.jsonl  # Pi session transcript (context gather)
│       ├── session-plan.jsonl     # Pi session transcript (plan)
│       ├── session-implement.jsonl # Pi session transcript (implement)
│       ├── session-fix.jsonl      # Pi session transcript (fix, if any)
│       ├── diff.patch             # Final code diff
│       ├── metrics.json           # Token usage, cost, timing
│       └── orchestrator.log       # Structured orchestrator logs
│
├── tests/                        # Tests for the agent itself
│   ├── orchestrator.test.ts
│   ├── steps/
│   │   ├── setup.test.ts
│   │   ├── lint-format.test.ts
│   │   └── test.test.ts
│   ├── extensions/
│   │   ├── context-tools.test.ts
│   │   └── quality-tools.test.ts
│   └── context/
│       ├── repo-map.test.ts
│       └── embeddings.test.ts
│
├── Dockerfile.devbox             # Devbox container definition
├── docker-compose.yml            # Compose file for devbox
├── pi-agent.config.ts            # Agent configuration (TypeScript)
├── package.json                  # Node.js project config
├── tsconfig.json                 # TypeScript config
├── .pi/                          # Pi-specific config directory
│   └── settings.json             # Pi settings (provider, model, etc.)
│
├── AGENTS.md                     # Project rules (auto-loaded by Pi)
├── README.md                     # Project documentation
│
├── SPEC.md                       # Original Python/AF spec
├── SPEC-PI.md                    # ← This file
├── context-management-strategies.md
└── common-context-management-strategies.md
```

## Appendix B: Example `pi-agent.config.ts`

```typescript
// pi-agent.config.ts — Agent configuration
import { AgentConfig } from "./src/types.js";

const config: AgentConfig = {
  agent: {
    name: "one-shot-agent",
    harness: "pi",
    maxTokensPerRun: 200_000,
    maxCostPerRunUsd: 2.00,
    timeoutSeconds: 600,
  },

  provider: {
    default: "anthropic",
    anthropicModel: "claude-sonnet-4-20250514",
    openaiModel: "gpt-4.1",
    // API keys read from environment: ANTHROPIC_API_KEY, OPENAI_API_KEY
  },

  repo: {
    path: "/workspace",
    language: "python",
    testCommand: "pytest",
    lintCommand: "ruff check --fix",
    formatCommand: "ruff format",
    typeCheckCommand: "mypy",
  },

  context: {
    repoMapMaxTokens: 5000,
    searchResultsMaxTokens: 15000,
    fullFileMaxTokens: 40000,
    embeddingModel: "nomic-embed-text",
    vectorStore: "chromadb",  // or "vectra" for pure TS
  },

  shiftLeft: {
    runLintBeforePush: true,
    runTypeCheckBeforePush: true,
    runTargetedTests: true,
    maxCiRetries: 1,
  },

  git: {
    branchPrefix: "agent/",
    commitMessagePrefix: "[agent]",
    autoPush: true,
  },

  fileEditing: {
    writeThresholdLines: 250,  // Files ≤ this → write; above → edit
  },

  extensions: {
    contextTools: "./extensions/context-tools.ts",
    qualityTools: "./extensions/quality-tools.ts",
    webTools: "./extensions/web-tools.ts",
  },
};

export default config;
```

## Appendix C: Example Run (End-to-End)

```
$ npx pi-agent run "Add email validation to the create_user endpoint"

[14:30:01] BLUEPRINT START: standard_minion
[14:30:01] NODE 1/9: setup [DETERMINISTIC]
           → Created branch: agent/add-email-validation-1710012601
           → Loaded AGENTS.md rules
           → Task parsed: modify create_user, add validation

[14:30:02] NODE 2/9: context_gather [PI SESSION]
           → Pi session started (anthropic/claude-sonnet-4-20250514)
           → Extensions: context-tools.ts
           → Tools: read, grep, find, ls + repo_map, semantic_search, symbol_nav, dependency_graph
           → Built repo map (127 symbols, 4,832 tokens)
           → grep: "create_user" → 3 files
           → grep: "email" → 5 files
           → semantic_search: "email validation" → 2 chunks
           → dependency_graph: routes.py → service.py → models.py
           → Selected 6 files for context (18,432 tokens)
           [8 tool calls, 2,100 tokens used]
           → Session saved: runs/.../session-context.jsonl

[14:30:08] NODE 3/9: plan [PI SESSION]
           → Pi session started (anthropic/claude-sonnet-4-20250514)
           → Tools: read (read-only)
           → Plan: modify src/api/routes.py (add validation)
                   modify src/services/user_service.py (validate in create)
                   add tests/test_email_validation.py
           [1 tool call, 1,800 tokens used]
           → Session saved: runs/.../session-plan.jsonl

[14:30:12] NODE 4/9: implement [PI SESSION]
           → Pi session started (anthropic/claude-sonnet-4-20250514)
           → Tools: read, write, edit, bash, grep, find
           → Modified: src/services/user_service.py (+12 lines) [edit]
           → Modified: src/api/routes.py (+3 lines) [edit]
           → Created: tests/test_email_validation.py (5 tests) [write]
           [8 tool calls, 12,400 tokens used]
           → Session saved: runs/.../session-implement.jsonl

[14:30:25] NODE 5/9: lint_and_format [DETERMINISTIC]
           → ruff check --fix: 1 issue fixed (unused import)
           → ruff format: 2 files formatted
           → mypy: 0 errors ✓

[14:30:27] NODE 6/9: test [DETERMINISTIC]
           → pytest tests/test_email_validation.py: 5/5 passed ✓
           → pytest tests/test_user_routes.py: 5/5 passed ✓ (regression)

[14:30:33] NODE 7/9: fix_failures (skipped — no failures)

[14:30:33] NODE 8/9: commit_and_push [DETERMINISTIC]
           → Committed: "[agent] Add email validation to create_user endpoint"
           → Pushed to: origin/agent/add-email-validation-1710012601

[14:30:36] NODE 9/9: report [DETERMINISTIC]
           ┌─────────────────────────────────┐
           │ ✓ RUN COMPLETE                  │
           │ Harness: Pi v0.57.1             │
           │ Provider: anthropic/claude-4s   │
           │ Branch: agent/add-email-...     │
           │ Files changed: 3               │
           │ Lines added: 47                │
           │ Tests: 10/10 passed            │
           │ Lint: 0 errors                 │
           │ Pi sessions: 3 (ctx+plan+impl) │
           │ Tokens: 16,300 total           │
           │ Cost: $0.12                    │
           │ Time: 35 seconds               │
           └─────────────────────────────────┘

[14:30:36] BLUEPRINT COMPLETE ✓
           Run artifacts saved to: runs/2026-03-10T14-30-01/
```

---

## Appendix D: Comprehensive Comparison — With Pi vs Without Pi

### D.1 Side-by-Side Architecture

```
WITHOUT PI (Original Spec)               WITH PI (This Spec)
─────────────────────────────             ─────────────────────────────
  CLI (click/typer)                         CLI (commander / npx)
       │                                         │
       ▼                                         ▼
  AF WorkflowBuilder                        BlueprintRunner (custom TS)
  ┌─ 9 nodes, edges ──┐                    ┌─ 9 nodes, next() ──┐
  │  Executors (det.)  │                    │  TS functions (det.)│
  │  AIAgent   (LLM)   │                    │  Pi sessions (LLM)  │
  └──── ↕ ─────────────┘                    └──── ↕ ──────────────┘
        │                                         │
  FastMCP Server (stdio)                    Pi Built-in Tools (7)
  14 MCP tools (Python)                     Pi Extensions (7 custom TS)
        │                                         │
  Docker (python:3.12-slim)                 Docker (node:20-slim)
```

### D.2 Component-by-Component Comparison

| Component | Without Pi (Python / AF) | With Pi (TypeScript / Pi SDK) | Winner |
|---|---|---|---|
| **Language** | Python 3.12+ | TypeScript (Node.js 20+) | **Tie** — depends on team skills |
| **Agent harness** | Microsoft Agent Framework (`AIAgent`, `WorkflowBuilder`, superstep BSP execution) | Pi (`@mariozechner/pi-coding-agent` SDK + custom `BlueprintRunner`) | **Without Pi** — AF provides workflow engine built-in |
| **Workflow / graph** | AF `WorkflowBuilder`: declarative `.add_edge()` with conditions, built-in superstep execution model | Custom `BlueprintRunner` class (~200 LOC): imperative `next()` routing, manual loop | **Without Pi** — zero custom orchestration code needed |
| **LLM provider support** | Custom wrappers required: `AnthropicProvider` (~100 LOC) + `OpenAIProvider` (~100 LOC) translating AF format ↔ API format | Pi native: 15+ providers out of the box, zero wrapper code | **With Pi** — no provider boilerplate |
| **Tool protocol** | MCP standard (FastMCP, stdio transport). Industry-standard, interoperable. ~300 LOC server. | Pi Extensions (`registerTool()`). Pi-specific, not interoperable. ~200 LOC. | **Without Pi** — MCP is an industry standard |
| **Built-in tools** | None — all 14 tools must be built as MCP tools | 7 built-in (`read`, `write`, `edit`, `bash`, `grep`, `find`, `ls`) | **With Pi** — half the tools are free |
| **Tool scoping** | `AIAgent(tools=[...])` — first-class AF feature | `createAgentSession({ tools: [...], extensions: [...] })` — SDK flags | **Tie** — both work |
| **Context mechanism** | Custom Python modules only — no auto-loading | `AGENTS.md` (auto-loaded), `SYSTEM.md`, Skills (SKILL.md), auto-compaction | **With Pi** — native context conventions |
| **Session management** | Custom JSON transcript logging | Native JSONL tree-structured sessions, auto-compaction, resumable | **With Pi** — built-in session management |
| **Configuration** | `agent.toml` (TOML) + `pyproject.toml` | `pi-agent.config.ts` (TypeScript) + `package.json` + `.pi/settings.json` | **Without Pi** — simpler, one config file |
| **Docker base** | `python:3.12-slim` (~150 MB) | `node:20-slim` (~200 MB) + Python runtime for target repos | **Without Pi** — smaller image, no dual runtime |
| **Testing (agent itself)** | `pytest` — mature, rich ecosystem | `vitest` — fast, but less ecosystem for agent testing | **Tie** |
| **Observability** | `structlog` + AF OpenTelemetry integration | `pino` + custom logging (no OTel integration in Pi) | **Without Pi** — OTel is standard |

### D.3 Lines of Code Comparison (Estimated)

| Module | Without Pi (Python) | With Pi (TypeScript) | Delta |
|---|---|---|---|
| **Orchestrator / Workflow** | ~50 LOC (AF `WorkflowBuilder` does the work) | ~200 LOC (`BlueprintRunner` + node wiring) | **+150 LOC with Pi** |
| **LLM Providers** | ~200 LOC (AnthropicProvider + OpenAIProvider) | 0 LOC (Pi handles natively) | **-200 LOC with Pi** |
| **MCP / Tool Server** | ~300 LOC (FastMCP server + tool decorators) | 0 LOC (use Pi built-ins) | **-300 LOC with Pi** |
| **Custom Tool Impls** | ~400 LOC (14 tools in Python) | ~200 LOC (7 extensions — 7 built-in are free) | **-200 LOC with Pi** |
| **Context Engine** | ~500 LOC (repo map, embeddings, chunker, budget) | ~500 LOC (same modules rewritten in TS) | **Same** |
| **Steps / Nodes** | ~300 LOC (executor classes + AF wiring) | ~400 LOC (step functions + Pi session setup) | **+100 LOC with Pi** |
| **CLI** | ~100 LOC (click/typer) | ~100 LOC (commander) | **Same** |
| **Config** | ~50 LOC (TOML loader) | ~80 LOC (TS config + type definitions) | **+30 LOC with Pi** |
| **TOTAL (estimated)** | **~1,900 LOC** | **~1,480 LOC** | **-420 LOC with Pi** |

> **Net:** Pi saves ~420 LOC total, mainly from eliminating LLM provider wrappers and MCP server boilerplate. The trade-off is +150 LOC of custom orchestration that AF gives you for free.

### D.4 Development Effort Comparison

| Phase | Without Pi | With Pi | Notes |
|---|---|---|---|
| **Phase 1: Foundation** | 1-2 weeks | 1-2 weeks | Pi version needs custom `BlueprintRunner`; AF version needs AF learning curve |
| **Phase 2: Agent Integration** | 1-2 weeks (write 2 providers + wire AIAgent) | 1 week (Pi sessions just work, no providers) | **Pi faster** — no provider boilerplate |
| **Phase 3: Tools** | 1-2 weeks (build MCP server + 14 tools) | 1 week (7 built-in, only 7 extensions) | **Pi faster** — half the tools are free |
| **Phase 4: Context** | 1-2 weeks | 1-2 weeks | Same effort — core logic is identical |
| **Phase 5: Shift-Left** | 1 week | 1 week | Framework-agnostic — identical work |
| **Phase 6: Harden** | 2 weeks | 2 weeks | Similar effort |
| **TOTAL** | **7-11 weeks** | **6-9 weeks** | **Pi saves ~1-2 weeks** |

### D.5 Runtime Characteristics

| Metric | Without Pi | With Pi | Notes |
|---|---|---|---|
| **Session startup** | Fast — Python process, in-memory AF graph | Slower — each Pi session spawns/initializes SDK | Pi has session initialization overhead |
| **Tool call latency** | MCP stdio: ~5-10ms per call (IPC) | Pi built-in: ~1ms (in-process). Extension: ~2-5ms. | **Pi faster** — no IPC |
| **Token usage** | Same model, same prompts ≈ same tokens | Same model, same prompts ≈ same tokens | **Same** (depends on prompts, not harness) |
| **Memory footprint** | ~200 MB (Python + AF + ChromaDB) | ~300 MB (Node.js + Pi + dependencies) | Without Pi slightly lighter |
| **Docker image size** | ~400 MB (python:3.12-slim + tools) | ~500 MB (node:20-slim + Python for targets + Pi) | Without Pi smaller |
| **Cold start (container)** | ~5s | ~7s (Pi global install + Node.js startup) | Without Pi faster cold start |

### D.6 Ecosystem & Longevity

| Factor | Without Pi | With Pi |
|---|---|---|
| **Framework maturity** | Microsoft Agent Framework — corporate backing, stable API, versioned releases | Pi — one-person project (v0.57.x), MIT license, API may change |
| **Community / docs** | AF has Microsoft docs, examples, enterprise adoption | Pi has GitHub README, examples in repo, small community |
| **MCP compatibility** | Full MCP support — tools work with any MCP client | No MCP — Pi-specific extension API, not interoperable |
| **Multi-agent** | AF supports multi-agent workflows natively (superstep BSP) | Pi explicitly says "no sub-agents" — must spawn separate processes |
| **Provider ecosystem** | Must write provider wrappers (but full control) | 15+ providers built-in (but less control over translation) |
| **Extensibility model** | Python: MCP tools + AF Executors | TypeScript: Pi Extensions + Pi Skills + Pi Packages (npm/git) |
| **Risk of abandonment** | Low (Microsoft) | Medium (solo maintainer, but MIT = forkable) |

### D.7 When to Choose Which

#### Choose **Without Pi** (Original Spec / Python + AF) if:

- You prefer Python or your target repos are primarily Python
- You want a battle-tested workflow engine (`WorkflowBuilder`) with no custom orchestration
- MCP compatibility matters (future tool sharing, IDE integration)
- You want OpenTelemetry observability out of the box
- You value framework stability (Microsoft backing)
- You plan to build multi-agent workflows later (AF superstep model)

#### Choose **With Pi** (This Spec / TypeScript + Pi) if:

- You prefer TypeScript or want the agent in the same language as target repos
- You want fast prototyping (zero provider code, half the tools built-in)
- You value fewer dependencies and less boilerplate overall (~420 LOC less)
- You want native AGENTS.md/Skills/auto-compaction context management
- You're comfortable building ~200 LOC of custom orchestration
- You don't need MCP interoperability for v1
- You accept the risk of depending on a v0.x solo-maintained project

### D.8 Verdict Summary

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SCORECARD                                       │
├──────────────────────┬──────────────────┬──────────────────────────────┤
│ Category             │ Without Pi       │ With Pi                      │
├──────────────────────┼──────────────────┼──────────────────────────────┤
│ Workflow engine      │ ★★★★★ (built-in) │ ★★★☆☆ (must build)           │
│ LLM provider setup   │ ★★★☆☆ (manual)   │ ★★★★★ (native 15+ providers) │
│ Tool ecosystem       │ ★★★★☆ (MCP std)  │ ★★★★☆ (7 built-in + ext)    │
│ Boilerplate          │ ★★★☆☆ (~1900 LOC)│ ★★★★☆ (~1480 LOC)           │
│ Context management   │ ★★★☆☆ (custom)   │ ★★★★☆ (AGENTS.md, Skills)   │
│ Session / logging    │ ★★★☆☆ (custom)   │ ★★★★★ (native JSONL)        │
│ Observability        │ ★★★★★ (OTel)     │ ★★★☆☆ (custom logging)      │
│ Ecosystem maturity   │ ★★★★★ (Microsoft)│ ★★☆☆☆ (v0.x, solo dev)      │
│ MCP interop          │ ★★★★★ (native)   │ ★☆☆☆☆ (none, by design)     │
│ Dev speed (time)     │ ★★★☆☆ (7-11 wks) │ ★★★★☆ (6-9 wks)             │
│ Docker image size    │ ★★★★☆ (~400 MB)  │ ★★★☆☆ (~500 MB)             │
│ Multi-agent future   │ ★★★★★ (native)   │ ★★☆☆☆ (spawn processes)     │
├──────────────────────┼──────────────────┼──────────────────────────────┤
│ OVERALL              │ Prod-ready path  │ Faster prototype, more risk  │
└──────────────────────┴──────────────────┴──────────────────────────────┘
```

**Bottom line:**
- **Without Pi** is the safer, more production-aligned choice — you get a real workflow engine, MCP standard tooling, OTel observability, and Microsoft's backing. The cost is ~420 more LOC and writing two LLM provider wrappers.
- **With Pi** is the faster-to-prototype choice — you skip provider wrappers, get half the tools for free, and write ~420 fewer LOC. The cost is building your own workflow orchestrator, losing MCP interoperability, and depending on a v0.x solo project.
