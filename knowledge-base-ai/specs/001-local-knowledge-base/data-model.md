# Data Model: Local Knowledge Base Application

**Feature**: 001-local-knowledge-base  
**Date**: 2026-03-02

---

## 1. SQL Database (SQLite / PostgreSQL via SQLAlchemy)

### 1.1 Document

Tracks source files in the knowledge folder for incremental ingestion.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique document identifier |
| file_path | VARCHAR(1024) | NOT NULL, UNIQUE | Absolute path to the source file |
| file_name | VARCHAR(255) | NOT NULL | Filename for display |
| file_type | VARCHAR(10) | NOT NULL | `pdf`, `docx`, `md` |
| file_hash | VARCHAR(64) | NOT NULL | SHA-256 hash for change detection |
| file_size_bytes | BIGINT | NOT NULL | File size in bytes |
| chunk_count | INTEGER | NOT NULL, DEFAULT 0 | Number of chunks generated |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | `pending`, `processing`, `completed`, `failed` |
| error_message | TEXT | NULLABLE | Error details if status = failed |
| ingested_at | TIMESTAMP | NULLABLE | When ingestion completed |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Record creation time |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Last modification time |

**Indexes**: `file_path` (UNIQUE), `file_hash`, `status`

**State Transitions**:
```
pending → processing → completed
                    → failed
```

---

### 1.2 Conversation

A chat session containing a sequence of messages.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique conversation identifier |
| title | VARCHAR(255) | NULLABLE | Auto-generated from first question or user-set |
| preview | VARCHAR(500) | NULLABLE | First user message, truncated for list display |
| message_count | INTEGER | NOT NULL, DEFAULT 0 | Total messages in conversation |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When conversation started |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Last message timestamp |

**Indexes**: `created_at` (DESC), `updated_at` (DESC)

---

### 1.3 Message

A single exchange (user question or assistant answer) within a conversation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique message identifier |
| conversation_id | UUID | FK → Conversation.id, NOT NULL | Parent conversation |
| role | VARCHAR(10) | NOT NULL | `user` or `assistant` |
| content | TEXT | NOT NULL | Message text content |
| source_references | JSON | NULLABLE | Array of `{document_id, file_name, chunk_ids, relevance_score}` |
| token_count | INTEGER | NULLABLE | Approximate token count for context window management |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When message was created |

**Indexes**: `conversation_id` + `created_at` (composite, for sliding window queries)

**Relationships**: 
- Conversation (1) → Messages (N) — CASCADE DELETE

---

### 1.4 DocumentSummary

Cached summaries generated on demand for individual documents.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique summary identifier |
| document_id | UUID | FK → Document.id, NOT NULL, UNIQUE | Source document |
| summary_text | TEXT | NOT NULL | Generated summary content |
| section_references | JSON | NULLABLE | Array of `{section, page, contribution}` |
| model_version | VARCHAR(100) | NOT NULL | LLM model used to generate |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW | When summary was generated |

**Indexes**: `document_id` (UNIQUE)

**Relationships**:
- Document (1) → DocumentSummary (0..1) — CASCADE DELETE

---

### 1.5 IngestionJob

Tracks batch ingestion runs for progress reporting and audit.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique job identifier |
| source_folder | VARCHAR(1024) | NOT NULL | Path to knowledge folder |
| trigger_reason | VARCHAR(20) | NOT NULL, DEFAULT 'user' | `user` (manual trigger) or `reembed` (auto model-version mismatch) |
| total_files | INTEGER | NOT NULL | Total files discovered |
| processed_files | INTEGER | NOT NULL, DEFAULT 0 | Files processed so far |
| new_files | INTEGER | NOT NULL, DEFAULT 0 | New files added |
| modified_files | INTEGER | NOT NULL, DEFAULT 0 | Modified files re-processed |
| deleted_files | INTEGER | NOT NULL, DEFAULT 0 | Deleted files cleaned up |
| skipped_files | INTEGER | NOT NULL, DEFAULT 0 | Unsupported/errored files |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'running' | `running`, `completed`, `failed` |
| error_message | TEXT | NULLABLE | Error details if failed |
| started_at | TIMESTAMP | NOT NULL, DEFAULT NOW | Job start time |
| completed_at | TIMESTAMP | NULLABLE | Job completion time |

**Indexes**: `started_at` (DESC), `status`

**State Transitions**:
```
running → completed
       → failed
```

---

## 2. Vector Database (ChromaDB)

### 2.1 Collection: `knowledge_base`

Each record in ChromaDB represents a single text chunk with its embedding vector.

