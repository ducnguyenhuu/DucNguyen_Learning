# Standard Blueprint Diagram

## 9-Node Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STANDARD BLUEPRINT (9 nodes)                     │
└─────────────────────────────────────────────────────────────────────┘

  [1] setup              DETERMINISTIC
       │  create git branch, load AGENTS.md
       ▼
  [2] context_gather     AGENT (Pi session)
       │  read/grep/find/ls tools
       │  → relevantFiles, understanding
       ▼
  [3] plan               AGENT (Pi session)
       │  read-only tools
       │  → plan (structured change plan)
       ▼
  [4] implement          AGENT (Pi session)
       │  read/write/edit/bash/grep/find tools
       │  → code changes on disk
       ▼
  [5] lint_and_format    DETERMINISTIC
       │  run lintCommand + formatCommand
       ▼
  [6] test               DETERMINISTIC
       │  run testCommand
       │
       ├── PASS ──────────────────────────────────────────────────┐
       │                                                           │
       └── FAIL ──► [7] fix_failures    AGENT (Pi session)        │
                         │  read/write/edit/bash/grep tools        │
                         │  retry up to maxRetries (default: 2)    │
                         └──► [6] test (loop back)                 │
                                                                   │
  ┌────────────────────────────────────────────────────────────────┘
  ▼
  [8] commit_and_push    DETERMINISTIC
       │  git add . → commit → push branch
       ▼
  [9] report             DETERMINISTIC
       │  print summary: files, tests, tokens, cost, time
       ▼
      END
```

## Node Types

| Type | Description |
|------|-------------|
| **DETERMINISTIC** | Always runs the same way — git, lint, test, report. No LLM involved. |
| **AGENT (Pi session)** | Creates a Pi session, sends a prompt, LLM loops with tools until `stopReason: "stop"`. |

## Pi Session Tools per Agent Node

| Node | Tools available |
|------|----------------|
| `context_gather` | `read`, `grep`, `find`, `ls` (read-only) |
| `plan` | `read`, `grep`, `find`, `ls` (read-only) |
| `implement` | `read`, `write`, `edit`, `bash`, `grep`, `find` |
| `fix_failures` | `read`, `write`, `edit`, `bash`, `grep` |

## Retry Loop

- `fix_failures` → `test` loops up to `config.shiftLeft.maxRetries` times (default: **2**)
- After retry cap is hit: run ends with `status: "failed"`, no commit/push

## Source Files

| Node | Implementation |
|------|---------------|
| `setup` | `src/steps/setup.ts` |
| `context_gather` | `src/steps/context-gather.ts` |
| `plan` | `src/steps/plan.ts` |
| `implement` | `src/steps/implement.ts` |
| `lint_and_format` | `src/steps/lint-format.ts` |
| `test` | `src/steps/test.ts` |
| `fix_failures` | `src/steps/fix-failures.ts` |
| `commit_and_push` | `src/steps/commit-push.ts` |
| `report` | `src/steps/report.ts` |
| Blueprint wiring | `src/blueprints/standard.ts` |

---

## How an Agent Provides Context to the LLM

### Overview: Two-Layer Context Injection

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Pi AgentSession                                  │
│                                                                         │
│  LAYER 1: STATIC (set once at session creation)                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  System Prompt                                                    │  │
│  │  "You are a code analysis agent. Use read/grep/find/ls only..."   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  LAYER 2: DYNAMIC (grows with each tool call during the loop)           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  User Message (sent via runPrompt)                                │  │
│  │  "## Task: fix login bug                                          │  │
│  │   ## Workspace: /workspace/test-repo                              │  │
│  │   ## Project Rules (AGENTS.md): ..."                             │  │
│  └──────────────────┬────────────────────────────────────────────────┘  │
│                     │                                                   │
│                     ▼  ← agentic loop (auto-managed by Pi SDK)          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Round 1: LLM calls ls("/workspace")                             │  │
│  │  Tool result appended: ["src/", "tests/", "package.json", ...]   │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  Round 2: LLM calls ls("/workspace/src")                         │  │
│  │  Tool result appended: ["auth/", "cli.ts", "config.ts", ...]     │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  Round 3: LLM calls grep("login", "/workspace/src")              │  │
│  │  Tool result appended: ["src/auth/login.ts:12: export fn..."]    │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  Round 4: LLM calls read("/workspace/src/auth/login.ts")         │  │
│  │  Tool result appended: [full file content]                        │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │  Round N: LLM decides it has enough → stopReason: "stop"         │  │
│  │  LLM writes final response: relevant files + understanding text   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Sequence: contextGatherStep → Pi SDK → LLM

```
contextGatherStep()
  │
  ├─ readFile(AGENTS.md)          # load project rules (non-fatal if missing)
  │
  ├─ createSession({              # LAYER 1: static context
  │    systemPrompt: "...",       #   → who the LLM is + what tools it has
  │    tools: [read,grep,find,ls] #   → enforced tool scope (read-only)
  │    provider, model            #   → which LLM to use
  │  }, { cwd: workspacePath })
  │
  ├─ runPrompt(handle,            # LAYER 2: task-specific context
  │    "## Task\n..."             #   → what to do
  │    "## Workspace\n..."        #   → where the code is
  │    "## Project Rules\n..."    #   → AGENTS.md rules
  │  )
  │    │
  │    │   ┌──────────────────────────────────────┐
  │    │   │  Pi SDK agentic loop (internal)       │
  │    │   │                                      │
  │    │   │  LLM ──tool_call──► ls / grep /      │
  │    │   │   ▲                 read / find       │
  │    │   │   │                    │              │
  │    │   │   └──tool_result───────┘              │
  │    │   │  (repeats until LLM stops)            │
  │    │   └──────────────────────────────────────┘
  │    │
  │    └─► returns final assistant text (string)
  │
  ├─ parseRelevantFiles(output)   # extract "- src/auth/login.ts" lines
  │
  ├─ ctx.relevantFiles = [...]    # mutate shared RunContext
  ├─ ctx.understanding = output   # for downstream plan/implement steps
  │
  └─ return StepResult { passed, tokensUsed, data }
