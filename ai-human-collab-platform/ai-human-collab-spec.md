# Feature Specification: Human-AI Collaboration Platform

**Feature Branch**: `001-one-shot-coding-agent`  
**Created**: 2026-05-09  
**Status**: Draft  
**Input**: User description: "A platform where humans and AI collaborate on projects. An AI agent decomposes a project into detailed tasks, classifies each as human or AI work, describes each task with input/action/output, visualizes them as sequential or parallel workflows, and orchestrates execution with automatic handoffs — AI tasks run automatically, human tasks pause the workflow to notify the user, who then resumes after completion."

## Overview

The **Human-AI Collaboration Platform** (HACP) is a workspace where users and AI agents collaborate on complex projects through a shared, structured task system. The platform automates the decomposition of projects into discrete tasks, assigns each task to either a human or an AI based on task nature, and orchestrates execution — pausing for human input when needed and resuming automatically when AI continues.

The core value proposition: **reduce cognitive overhead by letting AI plan the work, while keeping humans in control of decisions that require judgment, creativity, or accountability.**

### Workspace: The Local Folder

Every project in HACP is backed by a **Workspace** — a plain local folder on the user's machine. The platform creates and manages this folder, but it remains a normal directory that users can open, inspect, and edit with any text editor. The workspace is portable: it can be copied, zipped, shared, or committed to version control. The workspace is the project. There is no separate server state to replicate.

### Agent Architecture: Folder Structure as Orchestration

HACP follows the **Interpretable Context Methodology (ICM)** — a pattern where folder structure replaces framework-level agent orchestration. Instead of multiple specialized agents coordinating through code (LangChain, AutoGen, CrewAI), a single orchestrating agent reads different context files at each stage. The numbered folder structure tells it what to do and in what order. Markdown files carry the prompts and context. Local scripts handle mechanical work that does not need AI.

The result: one agent, reading the right files at the right moment, does the work of a multi-agent framework. Every intermediate output is a plain text file a human can open, read, and edit before the next stage runs.

**ICM Five-Layer Context Hierarchy per stage:**

| Layer | File | Purpose | Approx. Size |
|---|---|---|---|
| 0 | `WORKSPACE.md` | Workspace identity — what project this is, what the folder contains | ~800 tokens |
| 1 | `CONTEXT.md` | Stage routing — what stages exist, their order, dependencies | ~300 tokens |
| 2 | `stages/NN_name/CONTEXT.md` | Stage contract — inputs, process, outputs, assignee | ~200–500 tokens |
| 3 | `references/`, `_config/`, `shared/` | Reference material — stable domain knowledge, conventions (configured once) | ~500–2k tokens |
| 4 | `stages/NN_name/output/` | Working artifacts — actual output from this run (changes each run) | varies |

**Workspace folder structure:**
```
workspace/
├── WORKSPACE.md            (Layer 0 — project identity, metadata)
├── CONTEXT.md              (Layer 1 — stage routing table)
├── stages/
│   ├── 01_task_name/       (earliest stage)
│   │   ├── CONTEXT.md      (Layer 2 — stage contract)
│   │   ├── references/     (Layer 3 — stable context for this stage)
│   │   ├── output/         (Layer 4 — output produced here)
│   │   └── conversation.md (AI-Human conversation thread for this stage)
│   ├── 02_task_name/
│   │   ├── CONTEXT.md
│   │   ├── references/
│   │   ├── output/
│   │   └── conversation.md
│   └── ...                 (as many stages as the project needs)
├── _config/                (Layer 3 shared — project-wide conventions)
│   ├── project-brief.md
│   └── conventions.md
├── run-log.md              (append-only execution log, workspace root)
├── _runs/                  (archived run snapshots)
│   ├── run-2026-05-09T14-30/
│   │   ├── 01_task_name/output/
│   │   └── 02_task_name/output/
│   └── run-2026-05-10T09-15/
└── shared/                 (Layer 3 shared — reusable reference materials)
```

Each stage's `CONTEXT.md` (Layer 2) defines a **stage contract** with three sections:
- **Inputs**: which Layer 3 files and which upstream `output/` folders (Layer 4) the agent or human should read
- **Process**: what action to perform (AI executes this; human reads this as their task description)
- **Outputs**: what file(s) to write to this stage's `output/` folder

The stage also declares its **Assignee** (AI or Human) and optionally a **Model** override (e.g., `Model: claude-sonnet-4`) to use a specific LLM for AI stages. When Assignee = AI, the orchestrating agent executes the stage automatically. When Assignee = Human, the platform pauses, surfaces the stage contract to the user, waits for them to provide output in the `output/` folder, then resumes — this is the **review gate**.

---

## User Scenarios & Testing *(mandatory)*

### User Story 0 - Workspace Setup & Configuration (Priority: P1)

Before starting a project, the user creates or opens a Workspace — a local folder on their machine. The platform initializes the folder with the ICM structure: `WORKSPACE.md`, `CONTEXT.md`, `_config/`, `shared/`, and an empty `stages/` directory. The user can configure project-wide context (conventions, domain knowledge, style preferences) in the `_config/` folder. The workspace is then ready for the orchestrating agent to create stage folders.

**Why this priority**: The workspace is the foundation for everything. It must exist before any planning or execution can happen. It also gives users full ownership and transparency — the workspace is their folder, inspectable and editable at any time.

**Independent Test**: Can be fully tested by creating a new workspace and verifying the ICM folder structure is created correctly with all required files — without submitting any project description.

**Acceptance Scenarios**:

1. **Given** a user creates a new project in the platform, **When** the platform initializes the workspace, **Then** a local folder is created at a user-selected path containing `WORKSPACE.md`, `CONTEXT.md`, `_config/project-brief.md`, `_config/conventions.md`, `shared/`, and `stages/`.
2. **Given** a workspace folder, **When** the user opens it in their file system, **Then** all files are plain text (markdown or JSON) readable without special tools.
3. **Given** an existing workspace folder, **When** the user points the platform to it, **Then** the platform reads the ICM structure and restores the project state (stages, outputs, status) from the files on disk.
4. **Given** a workspace, **When** the user edits `_config/conventions.md` directly in a text editor, **Then** the platform reflects those changes the next time it reads that file (at the next stage execution).
5. **Given** a workspace at any state, **When** the user copies the folder to another machine and opens it in the platform, **Then** the full project state is restored from the files alone — no server or database required.

---

### User Story 1 - Project Decomposition & Stage Planning (Priority: P1)

A user provides a project description. The orchestrating agent reads the description and decomposes it into numbered stage folders inside the workspace's `stages/` directory. Each stage folder contains a `CONTEXT.md` file — the stage contract — specifying what the stage reads (inputs from upstream output/ folders and reference files), what action to perform (process), and what to produce (outputs written to its own output/ folder). The stage contract also declares the Assignee: AI (agent executes automatically) or Human (platform waits for user). The platform's Layer 1 `CONTEXT.md` is updated with the routing table listing all stages and their dependencies. The user reviews the generated stage plan before triggering execution.

**Why this priority**: This is the entry point of the entire collaboration cycle. Without stage decomposition, nothing else can happen. It directly saves users hours of manual planning and creates the foundation for all other stories.

**Independent Test**: Can be fully tested by entering a project description and verifying that numbered stage folders appear in the workspace `stages/` directory, each with a correctly structured `CONTEXT.md` — without triggering execution.

**Acceptance Scenarios**:

