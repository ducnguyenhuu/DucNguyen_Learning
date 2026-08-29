# Tasks: Local Knowledge Base Application

**Input**: Design documents from `/specs/001-local-knowledge-base/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Included as dedicated tasks per constitution mandate — unit tests for parsers, chunker, providers, and services; integration tests for full RAG pipeline. Quality Gates QG-001 through QG-003 apply.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Exact file paths included in every task description

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create project skeleton, install dependencies, configure tooling

- [X] T001 Create full project directory structure per plan.md — `backend/app/{api/routes,models,services,providers,parsers,db,core}`, `backend/tests/{unit,integration}`, `frontend/src/{pages,components/{chat,documents,common},services,hooks}`, `data/`
- [X] T002 Initialize Python backend — create `backend/requirements.txt` (fastapi, uvicorn, sqlalchemy, alembic, chromadb, sentence-transformers, structlog, python-docx, PyMuPDF, markdown, pydantic-settings, httpx), `backend/.env.example`, `backend/alembic.ini`
- [X] T003 [P] Initialize React+TypeScript frontend with Vite — run scaffolding, configure `frontend/package.json` (react, react-router-dom, axios), `frontend/tsconfig.json` (strict mode), `frontend/vite.config.ts` (proxy /api → localhost:8000)
- [X] T004 [P] Implement Pydantic Settings configuration in `backend/app/config.py` — all env vars from quickstart.md §6 (HOST, PORT, KNOWLEDGE_FOLDER, EMBEDDING_*, LLM_*, RETRIEVAL_*, CHUNK_*, SLIDING_WINDOW_MESSAGES, DATABASE_URL, CHROMA_*, LOG_LEVEL)
- [X] T005 [P] Configure structured JSON logging via structlog in `backend/app/core/logging.py` — JSON format, request_id binding, context fields (job_id, document_id, conversation_id, file_name, duration_ms), stdout + rotating file output (FR-015)
- [X] T006 [P] Create domain exception hierarchy in `backend/app/core/exceptions.py` — base `AppError`, plus `DocumentNotFoundError`, `ConversationNotFoundError`, `IngestionConflictError`, `ValidationError`, `ModelUnavailableError`, `PathValidationError`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Set up SQLAlchemy 2.0 async engine and session factory in `backend/app/db/database.py` — connection from config DATABASE_URL, session context manager, Base declarative model
- [X] T008 [P] Set up ChromaDB persistent client and collection manager in `backend/app/db/vector_store.py` — `knowledge_base` collection, cosine distance, CRUD wrappers (add, delete by document_id, query with top-K + threshold), persist dir from config
- [X] T009 [P] Create Document ORM model in `backend/app/models/document.py` — all fields per data-model.md §1.1 (id, file_path, file_name, file_type, file_hash, file_size_bytes, chunk_count, status, error_message, ingested_at, created_at, updated_at), indexes, state transitions
- [X] T010 [P] Create Conversation ORM model in `backend/app/models/conversation.py` — all fields per data-model.md §1.2 (id, title, preview, message_count, created_at, updated_at), indexes
- [X] T011 [P] Create Message ORM model in `backend/app/models/message.py` — all fields per data-model.md §1.3 (id, conversation_id FK, role, content, source_references JSON, token_count, created_at), composite index, CASCADE DELETE relationship
- [X] T012 [P] Create DocumentSummary ORM model in `backend/app/models/document_summary.py` — all fields per data-model.md §1.4 (id, document_id FK UNIQUE, summary_text, section_references JSON, model_version, created_at), CASCADE DELETE relationship
- [X] T013 [P] Create IngestionJob ORM model in `backend/app/models/ingestion_job.py` — all fields per data-model.md §1.5 (id, source_folder, trigger_reason, total_files, processed_files, new_files, modified_files, deleted_files, skipped_files, status, error_message, started_at, completed_at), indexes, state transitions
- [X] T014 Initialize Alembic and generate initial migration for all 5 SQL tables in `backend/alembic/`
- [X] T015 [P] Create EmbeddingProvider and LLMProvider ABC interfaces in `backend/app/providers/base.py` — EmbeddingProvider: `embed(text)→vector`, `embed_batch(texts)→list`; LLMProvider: `generate(prompt, context)→str`, `stream(prompt, context)→AsyncIterator[str]`
- [X] T016 [P] Implement LocalEmbeddingProvider using sentence-transformers in `backend/app/providers/local_embedding.py` — load nomic-embed-text-v1.5, 768 dimensions, batch embedding support
- [X] T017 [P] Implement LocalLLMProvider using Ollama HTTP API in `backend/app/providers/local_llm.py` — async HTTP client to Ollama at LLM_BASE_URL, generate + stream methods, configurable temperature and context_window
- [X] T018 Implement provider factory (config → provider instance) in `backend/app/providers/factory.py` — read EMBEDDING_PROVIDER and LLM_PROVIDER from config, instantiate correct class, raise clear error for unknown provider
- [X] T019 Implement model manager in `backend/app/services/model_manager.py` — on first run, auto-download required models if not present (trigger `ollama pull` for LLM, sentence-transformers auto-download for embedding; FR-014), health check (verify Ollama connectivity + model availability), model version comparison (read model_version from ChromaDB metadata vs configured EMBEDDING_MODEL), warm-up calls
- [X] T020 Create FastAPI application entry point in `backend/app/main.py` — CORS middleware (allow frontend origin), lifespan (startup: init DB, init ChromaDB, warm models; shutdown: cleanup), request_id middleware (read/generate X-Request-ID, bind to structlog context), HOST from config (FR-020), include all route routers under `/api/v1`
- [X] T021 [P] Create dependency injection utilities in `backend/app/api/deps.py` — get_db_session, get_vector_store, get_embedding_provider, get_llm_provider, get_ingestion_service, get_chat_service, get_summary_service
- [X] T022 [P] Implement system routes in `backend/app/api/routes/system.py` — GET /health (component status + reembedding field per api-contracts.md §5.1), GET /config (non-sensitive settings per api-contracts.md §5.2)
- [X] T023 [P] Implement common error response handler as FastAPI exception handlers in `backend/app/main.py` — catch AppError subclasses, format per api-contracts.md §6 ({error: {code, message, request_id, details}}), map to correct HTTP status codes (400/404/409/500/503)
- [X] T024 [P] Create frontend App shell with React Router in `frontend/src/App.tsx` and `frontend/src/main.tsx` — routes for /, /chat, /chat/:conversationId, /documents, /documents/:documentId, /settings per frontend-contract.md §1
- [X] T025 [P] Create Layout component (sidebar nav + content area), Navbar, and LoadingSpinner in `frontend/src/components/common/Layout.tsx`, `frontend/src/components/common/Navbar.tsx`, `frontend/src/components/common/LoadingSpinner.tsx`
- [X] T026 [P] Create API client with Axios, base URL `/api/v1`, automatic X-Request-ID header generation in `frontend/src/services/api.ts`
- [X] T027 [P] Create WebSocket manager (connect, disconnect, auto-reconnect with exponential backoff, message handlers) in `frontend/src/services/websocket.ts`
- [X] T028 [P] Create TypeScript type definitions matching all API request/response contracts in `frontend/src/services/types.ts` — Document, Conversation, Message, IngestionJob, HealthResponse, ConfigResponse, ErrorResponse, all WS message types
- [X] T029 [P] Create Settings page (display current config from GET /config) in `frontend/src/pages/Settings.tsx`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Document Ingestion & Indexing (Priority: P1) 🎯 MVP

**Goal**: Point the app at a folder of Word/MD/PDF documents → automatically parse, chunk, embed, and store in vector DB with real-time progress

**Independent Test**: Trigger ingestion on a folder with mixed-format files. Verify all documents are parsed, chunked, embedded, stored in ChromaDB, and listed in the UI with correct counts. Verify incremental re-ingestion handles new/modified/deleted files. Verify progress updates appear in real time.

### Implementation for User Story 1

- [X] T030 [P] [US1] Create DocumentParser ABC in `backend/app/parsers/base.py` — abstract `parse(file_path)→ParsedDocument` returning text content + page/section metadata
- [X] T031 [P] [US1] Implement PDF parser using PyMuPDF in `backend/app/parsers/pdf_parser.py` — extract text per page, preserve page numbers, handle corrupted/unreadable files gracefully (skip file, log error with filename, continue — per Edge Case §corrupted)
- [X] T032 [P] [US1] Implement DOCX parser using python-docx in `backend/app/parsers/docx_parser.py` — extract paragraphs with section headings, handle corrupted files gracefully. For very large documents (500+ pages), use iterative paragraph extraction to manage memory (Edge Case §large-document)
- [X] T033 [P] [US1] Implement Markdown parser in `backend/app/parsers/markdown_parser.py` — extract text preserving heading structure, handle malformed markdown gracefully
- [X] T033b [P] [US1] Implement Excel parser using openpyxl in `backend/app/parsers/excel_parser.py` — iterate sheets, use sheet names as section headings (level 1), convert rows to readable `key: value` or tab-separated text, handle password-protected workbooks and corrupted files gracefully. Support `.xlsx` only; skip `.xls` with a WARNING log directing user to convert to .xlsx.
- [X] T034 [US1] Implement text chunker in `backend/app/parsers/chunker.py` — configurable CHUNK_SIZE and CHUNK_OVERLAP from config, preserve paragraph and section boundaries (FR-002); when the next boundary would produce a chunk larger than CHUNK_SIZE × 1.5, force-split at CHUNK_SIZE with overlap. Return list of chunks with position metadata
- [X] T035 [US1] Implement embedding service in `backend/app/services/embedding.py` — delegates to EmbeddingProvider via DI, embed single text and batch embed, tag each vector with model_version metadata (FR-021)
- [X] T036 [US1] Implement ingestion service in `backend/app/services/ingestion.py` — full pipeline: pre-flight disk space check (warn and return 400 if below configurable threshold, Edge Case §disk-space), validate source_folder path (exists, is_dir, resolve symlinks via `os.path.realpath()`, FR-023), enforce single active job (FR-022, check IngestionJob status=running → raise 409), scan folder recursively, skip files not matching `.pdf`/`.docx`/`.md` extensions with WARNING log (FR-016), compute SHA-256 file hashes, detect new/modified/deleted files (FR-005), create IngestionJob record, for each file: update Document status pending→processing→completed/failed, parse → chunk → embed → store in ChromaDB, remove deleted Document + ChromaDB chunks, resume-safe on crash (skip completed, re-process processing/pending, FR-005), emit progress events via callback, log all operations with structured fields
- [X] T037 [US1] Implement ingestion REST routes in `backend/app/api/routes/ingestion.py` — POST /ingestion/start (202 Accepted, request body per api-contracts.md §1.1, errors 400/409), GET /ingestion/status/{job_id} (200 with full status per §1.2, error 404)
- [X] T038 [US1] Implement ingestion WebSocket in `backend/app/api/routes/ingestion.py` — WS /ingestion/progress/{job_id} (send progress, file_complete, file_error, completed messages per api-contracts.md §1.3)
- [X] T039 [P] [US1] Implement document REST routes in `backend/app/api/routes/documents.py` — GET /documents (paginated list with status filter per §1.4), GET /documents/{id} (detail with has_summary flag per §1.5, 404), DELETE /documents/{id} (remove doc + ChromaDB chunks per §1.6, 404)
- [X] T040 [P] [US1] Create DocumentTable component in `frontend/src/components/documents/DocumentTable.tsx` — sortable table (name, type, chunks, actions), click name → DocumentDetail, summary button per frontend-contract.md §2.2
- [X] T041 [P] [US1] Create IngestionProgress component in `frontend/src/components/documents/IngestionProgress.tsx` — progress bar (processed/total), current file name, estimated time remaining, inline file errors per frontend-contract.md §2.2
- [X] T042 [US1] Create useDocuments hook in `frontend/src/hooks/useDocuments.ts` — fetch document list (GET /documents), delete document, loading/error state
- [X] T043 [US1] Create useIngestion hook in `frontend/src/hooks/useIngestion.ts` — trigger ingestion (POST /ingestion/start), connect WS for progress, track job status, handle 409 conflict
- [X] T044 [US1] Create DocumentList page in `frontend/src/pages/DocumentList.tsx` — compose DocumentTable + IngestionProgress + "Run Ingest" button, wire hooks per frontend-contract.md §2.2

**Checkpoint**: User Story 1 fully functional — documents can be ingested, tracked, and listed. MVP deliverable.

---

## Phase 4: User Story 2 — Conversational Query via Web Chatbot (Priority: P2)

**Goal**: Open the chatbot, type a question, receive an LLM-generated answer grounded in ingested documents with source citations and streaming response

**Independent Test**: Ingest documents, open chatbot, ask a factual question. Verify the answer is grounded in document content, includes source references, and streams token-by-token. Ask an unrelated question and verify "no relevant information" response.

### Implementation for User Story 2

- [X] T045 [US2] Implement retrieval service in `backend/app/services/retrieval.py` — embed query via EmbeddingProvider, query ChromaDB with configurable top_k and similarity_threshold (FR-008), exclude chunks below threshold, return ranked results with document metadata and relevance scores
- [X] T046 [US2] Implement chat service (RAG orchestration) in `backend/app/services/chat.py` — receive user question + conversation_id, retrieve sliding window of recent N messages from DB (FR-011), call retrieval service for context chunks, build prompt (system instruction + context chunks + conversation history + user question), call LLMProvider.generate() or .stream(), include source_references from retrieval results (FR-010), persist user Message and assistant Message to DB, update Conversation (message_count, updated_at, title/preview if first message), handle "no relevant info" case when retrieval returns empty (FR-008)
- [X] T047 [US2] Implement conversation creation and message routes in `backend/app/api/routes/conversations.py` (POST /conversations per §2.1) and `backend/app/api/routes/chat.py` (POST /conversations/{id}/messages per §3.1, errors 404/503)
- [X] T048 [US2] Implement chat streaming WebSocket in `backend/app/api/routes/chat.py` — WS /conversations/{id}/stream (receive question → send user_message_saved → sources_found → token stream → complete, per api-contracts.md §3.2, handle errors)
- [X] T049 [P] [US2] Create MessageBubble component in `frontend/src/components/chat/MessageBubble.tsx` — render user/assistant roles differently, render assistant markdown content, show clickable source citation badges per frontend-contract.md §2.1
- [X] T050 [P] [US2] Create ChatInput component in `frontend/src/components/chat/ChatInput.tsx` — text input, Enter to send, Shift+Enter for newline, disabled state during streaming/loading
- [X] T051 [P] [US2] Create SourcePanel component in `frontend/src/components/chat/SourcePanel.tsx` — display document references (file_name, page_number, relevance_score) when citation clicked per frontend-contract.md §2.1
- [X] T052 [US2] Create useChat hook in `frontend/src/hooks/useChat.ts` — send message (REST or WS), handle token streaming, manage current conversation messages, loading/error state
- [X] T053 [US2] Create ChatView page in `frontend/src/pages/ChatView.tsx` — 3-column layout (placeholder sidebar, chat area with MessageBubble list + ChatInput, SourcePanel), wire useChat hook, auto-scroll to latest message per frontend-contract.md §2.1

**Checkpoint**: User Stories 1 AND 2 functional — full document ingestion and conversational Q&A pipeline works end-to-end.

---

## Phase 5: User Story 3 — Conversation History & Session Management (Priority: P3)

**Goal**: Persist conversation history across browser sessions; list, navigate, delete, and clear all conversations

**Independent Test**: Have a conversation, close the browser, reopen — verify conversation is listed and resumable. Delete a conversation — verify it's gone. Clear all — verify empty state and fresh LLM context.

### Implementation for User Story 3

- [X] T054 [US3] Extend conversation routes in `backend/app/api/routes/conversations.py` — add GET /conversations (paginated list per §2.2), GET /conversations/{id} (full message history per §2.3, 404), DELETE /conversations/{id} (cascade delete per §2.4, 404), DELETE /conversations?confirm=true (bulk clear per §2.5, FR-024, 400 if confirm missing)
- [X] T055 [US3] Create useConversations hook in `frontend/src/hooks/useConversations.ts` — fetch conversation list (GET /conversations), delete single conversation (DELETE /conversations/{id}), clear all with confirm (DELETE /conversations?confirm=true), loading/error state, auto-refresh after mutations
- [X] T056 [US3] Create ConversationSidebar component in `frontend/src/components/chat/ConversationSidebar.tsx` — scrollable list sorted by updated_at DESC, "New Chat" button, "Clear All" button with confirmation dialog (FR-024), individual delete via context menu/swipe, redirect to new empty chat after clearing active conversation per frontend-contract.md §2.1, wire useConversations hook
- [X] T057 [US3] Integrate ConversationSidebar into ChatView page in `frontend/src/pages/ChatView.tsx` — replace placeholder sidebar, wire conversation selection (navigate to /chat/:id), handle new chat creation, handle delete/clear redirects
- [X] T058 [US3] Create Dashboard page in `frontend/src/pages/Dashboard.tsx` — stats cards (document count from GET /documents, conversation count from GET /conversations, model health from GET /health), recent conversations list, quick action buttons (New Chat, Ingest Docs, Settings) per frontend-contract.md §2.3

**Checkpoint**: User Stories 1, 2, AND 3 functional — full conversation lifecycle with persistence, navigation, and cleanup.

---

## Phase 6: User Story 4 — On-Demand Document Summarization (Priority: P4)

**Goal**: Select an ingested document and generate a concise summary with section references using the local LLM

**Independent Test**: Ingest a multi-page document, navigate to it in the UI, request a summary. Verify summary captures key points, includes section references, and is cached for subsequent views.

### Implementation for User Story 4

- [X] T059 [US4] Implement summary service in `backend/app/services/summary.py` — retrieve all chunks for a document from ChromaDB ordered by chunk_index, iterative summarization (batch chunks → LLM summarize → combine, FR-017), extract section_references mapping key points to source sections/pages (FR-018), store/update DocumentSummary record, return cached summary if exists and document unchanged
- [X] T060 [US4] Implement summary routes in `backend/app/api/routes/summary.py` — POST /documents/{id}/summary (generate/regenerate per §4.1, errors 404/409/503), GET /documents/{id}/summary (cached per §4.2, error 404)
- [X] T061 [P] [US4] Create SummaryView component in `frontend/src/components/documents/SummaryView.tsx` — display summary text with section references, loading state during generation, "Regenerate" button
- [X] T062 [US4] Create DocumentDetail page in `frontend/src/pages/DocumentDetail.tsx` — document metadata (name, type, size, chunks, ingested_at), SummaryView component, "Generate Summary" / "View Summary" button based on has_summary flag

**Checkpoint**: User Stories 1 through 4 functional — complete document management with ingestion, Q&A, history, and summarization.

---

## Phase 7: User Story 5 — Model Provider Abstraction (Priority: P5)

**Goal**: Verify provider abstraction enables config-only switching between model backends without core logic changes

**Independent Test**: Configure the app to use a different provider key in .env. Verify the factory instantiates the correct adapter and the system operates identically (or raises a clear "not implemented" error for stubs).

### Implementation for User Story 5

- [X] T063 [P] [US5] Create OpenAI embedding adapter stub in `backend/app/providers/openai_embedding.py` — implement EmbeddingProvider ABC, raise `NotImplementedError("OpenAI adapter not yet configured — set OPENAI_API_KEY")` with clear setup instructions in each method
- [X] T064 [P] [US5] Create Claude LLM adapter stub in `backend/app/providers/claude_llm.py` — implement LLMProvider ABC, raise `NotImplementedError("Claude adapter not yet configured — set CLAUDE_API_KEY")` with clear setup instructions in each method
- [X] T065 [US5] Register stub adapters in provider factory in `backend/app/providers/factory.py` — add `openai` and `claude` to factory mappings, verify switching EMBEDDING_PROVIDER=openai or LLM_PROVIDER=claude in config instantiates the correct adapter class

**Checkpoint**: All 5 user stories functional. Provider abstraction verified — adding a real commercial adapter requires only implementing the ABC interface + one factory mapping.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Startup behaviors, deployment, documentation, and UI refinements

- [X] T066 Implement startup model version check and auto re-embed trigger in `backend/app/services/model_manager.py` — on app startup (lifespan), compare configured EMBEDDING_MODEL against model_version in existing ChromaDB vectors, if mismatch: create IngestionJob with trigger_reason='reembed', call ingestion service in background task, emit reembed_started WS message (FR-021), update /health reembedding field
- [X] T067 [P] Add re-embedding notification banner to frontend — detect reembedding.in_progress from GET /health polling, show persistent info banner "Re-embedding documents due to model update..." with progress link to ingestion page per frontend-contract.md §6
- [X] T068 [P] Create `Dockerfile.backend` (Python 3.11 slim, pip install, uvicorn + gunicorn) and `Dockerfile.frontend` (Node 18, npm build, nginx serve)
- [X] T069 [P] Create `docker-compose.yml` — services: backend (FastAPI), frontend (Nginx), ollama (GPU-optional); production profile adds PostgreSQL; shared volumes for chromadb data and model cache per quickstart.md §7
- [X] T070 [P] Create `README.md` — project overview, features, tech stack, setup instructions (reference quickstart.md), architecture diagram, development commands, Docker deployment
- [X] T071 Implement responsive layout across all pages — desktop ≥1024px (3-column), tablet 768-1023px (sidebar collapses to icons), mobile <768px (tab-based navigation) per frontend-contract.md §5
- [X] T072 Add React Error Boundaries on all route-level components in `frontend/src/App.tsx` — catch unhandled exceptions, render fallback UI with "Report Issue" option, log error with request_id context per frontend-contract.md §6
- [X] T073 Run quickstart.md end-to-end validation — follow setup steps from quickstart.md §1-4, verify backend starts on 127.0.0.1:8000, frontend on 5173, ingestion works, chat works, summary works, all quality gates pass (mypy, ruff, tsc, eslint). Validate SC-001 through SC-009 with a benchmark corpus of 10 documents containing known facts + 10 out-of-scope queries to verify answer accuracy (SC-003), rejection accuracy (SC-004), and performance targets (SC-001, SC-002, SC-009)

---

## Phase 9: Testing (Constitution Mandate)

**Purpose**: Unit and integration tests per constitution §Testing mandate — "Unit tests MUST cover parsers, chunker, providers, and services independently" and "Integration tests MUST verify the full RAG pipeline"

**⚠️ MANDATORY (Constitution §VII)**: Unit tests MUST be written immediately after each implementation task completes — NOT deferred. A task is NOT done until its unit tests pass. Integration tests (T079–T081) alone may be deferred until all pipeline components exist, but unit tests for every module are non-negotiable.

- [X] T074 [P] Create test configuration and fixtures in `backend/tests/conftest.py` — in-memory SQLite test DB, mock ChromaDB collection, mock EmbeddingProvider and LLMProvider, sample document fixtures (PDF, DOCX, MD), temp directory with test files
- [X] T075 [P] Write parser unit tests in `backend/tests/unit/test_parsers.py` — test PDF extraction (multi-page, corrupted), DOCX extraction (headings, empty), MD extraction (headings, malformed), Excel extraction (multi-sheet, empty sheet, password-protected), verify ParsedDocument output structure
- [X] T076 [P] Write chunker unit tests in `backend/tests/unit/test_chunker.py` — test chunk size/overlap config, boundary preservation, force-split at 1.5× threshold, empty input, single-paragraph input, position metadata
- [x] T077 [P] Write provider unit tests in `backend/tests/unit/test_providers.py` — test LocalEmbeddingProvider embed/embed_batch (mock model), LocalLLMProvider generate/stream (mock Ollama HTTP), factory instantiation for all registered providers, unknown provider error
- [x] T078 [P] Write service unit tests in `backend/tests/unit/test_services.py` — test ingestion service (new/modified/deleted detection, crash recovery, single-job enforcement, path validation, unsupported file skip), chat service (RAG prompt construction, sliding window, no-results handling), retrieval service (threshold filtering), summary service (iterative summarization, caching), embedding service (model_version tagging)
- [x] T079 Write ingestion integration test in `backend/tests/integration/test_ingestion.py` — end-to-end: create temp folder with sample files → call ingestion service → verify Documents in DB + chunks in ChromaDB → add/modify/delete files → re-ingest → verify incremental behavior
- [x] T080 Write chat integration test in `backend/tests/integration/test_chat.py` — end-to-end RAG pipeline: ingest sample docs → create conversation → send question → verify answer contains source references → verify conversation + messages persisted in DB
- [x] T081 Write API integration tests in `backend/tests/integration/test_api.py` — test all REST endpoints via FastAPI TestClient: ingestion start/status, document CRUD, conversation CRUD + bulk delete, chat message, summary generate/get, health, config; verify error response format matches api-contracts.md §6

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──────────────┐
                              ▼
Phase 2: Foundational ───────┐ (BLOCKS all user stories)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
Phase 3: US1 (P1)    Phase 7: US5 (P5)     [US2-US4 wait
  🎯 MVP                                    for US1]
        │
        ├──────────────────────┐
        ▼                      ▼
Phase 4: US2 (P2)      Phase 6: US4 (P4)
        │
        ▼
Phase 5: US3 (P3)
        │
        ▼
Phase 8: Polish (after desired stories complete)
        │
        ▼
Phase 9: Testing (alongside or after each story)
```

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — **no** dependencies on other stories
- **US2 (P2)**: Depends on US1 (needs ingested documents for retrieval)
- **US3 (P3)**: Depends on US2 (needs conversation creation for history management)
- **US4 (P4)**: Depends on US1 (needs ingested documents for summarization) — **independent** of US2/US3
- **US5 (P5)**: Depends on Foundational only (provider ABCs already exist) — **independent** of US1-US4