```

### What context the LLM never gets

The LLM does **not** receive:
- All files in the repo upfront
- A pre-built file tree

It must **navigate** the repo like a developer would — broad first (`ls`), then narrow (`grep`, `read`). This is the scaling strategy: a 50K LOC repo can't fit in a context window, but the 3–5 files relevant to a specific bug usually can.

### How downstream nodes inherit context

```
┌──────────────────┐   ctx.relevantFiles   ┌──────────────────┐
│  context_gather  │ ────────────────────► │      plan        │
│                  │   ctx.understanding   │                  │
└──────────────────┘                       └────────┬─────────┘
                                                    │ ctx.plan
                                                    ▼
                                           ┌──────────────────┐
                                           │    implement     │
                                           └──────────────────┘

RunContext is the shared carrier — each step reads what it needs
and writes what the next step should know.
```

---

## Learning Notes — Agent Architecture Mental Models

### 1. LLM is a stateless function

```
f(context_window) → next_tokens
```

The LLM has no memory between calls. It only knows what is in the current context window.
When the call ends, everything is gone. **All memory is managed by the agent, not the LLM.**

---

### 2. Why read-only session for context_gather?

The context_gather step's job is **reconnaissance only** — understand the codebase, not change it.

Restricting tools to `["read", "grep", "find", "ls"]` is enforced at the SDK level.
If `write`/`edit`/`bash` were available, the LLM could accidentally modify files before
the plan step has even run — or be tricked into doing so via prompt injection in source files.

Security boundary = separate session with scoped tools per step.

---

### 3. What ctx.relevantFiles and ctx.understanding are

They are shared state on `RunContext` — the carrier object passed through all steps:

```
ctx.relevantFiles  = ["src/auth/login.ts", "src/auth/user.ts"]
                     ↑ used by plan + implement to know which files to focus on

ctx.understanding  = full LLM text output from context_gather
                     ↑ injected into plan step's prompt as background context
```

The LLM does NOT receive all files upfront. It self-selects what to read via tool calls,
navigating like a developer: broad first (ls), then narrow (grep, read).

---

### 4. Why the plan step exists (even in one-shot)

**Intuition**: "We're one-shot with no human, so why plan before implementing?"

**Answer**: The plan is not for the human — it is for the implement step to read.

Each Pi session starts **fresh** with no memory of previous sessions. Without `ctx.plan`,
the implement session would only have "fix the login bug" — no guidance on where or how.

```
context_gather session → ctx.understanding → plan session → ctx.plan → implement session
```

Additional benefits:
- Separates analysis (what exists) from decision (what to change) from execution (write code)
- Cheaper to catch wrong decisions in the plan step than after implement has written bad code
- fix_failures can read ctx.plan to understand intent — without it, it must re-investigate

For simple single-file tasks, plan is optional overhead.
For multi-file changes with ordering dependencies, plan prevents implement from making
wrong ordering decisions mid-stream (e.g. TypeScript errors if callers updated before types).

---

### 5. How implement actually works (not a programmatic loop)

**Common misconception**:
```
plan    = creates task list [task1, task2, task3]
implement = for each task → new LLM session
```

**Reality**:
```
plan    = one LLM session → writes text task list into ctx.plan
implement = ONE LLM session → reads ctx.plan, self-manages execution internally
```

The implement step is a single Pi session. The LLM reads the whole plan and decides
its own execution order via tool calls internally. Our TypeScript only starts the session
and waits for `stopReason: "stop"`. The LLM is its own executor.

This is what makes agents powerful (and unpredictable) — the LLM can adapt mid-execution
("I read the file, the plan was slightly wrong, let me adjust").

---

### 6. Agent memory tiers

```
TIER 1: In-session memory (context window)
  Lives:   RAM, inside the growing message array
  Dies:    when session ends
  Content: all messages + tool results this session
  Managed: agent runtime automatically