| Field | ChromaDB Mapping | Description |
|-------|-----------------|-------------|
| id | `id` | UUID string — matches format `{document_id}_{chunk_index}` |
| embedding | `embedding` | 768-dimension float vector (nomic-embed-text-v1.5) |
| text | `document` | Raw text content of the chunk |
| document_id | `metadata.document_id` | FK reference to SQL Document.id |
| file_name | `metadata.file_name` | Source filename for citation |
| file_path | `metadata.file_path` | Source file path |
| chunk_index | `metadata.chunk_index` | Position within the parent document (0-based) |
| total_chunks | `metadata.total_chunks` | Total chunks in parent document |
| page_number | `metadata.page_number` | Page number (for PDF) or section (for MD/DOCX), nullable |
| model_version | `metadata.model_version` | Embedding model version used |
| ingested_at | `metadata.ingested_at` | ISO timestamp of ingestion |

**Distance Metric**: Cosine similarity

**Operations**:
- **Add**: During ingestion, add chunks for new/modified documents
- **Delete**: On file deletion or re-ingestion, delete by `metadata.document_id` filter
- **Query**: Similarity search with top-K + threshold, optional metadata filters

---

## 3. Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────┐
│   IngestionJob   │       │     Document      │
│─────────────────│       │──────────────────│
│ id (PK)          │       │ id (PK)           │
│ source_folder    │       │ file_path (UQ)    │
│ trigger_reason   │       │ file_name         │
│ total_files      │       │ file_type         │
│ processed_files  │       │ file_hash         │
│ status           │       │ status            │
│ started_at       │       │ ingested_at       │
│ completed_at     │       │                   │
└─────────────────┘       └────────┬─────────┘
                                    │ 1
                                    │
                          ┌─────────┴──────────┐
                          │                     │
                     0..1 ▼                  N  ▼
              ┌──────────────────┐   ┌───────────────────┐
              │ DocumentSummary  │   │  ChromaDB Chunks   │
              │──────────────────│   │───────────────────│
              │ id (PK)          │   │ id                 │
              │ document_id (FK) │   │ embedding [768]    │
              │ summary_text     │   │ text               │
              │ model_version    │   │ document_id (meta) │
              └──────────────────┘   │ chunk_index (meta) │
                                     │ page_number (meta) │
                                     └───────────────────┘

┌─────────────────┐       ┌──────────────────┐
│  Conversation    │ 1───N │     Message       │
│─────────────────│       │──────────────────│
│ id (PK)          │       │ id (PK)           │
│ title            │       │ conversation_id   │
│ preview          │       │ role              │
│ message_count    │       │ content           │
│ created_at       │       │ source_references │
│ updated_at       │       │ token_count       │
└─────────────────┘       │ created_at        │
                           └──────────────────┘
```

---

## 4. Data Validation Rules

| Entity | Rule | Description |
|--------|------|-------------|
| Document | file_type IN ('pdf', 'docx', 'md') | Only supported formats |
| Document | file_hash is SHA-256 | 64-character hex string |
| Document | file_path is unique | No duplicate file tracking |
| Chunk (ChromaDB) | embedding dimension = 768 | Must match nomic-embed-text-v1.5 output |
| Chunk (ChromaDB) | chunk_index >= 0 | Non-negative position |
| Message | role IN ('user', 'assistant') | Only two roles |
| Message | content length > 0 | Non-empty messages |
| Conversation | message_count >= 0 | Non-negative count |
| IngestionJob | processed_files <= total_files | Cannot exceed total |
| IngestionJob | trigger_reason IN ('user', 'reembed') | Only two trigger types |

---

## 5. Data Lifecycle

### Document Ingestion
1. Scan folder → create/update Document records (status: `pending`)
2. For each pending document → parse, chunk, embed → store in ChromaDB
3. Update Document record (status: `completed`, chunk_count)
4. Detect missing files → delete Document + ChromaDB chunks (cascade)
5. On crash/restart: documents with status `completed` are skipped; `processing`/`pending` are re-processed (FR-005)

### Model Version Check (Startup)
1. On startup, read `model_version` from any existing ChromaDB vector metadata
2. Compare to the currently configured `EMBEDDING_MODEL` version
3. If mismatch detected → automatically create IngestionJob with `trigger_reason='reembed'`
4. Re-embed all documents in background; notify user via UI and logs (FR-021)

### Conversation Flow
1. User starts new conversation → create Conversation record
2. User sends message → create Message (role: `user`)
3. Embed question → query ChromaDB → retrieve top-K chunks
4. Send context + sliding window of recent Messages to LLM
5. Store response → create Message (role: `assistant`, source_references)
6. Update Conversation (message_count, updated_at)

### Document Summary
1. User requests summary for Document
2. Retrieve all chunks for document from ChromaDB
3. Send chunks iteratively to LLM for summarization
4. Store result in DocumentSummary (or update if exists)

### Conversation Deletion (FR-024)
1. **Delete single**: User deletes a conversation → CASCADE DELETE removes all associated Messages → conversation removed from list
2. **Clear all**: User confirms bulk clear → DELETE all Conversation records → CASCADE DELETE removes all Messages → conversation list becomes empty
3. After deletion, new queries operate with zero prior context from deleted conversations
4. Deletion is permanent — no soft-delete or undo