1. **Given** a user provides a project description (e.g., "Build a market research report on EV adoption trends"), **When** the user submits it to the platform, **Then** the orchestrating agent creates ≥3 numbered stage folders in `stages/` (e.g., `01_data_collection/`, `02_analysis/`, `03_report_draft/`), each with a `CONTEXT.md`, a `references/` folder, and an empty `output/` folder.
2. **Given** generated stage folders, **When** the user reviews them, **Then** each stage's `CONTEXT.md` contains an Inputs section, a Process section, an Outputs section, and an Assignee declaration (AI or Human).
3. **Given** a project with both analytical and creative tasks, **When** stages are generated, **Then** tasks requiring subjective judgment or accountability are classified as Assignee: Human; tasks involving data processing, summarization, or code generation are classified as Assignee: AI.
4. **Given** generated stages, **When** the user wants to modify a stage before running, **Then** the user can edit the stage's `CONTEXT.md` directly (or via the platform UI) and the changes persist in the file.
5. **Given** the Layer 1 `CONTEXT.md`, **When** stage generation completes, **Then** it contains a routing table listing all stages, their sequence order, and any parallel groupings.

---

### User Story 2 - Workflow Visualization & Node Interaction (Priority: P2)

The user views the generated stages arranged visually as a workflow graph. Stages can be sequential (one after another) or parallel (multiple stages with no mutual dependency). The graph clearly distinguishes Human stages from AI stages using visual cues (color, icon, or label). Dependencies between stages are shown as directional connectors. The user can click any node to view its full details, edit it, and — after the stage completes — see its output rendered directly on the node in the workflow canvas.

**Why this priority**: Visualization builds user trust and comprehension. The ability to inspect and edit nodes directly in the workflow canvas eliminates the need to switch between views, keeping the user in a single coherent workspace. Output display on completed nodes gives immediate feedback without requiring navigation.

**Independent Test**: Can be fully tested by generating stages for a sample project, verifying the workflow graph renders correctly, clicking a node to open and edit its detail panel, and — after simulating stage completion — verifying that the output summary appears on the node itself.

**Acceptance Scenarios**:

1. **Given** a stage list with dependencies defined, **When** the workflow view is displayed, **Then** stages appear as nodes connected by directional arrows representing execution order.
2. **Given** stages that have no mutual dependency, **When** displayed, **Then** they appear on the same horizontal level (parallel track) with clear visual separation from sequential stages.
3. **Given** a workflow with mixed Human and AI stages, **When** the graph is shown, **Then** Human stages have a distinct visual style (e.g., person icon, different color) compared to AI stages.
4. **Given** any stage node, **When** the user clicks on it, **Then** a side panel or modal opens showing the stage's full details: title, description, assignee type, input specification, action description, expected output, and current status.
5. **Given** a stage node detail panel is open and the workflow has not yet started, **When** the user edits any field (title, description, assignee, input, action, expected output), **Then** the changes are saved and reflected immediately on the node in the canvas.
6. **Given** a stage node that has completed execution, **When** viewed in the workflow canvas, **Then** the node displays a preview of the actual output (summary or truncated value) directly on the node surface without requiring the user to open the detail panel.
7. **Given** a completed stage node showing output on its surface, **When** the user clicks the node, **Then** the detail panel opens with the full output rendered in its entirety, along with execution metadata (start time, end time, agent used).
8. **Given** a stage node that is currently "In Progress", **When** viewed in the canvas, **Then** the node displays a live progress indicator (e.g., spinner, progress bar, or status label) that updates in real time.

---

### User Story 3 - Workflow Execution & AI Auto-run (Priority: P1)

After reviewing the stage plan, the user triggers execution. The orchestrating agent reads each stage's `CONTEXT.md` in order. For AI-assigned stages, it loads the specified Layer 3 reference files and the previous stage's `output/` folder (Layer 4), performs the action described in the Process section, and writes the result as plain text files to the stage's own `output/` folder. The next AI stage reads that output as its Layer 4 input. The workflow progresses automatically through consecutive AI stages without user intervention.

**Why this priority**: Auto-execution of AI stages is the core automation value. Without this, every task requires manual user action, eliminating the platform's primary benefit.

**Independent Test**: Can be fully tested by creating a workspace with 3 consecutive AI stages, triggering execution, and verifying all 3 complete automatically with plain text files in each stage's `output/` folder — without human interaction.

**Acceptance Scenarios**:

1. **Given** the user triggers execution, **When** the first stage is Assignee: AI, **Then** the orchestrating agent reads that stage's `CONTEXT.md`, loads the specified input files, executes the Process, and writes output to `stages/01_name/output/`.
2. **Given** the user triggers execution, **When** the first stage is Assignee: Human, **Then** the workflow immediately pauses at the first stage's review gate, presenting the stage contract and Layer 3 reference files as context — no upstream `output/` is needed.
3. **Given** stage `01` output is written, **When** stage `02` is also Assignee: AI, **Then** the agent reads `02`'s `CONTEXT.md`, loads `stages/01_name/output/` as Layer 4 input, and executes automatically without user action.
3. **Given** an AI stage completes, **When** its output files are written to `output/`, **Then** those files are immediately available as Layer 4 input to all downstream stages that declare them in their Inputs section.
4. **Given** an AI stage fails, **When** an error occurs, **Then** the workflow pauses, no partial output is written to `output/`, the user is notified with the error details, and given options to retry, skip, or manually resolve.

---

### User Story 4 - Human Review Gate (Priority: P1)

When the workflow reaches a stage with Assignee: Human, execution pauses at a **review gate**. The platform surfaces the stage's `CONTEXT.md` to the user as their task briefing — showing what files to read (Inputs), what to do (Process), and what to produce (Outputs). The user performs the work, writes their output to the stage's `output/` folder via the platform's submission UI (or directly in the file system), then signals the platform to resume. The next stage then reads this human-produced `output/` as its Layer 4 input, exactly as it would for any AI-produced output.

**Why this priority**: This is the core differentiator. Without the review gate, the platform is a simple AI automation tool. The human review gate keeps humans meaningfully involved at the right decision points, with full context from upstream stages and clear delivery criteria.

**Independent Test**: Can be fully tested by creating a workspace where stage `02` is Assignee: Human and stages `01` and `03` are Assignee: AI — verifying that execution pauses after stage `01`, the user sees stage `02`'s stage contract and stage `01`'s output, the user writes output to `stages/02_name/output/`, and stage `03` resumes with that output as input.

**Acceptance Scenarios**:

1. **Given** the workflow is running and reaches a stage with Assignee: Human, **When** the preceding AI stage writes its `output/`, **Then** the workflow pauses and the platform notifies the user that their input is required at this stage.
2. **Given** the user opens the human stage, **When** the stage detail is displayed, **Then** they see the full stage contract from `CONTEXT.md` — Inputs (which upstream output files to read), Process (what they need to do), and Outputs (what files to produce) — alongside the actual content of all referenced input files.
3. **Given** the user performs their work and submits their output via the platform UI, **When** the submission is received, **Then** the platform writes it as plain text to `stages/NN_name/output/` and marks the stage as Completed.
4. **Given** the human stage output is written, **When** the next stage is Assignee: AI, **Then** the workflow resumes automatically and the agent reads the human's output as its Layer 4 input.
5. **Given** a human stage is open and the user navigates away, **When** they have not submitted output within a configurable time window, **Then** the platform sends a reminder notification with a direct link back to the stage.
6. **Given** the stage's `output/` folder already has files from a previous run, **When** the user is at this stage again (re-run), **Then** the platform shows the prior output as a starting point and allows the user to revise rather than starting from blank.
7. **Given** a human stage at any point, **When** the user opens the workspace folder in their file system and writes output files directly, **Then** the platform detects the new files and treats them as the stage output, allowing resume from the UI.

---

### User Story 5 - Collaboration Dashboard (Priority: P2)

The **Project Library** (User Story 7) is the home screen showing all projects. The **Collaboration Dashboard** is a cross-project summary view *within* the Project Library that aggregates actionable items across all open projects. It highlights workflows requiring human attention, shows recently active workflows, and provides quick-jump links — so the user does not have to open each project individually to find what needs action.

**Why this priority**: The dashboard saves users from opening each project to check status. It provides a single aggregated view of "what needs my attention right now" across all active projects.

