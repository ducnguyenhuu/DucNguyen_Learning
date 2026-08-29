# Research: Human-AI Collaboration Platform (HACP)

**Date**: 2026-05-16  
**Purpose**: Resolve technology choices and document best practices for all primary dependencies.

---

## R1: Backend HTTP Framework — FastAPI vs Flask

**Decision**: FastAPI + uvicorn

**Rationale**:
- Automatic OpenAPI 3.1 schema generation from Pydantic models — contracts stay in sync with implementation
- Native async/await via ASGI — concurrent stage execution and SSE streaming without threads
- Pydantic v2 integration provides input validation at all endpoints (Constitution V)
- Built-in dependency injection — clean service wiring without a DI framework
- `StreamingResponse` + `sse-starlette` for SSE out of the box (FR-034, FR-065, FR-077)
- Production-grade with uvicorn; `--reload` flag for hot-reload in dev

**Alternatives considered**:
- **Flask**: Synchronous by default; requires gevent/eventlet for async; no native type validation or OpenAPI generation
- **Django REST Framework**: Full-stack; too heavy for a local-first app with simple REST endpoints
- **Litestar**: Fast and modern but younger ecosystem; fewer SSE examples and community resources
- **aiohttp**: Low-level; significantly more boilerplate than FastAPI for equivalent functionality

---

## R2: LLM Provider Abstraction — LiteLLM vs provider SDKs

**Decision**: LiteLLM 1.x

**Rationale**:
- Single unified API for OpenAI, Anthropic, Google Gemini, Ollama, and 100+ providers — covers all FR-081 providers with one interface
- Streaming support via `litellm.acompletion()` async generators — maps cleanly to SSE stage streaming (FR-077) and conversation streaming (FR-065)
- Token counting and cost tracking built-in — supports token efficiency monitoring (Constitution I)
- Python-native, actively maintained
- Forward-compatible: same API supports future RAG (embedding endpoint) and MCP agent tool use

**Alternatives considered**:
- **Direct provider SDKs** (openai, anthropic, google-genai): Lightweight but requires custom provider switching, retry logic, and error normalization per provider
- **LangChain**: Feature-rich but heavy abstraction layers; most chains/agents irrelevant for HACP's simple "send prompt → get text" pattern; adds 50MB+ of dependencies
- **Vercel AI SDK**: Excellent streaming API but Node.js-only — not applicable for Python backend
- **Pydantic AI**: Excellent typed agent framework; higher-level than needed in v1 — can adopt in v2 for agentic features

---

## R3: Workflow Visualization — React Flow (Xyflow) vs alternatives

**Decision**: React Flow (Xyflow) 12.x

**Rationale**:
- Purpose-built for node-based workflow graphs in React
- Supports custom nodes (needed for stage nodes with status, output preview, assignee badge)
- Built-in zoom, pan, fit-to-screen (FR-072)
- Keyboard navigation support (FR-110)
- Handles 50+ nodes smoothly — exceeds our 15+ stage requirement
- Large community, active development, MIT license
- Minimap and controls plugins included

**Alternatives considered**:
- **D3.js**: Maximum flexibility but requires building the entire graph UX from scratch (zoom, pan, selection, dragging) — months of work
- **Cytoscape.js**: Graph theory library, not React-native; requires wrapper, less ergonomic for custom node rendering
- **elkjs + custom rendering**: Good layout algorithms but no interaction layer (click, drag, zoom)

---

## R4: Markdown Editor — CodeMirror 6 vs alternatives

**Decision**: CodeMirror 6

