# Implementation Plan: Human-AI Collaboration Platform (HACP)

**Branch**: `001-one-shot-coding-agent` | **Date**: 2026-05-16 | **Spec**: [ai-human-collab-spec.md](ai-human-collab-spec.md)
**Input**: Feature specification from `ai-human-collab-spec.md`

## Summary

Build a local-first desktop web platform where a single orchestrating AI agent decomposes projects into numbered stage folders (ICM methodology), classifies each stage as Human or AI work, visualizes them as a workflow graph, and orchestrates execution — auto-running AI stages and pausing at human review gates. The workspace is a plain local folder (markdown + JSON files) that IS the project state. The platform provides a Project Library, run history with archiving, per-stage AI conversation, templates, and export capabilities. Tech stack: Python backend (FastAPI) + React frontend (TypeScript), local filesystem as storage, multi-provider LLM support.

## Technical Context

**Language/Version**: Python 3.12+ (strict type annotations, backend) + TypeScript 5.x strict (frontend only)  
**Primary Dependencies**: Python 3.12+ (backend), React 18+ / TypeScript (frontend), React Flow / Xyflow (workflow graph), FastAPI + uvicorn (backend HTTP server), LiteLLM (multi-provider LLM abstraction with streaming), Pydantic v2 (data validation), CodeMirror 6 (markdown editor for human review gates)  
**Storage**: Local filesystem only — workspace folders are the database. Platform index: `~/.hacp/projects.json`. Settings: `~/.hacp/settings.json` + OS keychain for API keys.  
**Testing**: pytest + pytest-asyncio (backend unit + integration), Vitest (frontend unit), Playwright (E2E/UI)  
**Target Platform**: macOS, Windows, Linux — desktop web app (localhost) served by local Python process. Min screen 1280px.  
**Project Type**: Web application (frontend + backend)  
**Performance Goals**: Stage plan generation <60s, AI stage handoff <10s, workflow status updates <3s, search <2s for workspaces <100MB  
**Constraints**: Single user (no auth), all state on local filesystem, text-only outputs (no binary), parallel stages visual-only (sequential execution in v1)  
**Scale/Scope**: 10+ concurrent workflows, workspaces with 15+ stages, run history with dozens of snapshots

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Token-First Design | ⚠️ JUSTIFIED DEVIATION | HACP sends stage context to LLM per AI stage execution. The ICM layer hierarchy inherently limits context per stage (~1–4k tokens via Inputs declaration in CONTEXT.md, FR-040). Only declared files are loaded — never the full workspace. Token efficiency is architectural, not payload-filtering. |
| II. CLI-First Interface | ⚠️ JUSTIFIED DEVIATION | HACP is primarily a GUI web application (FR-070). Backend workspace operations (init workspace, run stage, archive run) WILL be exposed as CLI commands in `bin/hacp.py` (via `typer`) for testability and scripting. The orchestrating agent itself operates via file I/O + LLM API calls. |
| III. Code Execution Over MCP | ✅ PASS | HACP does not use MCP. The orchestrating agent reads files from disk and calls LLM APIs directly via LiteLLM. No tool schemas loaded at session start. |
| IV. Shared Infrastructure | ⚠️ JUSTIFIED DEVIATION | HACP is a standalone application, not a tool in the existing monorepo. It will create its own shared utilities (LLM client wrapper, filesystem helpers, error classes) following the same patterns (kebab-case files, standard error classes, typed exports). Extractable to shared packages later. |
| V. Production-Ready Quality | ✅ PASS | TypeScript strict mode, input validation at API boundaries, structured error handling, 80%+ test coverage target, no hardcoded secrets (API keys in OS keychain per FR-082). |

**Gate Result**: PASS with 3 justified deviations (I, II, IV). No blocking violations.

## Project Structure

### Documentation (this feature)

```text
ai-human-collab-platform/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── hacp/                    # Python package
│       ├── models/              # Pydantic models for all entities
│       │   ├── workspace.py     # Workspace, Stage, StageContract, StageStatus
│       │   ├── workflow.py      # WorkflowStatus, ExecutionState
│       │   ├── settings.py      # PlatformSettings, LLMProviderConfig
│       │   └── run.py           # RunSnapshot, ExecutionLogEntry
│       ├── services/
│       │   ├── workspace/       # Init, open, validate ICM structure, detect external changes
│       │   ├── orchestrator/    # Stage execution engine, routing, handoff logic
│       │   ├── llm/             # Multi-provider LLM client (via LiteLLM)
│       │   ├── planner/         # Project decomposition → numbered stage folders
│       │   ├── run_history/     # Archive to _runs/, restore, diff between runs
│       │   ├── conversation/    # Per-stage AI conversation (read context, stream response)
│       │   ├── export/          # Consolidate stage outputs → Markdown/HTML/txt
│       │   ├── search/          # Full-text search across workspace files
│       │   ├── settings/        # Platform settings CRUD + OS keychain integration
│       │   ├── template/        # Template gallery, clone, save-as-template
│       │   └── file_watcher/    # watchdog-based file system watcher (FR-044)
│       ├── api/
│       │   ├── routes/          # FastAPI routers grouped by domain
│       │   ├── middleware/       # Error handling, validation, SSE streaming setup
│       │   └── app.py           # FastAPI app factory + SSE setup
│       └── lib/
│           ├── fs_helpers.py    # Safe read/write, path resolution, atomic writes
│           ├── markdown.py      # Parse CONTEXT.md → structured StageContract
│           ├── errors.py        # AppError, NotFoundError, ValidationError
│           └── keychain.py      # OS keychain abstraction via keyring
├── bin/
│   └── hacp.py                  # CLI entry point via typer (workspace init, run stage, export)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                # Sample workspace folders for testing
├── pyproject.toml
└── uv.lock

frontend/
├── src/
│   ├── components/
│   │   ├── workflow/        # React Flow nodes, edges, custom node renderers
│   │   ├── stage-detail/    # Split-pane detail panel (inputs left, editor right)
│   │   ├── editor/          # CodeMirror markdown editor for human review gates
│   │   ├── conversation/    # Per-stage chat panel with streaming
│   │   ├── library/         # Project cards, search, filters, tags
│   │   ├── dashboard/       # Cross-project actionable summary
│   │   ├── settings/        # LLM config, UI prefs, workspace defaults
│   │   ├── export/          # Export dialog (format selection, cover page toggle)
│   │   ├── run-history/     # Run history panel, side-by-side diff viewer
│   │   └── common/          # Breadcrumb, activity feed, notifications, modals
│   ├── pages/
│   │   ├── library.tsx      # Home — Project Library + Dashboard
│   │   ├── project.tsx      # Single project — workflow canvas + stage detail
│   │   └── settings.tsx     # Platform settings page
│   ├── services/
│   │   ├── api-client.ts    # HTTP + SSE client to backend
│   │   └── store.ts         # Zustand state management
│   ├── hooks/               # Custom React hooks (useWorkflow, useStage, useSSE)
│   ├── styles/              # CSS/theme — light/dark mode, design tokens
│   └── App.tsx
├── tests/
│   ├── unit/
│   └── e2e/                 # Playwright E2E tests
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

**Structure Decision**: Web application — separate `backend/` (Python 3.12+) and `frontend/` (TypeScript). Backend handles all filesystem I/O, LLM orchestration, and serves REST + SSE APIs via FastAPI. Frontend is a React SPA via Vite. Types are shared via OpenAPI codegen: `openapi-typescript` generates TypeScript interfaces from FastAPI's Pydantic-based schema.

## Complexity Tracking

> Constitution deviations I, II, IV are justified above. No additional complexity tracking needed.
