# Quickstart: Human-AI Collaboration Platform (HACP)

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | ≥ 3.12 | Backend runtime |
| uv | ≥ 0.4 | Python package manager (replaces pip + venv) |
| Node.js | ≥ 20.x LTS | Frontend build tooling only |
| npm | ≥ 10.x (ships with Node 20) | Frontend package manager |
| Git | ≥ 2.40 | Version control |
| OS keychain | macOS Keychain / libsecret (Linux) / Credential Manager (Win) | Secure API key storage via `keyring` |

## Install

```bash
# Clone
git clone <repo-url> hacp && cd hacp

# Install backend dependencies (Python)
cd backend && uv sync && cd ..

# Install frontend dependencies
cd frontend && npm install && cd ..
```

Repository layout:

```
hacp/
├── backend/         # FastAPI + Python 3.12
│   └── pyproject.toml
├── frontend/        # React 18 + Vite (TypeScript)
│   └── package.json
└── Makefile         # dev, test, build shortcuts
```

## Configuration

### 1. LLM API Key

On first launch the Settings page will prompt you.  
To pre-configure via CLI:

```bash
# Store key in OS keychain (never in plaintext files)
python -m hacp keychain set openai <your-key>
```

### 2. Default workspace root (optional)

Edit `~/.hacp/settings.json`:

```json
{
  "workspaceDefaults": {
    "rootDir": "~/Documents/hacp-workspaces"
  }
}
```

## Run

```bash
# Backend — hot reload via uvicorn (run in one terminal)
cd backend && uv run uvicorn hacp.api.app:app --reload --port 3001

# Frontend — Vite dev server (run in another terminal)
cd frontend && npm run dev
```

Or with Make (from repo root):

```bash
make dev
```

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:5173 | Vite dev server, proxies `/api` to backend |
| Backend  | http://localhost:3001 | FastAPI + uvicorn REST + SSE |

## First Project

1. **Open** http://localhost:5173 → you land on the Project Library (empty).
2. **Create Project** → click "+ New Project".
3. **Describe your task** → paste a natural-language description (e.g., "Write a technical blog post about WebSockets").
4. **Review stages** → the AI decomposes your description into sequential stages displayed as a node graph.
5. **Edit stages** → click any node to change title, assignee (AI / Human), inputs, process prompt, or outputs.
6. **Run workflow** → click "▶ Start". AI stages execute automatically; human stages pause and notify you.
7. **Submit human output** → when the workflow reaches a Human stage, write your content in the built-in editor and click "Submit".
8. **Export** → after completion, click "Export" for a consolidated Markdown / HTML document.

## Common commands

### Backend (Python / uv)

| Command | Description |
|---------|-------------|
| `uv run uvicorn hacp.api.app:app --reload` | Start backend with hot reload |
| `uv run pytest` | Run unit + integration tests |
| `uv run pytest --cov` | Run tests with coverage report |
| `uv run ruff check .` | Lint |
| `uv run mypy .` | Type check |

### Frontend (Node.js / npm)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Production build |
| `npm run test` | Run Vitest unit tests |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run lint` | ESLint + tsc --noEmit |

## Tech Stack Summary

- **Backend**: FastAPI + uvicorn, LiteLLM, watchdog, keyring, Pydantic v2, Python 3.12+
- **Frontend**: React 18, React Flow 12.x, CodeMirror 6, Zustand 5.x, TypeScript 5.x
- **Build**: Vite (frontend), uv (backend)
- **Test**: pytest + pytest-asyncio (backend), Vitest (frontend unit), Playwright (E2E)
- **Transport**: REST + SSE (no WebSocket)