**Independent Test**: Can be fully tested by running 2 simultaneous workflows and verifying the dashboard correctly reflects each workflow's status, task counts, and links to human-pending tasks — without creating new workflows.

**Acceptance Scenarios**:

1. **Given** multiple workflows exist, **When** the user opens the dashboard, **Then** all workflows are listed with their current status (Running, Paused, Completed, Failed) and a progress indicator.
2. **Given** a workflow has a human task awaiting action, **When** the dashboard is viewed, **Then** that workflow is prominently highlighted as "Needs Your Input" with a direct action link.
3. **Given** the user clicks on a workflow in the dashboard, **When** navigated, **Then** the full workflow visualization is shown with real-time status of each stage node.
4. **Given** a workflow completes, **When** viewed in the dashboard, **Then** all task outputs are accessible and the overall result/summary is displayed.

---

### User Story 6 - Manual Stage Creation & Ad-hoc Assignment (Priority: P3)

Beyond AI-generated stage plans, users can manually create individual stages, assign them to themselves or AI, and add them to an existing workflow or start a new standalone stage.

**Why this priority**: Real-world collaboration is rarely fully planned. Users need the flexibility to add unplanned work items, fix gaps in AI-generated plans, or delegate spontaneous tasks.

**Independent Test**: Can be fully tested by manually creating a stage with assignee=AI, providing inputs, and verifying the AI processes it and returns output — independent of the orchestrating agent's planning phase or any existing workflow.

**Acceptance Scenarios**:

1. **Given** a user creates a manual stage, **When** they set the assignee to "AI" and provide inputs, **Then** the AI agent processes it and returns output within the expected time.
2. **Given** a user creates a manual stage, **When** they assign it to themselves, **Then** it appears in their human task queue awaiting their action.
3. **Given** an existing workflow, **When** a user inserts a manual stage between two existing stages, **Then** the workflow re-renders with the new stage in the correct position and execution order, and the Layer 1 `CONTEXT.md` routing table is updated.

---

### User Story 7 - Project Library & Persistence (Priority: P1)

The user has a **Project Library** — the home screen of the platform — showing all their saved projects as cards with title, description preview, last modified date, status, and a progress indicator. Projects are persisted as workspace folders. The user can open any project to resume where they left off, archive completed projects, duplicate a project as a starting point for a new one, or delete a project. The library supports search and filtering by status, date, and tags.

**Why this priority**: Without persistence and a project library, users lose track of their workspaces. The platform becomes a throwaway tool rather than a workspace they return to daily. This is the landing page — first impression and daily driver.

**Independent Test**: Can be fully tested by creating 3 projects in various states (draft, running, completed), closing the platform, reopening it, and verifying all 3 appear in the library with correct metadata — without re-importing.

**Acceptance Scenarios**:

1. **Given** the user opens the platform, **When** the home screen loads, **Then** a Project Library is displayed showing all known workspace folders as project cards with title, status badge, progress bar, last-modified date, and a short description preview.
2. **Given** the Project Library, **When** the user clicks "New Project", **Then** a project creation wizard opens guiding the user through: naming the project, selecting a folder path (or using default), optionally selecting a template, and entering the initial project description.
3. **Given** a project that was previously worked on, **When** the user clicks its card in the library, **Then** the platform opens the workspace and restores the exact state — including which stages are complete, which are paused, and which are pending.
4. **Given** a completed project, **When** the user selects "Duplicate", **Then** the platform copies the workspace folder (with all `_config/` and `CONTEXT.md` files but with empty `output/` folders) to a new path, creating a fresh project with the same structure.
5. **Given** a project, **When** the user selects "Archive", **Then** the project is removed from the active library view but the workspace folder is preserved on disk and can be restored later.
6. **Given** the Project Library with many projects, **When** the user searches or filters, **Then** projects can be filtered by status (Draft, Running, Paused, Completed, Archived), searched by name or description, and sorted by last-modified date.
7. **Given** the user assigns tags to projects (e.g., "research", "report", "engineering"), **When** browsing the library, **Then** projects can be filtered by tag.

---

### User Story 8 - Re-run, Versioning & Run History (Priority: P2)

The user can re-run a workflow from any stage. Before re-running, the platform archives the current `output/` files from that stage and all downstream stages into a timestamped run snapshot (e.g., `_runs/run-2026-05-09T14-30/`). The user can view a history of all past runs, compare outputs between runs, and restore a previous run's output as the current working version. This enables iterative refinement: tweak a stage's `CONTEXT.md`, re-run, compare results.

**Why this priority**: Iteration is the heart of collaboration. Users will want to re-run with modified prompts, different inputs, or after editing AI output. Without run history, each re-run destroys the previous result.

**Independent Test**: Can be fully tested by completing a 3-stage workflow, modifying stage `02`'s `CONTEXT.md`, re-running from stage `02`, and verifying that the old outputs are archived and a new run produces fresh outputs — while the old outputs remain accessible.

**Acceptance Scenarios**:

1. **Given** a completed workflow, **When** the user clicks "Re-run from Stage 02", **Then** the platform archives `output/` folders from stages 02 and downstream into a timestamped snapshot folder (e.g., `_runs/run-2026-05-09T14-30/`) and clears the current `output/` folders for those stages.
2. **Given** a re-run has been triggered, **When** the re-run completes, **Then** a new run entry appears in the Run History panel with timestamp, stages re-run, and completion status.
3. **Given** the Run History panel, **When** the user selects two runs, **Then** the platform displays a side-by-side diff view comparing outputs of each stage between the two runs.
4. **Given** a previous run in the history, **When** the user selects "Restore this run", **Then** the platform replaces the current `output/` files with the outputs from the selected run, effectively rolling back.
5. **Given** a workflow in any state, **When** the user clicks "Re-run entire workflow", **Then** all stages are re-executed from the beginning, with the previous run archived first.
6. **Given** a project with multiple runs, **When** the user opens the workspace folder on disk, **Then** the `_runs/` folder contains all archived run snapshots as plain text files, browsable without the platform.

---

### User Story 9 - AI Conversation & Interaction per Stage (Priority: P2)

At any stage (during planning, during review, or after completion), the user can open a **conversation thread** with the AI about that specific stage. The user can ask questions ("Why did you classify this as an AI task?", "Can you re-do this with more detail?"), request modifications, or ask the AI to explain its output. The AI responds with full context awareness — it reads the stage's `CONTEXT.md`, the stage's `output/`, and relevant reference files. The conversation is saved as `stages/NN_name/conversation.md` and is visible in the stage detail panel.

**Why this priority**: True collaboration requires dialogue, not just task execution. Without conversation, AI is a black box that produces output and the human can only accept or reject it. Conversation enables steering, learning, and co-creation.

**Independent Test**: Can be fully tested by completing an AI stage, opening its conversation thread, asking "Why did you structure the output this way?", and verifying the AI responds with a relevant explanation referencing the stage's inputs and process — without modifying the stage output.

**Acceptance Scenarios**:

1. **Given** any stage (draft, completed, or in progress), **When** the user opens the stage detail panel, **Then** a "Chat" tab is available showing the conversation thread for that stage.
2. **Given** the user types a message in the stage conversation, **When** sent, **Then** the AI reads the stage's `CONTEXT.md`, its `output/` (if any), and the referenced input files, and responds with context-aware answers.
3. **Given** the user asks "Re-do this with a different approach", **When** the AI produces a revised output, **Then** the user can preview it and choose to accept (overwriting the current output) or discard.
4. **Given** a conversation thread, **When** the user closes and re-opens the stage panel, **Then** the full conversation history is preserved and displayed (loaded from `stages/NN_name/conversation.md`).
5. **Given** a human review gate stage, **When** the user is unsure what to produce, **Then** they can ask the AI for suggestions, examples, or clarification — and the AI generates them based on the stage contract and upstream outputs.
6. **Given** an AI stage that produced unsatisfactory output, **When** the user provides feedback in the conversation ("This is too vague, add concrete data"), **Then** the AI can regenerate the output incorporating the feedback, subject to user approval.