### Within Each User Story

1. Models/entities before services
2. Services before API routes
3. Backend routes before frontend components
4. Hooks before pages
5. Core implementation before integration

### Parallel Opportunities

**Phase 1** (4 parallel): T003, T004, T005, T006 can all run simultaneously after T001+T002

**Phase 2** (16 parallel): T008-T013 (all models + vector store), T015-T017 (ABC + providers), T024-T029 (all frontend setup) can run simultaneously after T007

**Phase 3 US1** (7 parallel): T030-T033, T033b (all parsers), T040-T041 (frontend components) can run simultaneously

**Phase 4 US2** (3 parallel): T049-T051 (frontend chat components) can run simultaneously

**Phase 7 US5** (2 parallel): T063-T064 (adapter stubs) can run simultaneously

**Phase 8** (4 parallel): T067-T070 can run simultaneously

**Phase 9 Testing** (5 parallel): T074-T078 (all unit test files) can run simultaneously; T079-T081 (integration tests) run after corresponding services exist

---

## Parallel Execution Example: Phase 2 (Foundational)

```
Batch 1 (no dependencies — all in parallel):
  T007  database.py
  T008  vector_store.py
  T009  document.py model
  T010  conversation.py model
  T011  message.py model
  T012  document_summary.py model
  T013  ingestion_job.py model
  T015  providers/base.py
  T024  App.tsx + main.tsx
  T025  Layout.tsx + Navbar.tsx + LoadingSpinner.tsx
  T026  api.ts
  T027  websocket.ts
  T028  types.ts
  T029  Settings.tsx

Batch 2 (depends on Batch 1):
  T014  Alembic migration (needs T007, T009-T013)
  T016  local_embedding.py (needs T015)
  T017  local_llm.py (needs T015)

Batch 3 (depends on Batch 2):
  T018  factory.py (needs T016, T017)
  T019  model_manager.py (needs T018, T008)

Batch 4 (depends on Batch 3):
  T020  main.py (needs T007, T018, T005, T006)
  T021  deps.py (needs T020)
  T022  system.py routes (needs T021)
  T023  error handlers (needs T020, T006)
```

