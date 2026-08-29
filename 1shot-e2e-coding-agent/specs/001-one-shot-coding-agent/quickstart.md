# Quickstart: One-Shot End-to-End Coding Agent

**Date**: 2026-03-13  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## What Is This?

This is a **one-shot coding agent** — a program that takes a plain-text task description (like "Add email validation to the create_user endpoint"), autonomously reads your codebase, writes code, runs tests, and creates a pull request — all without human interaction.

**Think of it like**: You write a sticky note describing what you want changed, hand it to a robot developer, and get back a pull request ready for review.

## Prerequisites

Before you start, make sure you have:

| Requirement | How to Check | How to Install |
|-------------|-------------|----------------|
| Node.js 20+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| Docker | `docker --version` | [docker.com](https://www.docker.com/) |
| Git | `git --version` | `brew install git` (macOS) |
| Anthropic API key | Check your [Anthropic console](https://console.anthropic.com/) | Sign up at anthropic.com |
| GitHub token | `gh auth status` | `gh auth login` or create a personal access token |

## Quick Setup (5 minutes)

### 1. Clone and install

```bash
git clone https://github.com/your-user/1shot-e2e-coding-agent.git
cd 1shot-e2e-coding-agent
npm install
```

### 2. Set API keys

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."
```

### 3. Initialize for your target repo

```bash
npx pi-agent init --language python
```

This creates a `pi-agent.config.ts` file. Edit it to point to your repo:

```typescript
repo: {
  path: "/workspace",            // Don't change — this is inside Docker
  language: "python",
  testCommand: "pytest",         // ← Your test command
  lintCommand: "ruff check --fix", // ← Your lint command
  formatCommand: "ruff format",
},
```

### 4. Build the Docker devbox

```bash
docker build -t pi-agent-devbox \
  --build-arg REPO_URL=https://github.com/your-user/your-repo.git \
  -f Dockerfile.devbox .
```

### 5. Run your first task

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  pi-agent-devbox \
  run "Add input validation to the create_user endpoint"
```

The agent will:
1. Create a branch (`agent/add-input-validation-...`)
2. Read and understand your codebase
3. Plan the changes
4. Write the code and tests
5. Run lint and tests
6. Create a PR with a summary of all changes

## Key Concepts (For Beginners)

### Blueprint
A **blueprint** is the fixed sequence of steps the agent follows — like a recipe. It always goes: setup → gather context → plan → implement → lint → test → commit → report. Some steps use an LLM (Language Model — the AI that writes code), others are deterministic (always run the same way, like lint or test commands).

### Pi SDK
**Pi** is an open-source coding agent framework. We use it as the "engine" that talks to LLMs and provides built-in tools (read files, write files, run commands). Think of Pi as the robot's hands and brain interface.

### Shift-Left
**Shift-left** means catching errors as early as possible — before pushing code. Instead of waiting for CI/CD to find lint errors or test failures, the agent runs lint and tests locally inside the Docker container and tries to fix them automatically.

### Devbox
A **devbox** is an isolated Docker container where the agent works. It has a copy of your repo, all the tools installed, and can't touch your real system. If the agent makes a mess, you just discard the container.

## Common Tasks

```bash
# Simple bug fix
npx pi-agent run "Fix TypeError in parse_config when config is empty"

# Add a feature
npx pi-agent run "Add a --verbose flag to the CLI"

# Write tests
npx pi-agent run "Add tests for the auth/service.py module"

# Refactor
npx pi-agent run "Extract validation logic from create_user into a separate function"

# Dry-run (see the plan without executing)
npx pi-agent run "Add logging to all API endpoints" --dry-run
```

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| "ANTHROPIC_API_KEY not set" | Missing env var | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Docker build fails | Missing Docker daemon | Start Docker Desktop |
| Tests fail in container | Different environment | Check `repo.testCommand` in config |
| Agent loops without converging | Task too complex for one-shot | Try a simpler, more specific task |
| Token budget exceeded | Large codebase or complex task | Increase `agent.maxTokensPerRun` in config |

## What's Next?

- Review the [CLI contract](contracts/cli-contract.md) for all available commands and options
- Read the [data model](data-model.md) to understand the entities
- Check the [spec](spec.md) for full requirements and success criteria