---

### User Story 10 - Project Templates & Workspace Cloning (Priority: P3)

The platform provides pre-built **project templates** for common project types (e.g., "Market Research Report", "Software Feature Spec", "Blog Post Pipeline", "Data Analysis"). A template is a workspace folder with pre-defined stages, reference files, and conventions — but with empty `output/` folders. Users can also save any completed project as a custom template for reuse. When starting a new project, the user can select a template and the platform clones the workspace structure, ready for the user to customize and run.

**Why this priority**: Templates dramatically reduce setup time for recurring project types and encode best practices. They also enable sharing: a team can create a template once and reuse it across many similar projects.

**Independent Test**: Can be fully tested by selecting a template, creating a new project from it, and verifying the stage structure matches the template with fresh `output/` folders — without running any stages.

**Acceptance Scenarios**:

1. **Given** the "New Project" wizard, **When** the user reaches the template selection step, **Then** they see a gallery of available templates with name, description, stage count, and a preview of the workflow structure.
2. **Given** a selected template, **When** the user creates a project from it, **Then** the platform clones the template's workspace structure (stages, CONTEXT.md files, references, _config) into a new folder with empty `output/` folders.
3. **Given** a completed project, **When** the user selects "Save as Template", **Then** the platform creates a template from the workspace — preserving the folder structure, stage contracts, and reference files, but stripping all `output/` content and run history.
4. **Given** a custom template, **When** another user receives it (e.g., via shared folder or zip), **Then** they can import it into their platform's template gallery.

### User Story 11 - Platform Settings & Administration (Priority: P1)


The user needs a **Settings page** to configure platform-wide behavior: which LLM provider and model to use, API keys, default stage parameters, UI preferences, and workspace defaults. These settings are persisted locally (e.g., `~/.hacp/settings.json`) and apply across all projects unless overridden at the project level.

**Why this priority**: Without settings, the platform cannot connect to any AI provider. LLM model selection, API key management, and default configurations are prerequisites for any AI stage execution. This is a day-one requirement.

**Independent Test**: Can be fully tested by opening the settings page, configuring an LLM provider and API key, saving, restarting the platform, and verifying the settings persist — without creating any project.

**Acceptance Scenarios**:

1. **Given** the platform is launched for the first time, **When** no LLM API key is configured, **Then** the platform displays a guided setup wizard prompting the user to select an LLM provider, enter an API key, and optionally configure defaults before proceeding.
2. **Given** the Settings page, **When** the user selects an LLM provider (e.g., OpenAI, Anthropic, Google, Ollama/local), **Then** the platform displays provider-specific fields (API key, base URL, available models) and allows the user to select a default model.
3. **Given** a configured API key, **When** the user clicks "Test Connection", **Then** the platform sends a minimal test request to the LLM provider and displays a success/failure result with error details if it fails.
4. **Given** multiple LLM providers configured, **When** the user creates a new project, **Then** the project inherits the platform's default LLM settings but can override them in the project's `_config/` folder.
5. **Given** the Settings page, **When** the user changes the default model from GPT-4o to Claude Sonnet, **Then** all new AI stage executions use Claude Sonnet unless the project has a model override.
6. **Given** the Settings page, **When** the user saves changes and restarts the platform, **Then** all settings are preserved and applied on next launch.

---

### User Story 12 - Output Export & Final Deliverable (Priority: P2)

After completing a workflow (or at any point during execution), the user can **export** the project's outputs as a consolidated document. The platform collects all stage outputs in order, combines them into a single document with stage headings, and exports it as Markdown, HTML, or plain text. The user can also export individual stage outputs. This transforms raw `output/` files scattered across folders into a presentable final deliverable.

**Why this priority**: The entire point of running a workflow is to produce a result. Without export, users must manually navigate folders and copy-paste outputs. A one-click export makes the platform output immediately usable — for sharing, review, or delivery.

**Independent Test**: Can be fully tested by completing a 3-stage workflow, clicking "Export", and verifying a single consolidated document is produced containing all stage outputs in order with proper headings — without modifying any workspace files.

**Acceptance Scenarios**:

1. **Given** a completed workflow, **When** the user clicks "Export Project", **Then** the platform generates a single consolidated document containing all stage outputs in execution order, with each stage's title as a heading.
2. **Given** the export dialog, **When** the user selects a format (Markdown, HTML, or plain text), **Then** the platform produces the document in that format and saves it to a user-selected location.
3. **Given** a partially completed workflow, **When** the user exports, **Then** only completed stages are included, with a note indicating which stages are pending or incomplete.
4. **Given** any individual stage, **When** the user clicks "Export Stage" from the stage detail panel, **Then** the platform exports that stage's `output/` files as a single document or zip.
5. **Given** a completed workflow, **When** the user exports, **Then** the export includes an optional cover page with project name, description, creation date, completion date, and stage summary.

---

### Edge Cases

- **Empty project description**: What happens when the user submits a blank or very vague project description (e.g., "do something")?
- **AI stage timeout**: What happens when the orchestrating agent takes too long or never completes a stage?
- **Circular stage dependencies**: What happens if the orchestrating agent generates stage dependencies that form a cycle?
- **Human unavailability**: What happens when a human stage has not been acted on for an extended period?
- **Output file missing**: What happens when an AI stage does not produce the expected output files in its `output/` folder?
- **Output format mismatch**: What happens when an AI stage's output files do not match the format declared in the downstream stage's Inputs section?
- **Concurrent workspace modification**: What happens when a user edits a stage's `CONTEXT.md` or `output/` files while that stage is currently executing?
- **Partial workflow completion**: What happens when a workflow is abandoned mid-run — can it be resumed? The output files from completed stages should still be present on disk.
- **Workspace moved or renamed**: What happens when the user moves the workspace folder to a different path after the platform has started tracking it?
- **Stage folder manually deleted**: What happens when the user deletes a stage folder from the file system while the workflow references it?
- **File encoding or size**: What happens when a stage produces very large output files or non-UTF-8 content?
- **Re-run while running**: What happens when the user triggers a re-run on a workflow that is currently executing?
- **Template version drift**: What happens when a template is updated after projects were already created from it — are existing projects affected?
- **Conversation context overflow**: What happens when the conversation thread on a stage grows too long for the AI's context window?
- **Duplicate project names**: What happens when a user creates two projects with the same name?
- **Workspace folder permissions**: What happens when the platform lacks write permissions to the workspace folder?
- **Invalid API key**: What happens when the configured LLM API key is expired, revoked, or invalid — does the platform detect this before attempting stage execution?
- **LLM provider outage**: What happens when the configured LLM provider is unreachable during an AI stage execution — does the platform retry, fail gracefully, or allow switching providers?
- **Settings file corrupted**: What happens when `~/.hacp/settings.json` is corrupted or contains invalid JSON — does the platform fall back to defaults or prompt reconfiguration?
- **Model not available**: What happens when the user selects a model that their API key does not have access to (e.g., GPT-4 on a free-tier key)?
- **Browser crash during editing**: What happens when the browser crashes while the user is composing output in the rich text editor at a human review gate — is work lost?
- **Export with missing stages**: What happens when the user exports a workflow where some stages were skipped or failed?
- **Extremely large workspace**: What happens when `_runs/` accumulates hundreds of run snapshots consuming gigabytes of disk space?
- **Concurrent stage editing**: What happens when the user edits a stage's CONTEXT.md in the platform UI while also editing it in an external text editor?

---

## Requirements *(mandatory)*

### Functional Requirements

**Workspace & ICM Architecture**