TIER 2: Cross-session memory (CLAUDE.md / AGENTS.md)
  Lives:   disk, plain markdown file
  Dies:    never (until deleted)
  Content: rules, facts, preferences always needed
  Managed: human writes it, or LLM writes it when instructed
  Injected: at START of every new session → system prompt

TIER 3: Semantic long-term memory (vector store)
  Lives:   disk, embedded vector database
  Dies:    never (until deleted)
  Content: semantic embeddings of code chunks, past decisions
  Managed: agent code explicitly (not the LLM)
  Injected: selectively — only the N most relevant chunks for current task
```

CLAUDE.md / AGENTS.md is the simplest tier — human-readable, always injected in full.
Limitation: doesn't scale. You can't put 10K lines of codebase knowledge in a markdown file.
Vector store (our T046) solves this — inject only semantically relevant chunks.

---

### 7. Our architecture vs Claude Code vs Copilot

```
                    Our agent       Claude Code         Copilot Chat
─────────────────────────────────────────────────────────────────────
Sessions per task   4 (fixed)       1 main + N subs     1 per chat
Steps defined by    TypeScript      LLM decides          N/A
Next step decided   next() fn       LLM orchestrator     N/A
Memory between runs RunContext only  CLAUDE.md + JSON     none
Long-term memory    none (yet)      CLAUDE.md            none
Tools               Pi built-ins    Built-ins + MCP      IDE context
Predictability      High            Medium               High
Flexibility         Low             High                 Low
```

**Our tradeoff**: predictable and testable (BlueprintRunner) vs flexible (Claude Code subagents).
Right choice for one-shot because we need guaranteed step ordering and hard security boundaries.

---

### 8. What a session actually is

A session = the growing array of messages the LLM can see:

```
[
  SystemMessage,        ← set once at createSession(), never changes
  UserMessage,          ← sent via runPrompt()
  AssistantMessage,     ← LLM response / reasoning
  ToolCallMessage,      ← LLM calls ls("/workspace")
  ToolResultMessage,    ← tool returns ["src/", "tests/", ...]
  ToolCallMessage,      ← LLM calls read("src/auth/login.ts")
  ToolResultMessage,    ← [full file content]
  AssistantMessage,     ← final text output
]
```

Each LLM call receives the **entire array** as input. The array grows with each tool round.
Session ends when: LLM emits `stopReason: "stop"` | context window full | user exits.

---

### 9. Cost equation

```
Cost = (input tokens + output tokens) × price per token

input tokens = system prompt
             + AGENTS.md content
             + task description
             + all tool results (file contents, grep hits, ls outputs)
             + prior assistant messages in this session
             + ctx.understanding + ctx.plan (injected by agent code)
```

Every byte of file content read in context_gather adds to the input token bill for
plan (re-injected via ctx.understanding) and implement (re-injected via ctx.plan).
This is why TokenBudgetManager enforces hard per-layer limits:

```
L0 repoMap        5%  — repo structure + task description
L1 searchResults  15% — file contents found during context_gather
L2 fullFiles      40% — files to be modified in implement
L3 supplementary  10% — git blame, examples (if budget remains)
reserved          30% — system prompts, reasoning, output generation
```

Reading unnecessary files doesn't just hurt quality — it directly increases cost
for every subsequent step that receives those results via ctx.

---

### 10. Claude Code — Session Lifecycle

Claude Code uses **one continuous session per terminal conversation** — not one session per prompt.

```
User opens terminal
    │
    ▼
Session starts
  System prompt = CLAUDE.md + ~/.claude/CLAUDE.md + built-in rules
    │
    ├── User: "fix the login bug"
    │     LLM → ls → grep → read → edit → bash(run tests)
    │     [all tool results appended to SAME context window]
    │
    ├── User: "also add a log line"
    │     Same session continues — LLM still sees everything above
    │
    ├── User: "what files did you change?"
    │     LLM still has full history — can answer accurately
    │
    └── User exits / types /clear / context window fills up
    │
    ▼
