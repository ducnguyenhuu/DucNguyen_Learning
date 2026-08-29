# CLI Contract: One-Shot End-to-End Coding Agent

**Date**: 2026-03-13  
**Spec FR**: FR-001, FR-018  

## Overview

The agent's primary user interface is a CLI (Command Line Interface — a text-based way to interact with the agent by typing commands in a terminal). The CLI accepts a task description and runs the agent end-to-end.

## Command: `run`

The main command that executes a coding task.

### Usage

```bash
npx pi-agent run "<task description>" [options]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `task` | string | yes | Plain-text description of the coding task. Quoted string. |

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--config`, `-c` | string | `./pi-agent.config.ts` | Path to configuration file |
| `--provider`, `-p` | string | from config | LLM provider override ("anthropic" \| "openai") |
| `--model`, `-m` | string | from config | Model name override |
| `--dry-run` | boolean | false | Show plan without executing changes |
| `--max-retries` | number | from config (2) | Override max retry count |
| `--max-tokens` | number | from config (200000) | Override token budget |
| `--timeout` | number | from config (600) | Override timeout in seconds |
| `--verbose`, `-v` | boolean | false | Enable verbose logging |
| `--output-dir` | string | `./runs/` | Directory for run artifacts |

### Examples

```bash
# Basic usage
npx pi-agent run "Add email validation to the create_user endpoint"

# With provider override
npx pi-agent run "Fix TypeError in parse_config" --provider openai --model gpt-4.1

# Dry-run (plan only, no changes)
npx pi-agent run "Refactor auth module" --dry-run

# With custom config
npx pi-agent run "Add tests for user service" --config ./my-project.config.ts

# Verbose output
npx pi-agent run "Add --verbose flag to CLI" -v
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Run succeeded — PR created |
| 1 | Run failed — retries exhausted, no PR |
| 2 | Configuration error — invalid config or missing required fields |
| 3 | Timeout — run exceeded time limit |
| 4 | Budget exceeded — token budget exhausted |

### Output Format

**Standard output** (non-verbose):
```
[HH:MM:SS] BLUEPRINT START: standard
[HH:MM:SS] NODE 1/9: setup [DETERMINISTIC]
           → Created branch: agent/add-email-validation-1710012601
[HH:MM:SS] NODE 2/9: context_gather [PI SESSION]
           → Selected 6 files (18,432 tokens)
[HH:MM:SS] NODE 3/9: plan [PI SESSION]
           → Plan: modify 2 files, create 1 file
[HH:MM:SS] NODE 4/9: implement [PI SESSION]
           → Modified: src/services/user_service.ts (+12 lines)
           → Created: tests/email-validation.test.ts (5 tests)
[HH:MM:SS] NODE 5/9: lint_and_format [DETERMINISTIC]
           → Clean
[HH:MM:SS] NODE 6/9: test [DETERMINISTIC]
           → 10/10 passed
[HH:MM:SS] NODE 7/9: fix_failures — skipped (no failures)
[HH:MM:SS] NODE 8/9: commit_and_push [DETERMINISTIC]
           → PR created: https://github.com/user/repo/pull/42
[HH:MM:SS] NODE 9/9: report [DETERMINISTIC]
┌─────────────────────────────────┐
│ ✓ RUN COMPLETE                  │
│ Branch: agent/add-email-...     │
│ PR: #42                         │
│ Files changed: 3                │
│ Tests: 10/10 passed             │
│ Tokens: 16,300                  │
│ Cost: $0.12                     │
│ Time: 35s                       │
└─────────────────────────────────┘
```

**Verbose output** (`-v`): Adds per-tool-call logging, full prompt/response excerpts, and token budgets per step.

### Artifacts Produced

After each run, the following files are saved to `{output-dir}/{run-id}/`:

| File | Description |
|------|-------------|
| `session-context.jsonl` | Pi session transcript (context gather) |
| `session-plan.jsonl` | Pi session transcript (plan) |
| `session-implement.jsonl` | Pi session transcript (implement) |
| `session-fix.jsonl` | Pi session transcript (fix, if any) |
| `diff.patch` | Final code diff |
| `metrics.json` | Token usage, cost, timing |
| `orchestrator.log` | Structured orchestrator logs |
| `report.json` | Machine-readable run report |

---

## Command: `init`

Initialize configuration for a new target repository.

### Usage

```bash
npx pi-agent init [options]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--language`, `-l` | string | auto-detect | Target repo language |
| `--output`, `-o` | string | `./pi-agent.config.ts` | Config output path |

### Behavior

1. Detects the target repo's language (from `package.json`, `pyproject.toml`, `go.mod`, etc.)
2. Detects test and lint commands from project config
3. Generates a `pi-agent.config.ts` file with sensible defaults
4. Creates an `AGENTS.md` template if none exists

---

## GitHub PR Contract

When the agent creates a pull request (FR-009), the PR follows this structure:

### PR Title
```
[agent] {task description}
```

### PR Body (Markdown)
```markdown
## Summary
{task description}

## Changes

| File | Action | What Changed | Why |
|------|--------|-------------|-----|
| src/services/user_service.ts | Modified | Added email validation to create_user | Task requirement: validate email format |
| tests/email-validation.test.ts | Created | 5 test cases for email validation | Ensure validation works correctly |

## Test Results
- **10 passed**, 0 failed, 0 skipped
- Lint: ✅ Clean
- Type check: ✅ Clean

## Agent Run Details
- **Provider**: anthropic / claude-sonnet-4
- **Tokens**: 16,300
- **Cost**: $0.12
- **Duration**: 35s
- **Retries**: 0

---
*Generated by [one-shot-agent](https://github.com/user/1shot-e2e-coding-agent) — an unattended coding agent powered by Pi SDK*
```