- **FR-035**: When a user creates a new project, the system MUST initialize a local workspace folder at a user-selected path with the ICM folder structure: `WORKSPACE.md`, `CONTEXT.md`, `_config/project-brief.md`, `_config/conventions.md`, `shared/`, and `stages/`.
- **FR-036**: The system MUST be able to open and restore a project from an existing workspace folder by reading its ICM files, without requiring any separate database or server state.
- **FR-037**: The orchestrating agent MUST create numbered stage folders inside `stages/` (e.g., `01_research/`, `02_analysis/`) with a `CONTEXT.md` (Layer 2 stage contract), `references/` (Layer 3), and empty `output/` (Layer 4) in each.
- **FR-038**: Each stage `CONTEXT.md` MUST contain three labeled sections: **Inputs** (listing Layer 3 reference files and Layer 4 upstream `output/` folders to read), **Process** (description of the action to perform), and **Outputs** (names of files to write to this stage's `output/`). It MUST also declare **Assignee**: AI or Human. Optionally, it MAY include a **Model** override (e.g., `Model: claude-sonnet-4`) to use a specific LLM for this stage.
- **FR-039**: The platform's Layer 1 `CONTEXT.md` MUST be updated after planning to contain a routing table listing all stages, their execution order, dependencies, and assignee types.
- **FR-040**: When executing an AI stage, the orchestrating agent MUST load only the files declared in that stage's `CONTEXT.md` Inputs section (no other workspace files), execute the Process, and write output exclusively to that stage's `output/` folder as plain text or markdown files.
- **FR-041**: The output files written by a completed stage MUST be used verbatim as Layer 4 input for all downstream stages that declare them in their Inputs section — no transformation or re-encoding.
- **FR-042**: Users MUST be able to edit any stage's `CONTEXT.md` file directly in a text editor and have the platform reflect those changes at the next execution of that stage.
- **FR-043**: Users MUST be able to open the workspace folder in their operating system's file manager and navigate, read, or edit any file without the platform being open.
- **FR-044**: The platform MUST detect when files in a stage's `output/` folder are written or modified from outside the platform (e.g., user edits directly) and update the stage's status accordingly.
- **FR-045**: The workspace folder MUST be self-contained for **project state**: copying it to another machine and opening it in the platform MUST restore the full project state (stages, outputs, run history, conversations) from the files alone. Note: the user must separately configure LLM settings (`~/.hacp/settings.json` and API keys) on the target machine for AI stages to execute.

**Project & Stage Decomposition**

- **FR-001**: The system MUST allow users to submit a project description in natural language (plain text, min 10 characters).
- **FR-002**: The system MUST use the AI agent to analyze the project description and generate a structured stage plan with a minimum of 3 stages.
- **FR-003**: Each generated stage MUST include: title, description, assignee type (Human | AI), input specification, action description, and output specification — encoded in the stage's `CONTEXT.md`.
- **FR-004**: The AI agent MUST classify each stage as Human or AI based on the nature of the work (e.g., stages requiring judgment, creativity, or approval → Human; stages involving data processing, text generation, code execution → AI).
- **FR-005**: Users MUST be able to edit any field of any stage (assignee, description, inputs, outputs) before execution begins.
- **FR-006**: Users MUST be able to add, remove, or reorder stages in the generated plan before triggering execution.

**Workflow Visualization & Node UI**

- **FR-007**: The system MUST render the stage plan as a visual workflow graph with nodes (stages) and directional edges (dependencies).
- **FR-008**: The system MUST visually distinguish Human stages from AI stages in the workflow graph using distinct colors, icons, or labels.
- **FR-009**: The system MUST support two stage arrangement patterns: sequential (stages run one after another) and parallel (stages with no mutual dependency displayed on the same horizontal level). In v1, parallel stages are **visually grouped** but execute sequentially; true concurrent execution is future scope.
- **FR-010**: The workflow itself MUST have a top-level status: **Draft** (stages planned but execution not started), **Running** (at least one stage actively executing), **Paused** (user-initiated pause or waiting for human input), **Completed** (all stages done), or **Failed** (an unrecoverable stage failure). Each stage node in the workflow MUST display its own execution status (Pending | In Progress | Awaiting Human | Completed | Failed) via a visible indicator on the node itself.
- **FR-011**: Clicking a stage node MUST open a detail panel showing the stage's full information: title, description, assignee type, input specification, action description, expected output specification, current status, and execution log (if available).
- **FR-030**: The node detail panel MUST allow the user to edit any stage field (title, description, assignee type, input, action, expected output) when the workflow is in Draft or Paused state. Editing MUST be blocked while the stage status is `In Progress`; the panel MUST display a "Stage is running — editing locked" indicator and unlock automatically when the stage transitions to Completed, Failed, or AwaitingHuman.
- **FR-031**: Edits made in the node detail panel MUST be reflected on the node in the workflow canvas immediately upon saving, without requiring a page reload.
- **FR-032**: When a stage completes (Human or AI), the stage node MUST display the actual output directly on its surface in the workflow canvas — as a summary or truncated preview sufficient to understand the result at a glance.
- **FR-033**: The full output of a completed stage MUST be accessible in the node detail panel, rendered in its entirety with formatting preserved (e.g., lists, paragraphs, code blocks as appropriate to the content type).
- **FR-034**: While a stage is executing (status: In Progress), the node MUST display a real-time progress indicator that updates without requiring a manual page refresh.

**Workflow Execution**

- **FR-012**: Users MUST be able to trigger workflow execution with a single action after reviewing the stage plan.
- **FR-013**: Upon execution start, the system MUST automatically pick up and process all AI-assigned stages in dependency order without user intervention.
- **FR-014**: When an AI stage completes, its output MUST be automatically passed as the input to all dependent downstream stages.
- **FR-015**: When consecutive stages are AI-assigned, the workflow MUST continue automatically without pausing.
- **FR-016**: When an AI stage fails, the workflow MUST pause and notify the user with the error details, offering options to retry, skip, or manually resolve.

**Human-in-the-Loop Handoff**

- **FR-017**: When a workflow reaches a Human-assigned stage, execution MUST pause and the user MUST be notified.
- **FR-018**: The human stage notification MUST include: stage title, description, context from upstream outputs, required input format, and expected output format.
- **FR-019**: The platform MUST provide a submission interface for the user to provide their output for a human stage.
- **FR-020**: Upon user submission, the workflow MUST automatically resume and pass the user's output as input to the next stage.
- **FR-021**: If a human stage has not been acted on within a configurable time window, the platform MUST send a reminder notification.
- **FR-022**: Users MUST be able to pause, resume, or cancel a workflow at any time.

**Dashboard & Monitoring**

- **FR-023**: The platform MUST provide a dashboard showing all workflows (active, paused, completed, failed) with status and progress indicators.
- **FR-024**: The dashboard MUST prominently surface workflows that are "Awaiting Human Input" and provide direct navigation to the relevant stage.
- **FR-025**: Completed workflows MUST retain all stage outputs and be accessible for review after completion.
- **FR-026**: The system MUST maintain an audit log of all stage executions, outputs, and user actions within each workflow.

**Manual Stage Management**

- **FR-027**: Users MUST be able to manually create stages outside of the AI agent and assign them to Human or AI.
- **FR-028**: Manually created stages MUST support the same CONTEXT.md structure (Inputs/Process/Outputs/Assignee) as AI-generated stages.
- **FR-029**: Users MUST be able to insert manual stages into existing workflows at any position before or after existing stages, with the Layer 1 routing table updated automatically.

**Project Library & Persistence**

- **FR-046**: The platform MUST display a Project Library as the home screen, showing all known workspace projects as cards with title, status, progress indicator, last-modified date, and description preview.
- **FR-047**: The platform MUST persist a lightweight project index (e.g., `~/.hacp/projects.json`) mapping project names to workspace folder paths, so projects survive between platform restarts.
- **FR-048**: The platform MUST support creating a new project via a guided wizard: project name, workspace folder path selection, optional template selection, and initial project description.
- **FR-049**: Users MUST be able to duplicate a project — the platform copies the workspace folder (preserving `_config/`, all stage `CONTEXT.md` files and `references/`, but clearing all `output/` folders, `_runs/`, and `conversation.md` files).
- **FR-050**: Users MUST be able to archive a project (removed from active library view, folder preserved on disk) and restore it later.
- **FR-051**: Users MUST be able to tag projects with user-defined labels and filter/search the Project Library by tag, status, or name.
- **FR-052**: Each workspace MUST contain a `WORKSPACE.md` (Layer 0) that includes: project name, description, creation date, last-modified date, current workflow status, and a stage summary. The platform updates this file automatically after each state change.

**Re-run, Versioning & Run History**

- **FR-053**: Users MUST be able to trigger a re-run from any specific stage (all downstream stages are also re-run). The re-run action MUST be disabled (button greyed out with tooltip "Pause or wait for completion first") while the workflow status is `Running`; it becomes available once the workflow reaches `Paused`, `Completed`, or `Failed`.
- **FR-054**: Before a re-run, the platform MUST archive the current `output/` files from the target stage and all downstream stages into a timestamped snapshot folder inside `_runs/` (e.g., `_runs/run-2026-05-09T14-30/01_research/output/`).
- **FR-055**: The platform MUST display a Run History panel listing all past runs with timestamp, stages affected, completion status, and a link to view archived outputs.
- **FR-056**: Users MUST be able to select two runs and view a side-by-side diff comparison of stage outputs between them.
- **FR-057**: Users MUST be able to restore a previous run's outputs as the current working version (replaces current `output/` files with archived ones).
- **FR-058**: The `_runs/` folder MUST be part of the workspace and browsable as plain text files outside the platform.
- **FR-059**: When re-running a workflow, the platform MUST preserve the current `_config/` and stage `CONTEXT.md` files (only `output/` is archived and cleared). Conversation threads (`conversation.md`) are preserved in place — new conversation messages are appended after a re-run separator.

**AI Conversation & Interaction**

- **FR-060**: Each stage MUST support a conversation thread between the user and AI, accessible from the stage detail panel.
- **FR-061**: When the user sends a message in a stage conversation, the AI MUST read the stage's `CONTEXT.md`, its `output/` (if any), and referenced input files to provide context-aware responses.
- **FR-062**: The conversation thread MUST be persisted as `stages/NN_name/conversation.md` — a plain text file viewable outside the platform.
- **FR-063**: The user MUST be able to ask the AI to regenerate a stage's output with feedback (e.g., "Add more detail", "Change the approach"). The AI presents a preview that the user can accept or discard.
- **FR-064**: At a human review gate, the user MUST be able to ask the AI for suggestions, examples, or clarification about what to produce for that stage.
- **FR-065**: AI responses in the conversation MUST stream in real-time (token-by-token or chunk-by-chunk) to provide immediate feedback.
- **FR-112**: When the accumulated conversation history for a stage exceeds the LLM's context window, the platform MUST apply a **sliding window**: drop the oldest messages until the payload fits, always preserving the stage contract (`CONTEXT.md`) and current `output/` content. The platform MUST display a visible warning in the conversation panel indicating that older messages have been excluded from the current context.

**Project Templates**

- **FR-066**: The platform MUST provide a gallery of built-in project templates for common project types, each consisting of a workspace structure with pre-defined stages, reference files, and conventions.
- **FR-067**: Users MUST be able to create a new project from a selected template. The platform clones the template's folder structure into a new workspace with empty `output/` folders.
- **FR-068**: Users MUST be able to save any existing project as a custom template, stripping all `output/` content, run history, and conversation files.
- **FR-069**: Custom templates MUST be exportable as a zip file and importable by other users into their template gallery.

**User Interface & Experience**

- **FR-070**: The platform MUST be a desktop web application with a responsive layout supporting screen widths from 1280px to ultrawide.
- **FR-071**: The UI MUST use a clean, modern design language with consistent spacing, typography, color palette, and visual hierarchy. Human-assigned stages MUST use a warm color (e.g., amber/orange) and AI-assigned stages MUST use a cool color (e.g., blue/indigo) throughout the interface.
- **FR-072**: The workflow visualization MUST support zoom, pan, and fit-to-screen controls. Users MUST be able to zoom into a region and navigate large workflows (>15 stages) comfortably.
- **FR-073**: The stage detail panel MUST use a split-pane layout: left side shows input context (upstream outputs, reference files), right side shows the editing/submission area for the current stage's work.
- **FR-074**: For human review gate stages, the platform MUST provide a rich text editor (markdown-aware with preview) for composing the stage output, not just a plain textarea.
- **FR-075**: The platform MUST display an **Activity Feed** in the sidebar or as a collapsible panel showing a chronological list of all events: stage started, stage completed, human input requested, user edited a file, AI conversation message, etc.
- **FR-076**: The platform MUST support a **dark mode** and a **light mode**, with the user's preference persisted.
- **FR-077**: While an AI stage is executing, the platform MUST show a streaming output preview — the user can watch the AI's work in progress (text appearing token-by-token or in chunks) before it is finalized to the `output/` folder.
- **FR-078**: The platform MUST display a **breadcrumb navigation** showing: Project Library > Project Name > Stage Name, allowing one-click navigation to any level.
- **FR-079**: Keyboard shortcuts MUST be available for common actions: run workflow (Ctrl/Cmd+Enter), pause (Ctrl/Cmd+P), next stage (Ctrl/Cmd+→), previous stage (Ctrl/Cmd+←), toggle detail panel (Ctrl/Cmd+I).

**Platform Settings & Administration**

- **FR-080**: The platform MUST provide a Settings page accessible from the main navigation (sidebar or top bar) at all times.
- **FR-081**: The Settings page MUST include an **LLM Configuration** section where users can select an LLM provider (OpenAI, Anthropic, Google, Ollama/local, custom OpenAI-compatible endpoint) and enter the corresponding API key or connection details.
- **FR-082**: API keys MUST be stored securely on the local machine — encrypted at rest using the OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service) or an application-level encryption key. API keys MUST NOT be stored in plain text in settings files.
- **FR-083**: The Settings page MUST allow the user to select a **default LLM model** from the available models for the chosen provider (e.g., GPT-4o, Claude Sonnet 4, Gemini 2.5 Pro). The platform SHOULD fetch the available model list from the provider API when a valid key is present.
- **FR-084**: The Settings page MUST include a **Test Connection** button that sends a minimal request to the configured LLM provider and displays the result (success with model name and response time, or failure with error message).
- **FR-085**: The Settings page MUST include a **Default Parameters** section for configuring: default temperature (0.0–2.0), max output tokens, and system prompt prefix that applies to all AI stages unless overridden.
- **FR-086**: Individual projects MUST be able to override platform-wide LLM settings by placing a `_config/llm.json` file in the workspace folder. Individual stages MUST be able to override both project and platform settings by adding an `llm` field in their `CONTEXT.md` (e.g., `Assignee: AI | Model: claude-sonnet-4`). The precedence order is: stage-level > project-level (`_config/llm.json`) > platform-level (`~/.hacp/settings.json`).
- **FR-087**: The Settings page MUST include a **Workspace Defaults** section for configuring: default workspace root directory (where new project folders are created), default stage naming convention (e.g., `01_name` vs `001_name`), and whether to auto-create `conversation.md` files in new stages.
- **FR-088**: The Settings page MUST include a **UI Preferences** section for: theme (light/dark/system), editor font size, activity feed visibility default, and notification sound toggle.
- **FR-089**: All settings MUST be persisted in `~/.hacp/settings.json` (with API keys stored separately in the OS keychain). Changes take effect immediately without requiring a platform restart.
- **FR-090**: On first launch, if no settings file exists and no LLM API key is configured, the platform MUST display a **first-run setup wizard** that guides the user through: LLM provider selection → API key entry → connection test → default model selection → workspace directory selection.
- **FR-091**: The Settings page MUST support configuring **multiple LLM providers** simultaneously (e.g., OpenAI for fast stages, Anthropic for complex reasoning stages). Each provider configuration includes: provider type, API key, base URL (for custom endpoints), and preferred model. The user selects one as the platform-wide default.

