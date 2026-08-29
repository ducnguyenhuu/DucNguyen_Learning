# Research: Local Knowledge Base Application

**Feature**: 001-local-knowledge-base  
**Date**: 2026-03-02

## 1. Best Distilled Embedding Model

### Decision: **nomic-embed-text-v1.5**

### Rationale
- **MTEB Score**: 55.0 (competitive with models 3-5x larger)
- **Size**: 137M parameters, ~600MB RAM at float32
- **Context Window**: 8,192 tokens — handles large chunks without truncation
- **Matryoshka Dimensions**: Supports 256/512/768 dimensions — can trade precision for speed
- **Ollama Native**: Available as `nomic-embed-text` in Ollama, simplifying deployment
- **Python**: Also available via `sentence-transformers` for direct embedding

### Alternatives Considered

| Model | MTEB | Size | Context | Why Rejected |
|-------|------|------|---------|--------------|
| all-MiniLM-L6-v2 | 49.5 | 22M / ~90MB | 512 tokens | Significantly lower retrieval quality; 512-token limit too restrictive |
| bge-small-en-v1.5 | 51.7 | 33M / ~130MB | 512 tokens | Better than MiniLM but still 512-token limited |
| gte-base-en-v1.5 | 54.1 | 109M / ~430MB | 8192 tokens | Close competitor but slightly lower MTEB, less flexible dimensions |
| e5-small-v2 | 49.0 | 33M / ~130MB | 512 tokens | Lowest retrieval quality of candidates |

### Configuration
```yaml
embedding:
  model: nomic-embed-text-v1.5
  dimensions: 768          # Full precision; reduce to 384 for speed
  max_tokens: 8192
  provider: sentence-transformers  # Primary; Ollama as alternative
```

---

## 2. Best Distilled LLM Model

### Decision: **Phi-3.5-mini-Instruct (Q4_K_M quantization)**

### Rationale
- **Parameters**: 3.8B (Q4_K_M quantized to ~2.4GB file, ~3.0GB RAM)
- **Context Window**: 128K tokens — more than sufficient for RAG + conversation history
- **Quality**: Matches or exceeds 7B models on QA and summarization benchmarks while using half the RAM
- **Quantization**: Q4_K_M provides best quality-to-size ratio (minimal quality loss from full precision)
- **Ollama Native**: Available as `phi3.5` in Ollama
- **License**: MIT — fully permissive for commercial and local use

### Alternatives Considered

| Model | Params | RAM (Q4) | Context | Why Rejected |
|-------|--------|----------|---------|--------------|
| Qwen2.5-3B | 3B | ~2.5GB | 32K | Slightly lower QA benchmarks than Phi-3.5; smaller context |
| Llama 3.2-3B | 3B | ~2.5GB | 128K | Competitive but Phi-3.5 edges it on summarization tasks |
| Mistral-7B-Q4 | 7B | ~4.5GB | 32K | Too much RAM — leaves <2GB for embedding + vector DB on 8GB system |
| Gemma 2-2B | 2B | ~1.8GB | 8K | Too small context window; weaker QA quality |
| Qwen2.5-7B-Q4 | 7B | ~4.5GB | 128K | Best quality but too much RAM for 8GB target |

### Configuration
```yaml
llm:
  model: phi3.5:3.8b-mini-instruct-q4_K_M
  context_window: 4096     # Practical window for RAG (model supports 128K)
  temperature: 0.1          # Low temperature for factual RAG responses
  provider: ollama
```

---

## 3. Vector Database

### Decision: **ChromaDB**

### Rationale
- **Zero-config**: Embedded mode — no separate server process needed for local use
- **CRUD Operations**: Native support for add/update/delete — critical for incremental ingestion (FR-005)
- **Metadata Filtering**: Can filter by source document, file type, ingestion date
- **Persistence**: Built-in disk persistence via DuckDB+Parquet backend
- **Migration Path**: Can switch to client-server mode for deployment; or swap to Qdrant/Pinecone via provider abstraction
- **Python Native**: First-class Python SDK

