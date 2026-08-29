<!-- Sync Impact Report
Version change: 1.0.0 → 1.1.0 (MINOR — new principle VII added)
Modified principles: None renamed or removed
Added sections:
  - Core Principles §VII: Test-After-Implementation Mandate (new)
  - Additional Constraints §Testing: strengthened language from "MUST cover" to "MUST be written immediately after"
Removed sections: None
Templates requiring updates:
  - .specify/templates/tasks-template.md ✅ updated (tests mandatory, not optional)
  - .specify/templates/plan-template.md ✅ aligned (no changes needed)
  - .specify/templates/spec-template.md ✅ aligned (no changes needed)
  - .github/copilot-instructions.md ✅ updated (test-after-implementation rule added)
  - specs/001-local-knowledge-base/tasks.md ✅ updated (Phase 9 GUIDELINE → MANDATORY)
Follow-up TODOs: None
-->

# Knowledge Base AI Constitution

## Core Principles

### I. Production-Grade Architecture

All features MUST be designed and implemented to production
standards from day one. This means:

- Clean separation of concerns across well-defined layers
  (parsers, services, providers, API routes, UI components)
- Every module MUST have a single, clear responsibility
- No prototype-quality code in main branches; all merges
  MUST pass linting, type checking, and tests
- Error handling MUST be explicit — no silent failures;
  every error MUST be logged with context and surfaced
  appropriately to the caller
- Configuration MUST be externalized via environment
  variables with sensible defaults

**Rationale**: The application is designed for local use now
with a clear path to server deployment. Cutting corners on
architecture creates compounding technical debt that blocks
the deployment transition.

### II. REST API Contract Boundary

The backend MUST communicate with the frontend exclusively
through a versioned REST API (and WebSocket for real-time
features). This means:

- All backend functionality MUST be exposed through
  `/api/v1/` endpoints — no direct database access or
  shared state between frontend and backend
- API contracts MUST be documented before implementation
  and treated as the source of truth
- Breaking API changes MUST increment the API version
- Request/response schemas MUST be validated using Pydantic
  models on the backend and TypeScript interfaces on the
  frontend
- WebSocket channels are permitted only for real-time
  features (ingestion progress, LLM streaming)

**Rationale**: A strict API boundary enables independent
development, testing, and deployment of frontend and backend.
It also ensures the backend can serve other clients (CLI,
mobile) in the future without modification.

### III. Provider Abstraction (NON-NEGOTIABLE)

All external model integrations (embedding and LLM) MUST be
abstracted behind provider interfaces. This means:

- An abstract base class MUST define the contract for each
  provider type (`EmbeddingProvider`, `LLMProvider`)
- Concrete implementations (local distilled, OpenAI, Claude)
  MUST implement the abstract interface without leaking
  implementation details
- Switching providers MUST require only a configuration
  change — zero modifications to services, routes, or
  business logic
- A factory pattern MUST resolve the correct provider
  instance from configuration at startup

**Rationale**: The project explicitly plans to migrate from
cost-efficient local distilled models to commercial APIs.
This principle ensures that migration is a configuration
change, not a refactoring effort.

### IV. Structured Observability

All application behavior MUST be observable through
structured logging. This means:

- All log entries MUST be structured JSON via `structlog`
- Every request MUST carry a correlation `request_id`
  propagated through all downstream log entries
- Log entries MUST include contextual fields: `job_id`,
  `document_id`, `conversation_id`, `file_name`,
  `duration_ms` as applicable
- Log levels MUST be used consistently: INFO for normal
  operations, WARNING for recoverable issues (skipped
  files, low disk), ERROR for failures requiring attention
- Logs MUST be written to stdout (for Docker/server) and
  optionally to rotating files (for local development)

**Rationale**: Troubleshooting a RAG pipeline (parse → chunk
→ embed → store → retrieve → generate) requires tracing a
request across multiple services. Structured logging with
correlation IDs is the minimum viable observability for
production diagnosis.

### V. Lightweight & User-Friendly UI

The frontend MUST prioritize usability, speed, and clarity
over visual complexity. This means:

- Pages MUST load and become interactive within 2 seconds
  on a standard consumer machine
- The UI MUST be responsive across desktop, tablet, and
  mobile breakpoints
- Navigation MUST be intuitive — a new user MUST be able
  to ingest documents and ask their first question without
  reading documentation
- Visual feedback MUST be provided for all long-running
  operations (progress bars, spinners, streaming tokens)
- The design MUST use a clean, minimal aesthetic — no
  unnecessary decorative elements or heavy component
  libraries

**Rationale**: The target user is a knowledge worker running
the app locally. They need fast, distraction-free access to
their documents and answers, not a feature-heavy dashboard.

### VI. Incremental Delivery

Every feature MUST be deliverable as independently testable
user story slices. This means:

- Each user story in the spec MUST be implementable,
  testable, and demonstrable without depending on
  unfinished stories
