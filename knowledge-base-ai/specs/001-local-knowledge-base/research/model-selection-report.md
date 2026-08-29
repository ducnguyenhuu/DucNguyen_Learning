# Model & Infrastructure Selection Report

**Project**: Local Knowledge Base Application (NotebookLM-like)  
**Date**: 2026-03-02  
**Constraint**: Consumer hardware — 8GB RAM, no GPU required, fully offline after setup  

---

## Table of Contents

1. [Embedding Model Selection](#1-embedding-model-selection)
2. [LLM Model Selection](#2-llm-model-selection)
3. [Vector Database Selection](#3-vector-database-selection)
4. [SQL Database Selection](#4-sql-database-selection)
5. [Final Recommendations Summary](#5-final-recommendations-summary)

---

## 1. Embedding Model Selection

### Evaluation Criteria

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| MTEB Retrieval Score | High | Directly impacts RAG answer quality |
| Model Size (RAM) | High | Must fit in 8GB alongside LLM + app |
| Inference Speed | Medium | Affects ingestion time (SC-001: 50 docs < 30 min) |
| Max Token Input | Medium | Spec requires ≥512; longer is better for chunking flexibility |
| Library Support | Medium | sentence-transformers preferred for easy Python integration |

### Candidate Comparison

| Model | Params | Size on Disk | RAM Usage | MTEB Retrieval Avg | Max Tokens | Embedding Dim | Speed (sentences/sec)¹ |
|-------|--------|-------------|-----------|---------------------|------------|---------------|------------------------|
| **all-MiniLM-L6-v2** | 22M | ~80 MB | ~100 MB | 49.5 | 256 | 384 | ~14,000 |
| **bge-small-en-v1.5** | 33M | ~130 MB | ~160 MB | 51.7 | 512 | 384 | ~10,000 |
| **e5-small-v2** | 33M | ~130 MB | ~160 MB | 49.0 | 512 | 384 | ~10,000 |
| **nomic-embed-text-v1.5** | 137M | ~520 MB | ~600 MB | 55.0 | 8,192 | 768 | ~3,500 |
| **gte-base-en-v1.5** | 137M | ~520 MB | ~600 MB | 57.7 | 8,192 | 768 | ~3,500 |

¹ *Approximate CPU-only throughput on modern consumer hardware (no GPU, batch size 32).*

### Detailed Analysis

#### all-MiniLM-L6-v2
- **Pros**: Extremely fast, tiny footprint, battle-tested, most widely used.
- **Cons**: Max input only 256 tokens (a serious limitation — chunks must be very small), retrieval quality is notably lower than newer models. Released in 2022; significantly outperformed by 2024+ models.
- **Verdict**: ❌ Disqualified. The 256-token limit is below the project's 512-token minimum requirement.

#### bge-small-en-v1.5 (BAAI)
- **Pros**: Good quality-to-size ratio, 512-token support, well-supported in sentence-transformers, strong retrieval benchmarks for its size class.
- **Cons**: Outperformed by nomic and gte on retrieval tasks. 384-dim embeddings store less semantic information than 768-dim.
- **Verdict**: ✅ Strong runner-up. Best choice if RAM is extremely tight.

#### e5-small-v2 (Microsoft)
- **Pros**: Comparable size to bge-small, good general-purpose quality.
- **Cons**: Slightly lower retrieval scores than bge-small. Requires query prefix formatting ("query: " / "passage: ") which adds complexity.
- **Verdict**: ❌ No advantage over bge-small; adds prompt complexity.

#### nomic-embed-text-v1.5 (Nomic AI)
- **Pros**: 8,192-token context (excellent for long chunks/documents), Matryoshka embeddings (can truncate dimensions to 256/512/768 to trade quality for speed/storage), open-source with Apache 2.0 license, strong community adoption, excellent retrieval quality.
- **Cons**: ~600 MB RAM, slower than small models. Slightly behind gte-base on benchmarks.
- **Verdict**: ✅ Excellent choice. Great balance of quality, flexibility, and community support.

#### gte-base-en-v1.5 (Alibaba DAMO)
- **Pros**: **Highest MTEB retrieval score in this comparison** (~57.7 avg), 8,192-token context, excellent for knowledge retrieval tasks specifically. Released as an improved distillation in late 2024.
- **Cons**: ~600 MB RAM (same class as nomic), Apache 2.0 license. No Matryoshka embedding support (fixed 768-dim). Slightly less community tooling than nomic.
- **Verdict**: ✅ **Best raw retrieval quality.**

### RAM Budget Analysis

With 8GB total system RAM:
- OS + browser + Python runtime: ~2.5 GB
- LLM (quantized, see below): ~2.5–4.0 GB
- Vector DB in-memory index: ~0.5–1.0 GB (for ~50K chunks)
- **Remaining for embedding model: ~1.0–2.5 GB**

Both nomic-embed-text-v1.5 (~600 MB) and gte-base-en-v1.5 (~600 MB) fit comfortably.

### 🏆 RECOMMENDATION: nomic-embed-text-v1.5

**Why nomic over gte-base (despite gte's slightly higher benchmarks)?**

| Factor | nomic-embed-text-v1.5 | gte-base-en-v1.5 |
|--------|----------------------|-------------------|
| MTEB Retrieval | 55.0 (excellent) | 57.7 (best) |
| Matryoshka Support | ✅ Yes (256/512/768 dim) | ❌ No (768 only) |
| License | Apache 2.0 | Apache 2.0 |
| Ollama Integration | ✅ Native support | ❌ Limited |
| Community / Ecosystem | Broader adoption | Growing |
| Long Context | 8,192 tokens | 8,192 tokens |
| Flexible Storage | Can use 256-dim for faster search | Fixed 768-dim |

**Rationale**: The 2.7-point MTEB gap is marginal in practice. Nomic's **Matryoshka embeddings** are a decisive advantage — they let you start with 256-dim embeddings for fast iteration during development, then scale to 768-dim in production. Nomic also has **native Ollama support**, aligning with the LLM runtime below. The model is widely used in RAG applications and has excellent documentation.

**Installation**:
```python
# Via sentence-transformers
pip install sentence-transformers
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)

# Via Ollama (for unified runtime)
ollama pull nomic-embed-text
```

**Download source**: [HuggingFace: nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)

---

## 2. LLM Model Selection

### Evaluation Criteria

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| QA / RAG Quality | High | Core use case — grounded answers from context |
| Summarization Quality | High | FR-017 requires on-demand document summarization |
| Quantized Model Size | High | Must fit in 8GB RAM alongside embedding model + app |
| Context Window | High | Needs ≥4K; more helps with multi-chunk context |
| Instruction Following | Medium | Must respect system prompts, cite sources |
| Inference Speed | Medium | SC-002 requires answer within 30 seconds |
| Ollama/llama.cpp support | Medium | Preferred local runtime |

### Candidate Comparison

| Model | Params | Q4_K_M Size | RAM (Q4_K_M) | Context Window | MMLU | HumanEval | MT-Bench | Key Strength |
|-------|--------|-------------|-------------|----------------|------|-----------|----------|--------------|
| **Phi-3-mini-4k** | 3.8B | ~2.2 GB | ~3.0 GB | 4K | 68.8 | 57.3 | 8.38 | Reasoning, code |
| **Phi-3.5-mini** | 3.8B | ~2.2 GB | ~3.0 GB | 128K | 69.0 | 58.5 | 8.60 | Long context, reasoning |
| **Qwen2.5-3B-Instruct** | 3B | ~1.8 GB | ~2.5 GB | 32K | 65.6 | 48.8 | 7.80 | Multilingual, efficient |
| **Qwen2.5-7B-Instruct** | 7B | ~4.4 GB | ~5.5 GB | 128K | 74.2 | 63.4 | 8.50 | Best quality at 7B |
| **Llama 3.2-3B-Instruct** | 3B | ~1.9 GB | ~2.6 GB | 128K | 63.4 | 44.4 | 7.60 | Meta ecosystem, tool use |
| **Mistral-7B-Instruct-v0.3** | 7B | ~4.1 GB | ~5.2 GB | 32K | 62.5 | 40.2 | 7.60 | Mature, well-tested |
| **Gemma-2-2B-Instruct** | 2.6B | ~1.5 GB | ~2.2 GB | 8K | 56.8 | 35.7 | 6.90 | Smallest footprint |

### Detailed Analysis

#### Gemma-2-2B-Instruct (Google)
- **Pros**: Smallest model, fastest inference, fits anywhere.
- **Cons**: Noticeably lower quality across all benchmarks. Summarization tends to be shallow. 8K context is adequate but not generous.
- **Verdict**: ❌ Quality too low for a knowledge base application where answer accuracy matters (SC-003: 80% correct citations).

#### Llama 3.2-3B-Instruct (Meta)
- **Pros**: 128K context, good ecosystem, strong tool-use capabilities.
- **Cons**: Benchmarks trail Phi-3.5 and Qwen2.5 at the same size class. Instruction following is less precise for RAG-style prompts.
- **Verdict**: ⚠️ Acceptable but not best-in-class for RAG QA.

#### Qwen2.5-3B-Instruct (Alibaba)
- **Pros**: Very small, 32K context, good multilingual support.
- **Cons**: QA quality noticeably below Phi-3.5-mini. Summarization is adequate but not as coherent.
- **Verdict**: ⚠️ Good if you need multilingual support; otherwise Phi-3.5 wins.

#### Mistral-7B-Instruct-v0.3 (Mistral AI)
- **Pros**: Mature, well-tested, large community.
- **Cons**: At 7B Q4_K_M (~5.2 GB RAM), it leaves very little headroom. Benchmarks are lower than Qwen2.5-7B and Phi-3.5. Released in 2024 but surpassed by newer models.
- **Verdict**: ❌ Outclassed by Qwen2.5-7B at the same size, and by Phi-3.5 at half the size.

#### Qwen2.5-7B-Instruct (Alibaba)
- **Pros**: **Best absolute quality** in this comparison. 128K context. Excellent at both QA and summarization. Strong instruction following.
- **Cons**: At Q4_K_M quantization, requires ~5.5 GB RAM. With embedding model (~600 MB) + vector DB (~500 MB) + OS (~2 GB), total approaches ~8.6 GB → **may cause swapping on 8GB systems**.
- **Verdict**: ✅ Best quality but **risky for 8GB RAM constraint**. Excellent choice if user has 16GB RAM.

#### Phi-3.5-mini-Instruct (Microsoft)
- **Pros**: **Best quality-to-size ratio**. At only 3.8B params, it matches or beats many 7B models on QA and reasoning tasks. 128K context window is transformative for RAG (can fit many more chunks). Excellent instruction following — respects system prompts, cites sources when asked. Only ~3.0 GB RAM at Q4_K_M. Well-supported in Ollama.
- **Cons**: Slightly below Qwen2.5-7B on raw benchmarks (expected — it's half the size). English-centric (fine for this project's scope).
- **Verdict**: ✅ **Best choice for 8GB RAM systems.**

### RAM Budget Verification (Phi-3.5-mini)

| Component | RAM Usage |
|-----------|-----------|
| macOS / Linux OS | ~1.5 GB |
| Python runtime + FastAPI | ~0.3 GB |
| Web browser (1 tab) | ~0.5 GB |
| nomic-embed-text-v1.5 | ~0.6 GB |
| Phi-3.5-mini Q4_K_M | ~3.0 GB |
| ChromaDB in-memory index | ~0.5 GB |
| Headroom / OS cache | ~1.6 GB |
| **Total** | **~8.0 GB** |

✅ Fits within 8GB with reasonable headroom.

### 🏆 RECOMMENDATION: Phi-3.5-mini-Instruct (Q4_K_M quantization)

**Why Phi-3.5-mini over Qwen2.5-7B?**

| Factor | Phi-3.5-mini | Qwen2.5-7B |
|--------|-------------|-------------|
| RAM (Q4_K_M) | ~3.0 GB ✅ | ~5.5 GB ⚠️ |
| Fits in 8GB with full stack | ✅ Yes | ❌ Tight/swapping |
| Context Window | 128K ✅ | 128K ✅ |
| QA Quality | Excellent | Best |
| Summarization | Very Good | Excellent |
| Speed (tokens/sec CPU) | ~15-20 t/s | ~8-12 t/s |
| Ollama support | ✅ Native | ✅ Native |

The quality gap between Phi-3.5-mini and Qwen2.5-7B is modest (~3-5% on benchmarks), but Phi-3.5-mini uses **nearly half the RAM** and is **nearly twice as fast on CPU**. For an 8GB RAM constraint, this is the clear winner.

The 128K context window is a massive advantage for RAG — it means the system can include more retrieved chunks and longer conversation history in a single prompt, directly improving answer quality.

**Installation**:
```bash
# Via Ollama (recommended)
ollama pull phi3.5

# The Q4_K_M quantization is the default in Ollama
# Model will be cached at ~/.ollama/models/
```

**Download source**: [Ollama: phi3.5](https://ollama.com/library/phi3.5) | [HuggingFace: microsoft/Phi-3.5-mini-instruct](https://huggingface.co/microsoft/Phi-3.5-mini-instruct)

**Upgrade Path**: When the user has 16GB RAM or wants to upgrade quality, switch to `qwen2.5:7b-instruct-q4_K_M` via configuration only (FR-013 provider abstraction). No code changes required.

---

## 3. Vector Database Selection

### Candidate Comparison

| Database | Type | Persistence | Max Vectors (local) | Python API | Server Mode | Filtering | Ease of Setup |
|----------|------|-------------|---------------------|------------|-------------|-----------|---------------|
| **ChromaDB** | Embedded | ✅ SQLite-backed | Millions | ✅ Native | Optional | ✅ Metadata | pip install |
| **FAISS** (Meta) | Library | ❌ Manual save/load | Billions | ✅ via faiss-cpu | ❌ None | ❌ Manual | pip install |
| **Qdrant** | Client-Server | ✅ RocksDB | Billions | ✅ Client | ✅ Required | ✅ Rich | Docker or binary |
| **Milvus Lite** | Embedded | ✅ SQLite-backed | Millions | ✅ Native | Optional → Milvus | ✅ Rich | pip install |

### Detailed Analysis

#### FAISS
- **Pros**: Blazing fast search, used in production at massive scale, minimal overhead.
- **Cons**: It's a **library, not a database**. No built-in persistence (you must manually serialize/deserialize indexes). No metadata filtering (you'd need to build this yourself). No incremental deletion support (rebuilding index required). This creates significant development overhead for FR-005 (incremental ingestion with deletion).
- **Verdict**: ❌ Too low-level. Would require building a significant data management layer on top.

#### Qdrant
- **Pros**: Excellent filtering, rich API, production-grade, good documentation.
- **Cons**: Requires running a separate server process (Docker or binary). Adds operational complexity for a local single-user app. Overkill for the initial scope.
- **Verdict**: ⚠️ Great for production, but over-engineered for local-first single-user use.

#### Milvus Lite
- **Pros**: Embedded mode with migration path to full Milvus, rich filtering, growing ecosystem.
- **Cons**: Newer project with less community adoption than ChromaDB for local use. Heavier dependency chain. Documentation for the "Lite" embedded mode is less mature.
- **Verdict**: ⚠️ Promising but less proven for embedded local use.

#### ChromaDB
- **Pros**: **Purpose-built for AI/RAG applications**. Zero-config embedded mode with SQLite persistence. Native Python API that feels idiomatic. Built-in metadata filtering (crucial for FR-005: filtering by source document for deletion). Supports add/update/delete operations natively. Extremely easy to set up (`pip install chromadb`). Optional client-server mode for future scaling. Active community with excellent RAG documentation.
- **Cons**: Not as performant as FAISS at millions of vectors. No GPU acceleration. Less mature than Qdrant for production server deployments.
- **Verdict**: ✅ **Perfect fit for this project.**

### 🏆 RECOMMENDATION: ChromaDB

**Rationale**: ChromaDB is the only option that simultaneously provides:
1. **Zero-config embedded mode** — no Docker, no server process, just `import chromadb`
2. **Built-in persistence** — SQLite-backed, survives restarts
3. **Native CRUD operations** — add, update, delete vectors by ID (critical for FR-005 incremental ingestion)
4. **Metadata filtering** — filter by `source_file`, `chunk_position`, etc.
5. **Trivial Python integration** — matches the sentence-transformers ecosystem
6. **Migration path** — can switch to client-server mode when scaling

**Installation**:
```python
pip install chromadb

import chromadb
client = chromadb.PersistentClient(path="./data/vectordb")
collection = client.get_or_create_collection(
    name="knowledge_base",
    metadata={"hnsw:space": "cosine"}
)
```

**Storage estimate**: For 50 documents (~50K chunks) with 768-dim embeddings → ~150 MB on disk.

---

## 4. SQL Database Selection

### Candidate Comparison

| Database | Deployment | Setup Complexity | Concurrent Users | Migration Path | Python Library | Size |
|----------|-----------|-----------------|------------------|----------------|----------------|------|
| **SQLite** | Embedded file | None (built-in) | Single writer | → PostgreSQL | sqlite3 (stdlib) | 0 MB |
| **PostgreSQL** | Server | Moderate (install + config) | Unlimited | Already there | psycopg2/asyncpg | ~100 MB |

### Analysis

#### SQLite
- **Pros**: **Zero installation** — built into Python's standard library. Single file — easy backup, easy portability. Perfect for single-user local apps. No server process to manage. Excellent for the conversation history and document metadata use case (low write volume, moderate read volume). Can handle thousands of conversations without issue.
- **Cons**: Single writer at a time (fine for single-user). Not ideal if the app scales to multi-user server deployment. Schema migrations require more care.
- **Migration path**: SQLAlchemy ORM abstracts the database engine. Switching from SQLite to PostgreSQL requires only changing the connection string.

#### PostgreSQL
- **Pros**: Production-grade, unlimited concurrency, rich feature set, pgvector extension for embeddings.
- **Cons**: Requires installation, configuration, and a running server process. Overkill for local single-user use. Adds operational burden to initial setup.

### 🏆 RECOMMENDATION: SQLite (with SQLAlchemy ORM for migration path)

**Rationale**: The spec explicitly states "initial deployment is single-user." SQLite is the only choice that requires **zero setup** — it's built into Python. The conversation history workload (storing messages, retrieving conversation lists) is well within SQLite's capabilities.

**Critical design decision**: Use **SQLAlchemy** as the ORM layer. This means the codebase never contains raw SQLite calls — everything goes through SQLAlchemy models. When the time comes to deploy as a multi-user server:

```python
# Local development
DATABASE_URL = "sqlite:///./data/conversations.db"

# Production server (change only this line)
DATABASE_URL = "postgresql://user:pass@localhost:5432/knowledgebase"
```

This directly supports FR-013 (provider abstraction) and the spec's migration path requirement.

**Installation**:
```python
pip install sqlalchemy aiosqlite  # aiosqlite for async support with FastAPI
```

---

## 5. Final Recommendations Summary

| Component | Recommendation | Size | Why |
|-----------|---------------|------|-----|
| **Embedding Model** | **nomic-embed-text-v1.5** | ~520 MB disk, ~600 MB RAM | Best balance of quality (MTEB 55.0), 8K context, Matryoshka flexibility, Ollama integration, Apache 2.0 |
| **LLM Model** | **Phi-3.5-mini-Instruct (Q4_K_M)** | ~2.2 GB disk, ~3.0 GB RAM | Best quality-to-size ratio, 128K context, excellent QA/summarization, fits comfortably in 8GB |
| **Vector Database** | **ChromaDB** | ~150 MB on disk (50K chunks) | Zero-config, native CRUD, metadata filtering, Python-native, built for RAG |
| **SQL Database** | **SQLite via SQLAlchemy** | Built-in (0 MB) | Zero setup, perfect for single-user, migration to PostgreSQL via connection string |
| **LLM Runtime** | **Ollama** | ~100 MB | Unified runtime for both embedding and LLM, easy model management, REST API |

### Total Disk Space

| Item | Size |
|------|------|
| Ollama runtime | ~100 MB |
| Phi-3.5-mini Q4_K_M | ~2.2 GB |
| nomic-embed-text-v1.5 | ~520 MB |
| Vector DB (50K chunks) | ~150 MB |
| SQLite DB | < 10 MB |
| Python dependencies | ~500 MB |
| **Total** | **~3.5 GB** |

Well within the spec's 10GB disk space assumption.

### Total RAM Usage (Peak)

| Component | RAM |
|-----------|-----|
| OS + browser | ~2.0 GB |
| Python + FastAPI | ~0.3 GB |
| nomic-embed-text-v1.5 | ~0.6 GB |
| Phi-3.5-mini Q4_K_M | ~3.0 GB |
| ChromaDB index | ~0.5 GB |
| SQLAlchemy + buffers | ~0.1 GB |
| **Total** | **~6.5 GB** |

✅ **1.5 GB headroom** on an 8GB system.

### Architecture Alignment

| Spec Requirement | How Selections Support It |
|-----------------|--------------------------|
| **FR-003** Local embedding model | nomic-embed-text-v1.5 via sentence-transformers or Ollama |
| **FR-009** Local LLM | Phi-3.5-mini via Ollama |
| **FR-005** Incremental ingestion + deletion | ChromaDB native delete-by-metadata |
| **FR-008** Similarity search with threshold | ChromaDB `query()` with `where` filters and distance threshold |
| **FR-011** Conversation persistence | SQLite via SQLAlchemy |
| **FR-013** Provider abstraction | SQLAlchemy (DB swap), Ollama REST API (model swap), config-driven |
| **FR-014** Auto-download models | `ollama pull` + sentence-transformers auto-download |
| **SC-001** 50 docs < 30 min | nomic at ~3,500 sent/sec → 50K chunks in ~15 seconds for embedding; parsing is the bottleneck |
| **SC-002** Answer < 30 sec | Phi-3.5 at ~15-20 t/s → 300-400 token answer in ~20 seconds ✅ |
| **SC-007** Fully offline | All models cached locally, no network needed |

### Upgrade Path

| When | Action | Impact |
|------|--------|--------|
| User gets 16GB RAM | Switch LLM to `qwen2.5:7b-instruct` | ~10% quality improvement, config change only |
| User gets GPU | Switch to FP16 models | 5-10x faster inference, config change only |
| Multi-user deployment | Switch SQLite → PostgreSQL | Connection string change only |
| Commercial API budget | Add Claude/GPT provider adapter | Implement provider interface (FR-013), no core changes |
| Larger knowledge base | Switch ChromaDB to client-server mode | Configuration change, same API |
