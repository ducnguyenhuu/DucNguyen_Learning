# Tasks: Human-AI Collaboration Platform (HACP)

**Input**: Design documents from `ai-human-collab-platform/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/openapi.yaml ✅ · quickstart.md ✅

**Branch**: `001-one-shot-coding-agent` | **Generated**: 2026-05-17

**Stack**: Python 3.12+ / FastAPI / LiteLLM / Pydantic v2 (backend) · React 18 / TypeScript / React Flow / Zustand / CodeMirror 6 (frontend)

---

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no shared dependencies)
- **[Story]**: Which user story this task implements (US0–US12 from spec.md)
- Exact file paths are required in every task description
- Tasks MUST be executed sequentially within a phase unless marked [P]

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the project structure, tooling, and CI. No feature code here — only scaffolding.

- [x] T001 Create top-level directory structure: `backend/`, `frontend/`, `Makefile`, `.gitignore`, `.editorconfig` per plan.md Project Structure
- [x] T002 Initialize Python backend: create `backend/pyproject.toml` with dependencies (fastapi, uvicorn[standard], litellm, pydantic>=2, watchdog, keyring, sse-starlette, typer, ruff, mypy, pytest, pytest-asyncio, pytest-cov, httpx) and create `backend/uv.lock` via `uv sync`
- [x] T003 [P] Initialize React frontend: create `frontend/package.json` with dependencies (react 18, typescript 5, @xyflow/react 12, @codemirror/*, zustand 5, vite, vitest, @playwright/test, eslint, prettier) and run `npm install`
- [x] T004 Configure backend tooling: add `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` sections to `backend/pyproject.toml`
- [x] T005 [P] Configure frontend tooling: create `frontend/tsconfig.json` (strict mode, path aliases), `frontend/.eslintrc.cjs`, `frontend/prettier.config.cjs`
- [x] T006 [P] Create `Makefile` with targets: `dev`, `dev-backend`, `dev-frontend`, `test`, `test-backend`, `test-frontend`, `test-e2e`, `lint`, `type-check`, `build`, `codegen`
- [x] T007 [P] Create `.github/workflows/ci.yml` — jobs: `lint-backend` (ruff + mypy), `test-backend` (pytest), `lint-frontend` (eslint), `test-frontend` (vitest), `test-e2e` (playwright)
- [x] T008 Create `backend/src/hacp/__init__.py` and `backend/src/hacp/py.typed` marker to declare the package

**Checkpoint**: Directory skeleton exists, `uv sync` and `npm install` succeed, CI workflow is defined.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure shared by every user story. No user story implementation can begin until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase.

### Backend: Core Library (`lib/`)

- [ ] T009 Create `backend/src/hacp/lib/errors.py` — define `AppError`, `NotFoundError`, `ConflictError`, `ValidationError`, `LLMError` with `code` + `message` fields
- [ ] T010 [P] Create `backend/src/hacp/lib/fs_helpers.py` — `atomic_write(path, content)`, `safe_read(path)`, `ensure_dir(path)`, `resolve_workspace_path(base, rel)`, `list_files(dir, pattern)` using `pathlib.Path`
- [ ] T011 [P] Create `backend/src/hacp/lib/markdown.py` — `parse_context_md(path) -> StageContract`, `parse_workspace_md(path) -> WorkspaceMeta`, `parse_routing_table(content) -> list[RoutingEntry]`, `render_routing_table(entries) -> str`
- [ ] T012 [P] Create `backend/src/hacp/lib/keychain.py` — `get_api_key(service, provider) -> str | None`, `set_api_key(service, provider, key)`, `delete_api_key(service, provider)` via `keyring` library

### Backend: Pydantic Models (`models/`)

- [ ] T013 Create `backend/src/hacp/models/workspace.py` — Pydantic models: `StageStatus` (enum: Pending/InProgress/AwaitingHuman/Completed/Failed), `StageContract`, `RoutingEntry`, `Stage`, `WorkspaceMeta`, `Workspace`
- [ ] T014 [P] Create `backend/src/hacp/models/workflow.py` — `WorkflowStatus` (enum: Draft/Running/Paused/Completed/Failed), `ExecutionState`, `ExecutionLogEntry`, `RunLogEntry`
- [ ] T015 [P] Create `backend/src/hacp/models/settings.py` — `LLMProviderConfig`, `WorkspaceDefaults`, `UIPreferences`, `PlatformSettings`
- [ ] T016 [P] Create `backend/src/hacp/models/run.py` — `RunSnapshot`, `RunStageMeta`, `ActivityEvent`, `Notification`
- [ ] T017 [P] Create `backend/src/hacp/models/api.py` — API request/response models: `ProjectEntry`, `ProjectSummary`, `StageSummary`, `StageDetail`, `DashboardResponse`, `ErrorResponse`

### Backend: FastAPI Application

- [ ] T018 Create `backend/src/hacp/api/app.py` — FastAPI app factory with `lifespan` context manager (startup: recovery scan, file watcher init; shutdown: graceful teardown), CORS for `http://localhost:5173`, mount all routers
- [ ] T019 [P] Create `backend/src/hacp/api/middleware/error_handler.py` — `AppError → HTTPException` mapper, global exception handler returning `ErrorResponse` JSON
- [ ] T020 [P] Create `backend/src/hacp/api/middleware/sse.py` — `build_sse_event(event_type, data) -> dict`, SSE heartbeat logic, `EventSourceResponse` factory helper

### Backend: Core Services