**Output Export & Deliverable**

- **FR-092**: The platform MUST provide an "Export Project" action that consolidates all completed stage outputs into a single document in execution order, with each stage's title as a section heading.
- **FR-093**: Export MUST support at least three formats: Markdown (.md), HTML (.html), and plain text (.txt). The user selects the format before export.
- **FR-094**: The platform MUST support exporting individual stage outputs from the stage detail panel (as markdown or as a zip of all files in `output/`).
- **FR-095**: The export MUST include an optional cover page with project name, description, date range, and stage summary.

**Error Handling & Recovery**

- **FR-096**: When an AI stage fails, the platform MUST display an **error detail panel** showing: error message, stack trace or API error code (if available), which files were loaded as inputs, the model and provider used, and how long the stage ran before failing.
- **FR-097**: The error detail panel MUST offer three recovery actions: **Retry** (re-execute the same stage with the same inputs), **Retry with different model** (let the user select an alternative model from configured providers), and **Mark as Human** (convert the stage to Assignee: Human so the user can complete it manually).
- **FR-098**: The platform MUST maintain an **error log** as part of `run-log.md` (at workspace root), recording all errors with timestamps, stage references, and error details.
- **FR-111**: On backend startup, the platform MUST scan all open projects and check for interrupted stages: any stage whose folder's `output/` is empty but whose last recorded status in the routing table was `In Progress` MUST be automatically marked `Failed` with reason "Interrupted — no output found". No user action is required; the stage is immediately retryable.

