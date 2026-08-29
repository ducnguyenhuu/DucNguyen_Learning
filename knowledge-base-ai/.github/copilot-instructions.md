# Knowledge Base AI Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-02

## Active Technologies

- **Backend**: Python 3.11+ with FastAPI 0.110+
- **Frontend**: TypeScript + React 18 with Vite
- **Embedding**: nomic-embed-text-v1.5 via sentence-transformers
- **LLM**: Phi-3.5-mini-Instruct (Q4_K_M) via Ollama
- **Vector Database**: ChromaDB 0.5+
- **SQL Database**: SQLite via SQLAlchemy 2.0+ (PostgreSQL for server deployment)
- **Document Parsing**: python-docx, PyMuPDF, markdown, openpyxl
- **Logging**: structlog (JSON format)
- **Testing**: pytest, React Testing Library, Vitest

## Project Structure

```text
knowledge-base-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic Settings
│   │   ├── api/routes/          # REST + WebSocket endpoints
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── services/            # Business logic
│   │   ├── providers/           # Abstraction layer (embedding + LLM)
│   │   ├── parsers/             # Document format extractors
│   │   ├── db/                  # Database + vector store clients
│   │   └── core/                # Logging, exceptions
│   ├── alembic/                 # DB migrations
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/               # Route-level components
│   │   ├── components/          # Reusable UI components
│   │   ├── services/            # API client + WebSocket
│   │   └── hooks/               # Custom React hooks
│   └── public/
├── data/                        # Runtime data (gitignored)
├── specs/                       # Feature specifications
├── docker-compose.yml
└── README.md
```

## Commands

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pytest tests/ -v --cov=app
```

### Frontend
```bash
cd frontend
npm install
npm run dev       # Development
npm run build     # Production
npm test          # Tests
```

### Ollama Models
```bash
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
ollama pull nomic-embed-text
```

### Docker
```bash
docker-compose up --build -d
```

## Constitution Reference

See `.specify/memory/constitution.md` (v1.1.0) for governing principles:

1. **Production-Grade Architecture** — Clean layer separation, explicit errors, externalized config
2. **REST API Contract Boundary** — All frontend↔backend via `/api/v1/`; contracts documented first
3. **Provider Abstraction** — Embedding + LLM behind ABC interfaces; switch via config only
4. **Structured Observability** — JSON logs via structlog; `request_id` on every request
5. **Lightweight & User-Friendly UI** — Pages interactive <2s; feedback on all long-running ops
6. **Incremental Delivery** — Each user story independently testable and deployable
7. **Test-After-Implementation Mandate** — Unit tests MUST be written immediately after each implementation task; a task is NOT done until its tests pass

## Quality Gates

```bash
# Python — MUST pass before merge
mypy app/ --strict        # Type checking
ruff check app/            # Linting
pytest tests/ -v --cov=app # Tests (coverage MUST NOT decrease)

# TypeScript — MUST pass before merge
npx tsc --noEmit           # Type checking
npx eslint src/            # Linting
npm test                   # Tests
```

## Test-After-Implementation Rule (Constitution §VII)

> **NON-NEGOTIABLE**: After completing any implementation task (parser, service, provider, API route,
> frontend component), write and run its unit tests **before** moving to the next task.
> A task is considered incomplete until `pytest` (or `npm test`) reports all related tests passing.
> Coverage MUST NOT decrease. Integration tests for multi-component pipelines may follow after
> all pipeline components exist, but unit tests are never deferred.

## Code Style

### Python (Backend)
- Use type hints everywhere
- Async/await for I/O operations
- Pydantic models for request/response validation
- ABC classes in `providers/base.py` for model abstraction
- structlog for consistent JSON logging with context fields
- Every request MUST propagate a `request_id` through all log entries
- SQLAlchemy 2.0 style (mapped classes)
- Log levels: INFO (normal), WARNING (recoverable), ERROR (failures)

### TypeScript (Frontend)
- Functional components with hooks
- TypeScript strict mode
- Custom hooks for API state management
- WebSocket hooks for real-time features
- React Error Boundaries on all route-level components
- Display `request_id` in error messages for traceability

## Recent Changes

### 001-local-knowledge-base (2026-03-04)
- Initial feature: Document ingestion pipeline, RAG chatbot, conversation history
- Added: Provider abstraction for embedding + LLM models
- Added: On-demand document summarization
- Added: Localhost-only binding by default (FR-020), auto re-embedding on model change (FR-021)
- Added: Single ingestion job enforcement (FR-022), path validation with symlink resolution (FR-023)
- Added: Crash-recovery resume-safe ingestion (FR-005)
- Added: Conversation delete/clear-all with confirmation (FR-024)
- Added: Excel (.xlsx) document parsing support
- Added: Constitution §VII Test-After-Implementation Mandate (v1.1.0)
- Tech stack: Python/FastAPI + React/TypeScript + ChromaDB + SQLite + Ollama

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