- [ ] T021 Create `backend/src/hacp/services/llm/llm_service.py` — `LLMService`: `generate(messages, model, max_tokens) -> str`, `stream(messages, model) -> AsyncIterator[str]` via `litellm.acompletion()`, context-window check helper, error normalization to `LLMError`
- [ ] T022 [P] Create `backend/src/hacp/services/file_watcher/watcher_service.py` — `FileWatcherService`: `start_watching(project_id, workspace_path)`, `stop_watching(project_id)`, `watchdog Observer` dispatching `FileModifiedEvent` / `FileCreatedEvent` to SSE event queue
- [ ] T023 [P] Create `backend/src/hacp/services/settings/settings_service.py` — `SettingsService`: `load_settings() -> PlatformSettings`, `save_settings(settings)`, `get_api_key(provider)`, `set_api_key(provider, key)` with `~/.hacp/settings.json` and `keyring` integration
- [ ] T024 [P] Create `backend/src/hacp/services/workspace/project_index.py` — `ProjectIndex`: `load() -> list[ProjectEntry]`, `add(entry)`, `remove(project_id)`, `update(project_id, patch)`, `find_by_path(path)` operating on `~/.hacp/projects.json`

### Backend: Startup Recovery (FR-111)

- [ ] T025 Create `backend/src/hacp/services/orchestrator/recovery.py` — `scan_interrupted_stages(project_index)`: for each open project, if any stage has status `InProgress` and `output/` is empty, write status `Failed` with reason `"Interrupted — no output found"` and update `WORKSPACE.md`

### Frontend: Base Infrastructure

- [ ] T026 Create `frontend/vite.config.ts` — dev server port 5173, proxy `/api` → `http://localhost:3001`, HMR websocket config, `@` alias for `src/`
- [ ] T027 [P] Create `frontend/src/services/api-client.ts` — typed `apiFetch<T>(url, options)` wrapper, `createEventSource(url, handlers)` SSE client with auto-reconnect on connection drop
- [ ] T028 [P] Create `frontend/src/services/store.ts` — Zustand store slices: `projectsSlice` (library list), `workspaceSlice` (current project + stages), `workflowSlice` (execution status), `settingsSlice`, `notificationsSlice`
- [ ] T029 [P] Create `frontend/src/App.tsx` — React Router v6 with routes: `/` (library), `/projects/:id` (workflow canvas), `/settings` (platform settings), 404 fallback
- [ ] T030 [P] Create `frontend/src/styles/tokens.css` — CSS custom properties for color palette, typography scale, spacing, border radii, shadows; light and dark theme classes

### CLI Entry Point

- [ ] T031 Create `backend/bin/hacp.py` — `typer` CLI with commands: `init-workspace <path> <name>`, `run-stage <project-id> <stage-n>`, `archive-run <project-id>`, `export <project-id> --format md|html|txt`

### Test Fixtures

- [ ] T032 [P] Create `backend/tests/fixtures/` — three sample workspace folders: `ai_only_3stage/` (3 AI stages with output), `mixed_5stage/` (Human+AI stages, stage 3 AwaitingHuman), `empty_workspace/` (no stages, freshly initialized)

**Checkpoint**: Backend starts (`uv run uvicorn hacp.api.app:app --reload --port 3001`), FastAPI `/docs` renders, frontend dev server starts (`npm run dev`), basic API health check passes.

---

## Phase 3: User Story 0 — Workspace Setup & Configuration (P1) 🎯

**Goal**: User can create a new project workspace, open an existing one, and have the platform restore full state from disk files alone.

**Independent Test**: Create workspace → verify ICM folder structure on disk → close and reopen → confirm all stages, statuses, and metadata restored from filesystem with no database.

- [ ] T033 [US0] Implement `create_workspace(path, name, description)` in `backend/src/hacp/services/workspace/workspace_service.py` — write ICM structure: `WORKSPACE.md`, `CONTEXT.md`, `_config/project-brief.md`, `_config/conventions.md`, `shared/`, `stages/` (FR-035)
- [ ] T034 [P] [US0] Implement `open_workspace(path) -> Workspace` in `workspace_service.py` — read and parse all ICM files via `lib/markdown.py`, reconstruct full `Workspace` model including all stages and their statuses (FR-036)
- [ ] T035 [P] [US0] Implement `validate_icm_structure(path) -> ValidationResult` in `workspace_service.py` — check required files/folders exist, return list of missing items with recovery suggestions (FR-036)
- [ ] T036 [US0] Create `backend/src/hacp/api/routes/projects.py` — register `POST /api/projects` (create workspace, add to index), `GET /api/projects` (list), `DELETE /api/projects/{id}`, `PATCH /api/projects/{id}`; mount on app
- [ ] T037 [US0] Create `backend/src/hacp/api/routes/workspace.py` — `GET /api/projects/{id}/workspace` (full workspace state), `POST /api/projects/import` (add existing path to index), `GET /api/projects/{id}/workspace/disk-usage` (FR-105)
- [ ] T038 [P] [US0] Create `backend/src/hacp/api/routes/events.py` — `GET /api/projects/{id}/events` SSE endpoint: on connect start `FileWatcherService.start_watching()`, stream events from per-project asyncio `Queue`, heartbeat every 30s (FR-044)
- [ ] T039 [P] [US0] Create `frontend/src/hooks/useSSE.ts` — React hook wrapping `createEventSource`, dispatching typed SSE events to Zustand store on `stage:status`, `stage:output:chunk`, `stage:output:complete`, `workflow:status`, `notification`
- [ ] T040 [P] [US0] Create `frontend/src/pages/library.tsx` — shell: project cards grid (populated from store), top bar with "New Project" button and search input, first-run empty state
- [ ] T041 [P] [US0] Create `frontend/src/components/library/NewProjectWizard.tsx` — 3-step wizard: (1) name + path picker + description, (2) optional template selector, (3) confirm; calls `POST /api/projects`
- [ ] T042 [US0] Write `backend/tests/unit/test_workspace_service.py` — unit tests for `create_workspace` (verify files written), `open_workspace` (verify model fields), `validate_icm_structure` (missing file detection)

**Checkpoint**: `POST /api/projects` creates workspace folder on disk; `GET /api/projects/{id}/workspace` returns parsed model; Library page shows project card; SSE endpoint connects.

---

## Phase 4: User Story 11 — Platform Settings & Administration (P1)

**Goal**: User can configure LLM providers, set and store API keys securely, and test connectivity. This must be done before any AI execution.

