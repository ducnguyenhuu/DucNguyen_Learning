# Quickstart Guide: Local Knowledge Base Application

**Feature**: 001-local-knowledge-base  
**Date**: 2026-03-02

---

## Prerequisites

- **Python 3.11+** — Backend runtime
- **Node.js 18+** — Frontend build toolchain
- **Ollama** — Local LLM inference server ([install](https://ollama.com))
- **8GB+ RAM** — Required for running embedding + LLM models simultaneously
- **10GB+ free disk space** — For models, vector data, and database

---

## 1. Install Ollama & Pull Models

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama server
ollama serve &

# Pull the LLM model (~2.4GB download)
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M

# Pull the embedding model (~275MB download)
ollama pull nomic-embed-text
```

---

## 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env to set KNOWLEDGE_FOLDER path

# Run database migrations
alembic upgrade head

# Start the backend server (localhost only by default — FR-020)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Backend runs at**: http://localhost:8000  
**API docs at**: http://localhost:8000/docs (Swagger UI)

---

## 3. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Frontend runs at**: http://localhost:5173

---

## 4. First Use

1. Open http://localhost:5173 in your browser
2. Go to **Documents** → Click **Run Ingest**
3. Specify your document folder path (or use the default from `.env`)
4. Watch the progress bar as documents are parsed, chunked, and embedded
5. Once complete, go to **Chat** → Start asking questions!

---

## 5. Project Structure

```
knowledge-base-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entry point
│   │   ├── config.py                # Configuration management
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── ingestion.py     # Ingestion endpoints
│   │   │   │   ├── documents.py     # Document management endpoints
│   │   │   │   ├── conversations.py # Conversation endpoints
│   │   │   │   ├── chat.py          # Chat/query endpoints + WebSocket
│   │   │   │   ├── summary.py       # Document summary endpoints
│   │   │   │   └── system.py        # Health, config endpoints
│   │   │   └── deps.py              # Dependency injection
│   │   ├── models/
│   │   │   ├── document.py          # Document SQLAlchemy model
│   │   │   ├── conversation.py      # Conversation SQLAlchemy model
│   │   │   ├── message.py           # Message SQLAlchemy model
│   │   │   ├── document_summary.py  # DocumentSummary model
│   │   │   └── ingestion_job.py     # IngestionJob model
│   │   ├── services/
│   │   │   ├── ingestion.py         # Document parsing + chunking pipeline
│   │   │   ├── embedding.py         # Embedding generation service
│   │   │   ├── retrieval.py         # Vector similarity search service
│   │   │   ├── chat.py              # RAG orchestration (embed→retrieve→generate)
│   │   │   ├── summary.py           # Document summarization service
│   │   │   └── model_manager.py     # Model download + health checks
│   │   ├── providers/
│   │   │   ├── base.py              # Abstract base classes (EmbeddingProvider, LLMProvider)
│   │   │   ├── local_embedding.py   # sentence-transformers / Ollama embedding
│   │   │   ├── local_llm.py         # Ollama LLM provider
│   │   │   ├── openai_embedding.py  # Future: OpenAI embedding adapter
│   │   │   ├── claude_llm.py        # Future: Claude API adapter
│   │   │   └── factory.py           # Provider factory (config → instance)
│   │   ├── parsers/
│   │   │   ├── base.py              # Abstract document parser
│   │   │   ├── pdf_parser.py        # PDF extraction (PyMuPDF)
│   │   │   ├── docx_parser.py       # Word extraction (python-docx)
│   │   │   ├── markdown_parser.py   # Markdown extraction
│   │   │   └── chunker.py           # Text chunking with overlap
│   │   ├── db/
│   │   │   ├── database.py          # SQLAlchemy engine + session
│   │   │   └── vector_store.py      # ChromaDB client wrapper
│   │   └── core/
│   │       ├── logging.py           # Structured logging configuration
│   │       └── exceptions.py        # Custom exception types
│   ├── alembic/                     # Database migrations
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── requirements.txt
│   ├── .env.example
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Root component + router
│   │   ├── main.tsx                 # Entry point
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # Landing page
│   │   │   ├── ChatView.tsx         # Conversational interface
│   │   │   ├── DocumentList.tsx     # Document management
│   │   │   ├── DocumentDetail.tsx   # Document detail + summary
│   │   │   └── Settings.tsx         # Configuration page
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── SourcePanel.tsx
│   │   │   │   └── ConversationSidebar.tsx
│   │   │   ├── documents/
│   │   │   │   ├── DocumentTable.tsx
│   │   │   │   ├── IngestionProgress.tsx
│   │   │   │   └── SummaryView.tsx
│   │   │   └── common/
│   │   │       ├── Layout.tsx
│   │   │       ├── Navbar.tsx
│   │   │       └── LoadingSpinner.tsx
│   │   ├── services/
│   │   │   ├── api.ts               # Axios/fetch API client
│   │   │   ├── websocket.ts         # WebSocket manager
│   │   │   └── types.ts             # TypeScript interfaces
│   │   └── hooks/
│   │       ├── useChat.ts           # Chat state + streaming logic
│   │       ├── useDocuments.ts      # Document CRUD operations
│   │       └── useIngestion.ts      # Ingestion progress tracking
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── data/                            # Runtime data (gitignored)
│   ├── chromadb/                    # Vector database storage
│   └── knowledge_base.db           # SQLite database
│
├── models/                          # Cached model files (gitignored)
│
├── specs/                           # Feature specifications
│   └── 001-local-knowledge-base/
│
├── docker-compose.yml               # Production deployment
├── Dockerfile.backend
├── Dockerfile.frontend
└── README.md
```

---

## 6. Configuration (.env)

```env
# Knowledge Base
KNOWLEDGE_FOLDER=/path/to/your/documents

# Server Binding (FR-020)
HOST=127.0.0.1              # Default: localhost only
# HOST=0.0.0.0              # Uncomment for LAN/server access
PORT=8000

# Embedding
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=nomic-embed-text-v1.5
EMBEDDING_DIMENSIONS=768

# LLM
LLM_PROVIDER=ollama
LLM_MODEL=phi3.5:3.8b-mini-instruct-q4_K_M
LLM_BASE_URL=http://localhost:11434
LLM_CONTEXT_WINDOW=4096
LLM_TEMPERATURE=0.1

# Retrieval
RETRIEVAL_TOP_K=5
RETRIEVAL_SIMILARITY_THRESHOLD=0.7

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Conversation
SLIDING_WINDOW_MESSAGES=10

# Database
DATABASE_URL=sqlite:///./data/knowledge_base.db
# For server deployment:
# DATABASE_URL=postgresql://user:pass@host:5432/knowledge_base

# ChromaDB
CHROMA_PERSIST_DIR=./data/chromadb
CHROMA_COLLECTION_NAME=knowledge_base

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 7. Server Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build -d

# With PostgreSQL for production:
# 1. Set DATABASE_URL to PostgreSQL connection string in .env
# 2. docker-compose --profile production up --build -d
```

**docker-compose.yml** provisions:
- Backend (FastAPI + Uvicorn)
- Frontend (Nginx serving React build)
- Ollama (GPU-optional inference server)
- PostgreSQL (production profile only)
- Volumes for data persistence

---

## 8. Quick Start Script

A convenience script is available at the project root to manage all services at once:

```bash
# First-time setup (installs deps, pulls models, runs migrations)
./start.sh setup

# Start all services (Ollama → Backend → Frontend)
./start.sh

# Check service status
./start.sh status

# Stop all services
./start.sh stop
```

| Command | Description |
|---------|-------------|
| `./start.sh` | Start Ollama, Backend (port 8000), and Frontend (port 5173) |
| `./start.sh stop` | Stop all running services |
| `./start.sh status` | Show which services are currently running |
| `./start.sh setup` | One-time setup: create venv, install pip/npm deps, pull Ollama models, run DB migrations |

> **Note**: `start.sh` stores PID files in `.pids/` and logs in `.pids/*.log` for debugging.

---

## 9. Testing & Quality Gates

```bash
# Backend type checking + linting
cd backend
mypy app/ --strict
ruff check app/

# Backend tests
pytest tests/ -v --cov=app

# Frontend type checking + linting
cd frontend
npx tsc --noEmit
npx eslint src/

# Frontend tests
npm test

# Integration tests (requires running backend)
cd backend
pytest tests/integration/ -v
```

All type checking and linting MUST pass before merge (see Constitution Principle I & Development Workflow).