### Alternatives Considered

| Database | Why Rejected |
|----------|--------------|
| FAISS | No built-in persistence, no metadata filtering, no delete operations — manual bookkeeping required |
| Qdrant | Requires separate server process even locally; overkill for single-user |
| Milvus Lite | Newer, less mature embedded mode; heavier dependencies |

### Configuration
```yaml
vector_db:
  provider: chromadb
  persist_directory: ./data/chromadb
  collection_name: knowledge_base
  distance_metric: cosine
```

---

## 4. SQL Database

### Decision: **SQLite via SQLAlchemy ORM**

### Rationale
- **Zero Setup**: Built into Python — no server process, no installation
- **SQLAlchemy ORM**: Abstracts database operations; switching to PostgreSQL requires only changing the connection string
- **Deployment Path**: When deploying to a server, swap SQLite connection string to PostgreSQL — zero code changes
- **Sufficient for Scale**: Handles thousands of conversations and messages without performance issues

### Alternatives Considered

| Database | Why Rejected |
|----------|--------------|
| PostgreSQL (direct) | Requires server process running locally; unnecessary complexity for single-user |
| Raw SQLite (no ORM) | Harder to migrate; no abstraction layer |

### Configuration
```yaml
database:
  provider: sqlite
  url: sqlite:///./data/knowledge_base.db
  # For server deployment, change to:
  # url: postgresql://user:pass@host:5432/knowledge_base
```

---

## 5. RAM Budget Analysis (8GB System)

| Component | RAM Usage |
|-----------|-----------|
| Embedding Model (nomic-embed-text-v1.5) | ~600MB |
| LLM Model (Phi-3.5-mini Q4_K_M) | ~3,000MB |
| ChromaDB (in-process, 50 docs indexed) | ~200MB |
| Python Backend (FastAPI + dependencies) | ~300MB |
| React Frontend (browser tab) | ~200MB |
| Ollama Server Process | ~200MB |
| **Total Peak** | **~4,500MB** |
| OS + Other Processes | ~2,500MB |
| **Headroom** | **~1,000MB** |

The stack fits comfortably in 8GB with ~1GB headroom.

---

## 6. Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | React | 18+ | Web UI for chatbot, ingestion, document management |
| Backend | Python + FastAPI | 3.11+ / 0.110+ | REST API, ingestion pipeline, RAG orchestration |
| Embedding | nomic-embed-text-v1.5 | v1.5 | Local vector embeddings via sentence-transformers |
| LLM | Phi-3.5-mini-Instruct | Q4_K_M | Local reasoning via Ollama |
| LLM Runtime | Ollama | latest | Model management, inference server |
| Vector DB | ChromaDB | 0.5+ | Embedding storage and similarity search |
| SQL DB | SQLite + SQLAlchemy | 3.x / 2.0+ | Conversation history, document metadata |
| Document Parsing | python-docx, PyMuPDF, markdown, openpyxl | latest | Word, PDF, Markdown, Excel extraction |
| WebSocket | FastAPI WebSockets | built-in | Real-time ingestion progress, streaming responses |
| Testing | pytest + React Testing Library | latest | Backend + frontend tests |

---

## 7. Upgrade Path

| Component | Current (Distilled) | Commercial Upgrade | Change Required |
|-----------|--------------------|--------------------|-----------------|
| Embedding | nomic-embed-text-v1.5 (local) | OpenAI text-embedding-3-small / Claude | Change provider config + implement adapter |
| LLM | Phi-3.5-mini via Ollama (local) | Claude API / GPT-4o / Copilot | Change provider config + implement adapter |
| Vector DB | ChromaDB (embedded) | Qdrant Cloud / Pinecone | Change provider config + implement adapter |
| SQL DB | SQLite (file) | PostgreSQL (server) | Change SQLAlchemy connection string |

All upgrades are configuration-only changes due to the provider abstraction layer (FR-013).