**Independent Test**: Set OpenAI API key → `POST /api/settings/test-connection` → returns model name and latency → key persists in OS keychain across platform restarts.

- [ ] T043 [US11] Implement full `SettingsService` in `backend/src/hacp/services/settings/settings_service.py` — `load_settings()`, `save_settings(PlatformSettings)`, `add_provider(LLMProviderConfig)`, `remove_provider(id)`, `test_connection(provider_id) -> ConnectionTestResult`
- [ ] T044 [US11] Create `backend/src/hacp/api/routes/settings.py` — `GET /api/settings`, `PUT /api/settings`, `POST /api/settings/test-connection`, `GET /api/settings/providers/{id}/models`; mount on app
- [ ] T045 [P] [US11] Create `frontend/src/pages/settings.tsx` — Settings page shell with nav tabs: LLM Configuration, Workspace Defaults, UI Preferences
- [ ] T046 [P] [US11] Create `frontend/src/components/settings/LLMConfigSection.tsx` — provider list with Add/Edit/Delete, API key field (masked input, stored via `PUT /api/settings`), base URL field, model picker populated from `GET /api/settings/providers/{id}/models`, "Test Connection" button showing latency
- [ ] T047 [P] [US11] Create `frontend/src/components/settings/WorkspaceDefaultsSection.tsx` — fields for defaultRootDir (path picker), namingConvention, autoCreateConversation toggle, defaultModel
- [ ] T048 [P] [US11] Create `frontend/src/components/settings/UIPreferencesSection.tsx` — theme selector (light/dark/system), fontSize slider, activityFeed toggle, notificationSound toggle; persisted to settings store
- [ ] T049 [US11] Create `frontend/src/components/common/FirstRunWizard.tsx` — wizard shown on first launch (FR-090): Step 1: choose LLM provider; Step 2: enter API key + test; Step 3: select default model; Step 4: choose workspace root directory; Step 5: done
- [ ] T050 [US11] Write `backend/tests/unit/test_settings_service.py` — test load/save settings, add/remove provider, test_connection (mock LiteLLM), keychain set/get/delete

**Checkpoint**: Settings page renders; API key saved to OS keychain; test-connection returns success; settings persist across backend restart.

---

## Phase 5: User Story 7 — Project Library & Persistence (P1)

**Goal**: Home screen shows all known projects with status, progress, tags. Full CRUD (archive, duplicate, delete) with persistence across restarts.

**Independent Test**: Create 3 projects; tag them; filter by tag → 1 result; archive 1 → not in active view; duplicate 1 → new project has same stages but empty outputs; restart platform → all 3 projects still indexed.

- [ ] T051 [US7] Expand `GET /api/projects` in `projects.py` to support query params: `status`, `tag`, `search` (name/description), `sortBy` (lastModified/name/status), `archived` (bool) — reading from `project_index`
- [ ] T052 [P] [US7] Implement `POST /api/projects/{id}/duplicate` in `projects.py` — copy workspace folder, preserve `_config/` + stage `CONTEXT.md` + `references/`, clear all `output/`, `_runs/`, `conversation.md` (FR-049)
- [ ] T053 [P] [US7] Implement `GET /api/dashboard` in `backend/src/hacp/api/routes/dashboard.py` — aggregate: `awaitingHuman` stage list (across all active projects), `recentActivity` (last 20 log entries), counters (total/active/completed/failed projects)
- [ ] T054 [US7] Create `frontend/src/components/library/ProjectCard.tsx` — card with: title, status badge (color per WorkflowStatus), progress bar (completed stages / total), last-modified date, description preview, tag chips, context menu (Open/Duplicate/Archive/Delete)
- [ ] T055 [P] [US7] Add search + filter toolbar to `library.tsx` — search input (debounced), status filter chips, tag multi-select, sortBy dropdown; filters drive `GET /api/projects` query params
- [ ] T056 [P] [US7] Create `frontend/src/components/common/ConfirmModal.tsx` — reusable confirmation dialog with title, body, danger/safe variant, confirm/cancel buttons; used for all destructive actions (FR-103, FR-104)
- [ ] T057 [P] [US7] Create `frontend/src/components/dashboard/DashboardSection.tsx` — dashboard panel in library page: "Needs Your Input" card list (links to AwaitingHuman stages), recent activity feed, summary stats
- [ ] T058 [US7] Write `backend/tests/unit/test_project_service.py` — test create/list/filter/archive/duplicate project; test dashboard aggregation across multiple fixtures

**Checkpoint**: Library shows all projects; filter/search narrows results; duplicate creates clean copy; archive hides from default view; restart preserves index.

---

## Phase 6: User Story 1 — Project Decomposition & Stage Planning (P1)

**Goal**: User submits a project description; AI generates numbered stage folders with CONTEXT.md files; user can edit/add/remove/reorder stages before running.

**Independent Test**: Submit 20-word description → verify ≥3 stage folders created on disk → each has valid CONTEXT.md with Inputs/Process/Outputs/Assignee → Layer 1 routing table updated → edit stage title → disk file reflects change.