**Auto-save & Data Safety**

- **FR-099**: The rich text editor (human review gate stages) MUST auto-save drafts every 30 seconds to a local draft file (`stages/NN_name/.draft.md`). If the browser crashes or the user navigates away, the draft MUST be recoverable on the next visit to that stage.
- **FR-113**: When an AI stage writes an output file exceeding 1MB, the platform MUST write the file to `output/` without blocking, then display a **soft warning** in the Activity Feed and the stage detail panel stating "Output is large (X MB) — downstream stages may hit context limits." The workflow continues automatically; the user may edit or split the output before the next stage executes.
- **FR-100**: The conversation input field MUST preserve unsent messages across page navigation within the same session.

**Search & Navigation**

- **FR-101**: The platform MUST provide a **project-wide search** (Ctrl/Cmd+K or search bar) that searches across all stage outputs, stage `CONTEXT.md` files, reference files, and conversation threads within the current project. Results link directly to the matching stage and file.
- **FR-102**: The workflow canvas MUST support **drag-and-drop reordering** of stages in Draft state. Dropping a stage between two others MUST update the folder numbering and the Layer 1 routing table automatically.

**Confirmations & Destructive Actions**

- **FR-103**: All destructive actions MUST require explicit user confirmation via a modal dialog: delete project, restore a previous run (overwrites current outputs), clear all outputs, archive project, and delete a stage.
- **FR-104**: The confirmation dialog for destructive actions MUST clearly state what will be affected and whether the action is reversible.

**Workspace Maintenance**

- **FR-105**: The platform MUST display the current workspace disk usage (total size, `_runs/` size) in the project detail view or settings.
- **FR-106**: The platform MUST provide a **Prune Run History** action that lets the user delete old run snapshots from `_runs/`, with options to keep the last N runs or runs newer than a specified date.

**Onboarding & Help**

- **FR-107**: On first project creation, the platform MUST display contextual tooltips or a brief guided walkthrough highlighting: the workflow canvas, stage detail panel, human review gate, and activity feed.
- **FR-108**: The platform MUST include a **Help** menu (or ? icon) linking to documentation and showing keyboard shortcut reference.

**Accessibility**

- **FR-109**: The platform MUST meet WCAG 2.1 Level AA standards: all interactive elements MUST be keyboard-navigable, images and icons MUST have alt text or ARIA labels, color MUST NOT be the sole indicator of stage type (icons or labels MUST accompany color coding), and focus indicators MUST be visible.
- **FR-110**: The workflow canvas MUST support keyboard-only navigation: arrow keys to move between nodes, Enter to open stage detail, Escape to close panels.

---

### Key Entities

- **Workspace**: A local folder on the user's machine that represents one project. Contains `WORKSPACE.md` (Layer 0 — project identity), `CONTEXT.md` (Layer 1 — stage routing), `stages/` (all stage folders), `_config/` (project-wide reference material), and `shared/` (reusable reference files). The workspace is the single source of truth: the platform reads from and writes to it exclusively. It is portable — copying the folder copies the entire project.