## Parallel Execution Example: Phase 3 (US1)

```
Batch 1 (no dependencies — all in parallel):
  T030  parsers/base.py
  T040  DocumentTable.tsx
  T041  IngestionProgress.tsx

Batch 2 (depends on T030):
  T031  pdf_parser.py
  T032  docx_parser.py
  T033  markdown_parser.py
  T033b excel_parser.py
  T034  chunker.py

Batch 3 (depends on Batch 2):
  T035  embedding.py service (needs T034, providers)
  T039  documents.py routes (needs models)

Batch 4 (depends on T035):
  T036  ingestion.py service (needs T034, T035, models)

Batch 5 (depends on T036):
  T037  ingestion routes (needs T036)
  T038  ingestion WebSocket (needs T036)
  T042  useDocuments.ts hook
  T043  useIngestion.ts hook

Batch 6 (depends on T042, T043):
  T044  DocumentList.tsx page
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T029) **← CRITICAL, blocks all stories**
3. Complete Phase 3: User Story 1 (T030-T044)
4. **STOP and VALIDATE**: Ingest documents, verify parsing/chunking/embedding/storage, check progress UI
5. Deploy/demo if ready — this is the MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. **US1** → Ingest documents, browse document list → **MVP!**
3. **US2** → Ask questions, get grounded answers with citations → **Core value**
4. **US3** → Conversation history, delete, clear all → **Usability upgrade**
5. **US4** → Document summarization → **Power feature**
6. **US5** → Provider stubs verified → **Architecture validated**
7. **Polish** → Docker, responsive, re-embed, Error Boundaries → **Production-ready**
8. **Testing** → Unit + integration tests validate all stories → **Quality-assured**

Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable after its dependencies
- Test tasks (Phase 9) cover constitution-mandated unit and integration tests
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All file paths are relative to `knowledge-base-ai/` workspace root