- [ ] T059 [US1] Create `backend/src/hacp/services/planner/planner_service.py` — `decompose_project(description, workspace) -> list[StageDefinition]`: build ICM-aware system prompt, call `LLMService.generate()`, parse JSON response into `StageDefinition` list with minimum 3 stages, validate Assignee classification (FR-001–FR-004)
- [ ] T060 [US1] Implement `create_stages_from_plan(workspace, stages)` in `workspace_service.py` — write numbered stage folders (`stages/01_name/`, `02_name/`, …), each with `CONTEXT.md` (Inputs/Process/Outputs/Assignee), empty `references/`, empty `output/` (FR-037, FR-038)
- [ ] T061 [US1] Implement `update_routing_table(workspace, stages)` in `workspace_service.py` — serialize stage list to Layer 1 `CONTEXT.md` routing table section (FR-039)
- [ ] T062 [US1] Create `backend/src/hacp/api/routes/workflow.py` — `POST /api/projects/{id}/plan`: validate description length (≥10 chars), call planner, create stages, stream progress via SSE (FR-001, FR-002)
- [ ] T063 [P] [US1] Add `GET /api/projects/{id}/stages` and `GET /api/projects/{id}/stages/{n}` to `backend/src/hacp/api/routes/stages.py` (new file), mount on app
- [ ] T064 [P] [US1] Add `POST /api/projects/{id}/stages` (manual stage creation with full CONTEXT.md fields), `PATCH /api/projects/{id}/stages/{n}` (block if InProgress per FR-030), `DELETE /api/projects/{id}/stages/{n}` to `stages.py`
- [ ] T065 [P] [US1] Add `POST /api/projects/{id}/stages/reorder` to `stages.py` — accept new order array, rename stage folders, rewrite routing table (FR-102, FR-029)
- [ ] T066 [US1] Create `frontend/src/components/workflow/StageNode.tsx` — custom React Flow node component: title, assignee badge (AI=indigo/Human=amber), status indicator dot, output preview (truncated text or placeholder), edit icon
- [ ] T067 [P] [US1] Create `frontend/src/components/stage-detail/StageDetailPanel.tsx` — split-pane: left pane shows declared Inputs file list with read-only content; right pane shows editable form (title, description, assignee, inputs, process, outputs)
- [ ] T068 [P] [US1] Create `frontend/src/components/stage-detail/StageEditForm.tsx` — form fields for all contract fields; Save calls `PATCH /api/projects/{id}/stages/{n}`; shows "Stage is running — editing locked" overlay when status is InProgress (FR-030)
- [ ] T069 [P] [US1] Add plan submission UI to `frontend/src/pages/project.tsx` — description textarea shown in Draft state; Submit button calls `POST /api/projects/{id}/plan`; SSE progress events show stage names being created
- [ ] T070 [US1] Write `backend/tests/unit/test_planner_service.py` — test `decompose_project` (mock LiteLLM response), `create_stages_from_plan` (verify files on disk using `tmp_path` fixture), `update_routing_table` (verify CONTEXT.md format)

**Checkpoint**: Submit description → ≥3 stage folders on disk → workflow graph renders nodes → click node → edit form opens → save → CONTEXT.md updated on disk.

---

## Phase 7: User Story 3 — Workflow Execution & AI Auto-run (P1)

**Goal**: Single click starts sequential AI stage execution; outputs written atomically to `output/`; SSE streams live status updates; errors pause workflow with recovery options.

**Independent Test**: Run `ai_only_3stage` fixture → all 3 stages complete → output files present in each `output/` → workflow status Completed → WORKSPACE.md updated → startup recovery marks an InProgress-with-no-output stage as Failed.

- [ ] T071 [US3] Create `backend/src/hacp/services/orchestrator/orchestrator_service.py` — `OrchestratorService`: `execute_workflow(project_id)` as asyncio Task: load routing table, iterate stages in order, call `_execute_ai_stage()` or `_pause_for_human()` per assignee; emit SSE events at each transition
- [ ] T072 [US3] Implement `_execute_ai_stage(project_id, stage)` in `orchestrator_service.py` — set status InProgress, load declared Inputs files, call `LLMService.stream()`, write chunks to `output/<filename>` atomically on complete, set status Completed; emit `stage:output:chunk` + `stage:output:complete` SSE events (FR-013, FR-014, FR-040)
- [ ] T073 [US3] Implement AI stage failure handling in `_execute_ai_stage` — on `LLMError` set status Failed, emit `stage:failed` SSE event with error message, pause workflow (set WorkflowStatus.Paused), write error to `output/.error.md` (FR-016)
- [ ] T074 [P] [US3] Implement large-output warning in `_execute_ai_stage` — after writing output file, if size > 1MB emit `stage:output:warning` SSE event `{message: "Output is large (X MB) — downstream stages may hit context limits"}` (FR-113)
- [ ] T075 [P] [US3] Add `POST /api/projects/{id}/workflow/start` (spawn asyncio task, 202), `POST /api/projects/{id}/workflow/pause`, `POST /api/projects/{id}/workflow/resume`, `POST /api/projects/{id}/workflow/cancel`, `GET /api/projects/{id}/workflow/status` to `workflow.py`
- [ ] T076 [US3] Wire startup recovery into `app.py` lifespan startup hook — call `recovery.scan_interrupted_stages(project_index)` before accepting requests (FR-111)
- [ ] T077 [P] [US3] Create `frontend/src/hooks/useWorkflow.ts` — hook exposing `status`, `start()`, `pause()`, `resume()`, `cancel()` actions calling REST endpoints, consuming SSE `workflow:status` events from store
- [ ] T078 [P] [US3] Add workflow toolbar to `frontend/src/pages/project.tsx` — Run/Pause/Resume/Cancel buttons wired to `useWorkflow`; buttons show disabled state per workflow status (FR-022, FR-053)
- [ ] T079 [P] [US3] Create `frontend/src/components/workflow/InProgressNode.tsx` — sub-component rendered on StageNode when status=InProgress: spinner + streaming text preview updating on `stage:output:chunk` SSE events (FR-034, FR-077)
- [ ] T080 [P] [US3] Show large-output warning in `frontend/src/components/common/ActivityFeed.tsx` — render warning item with file name and size when `stage:output:warning` event received (FR-113)
- [ ] T137 [US3] Implement LLM override resolution in `backend/src/hacp/services/orchestrator/orchestrator_service.py` — `resolve_llm_config(workspace_path, stage) -> LLMProviderConfig`: (1) check stage `CONTEXT.md` for `Model:` field, (2) read `_config/llm.json` if present, (3) fall back to platform `~/.hacp/settings.json`; pass resolved config to `LLMService.stream()` inside `_execute_ai_stage` (FR-086)
- [ ] T081 [US3] Write `backend/tests/integration/test_orchestrator.py` — integration test using `ai_only_3stage` fixture (mock LiteLLM), verify all stages Completed, output files written, WORKSPACE.md updated; test failure path (mock LLMError on stage 2); test startup recovery; test stage-level `Model:` override is passed to LiteLLM (FR-086)