- The task list MUST be organized by user story, not by
  technical layer
- A working MVP MUST be achievable by completing only the
  P1 user story (document ingestion)
- Integration between stories MUST be additive — completing
  story N MUST NOT break stories 1 through N-1

**Rationale**: A single developer working locally benefits
most from seeing working software early and often. Incremental
delivery reduces risk and provides continuous validation that
the architecture works end-to-end.

### VII. Test-After-Implementation Mandate (NON-NEGOTIABLE)

Unit tests MUST be written immediately after each functional
component is completed — NOT deferred to a testing phase at
the end of the project. This means:

- Every implementation task that produces a new module,
  service, parser, or provider MUST be followed immediately
  by a corresponding unit test task before moving to the
  next implementation task
- Tests MUST cover: happy paths, error/exception paths,
  and all edge cases described in the spec
- A functional task is NOT considered complete until its
  unit tests exist, run, and pass
- Deferred test phases (e.g., "Phase 9: Testing") are
  permitted ONLY for integration tests that require multiple
  components to exist simultaneously — never for unit tests
- The task list MUST pair each implementation task with its
  test task in the same phase/batch, e.g.:
  - T031 Implement PDF parser → T075 PDF parser unit tests
  - T034 Implement chunker → T076 Chunker unit tests
- Test coverage MUST NOT decrease with any merge

**Rationale**: Deferred testing creates a false sense of
progress, allows subtle contract bugs to compound across
components, and produces a large, demoralizing test-writing
burst at the end of the project. Writing tests immediately
after each function validates the contract while the
implementation context is fresh, catches regressions
early, and ensures the test suite grows alongside the
codebase rather than trailing behind it.

## Additional Constraints

### Technology Stack

- **Backend**: Python 3.11+ with FastAPI — async-first,
  type-hinted, Pydantic-validated
- **Frontend**: TypeScript strict mode + React 18 with Vite
- **Database**: SQLAlchemy ORM with SQLite (local) /
  PostgreSQL (server) — switching MUST require only a
  connection string change
- **Vector Store**: ChromaDB in embedded mode
- **Models**: Ollama for LLM inference; sentence-transformers
  for embedding (with Ollama as fallback)
- **Logging**: structlog with JSON output

### Deployment

- Local development MUST work with `uvicorn --reload` (backend)
  and `npm run dev` (frontend) with no additional infrastructure
- Server deployment MUST be achievable via `docker-compose up`
  with PostgreSQL and Nginx
- All runtime data (SQLite DB, ChromaDB, model cache) MUST
  reside under a single `data/` directory that is gitignored

### Testing

- Backend: pytest with coverage reporting (`--cov=app`)
- Frontend: Vitest + React Testing Library
- Unit tests MUST be written immediately after each
  implementation task completes (see Principle VII)
- Unit tests MUST cover parsers, chunker, providers, and
  services independently
- Integration tests MUST verify the full RAG pipeline
  (ingest → query → answer)
- Test coverage MUST NOT decrease; any PR that reduces
  coverage MUST be rejected at the quality gate

## Development Workflow

### Code Review & Quality Gates

1. All code MUST pass type checking (`mypy` for Python,
   `tsc --noEmit` for TypeScript) before merge
2. All code MUST pass linting (`ruff` for Python, `eslint`
   for TypeScript)
3. Test coverage MUST NOT decrease with new changes
4. API contract changes MUST be reflected in
   `contracts/api-contracts.md` before implementation

### Branching & Commits

- Feature branches follow the format `###-feature-name`
- Commits MUST be atomic and descriptive
- Each completed user story SHOULD be a merge-ready
  increment

### Specification Workflow

1. `/speckit.specify` → Feature specification (user stories,
   requirements, success criteria)
2. `/speckit.clarify` → Resolve ambiguities (up to 5
   targeted questions)
3. `/speckit.plan` → Implementation plan (research, data
   model, contracts, quickstart)
4. `/speckit.tasks` → Task breakdown by user story
5. `/speckit.implement` → Execute tasks

## Governance

This constitution supersedes all other development practices
for the Knowledge Base AI project. Amendments follow this
process:

1. **Proposal**: Document the change with rationale
2. **Impact Assessment**: Identify affected principles,
   templates, and existing code
3. **Versioning**: Apply semantic versioning — MAJOR for
   principle removals/redefinitions, MINOR for additions/
   expansions, PATCH for clarifications/typos
4. **Propagation**: Update all dependent templates and
   agent context files to reflect the change
5. **Compliance Review**: All active pull requests MUST be
   re-validated against updated principles

Complexity beyond what is prescribed MUST be justified in
the plan's Complexity Tracking table with a clear rationale
and an explanation of why the simpler alternative was
rejected.

Use `.github/copilot-instructions.md` for runtime
development guidance.

**Version**: 1.1.0 | **Ratified**: 2026-03-02 | **Last Amended**: 2026-03-04