Session ends
```

**Session ends when:**
- User types `exit` or closes the terminal
- Context window is full (~200K tokens) → Claude Code auto-summarizes → starts new session with summary as starting context
- User runs `/clear` command explicitly
- Idle timeout (implementation detail, not publicly documented)

---

### 11. Claude Code — What Happens After Session Ends

```
Session ends
    │
    ├── CLAUDE.md updated?
    │   Only if LLM was explicitly instructed to remember something:
    │   "Remember: this repo uses pnpm not npm"
    │   → LLM writes it to CLAUDE.md itself using Write tool
    │
    ├── ~/.claude/projects/{project-hash}/conversations/
    │   └── {session-id}.jsonl   ← full JSON transcript saved locally
    │
    └── Context window discarded — LLM forgets everything not written to disk

Next session starts:
    ├── CLAUDE.md injected into system prompt automatically
    ├── ~/.claude/CLAUDE.md (global user preferences) also injected
    └── Fresh context window — previous tool results and reasoning are gone
```

The LLM does **not** automatically decide what to remember — it only writes to CLAUDE.md
when the user asks it to, or when it is instructed to in the system prompt.

---

### 12. Claude Code — Tool Organization (3 Tiers)

```
TIER 1: Built-in tools (always available, no configuration)
  ├── Bash          — run any shell command
  ├── Read          — read file content
  ├── Write         — write/create file
  ├── Edit          — targeted string replacement in a file
  ├── Glob          — find files by pattern
  ├── Grep          — search file contents by pattern
  ├── LS            — list directory contents
  ├── WebFetch      — fetch a URL (with domain restrictions)
  └── TodoWrite     — manage an internal task checklist (!)
                      (this is how Claude Code tracks multi-step work internally)

TIER 2: MCP Servers (user-configured, plugged in via settings)
  ├── Configured in ~/.claude/settings.json
  ├── Each MCP server exposes its own named tools
  ├── Examples: GitHub MCP (create PR, list issues)
  │             Postgres MCP (query database)
  │             Puppeteer MCP (browser automation)
  └── LLM sees MCP tools exactly like built-in tools — no difference in usage

TIER 3: Slash commands (user-defined prompt shortcuts)
  ├── /review, /commit, /test, /explain etc.
  ├── NOT real tools — just pre-written prompt templates
  └── Typing /review triggers: "Please review the current changes for..."
```

**Key difference from Pi SDK**: Claude Code has no "Extensions" concept.
Tools are either built-in or MCP. Pi SDK separates tools (single functions)
from extensions (bundles of tools + context + prompts loaded as a unit).

---

### 13. Claude Code — Orchestrator / Subagent Pattern

For large tasks, Claude Code uses a **Task tool** to spawn child sessions:

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator session  (main Claude session)                │
│                                                             │
│  User: "refactor the auth module and add tests"             │
│                                                             │
│  LLM decides: too large for one context window              │
│  → breaks into subtasks, calls Task tool per subtask        │
│                                                             │
│  Task tool call #1:                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Subagent session (isolated context window)         │   │
│  │  Prompt: "explore auth module, list all files"      │   │
│  │  Has its own tool calls internally                  │   │
│  │  Returns: file list + understanding text            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Task tool call #2 (can run in parallel with #3):          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Subagent session                                   │   │
│  │  Prompt: "refactor src/auth/login.ts per plan"      │   │
│  │  Returns: done / error                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Task tool call #3 (parallel):                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Subagent session                                   │   │
│  │  Prompt: "write tests for auth/login.ts"            │   │
│  │  Returns: done / error                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Orchestrator collects all results, reports to user         │
└─────────────────────────────────────────────────────────────┘
```

**Key properties of this pattern:**
- Orchestrator never sees what subagent read internally — only gets the final result
- Each subagent gets its own fresh context window → no cross-contamination
- Subagents can run in parallel if they don't depend on each other
- The LLM decides when to spawn subagents — not hardcoded in TypeScript

**Why this differs from our architecture:**

| | Claude Code | Our agent |
|---|---|---|
| Who decides next step | The LLM (dynamic) | TypeScript `next()` fn (static) |
| Sessions per run | 1 + N subagents (LLM decides N) | 4 fixed sessions |
| Parallelism | LLM can run subagents in parallel | Sequential only |
| Predictability | Medium (LLM can go off-script) | High (always same structure) |
| Testability | Hard (non-deterministic routing) | Easy (deterministic routing) |

Our BlueprintRunner is the "TypeScript orchestrator" equivalent — but instead of
the LLM deciding what to do next, our `next()` functions hardcode the routing.
This sacrifices flexibility for predictability, which is the right tradeoff for
a one-shot agent where correctness and auditability matter more than adaptability.