**Checkpoint**: Run workflow → SSE events flow → nodes update live → output files on disk → WORKSPACE.md status = Completed → crash recovery test passes.

---

## Phase 8: User Story 4 — Human Review Gate (P1)

**Goal**: Workflow pauses at Human stages; user is notified; user writes output (with auto-save) via CodeMirror editor; workflow resumes on submit; external file writes also accepted.

**Independent Test**: Run `mixed_5stage` fixture → workflow pauses at Human stage → editor renders with upstream output in left pane → type content → auto-save writes `.draft.md` every 30s → Submit → output file written → workflow resumes automatically.

- [ ] T082 [US4] Implement `_pause_for_human(project_id, stage)` in `orchestrator_service.py` — set stage status AwaitingHuman, set workflow status Paused, emit `stage:awaiting_human` SSE event (with stage context for notification), write entry to `run-log.md`, start reminder timer if configured (FR-017, FR-018, FR-021)
- [ ] T083 [US4] Create `backend/src/hacp/api/routes/human_gate.py` — `POST /api/projects/{id}/stages/{n}/submit` (write files to `output/`, mark Completed, call `orchestrator.resume()`); `GET /api/projects/{id}/stages/{n}/draft`; `PUT /api/projects/{id}/stages/{n}/draft` (write `.draft.md`); mount on app (FR-019, FR-020, FR-099)
- [ ] T084 [P] [US4] Implement external-output detection in `watcher_service.py` — when `FileCreatedEvent` fires in any stage `output/` dir, call `workspace_service.mark_stage_completed_external(project_id, stage_n)` → emit `stage:status` SSE event; orchestrator resumes if stage was AwaitingHuman (FR-044)
- [ ] T085 [US4] Create `frontend/src/components/editor/MarkdownEditor.tsx` — CodeMirror 6 editor with markdown language extension, syntax highlighting, preview toggle (split/source/preview modes), unsaved indicator; expose `value` / `onChange` props
- [ ] T086 [P] [US4] Create `frontend/src/components/stage-detail/HumanGatePanel.tsx` — layout: left pane (read-only upstream output file viewer), right pane (`MarkdownEditor`); auto-save via debounced `PUT /draft` every 30s (FR-099); Submit button calls `POST /submit`; shows "Submitting…" loading state
- [ ] T087 [P] [US4] Add human gate notification badge to `frontend/src/components/common/Breadcrumb.tsx` — count of AwaitingHuman stages; clicking badge opens AwaitingHuman stage list modal
- [ ] T138 [US4] Wire AI-assist into `frontend/src/components/stage-detail/HumanGatePanel.tsx` — add "Ask AI for help" button in the left context pane opening a single-turn conversation panel; calls `POST /api/projects/{id}/stages/{n}/conversation` with the stage contract pre-loaded as system context; streams AI suggestions inline without overwriting the user's editor content (FR-064)
- [ ] T088 [US4] Write `backend/tests/integration/test_human_gate.py` — test: workflow pauses at human stage → submit via API → status Completed → workflow resumes → next AI stage runs; test external file detection path; test AI-assist conversation returns suggestion for human stage

**Checkpoint**: Workflow pauses at Human stage; notification shown; editor renders with context; auto-save writes draft; Submit resumes workflow; next AI stage runs.

---

## Phase 9: User Story 2 — Workflow Visualization & Node Interaction (P2)

**Goal**: Visual React Flow graph with live status updates; click nodes for details; output preview on completed nodes; drag-to-reorder.

**Independent Test**: Open project with 5 stages (mixed) → graph renders all 5 nodes with correct colors/icons → click node → detail panel opens → run workflow → nodes update live (no page reload) → drag node 3 before node 2 → routing table updated.

- [ ] T089 [US2] Create `frontend/src/components/workflow/WorkflowCanvas.tsx` — React Flow canvas: `fitView`, zoom controls, background grid, minimap; builds nodes and edges from `workspace.stages`; calls `useSSE` for live updates (FR-007, FR-072)
- [ ] T090 [P] [US2] Style `StageNode.tsx` with status-specific variants — colors: Pending (gray), InProgress (blue pulse), AwaitingHuman (amber), Completed (green), Failed (red); Human stage outer ring (amber dashed), AI stage (indigo solid); icons per assignee (FR-008, FR-010)
- [ ] T091 [P] [US2] Add completed-output preview to `StageNode.tsx` — when stage.status = Completed and output files exist, render first 150 chars of first output file as a text preview beneath the title; add "See more" chevron (FR-032, FR-033)
- [ ] T092 [P] [US2] Add execution metadata footer to `StageDetailPanel.tsx` — show: start time, end time, elapsed duration, model used, token count (if available); sourced from `ExecutionLogEntry` (FR-007)
- [ ] T093 [P] [US2] Implement drag-and-drop reorder in `WorkflowCanvas.tsx` — `onNodeDragStop` calls `POST /api/projects/{id}/stages/reorder`; update store optimistically; rollback on API error (FR-102)
- [ ] T094 [P] [US2] Add keyboard navigation to `WorkflowCanvas.tsx` — Arrow keys move focus between nodes, Enter opens detail panel, Escape closes it, Tab cycles through nodes (FR-110)
- [ ] T095 [US2] Wire `StageDetailPanel` into `project.tsx` — slide-in from right on node click, close on Escape or clicking canvas; subscribe to SSE `stage:status` and `stage:output:complete` to auto-refresh panel without page reload (FR-011, FR-031)

**Checkpoint**: Workflow graph renders; clicking nodes opens panel; statuses update live; drag reorder reflects on disk; keyboard navigation works.

---

## Phase 10: User Story 9 — AI Conversation & Interaction per Stage (P2)