**Rationale**:
- Modular architecture — include only what's needed (markdown syntax, preview)
- Excellent performance even on large documents
- Accessibility built-in (screen reader support, ARIA)
- Extensible for auto-save (FR-099: save draft every 30s)
- TypeScript types included
- Used by major editors (VS Code's Monaco is the alternative but heavier)

**Alternatives considered**:
- **Monaco Editor**: VS Code's editor; extremely powerful but 3MB+ bundle, designed for code editing not markdown authoring
- **TipTap/ProseMirror**: Rich-text WYSIWYG, but we need markdown-source editing with preview, not WYSIWYG
- **MDXEditor**: React-native markdown editor, but less mature, limited extension API

---

## R5: State Management (Frontend) — Zustand vs alternatives

**Decision**: Zustand 5.x

**Rationale**:
- Minimal boilerplate, TypeScript-first
- No providers/context needed — works outside React tree (useful for SSE event handlers updating state)
- Built-in middleware: `persist` (for draft recovery), `devtools`
- Tiny bundle (~1KB)
- Handles complex nested state (workflow stages, run history) without immutability libraries

**Alternatives considered**:
- **Redux Toolkit**: More structured but verbose for a single-user local app
- **Jotai**: Atomic state, good for independent pieces, but workflow state is deeply interconnected
- **React Context + useReducer**: No library needed, but gets unwieldy with SSE streaming updates and multiple data domains

---

## R6: File System Watching — chokidar vs alternatives

**Decision**: chokidar 4.x

**Rationale**:
- De facto standard for Node.js file watching
- Cross-platform (macOS FSEvents, Linux inotify, Windows ReadDirectoryChanges)
- Handles rename, delete, create events — needed for FR-044 (detect external file changes)
- Debouncing and glob filtering built-in
- Stable, battle-tested (used by Vite, webpack, nodemon)

**Alternatives considered**:
- **Node.js `fs.watch`**: Native but unreliable cross-platform (double events on macOS, missing events on Linux)
- **Parcel watcher (`@parcel/watcher`)**: Faster, but C++ native addon — adds build complexity
- **fs.watchFile (polling)**: Works everywhere but CPU-intensive for watching entire workspace trees

---

## R6: File System Watching — watchdog vs alternatives

**Decision**: watchdog 4.x

**Rationale**:
- Python-native cross-platform file system event library
- Uses platform-optimal APIs: macOS FSEvents/kqueue, Linux inotify, Windows ReadDirectoryChanges
- Observer + event handler pattern integrates cleanly with FastAPI background tasks
- Handles create, modify, delete, rename events — needed for FR-044 (detect external workspace changes)
- Actively maintained; widely used in production (Flask debug reloader, Celery)

**Alternatives considered**:
- **`watchfiles` (Rust-based)**: Fastest Python file watcher (used by uvicorn itself); good alternative but less suited to app-level event handling patterns
- **`asyncio` + polling**: Works everywhere but CPU-intensive for watching entire workspace trees
- **`inotify` (Linux-only)**: Not cross-platform — excluded by Target Platform requirement

---

## R7: OS Keychain Integration — keyring vs alternatives

**Decision**: `keyring` 25.x

**Rationale**:
- Official Python library for OS keychain access (PyPA recommended)
- Cross-platform: macOS Keychain, Windows Credential Manager, Linux libsecret/SecretService
- Simple API: `keyring.set_password(service, username, password)` / `keyring.get_password(service, username)`
- No native compilation required (unlike keytar which needs node-gyp)
- Meets FR-082 (API keys encrypted at rest using OS keychain)

**Alternatives considered**:
- **keytar (Node.js)**: Node.js-only — not applicable
- **Manual encryption (`cryptography` library)**: Application-level encryption key creates a circular problem — where to store the key itself?
- **Plaintext settings file**: Explicitly disallowed by FR-082 and Constitution V (no hardcoded secrets)

---

## R8: Desktop Shell — Electron vs Tauri vs localhost-only

**Decision**: Localhost-only (no desktop shell in v1)

**Rationale**:
- Spec says "local web application (localhost)" in Assumptions
- Adding Electron/Tauri adds ~100MB+ to distribution, complex build pipeline, and OS-specific packaging
- Users open `http://localhost:3001` in their browser — simpler, lighter, faster iteration
- The `bin/hacp.py` CLI (via `typer`) starts the server; user opens browser
- Desktop shell can be added in v2 as a thin wrapper

**Alternatives considered**:
- **Electron**: Full desktop app, but huge bundle size, complex auto-update, Chromium version management
- **Tauri**: Rust-based, much smaller (~10MB), but adds Rust to the build chain and has a younger ecosystem
- **Neutralinojs**: Lightweight but limited API access for file system and keychain

---

## R9: Build & Dev Tooling

**Decision**: Vite (frontend) + uv (Python package manager) + uvicorn (backend dev server)

**Rationale**:
- **Vite**: Standard React build tool, HMR, fast dev server (unchanged from original decision)
- **uv**: Extremely fast Python package manager (10–100x faster than pip); built-in virtual env management; `uv.lock` lockfile for reproducible installs
- **uvicorn**: ASGI server for FastAPI; `--reload` flag for hot-reload in dev (equivalent of `tsx` for Python)
- **pyproject.toml**: Single config file for dependencies, tool settings (ruff, mypy, pytest)
- **OpenAPI codegen**: `openapi-typescript` generates TypeScript interfaces from FastAPI's auto-generated schema — maintains FE/BE type alignment without duplication

---

## R10: SSE (Server-Sent Events) for Real-Time Updates

**Decision**: `sse-starlette` (`EventSourceResponse`) + native `EventSource` on frontend

**Rationale**:
- SSE is simpler than WebSocket for our use case (server → client unidirectional streaming)
- `sse-starlette` provides `EventSourceResponse` with async generator support — integrates natively with FastAPI route handlers
- Async generators in Python map naturally to token-by-token LiteLLM streaming output
- Covers: AI stage streaming output (FR-077), workflow status updates (FR-034), notifications (FR-017)
- Native browser `EventSource` API — no client library needed

**Alternatives considered**:
- **WebSocket (`websockets`)**: Bidirectional, but we don't need client→server streaming; adds reconnection complexity
- **FastAPI `StreamingResponse` (raw)**: Works for single responses but `sse-starlette` adds event naming, retry, and reconnect headers for free
- **HTTP polling**: Wastes bandwidth; unacceptable for streaming AI output
