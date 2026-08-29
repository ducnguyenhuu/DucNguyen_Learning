# Knowledge Base AI

A local, privacy-first knowledge base application — ingest your documents, then chat with them using a fully offline LLM. Similar in spirit to NotebookLM, but runs entirely on your machine.

---

## Features

- **Document Ingestion** — Parse PDF, Word (DOCX), Markdown, and Excel files into a searchable vector store
- **Conversational Q&A** — Chat with your documents via a React web interface; answers cite their sources
- **On-Device LLM** — Powered by [Ollama](https://ollama.com) with `phi3.5:3.8b-mini-instruct` (runs offline after the first model pull)
- **Document Summaries** — Generate and cache AI summaries of individual documents on demand
- **Auto Re-Embedding** — Detects embedding model changes on startup and re-indexes automatically (FR-021)
- **Provider Abstraction** — Swap embedding/LLM backends via config (local → OpenAI/Claude with zero code changes)
- **Localhost-Only by Default** — Binds to `127.0.0.1` (FR-020); configurable for LAN/server use

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI 0.110 · SQLAlchemy 2.0 · Alembic |
| Frontend | TypeScript · React 18 · Vite · React Router |
| Embedding | `nomic-embed-text-v1.5` via `sentence-transformers` |
| LLM | `phi3.5:3.8b-mini-instruct-q4_K_M` via Ollama |
| Vector DB | ChromaDB 0.5 |
| SQL DB | SQLite (dev) · PostgreSQL (production) |
| Doc Parsing | PyMuPDF · python-docx · openpyxl · markdown |
| Logging | structlog (JSON) |
| Testing | pytest · React Testing Library · Vitest |

---

## Architecture

```
Browser (React + Vite)
  │
  │  REST /api/v1/   WebSocket ws://
  ▼
FastAPI (Uvicorn)
  ├── Routes:  ingestion · documents · conversations · chat · summary · system
  ├── Services: ingestion · embedding · retrieval · chat · summary · model_manager
  ├── Providers (ABC): EmbeddingProvider · LLMProvider
  │     ├── LocalEmbeddingProvider  (sentence-transformers)
  │     ├── LocalLLMProvider        (Ollama HTTP)
  │     ├── OpenAIEmbeddingProvider (future)
  │     └── ClaudeLLMProvider       (future)
  ├── ChromaDB  ← vector embeddings (similarity search)
  └── SQLite/PostgreSQL ← documents · conversations · messages · jobs
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed
- 8 GB+ RAM, 10 GB+ free disk

### 1. Pull Ollama Models

```bash
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
ollama pull nomic-embed-text
```

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Then set KNOWLEDGE_FOLDER in .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: <http://localhost:8000/docs>

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>

### 4. First Use

1. Open <http://localhost:5173>
2. **Documents → Run Ingest** — point at your folder and watch the progress bar
3. **Chat** — start asking questions; answers include source citations

---

## Development Commands

### Backend

```bash
# Type checking
mypy app/ --strict

# Linting
ruff check app/

# Tests + coverage
pytest tests/ -v --cov=app
```

### Frontend

```bash
# Type checking
npx tsc --noEmit

# Linting
npx eslint src/

# Tests
npm test
```

---

## Docker Deployment

### Development (SQLite)

```bash
docker-compose up --build -d
```

- Frontend: <http://localhost>
- Backend API: <http://localhost:8000>
- Ollama: <http://localhost:11434>

### Production (PostgreSQL)

```bash
# Set DATABASE_URL to your PostgreSQL connection string in backend/.env
docker-compose --profile production up --build -d
```

Services provisioned:

| Service | Image | Purpose |
|---|---|---|
| `backend` | `Dockerfile.backend` | FastAPI + Gunicorn/Uvicorn |
| `frontend` | `Dockerfile.frontend` | Nginx serving React SPA |
| `ollama` | `ollama/ollama:latest` | Local LLM inference (GPU-optional) |
| `postgres` | `postgres:16-alpine` | SQL DB (production profile) |

Persistent volumes: `chroma_data`, `sqlite_data`, `ollama_models`, `postgres_data`

---

## Configuration

All configuration lives in `backend/.env` (copy from `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `KNOWLEDGE_FOLDER` | _(required)_ | Path to the folder of documents to ingest |
| `HOST` | `127.0.0.1` | Server bind address (`0.0.0.0` for LAN/Docker) |
| `PORT` | `8000` | Backend port |
| `EMBEDDING_MODEL` | `nomic-embed-text-v1.5` | Embedding model name |
| `LLM_MODEL` | `phi3.5:3.8b-mini-instruct-q4_K_M` | LLM model name |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `DATABASE_URL` | `sqlite:///./data/knowledge_base.db` | SQLAlchemy DB URL |
| `CHROMA_PERSIST_DIR` | `./data/chromadb` | ChromaDB storage directory |

See [quickstart.md](specs/001-local-knowledge-base/quickstart.md) for the full reference.

---

## Project Structure

```
knowledge-base-ai/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point + lifespan
│   │   ├── config.py         # Pydantic Settings (.env)
│   │   ├── api/routes/       # REST + WebSocket endpoints
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── services/         # Business logic
│   │   ├── providers/        # Embedding + LLM abstraction layer
│   │   ├── parsers/          # Document format extractors
│   │   ├── db/               # Database + vector store clients
│   │   └── core/             # Logging, exceptions
│   ├── alembic/              # DB migrations
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/            # Route-level components
│   │   ├── components/       # Reusable UI components
│   │   ├── hooks/            # Custom React hooks
│   │   └── services/         # API client + WebSocket
├── docker/
│   └── nginx.conf            # Nginx SPA + proxy config
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── specs/                    # Feature specifications
```

---

## License

MIT