- **Stage**: A numbered subfolder within `stages/` (e.g., `01_research/`). Represents one task in the workflow. Contains a `CONTEXT.md` stage contract, a `references/` folder (Layer 3 material specific to this stage), and an `output/` folder (Layer 4 working artifacts produced by this stage's execution). The folder number determines execution order; equal numbers indicate parallel stages.

- **Stage Contract**: The `CONTEXT.md` file within a stage folder (Layer 2). Defines four elements: **Inputs** (which Layer 3 reference files and which upstream `output/` folders to load), **Process** (the action to perform — executed by AI or followed by Human), **Outputs** (what files to produce in `output/`), and **Assignee** (AI | Human). Optionally includes a **Model** override for stage-specific LLM selection. This file is the control surface of the stage: editing it changes the agent's or human's behavior at that step.

- **Review Gate**: The pause point that occurs when the workflow reaches a stage with Assignee: Human. The platform pauses execution, surfaces the stage contract and all referenced input files to the user, waits for the user to write output to `output/`, then resumes. Note: between AI stages, a user can manually pause the workflow to inspect any completed stage's `output/` and edit files before the next stage runs — but this is a user-initiated pause, not an automatic review gate.

- **Reference Material (Layer 3)**: Stable files in `_config/`, `shared/`, or a stage's `references/` folder. These are configured once during workspace setup and persist across every run of the workflow. Examples: `project-brief.md`, `domain-conventions.md`, `style-guide.md`. The orchestrating agent reads these as constraints to apply, not content to transform.

- **Working Artifact (Layer 4)**: Per-run output files written to a stage's `output/` folder. Produced by the current execution run (by AI or Human) and consumed by downstream stages. Changes with every run. The output file from stage `N` becomes the Layer 4 input for stage `N+1` (or any stage that declares it in its Inputs).

- **Orchestrating Agent**: A single AI agent that reads the workspace's ICM structure, determines which stage to execute next, loads only the files specified in that stage's Inputs, performs the Process, and writes output to `output/`. The agent does not hold state between stages — all state lives in the workspace files. The same agent handles both planning (decomposing projects into stages) and execution (running AI stages), reading different context files at each phase.

- **Notification**: An alert sent to the user when a human review gate is reached, when a reminder is needed for an overdue human stage, or when an AI stage fails. Contains stage reference, urgency level, and a direct link to the stage in the platform UI.

- **Execution Log**: An append-only record of all events within a workflow run: stage start/end times, files loaded (Inputs), files written (Outputs), errors encountered, and user actions taken. Stored as `run-log.md` at the workspace root (not inside `_config/`, since `_config/` is for stable references only) so it is inspectable outside the platform.

- **Run Snapshot**: A timestamped archive of a previous workflow run's `output/` files, stored in `_runs/run-YYYY-MM-DDTHH-MM/`. Contains copies of all stage outputs from that run, enabling comparison, rollback, and history browsing. The `_runs/` folder grows over time as the user iterates on the project.

- **Conversation Thread**: A per-stage markdown file (`stages/NN_name/conversation.md`) containing the history of user-AI dialogue about that specific stage. The AI reads stage context when responding. Conversations are persisted as plain text and browsable outside the platform.

- **Project Template**: A workspace folder structure with pre-defined stages, reference files, and conventions, but without any `output/`, run history, or conversation files. Used as a starting point for new projects. Can be built-in or user-created.

- **Project Index**: A lightweight local file (`~/.hacp/projects.json`) that maps project names to workspace folder paths. Used by the Project Library to discover and display projects. Not part of the workspace itself — enables the platform to list all projects without scanning the entire disk.

- **Activity Event**: A single entry in the Activity Feed: what happened, when, which stage, by whom (AI or Human). Examples: "AI completed stage 01_research", "User submitted output for stage 03_review", "User edited CONTEXT.md for stage 02". Events are derived from the execution log.

- **Platform Settings**: A local configuration store (`~/.hacp/settings.json` + OS keychain for secrets) containing platform-wide preferences: LLM provider configurations (provider type, API key reference, base URL, default model, parameters), UI preferences (theme, font size), workspace defaults (root directory, naming conventions), and notification preferences. Settings apply globally unless overridden at the project level via `_config/llm.json`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can submit a project description and receive a structured, reviewable stage plan with human/AI classification in under 60 seconds.
- **SC-002**: A workflow with 5 consecutive AI stages completes end-to-end without any user intervention, with all outputs captured correctly in each stage's `output/` folder.
- **SC-003**: When a workflow reaches a human stage, the user receives a notification within 5 seconds of the preceding stage completing.
- **SC-004**: After a user submits their output for a human stage, the workflow resumes and the next stage begins within 10 seconds.
- **SC-005**: 90% of first-time users can successfully create a project, review a generated stage plan, trigger execution, and complete a human review gate without external guidance.
- **SC-006**: The workflow visualization accurately reflects real-time stage status — updates are visible within 3 seconds of a status change.
- **SC-007**: The platform correctly preserves and threads stage outputs as inputs to downstream stages with 100% fidelity (no data loss or corruption).
- **SC-008**: The dashboard provides a complete, accurate view of all workflow states and human-pending stages without requiring a page refresh.
- **SC-009**: Workflows that are paused (either by the user or due to a human stage) can be resumed and completed successfully from the point of interruption.
- **SC-010**: The platform supports at least 10 concurrent active workflows without degradation in response time for human stage notifications.
- **SC-011**: Completed stage output appears on the node in the workflow canvas within 2 seconds of stage completion, without requiring the user to navigate away or refresh.
- **SC-012**: A project closed and reopened 24 hours later restores the exact state — including all stage outputs, run history, and conversation threads — from the workspace folder alone.
- **SC-013**: A re-run from stage N correctly archives all outputs from stage N onward, re-executes stages, and produces new outputs — while the previous run remains accessible in the Run History.
- **SC-014**: AI conversation responses stream to the user within 500ms of the first token being generated by the LLM, providing immediate interactive feedback.
- **SC-015**: A user creating a project from a template can begin customizing and running the workflow within 30 seconds of selecting the template.
- **SC-016**: The platform UI is fully functional and visually coherent on screens from 1280px to ultrawide, in both light and dark modes.
- **SC-017**: A first-time user can configure an LLM provider, test the connection, and have the platform ready for AI stage execution within 2 minutes of first launch.
- **SC-018**: If the browser crashes while a user is editing at a human review gate, the auto-saved draft is recovered within 1 second of returning to the stage — with no more than 30 seconds of work lost.
- **SC-019**: Project-wide search returns results across all stage outputs and reference files within 2 seconds for workspaces under 100MB.
- **SC-020**: All destructive actions (delete project, restore run, clear outputs) display a confirmation dialog before executing — zero accidental data loss.

---

## Assumptions

- The platform is initially for a single user (multi-user real-time collaboration is future scope; sharing is via folder/template export).
- The orchestrating agent is a single AI instance reading ICM stage contracts for both planning (decomposition) and execution (running AI stages), not a multi-agent framework. The folder structure provides all context \u2014 no separate orchestration code.
- All stage outputs are plain text (markdown or JSON). Binary output (images, PDFs) is future scope.
- Human stage outputs submitted via the platform UI are written as plain text to the stage's `output/` folder, identical to AI-produced outputs — downstream stages cannot distinguish the source.
- AI stages do not have access to external APIs or the internet unless explicitly declared in the stage's `CONTEXT.md` Inputs section.
- Parallel stages (same folder number prefix or declared as parallel in Layer 1 `CONTEXT.md`) run sequentially in v1; true concurrent execution is future scope.
- The workspace folder must remain on a local or network-mounted path accessible to the platform process; cloud storage sync folders (e.g., Dropbox, iCloud Drive) are supported if they appear as normal filesystem paths.
- Notification delivery is in-platform (push to browser/app); email/SMS notifications are future scope.
- The platform runs as a local web application (localhost) with a Python/Node backend and a React frontend. No cloud deployment required for v1.
- AI conversation threads are bounded per stage (not a general chatbot). Context is scoped to the specific stage's files for focus and relevance.
- API keys are stored in the OS keychain or equivalent secure storage — never in plain text config files. The settings JSON file stores only non-sensitive configuration.
- The platform supports OpenAI-compatible API endpoints, enabling self-hosted models (Ollama, vLLM, LM Studio) alongside commercial providers.
- The project index file (`~/.hacp/projects.json`) is a convenience index only. The workspace folder remains the single source of truth — if the index is deleted, projects can be re-imported by pointing the platform to their folders.

---

## Out of Scope (v1)

- Multi-user real-time collaboration (concurrent editing by multiple users on the same project)
- Role-based access control and task routing to specific team members
- True concurrent parallel stage execution (stages run sequentially in v1)
- Binary or non-text stage outputs (images, PDFs, audio, spreadsheets)
- Custom AI agent plugins or marketplace (orchestrating agent is the platform's built-in agent)
- Integration with external project management tools (Jira, Asana, Rally, Linear)
- AI agent performance metrics and cost tracking per workflow run
- Mobile-native applications
- Cloud-hosted workspaces or cloud sync (workspace must be a local folder in v1)
- Automated source-level improvement based on recurring output edits (ICM "source integrity" — future direction per the paper)
- Semantic debugging / output provenance tracing (ICM future direction)
- OAuth / SSO authentication (local-only in v1)

---

## Clarifications

### Session 2026-05-17

- Q: If the backend crashes while an AI stage is executing (empty `output/`, stage last known "In Progress"), how should the platform recover on next startup? → A: Infer from filesystem — auto-mark the stage as `Failed` with reason "Interrupted — no output found"; no extra state file required. Encoded in FR-111.
- Q: When a stage conversation context exceeds the LLM context window, what should the platform do? → A: Sliding window — drop oldest messages to fit, always preserving stage contract + outputs; warn user when truncation occurs. Encoded in FR-112.
- Q: When the user edits a stage's `CONTEXT.md` in the platform UI while that stage is In Progress, what should happen? → A: Block the edit — show "Stage is running — editing locked"; unlock automatically when stage completes, fails, or is paused. Encoded in FR-030 (updated).
- Q: When an AI stage produces a very large output file (>1MB), what should the platform do? → A: Soft limit — write the file, display a warning in Activity Feed and stage detail panel noting the size and potential downstream context risk; workflow continues. Encoded in FR-113.
- Q: When the user triggers a re-run while the workflow is already executing (status: Running), what should happen? → A: Block — disable the re-run action while Running; show tooltip "Pause or wait for completion first"; re-run becomes available once Paused, Completed, or Failed. Encoded in FR-053 (updated).