**Goal**: Per-stage conversation thread with AI; context-aware streaming responses; regenerate output with feedback; context-overflow warning.

**Independent Test**: Open completed stage → send "Summarize the output in 3 bullets" → AI responds with stage context → conversation persists in `conversation.md` → send "Regenerate with more detail" → preview shown → accept → output file updated.

- [ ] T096 [US9] Create `backend/src/hacp/services/conversation/conversation_service.py` — `ConversationService`: `load_thread(stage_path) -> list[Message]`, `append_message(stage_path, message)`, `build_context_messages(stage, thread) -> list[dict]` with sliding-window truncation (drop oldest non-system messages to fit context window, always preserve CONTEXT.md + current output) (FR-060, FR-061, FR-062, FR-112)
- [ ] T097 [US9] Create `backend/src/hacp/api/routes/conversation.py` — `GET /api/projects/{id}/stages/{n}/conversation`, `POST /api/projects/{id}/stages/{n}/conversation` (append message + stream AI reply as `conversation:chunk` SSE events), `POST /api/projects/{id}/stages/{n}/conversation/regenerate` (stream new output preview, store as `output/.preview.md`); mount on app (FR-063)
- [ ] T098 [P] [US9] Create `frontend/src/components/conversation/ConversationPanel.tsx` — message list (user=right/blue, AI=left/neutral), streaming message with cursor, input textarea with Ctrl+Enter to send, auto-scroll to bottom; loads messages from `GET /conversation`
- [ ] T099 [P] [US9] Create `frontend/src/components/conversation/RegeneratePreview.tsx` — diff view between current output and `.preview.md`; Accept button calls `POST /submit` with preview content; Discard deletes preview (FR-063)
- [ ] T100 [P] [US9] Add context-overflow warning banner to `ConversationPanel.tsx` — shown when `conversation:truncation_warning` SSE event received (emitted when sliding window drops messages); banner: "Older messages were trimmed to fit context window" (FR-112)
- [ ] T101 [P] [US9] Add "Conversation" tab to `StageDetailPanel.tsx` alongside "Details" and "Output" tabs; mount `ConversationPanel` within it
- [ ] T102 [US9] Write `backend/tests/unit/test_conversation_service.py` — test `build_context_messages` sliding window: verify oldest messages dropped when total exceeds context window, system message always retained, CONTEXT.md always included

**Checkpoint**: Conversation panel renders; send message → AI streams reply; reply persists in `conversation.md`; truncation warning shown when context exceeded; regenerate → diff view → accept → output updated.

---

## Phase 11: User Story 8 — Re-run, Versioning & Run History (P2)

**Goal**: Archive current outputs before re-run; diff two runs side-by-side; restore previous run; manage run history storage.

**Independent Test**: Complete workflow → re-run from stage 2 → verify `_runs/run-TIMESTAMP/` created with stage 1+2 outputs → complete again → diff view shows changes → restore first run → output files match original.

- [ ] T103 [US8] Create `backend/src/hacp/services/run_history/run_history_service.py` — `archive_run(project_id, from_stage_n)`: copy `output/` for all stages ≥ from_stage_n into `_runs/run-YYYY-MM-DDTHH-MM/`, write `_runs/run-YYYY-MM-DDTHH-MM/run-meta.json` (FR-054, FR-058)
- [ ] T104 [US8] Create `backend/src/hacp/api/routes/runs.py` — `GET /api/projects/{id}/runs` (list with metadata), `POST /api/projects/{id}/runs/rerun` (validate workflow not Running per FR-053, archive, clear target outputs, trigger execution), `GET /api/projects/{id}/runs/{runId}/diff` (side-by-side content diff for all changed stage outputs), `POST /api/projects/{id}/runs/{runId}/restore` (requires confirmation, overwrites `output/` files), `POST /api/projects/{id}/runs/prune` (delete by count or age); mount on app (FR-053–FR-059)
- [ ] T105 [P] [US8] Create `frontend/src/components/run-history/RunHistoryPanel.tsx` — list of past runs: timestamp, stages-affected badge, status chip; "Restore" button (opens ConfirmModal), "Diff" button opens diff view; "Prune" button
- [ ] T106 [P] [US8] Create `frontend/src/components/run-history/RunDiffViewer.tsx` — two-column diff: left=older run, right=newer run, per-stage sections, line-level additions (green) / deletions (red) (FR-056)
- [ ] T107 [P] [US8] Add re-run button to project toolbar in `project.tsx` — disabled + tooltip "Pause or wait for completion first" when workflow Running (FR-053); opens stage-picker dialog for "Re-run from stage N"
- [ ] T108 [US8] Write `backend/tests/unit/test_run_history_service.py` — test archive (verify folder structure), restore (verify output files replaced), prune (verify old runs deleted), re-run blocked while Running

**Checkpoint**: Complete workflow → re-run → `_runs/` folder created → diff view shows output changes → restore works → re-run button disabled while Running.

---

## Phase 12: User Story 5 — Collaboration Dashboard (P2)

**Goal**: Dashboard home screen highlights all projects needing human input across the workspace, with recent activity and quick-jump links.

**Independent Test**: 3 projects — 2 with AwaitingHuman stages → dashboard shows 2 "Needs Your Input" cards → click card → navigates directly to that stage's human gate editor.

- [ ] T109 [US5] Expand `GET /api/dashboard` in `dashboard.py` — scan all active projects from `project_index`, aggregate AwaitingHuman stages with project name + stage title + duration-waiting; append last 20 `ActivityEvent` entries from all `run-log.md` files (FR-023, FR-024, FR-026)
- [ ] T110 [P] [US5] Expand `DashboardSection.tsx` — "Needs Your Input" section: highlighted card per AwaitingHuman stage (project name, stage title, time waiting, direct link to `/projects/{id}?stage={n}`); Recent Activity list; Stats row (total/active/awaiting/completed)
- [ ] T111 [P] [US5] Auto-refresh dashboard via SSE — subscribe to `notification` events in `useSSE`, on `stage:awaiting_human` or `stage:status` events re-fetch dashboard API; fallback poll every 30s (FR-024)

**Checkpoint**: Dashboard surfaces all AwaitingHuman items; clicking card navigates to stage; dashboard updates on workflow state changes.

---

## Phase 13: User Story 12 — Output Export & Final Deliverable (P2)

**Goal**: Export full project (all completed stage outputs) as a single Markdown/HTML/TXT document; individual stage export also available.

**Independent Test**: Complete 3-stage project → export as HTML → downloaded file contains all 3 stage outputs with headings and optional cover page → individual stage export as markdown produces single-stage file.

- [ ] T112 [US12] Create `backend/src/hacp/services/export/export_service.py` — `consolidate_outputs(project, format) -> bytes`: collect stage outputs in routing-table order (completed stages only), render as `md` (headings per stage), `html` (Pandoc-style), or `txt` (plain); optionally prepend cover page (project name, description, date range, stage summary) (FR-064, FR-065, FR-066)
- [ ] T113 [US12] Create `backend/src/hacp/api/routes/export.py` — `POST /api/projects/{id}/export` (full project, returns file download response with correct Content-Type), `POST /api/projects/{id}/stages/{n}/export` (single stage output or zip of `output/`); mount on app
- [ ] T114 [P] [US12] Create `frontend/src/components/export/ExportDialog.tsx` — modal: format radio (md/html/txt), cover page toggle, optional filename field, Export button calling `POST /api/projects/{id}/export`, triggers browser file download via `Blob` URL
- [ ] T115 [US12] Write `backend/tests/unit/test_export_service.py` — test markdown consolidation (correct heading order), HTML output (valid HTML), cover page inclusion, single-stage export

**Checkpoint**: Export dialog opens; select HTML with cover page; download file; file contains all stage outputs with correct structure.

---

## Phase 14: User Story 6 — Manual Stage Creation & Ad-hoc Assignment (P3)

**Goal**: User can create individual stages manually (not via AI planning), insert them at any position, and have the routing table updated automatically.

**Independent Test**: Existing 3-stage project → Add Stage (position 2) → folder `02_new/` created → former `02_` becomes `03_` → routing table reflects new order → new stage editable with full CONTEXT.md fields.

- [ ] T116 [US6] Implement `insert_stage(workspace, position, stage_def)` in `workspace_service.py` — create folder at position, shift all higher-numbered folders (rename), rewrite routing table (FR-027, FR-028, FR-029)
- [ ] T117 [P] [US6] Wire "Add Stage" button in project toolbar — opens `frontend/src/components/stage-detail/AddStageDialog.tsx` with fields (title, assignee, insertAfterStage, process description, inputs, outputs); calls `POST /api/projects/{id}/stages`
- [ ] T118 [US6] Write `backend/tests/unit/test_stage_insert.py` — test inserting at position 1 (shift all), middle, end; verify folder renaming and routing table

**Checkpoint**: Add Stage dialog → stage inserted at correct position → folders renumbered on disk → routing table updated → new stage appears in graph.

---

## Phase 15: User Story 10 — Project Templates & Workspace Cloning (P3)

**Goal**: Template gallery in New Project wizard; create project from template; save existing project as template; import/export templates.

**Independent Test**: Load built-in "Blog Post Pipeline" template → new project created with pre-defined stages + CONTEXT.md files → save project as template → template appears in gallery.

- [ ] T119 [US10] Create `backend/src/hacp/services/template/template_service.py` — `list_templates() -> list[Template]` (reads `~/.hacp/templates/`), `clone_template(template_id, dest_path)` (copy workspace structure), `save_as_template(project_id, name)` (copy `_config/` + stage `CONTEXT.md` + `references/`, exclude `output/` + `_runs/`), `import_template(zip_path)`, `export_template(template_id) -> bytes`
- [ ] T120 [US10] Create `backend/src/hacp/api/routes/templates.py` — `GET /api/templates`, `POST /api/templates/import`, `GET /api/templates/{id}/export`, `POST /api/projects/{id}/save-as-template`; mount on app
- [ ] T121 [P] [US10] Add template gallery step to `NewProjectWizard.tsx` — grid of template cards with name, description, stage count, assignee breakdown; "Start blank" option; selecting template pre-populates wizard fields
- [ ] T122 [US10] Bundle 3 built-in templates in `backend/src/hacp/templates/` — `market_research_report/`, `blog_post_pipeline/`, `software_feature_spec/` — each as a valid ICM workspace folder (WORKSPACE.md + stages/ with CONTEXT.md files)

**Checkpoint**: New Project wizard shows 3 built-in templates; select template → project created with pre-defined stages; Save as Template → appears in gallery.

---

## Phase 16: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, keyboard shortcuts, search, error recovery UI, onboarding, OpenAPI codegen, and E2E test suite.

- [ ] T123 Generate TypeScript API types: run `openapi-typescript http://localhost:3001/openapi.json --output frontend/src/types/api.ts` and add to `make codegen` target; replace ad-hoc interfaces in `api-client.ts` with generated types
- [ ] T124 [P] Implement project-wide search: `GET /api/projects/{id}/search?q=&scope=outputs|stages|conversations` in `backend/src/hacp/api/routes/search.py` — grep across declared files, return matches with file + line (FR-101)
- [ ] T125 [P] Create `frontend/src/components/common/SearchBar.tsx` — Cmd/Ctrl+K command palette: search input, results list (project name / stage title / file match), keyboard nav (↑↓ Enter Escape); uses `GET /api/projects/{id}/search` for in-project scope (FR-102)
- [ ] T126 [P] Implement keyboard shortcuts in `project.tsx` — Ctrl/Cmd+Enter: run, +P: pause, +→/←: next/prev stage, +I: toggle detail panel, Esc: close panel (FR-079)
- [ ] T127 [P] Implement dark/light/system theme — `UIPreferencesSection` persists to settings; `App.tsx` applies `data-theme` attribute on `<html>`; CSS custom properties swap per theme token class (FR-076)
- [ ] T128 [P] Implement error detail view in `StageDetailPanel.tsx` — for Failed stages: show error message, loaded inputs list, model used, duration, stack trace (if available); action buttons: Retry, Retry with different model (opens model picker), Mark as Human (FR-096, FR-097)
- [ ] T129 [P] Implement breadcrumb navigation in `project.tsx` — "Project Library > {project name} > {stage name}" path; stage segment shown when detail panel open; each segment is a navigation link (FR-078)
- [ ] T130 [P] Add WCAG 2.1 AA accessibility to `WorkflowCanvas.tsx` and `StageNode.tsx` — `aria-label` on nodes with status/type, `role="region"` on canvas, non-color stage type indicator (text label + icon in addition to color), focus rings on interactive elements (FR-109)
- [ ] T131 [P] Create `frontend/src/components/common/OnboardingTooltips.tsx` — first-project tour: tooltips on workflow canvas, stage node, detail panel, human gate, activity feed; dismissed per-feature using localStorage flags (FR-107)
- [ ] T132 [P] Add Help menu to top navigation — keyboard shortcut reference sheet modal, link to README documentation (FR-108)
- [ ] T133 [P] Implement workspace disk-usage in project settings tab — call `GET /api/projects/{id}/workspace/disk-usage`, display breakdown: outputs, runs, conversations (FR-105)
- [ ] T134 [P] Implement run history prune UI in project settings tab — "Keep last N runs" input + "Prune now" button calling `POST /api/projects/{id}/runs/prune` (FR-106)
- [ ] T135 Write Playwright E2E tests in `frontend/tests/e2e/` — test files: `create-project.spec.ts` (new project wizard → stages created), `run-ai-workflow.spec.ts` (3-stage AI workflow completion), `human-gate.spec.ts` (pause → editor → submit → resume), `export.spec.ts` (export HTML → download)
- [ ] T136 Run full test suite and fix failures — `uv run pytest backend/tests/ --cov=hacp --cov-report=term` (target ≥80% coverage) + `npm run test` (Vitest) + `npx playwright test`

**Checkpoint**: All tests pass; coverage ≥80% backend; E2E tests pass; keyboard shortcuts work; dark mode toggles correctly; search returns results.

---

## Dependencies (Story Completion Order)

```
Phase 1 (Setup)
  └── Phase 2 (Foundational)
        ├── Phase 3 (US0: Workspace Setup) — required by all stories
        │     ├── Phase 4 (US11: Settings) — required before any AI execution
        │     │     └── Phase 6 (US1: Decomposition) — requires LLM config
        │     │           └── Phase 7 (US3: Execution) — requires stages to exist
        │     │                 ├── Phase 8 (US4: Human Gate) — parallel with US3 gate logic
        │     │                 ├── Phase 9 (US2: Visualization) — enhances US3 output
        │     │                 ├── Phase 10 (US9: Conversation) — requires stage output
        │     │                 ├── Phase 11 (US8: Re-run) — requires completed runs
        │     │                 └── Phase 13 (US12: Export) — requires completed outputs
        │     └── Phase 5 (US7: Library) — parallel with US11 (no LLM dependency)
        │           └── Phase 12 (US5: Dashboard) — aggregates across library
        └── Phase 14 (US6: Manual Stages) — parallel after Phase 3
        └── Phase 15 (US10: Templates) — parallel after Phase 3
Phase 16 (Polish) — after all story phases complete
```

## Parallel Execution Opportunities (Within Each Story Phase)

| Story | Tasks That Can Run in Parallel |
|-------|-------------------------------|
| US0 | T034+T035 (open+validate workspace), T039+T040+T041 (frontend hooks+pages) |
| US11 | T045+T046+T047+T048 (all settings UI sections) |
| US7 | T052+T053 (duplicate+dashboard endpoint), T055+T056 (filter bar+modal) |
| US1 | T063+T064+T065 (stage CRUD routes), T066+T067+T068 (frontend components) |
| US3 | T074+T075 (warning+routes), T077+T078+T079+T080 (frontend hooks+toolbar+node) |
| US4 | T085+T086+T087 (editor+panel+badge) |
| US2 | T090+T091+T092+T093+T094 (all node styling + interactions) |
| US9 | T098+T099+T100+T101 (all conversation UI components) |
| US8 | T105+T106+T107 (run history UI components) |

## Implementation Strategy

**MVP Scope** (Phases 1–8 = US0, US11, US7, US1, US3, US4):

Complete these phases first to deliver a fully functional end-to-end workflow:
1. Create workspace → configure LLM → submit description → stages generated
2. Run workflow → AI stages execute → human gate pauses → submit → resume
3. Library persists projects across restarts

**Increment 2** (Phases 9–13 = US2, US9, US8, US5, US12):

Enhances the MVP with better visualization, conversation, history, and export.

**Increment 3** (Phases 14–16 = US6, US10, Polish):

Adds power-user features and production-quality polish.

---

## Metrics

| Category | Count |
|----------|-------|
| **Total Tasks** | 138 |
| **Setup (Phase 1)** | 8 |
| **Foundational (Phase 2)** | 24 |
| **US0: Workspace Setup** (P1) | 10 |
| **US11: Settings** (P1) | 8 |
| **US7: Library** (P1) | 8 |
| **US1: Decomposition** (P1) | 12 |
| **US3: Execution** (P1) | 12 |
| **US4: Human Gate** (P1) | 8 |
| **US2: Visualization** (P2) | 7 |
| **US9: Conversation** (P2) | 7 |
| **US8: Re-run/History** (P2) | 6 |
| **US5: Dashboard** (P2) | 3 |
| **US12: Export** (P2) | 4 |
| **US6: Manual Stages** (P3) | 3 |
| **US10: Templates** (P3) | 4 |
| **Polish (Phase 16)** | 14 |
| **Parallelizable [P]** | 74 |
| **Parallel Ratio** | ~54% |
