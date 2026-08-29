# API Contracts: Backend REST API

**Feature**: 001-local-knowledge-base  
**Date**: 2026-03-02  
**Base URL**: `http://localhost:8000/api/v1`  
**Protocol**: REST + WebSocket

---

## 0. Common Headers

All responses MUST include the following header:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | UUID correlation ID for request tracing. If the client sends `X-Request-ID` in the request, the server echoes it; otherwise the server generates one. This ID is propagated through all structured log entries for the request. |

---

## 1. Document & Ingestion APIs

### 1.1 POST /ingestion/start

Trigger document ingestion from a configured knowledge folder.

**Request Body**:
```json
{
  "source_folder": "/path/to/documents"   // Optional — uses configured default if omitted
}
```

**Response** `202 Accepted`:
```json
{
  "job_id": "uuid-string",
  "status": "running",
  "total_files": 25,
  "source_folder": "/path/to/documents",
  "started_at": "2026-03-02T10:00:00Z"
}
```

**Errors**:
- `400` — Invalid or inaccessible folder path (path does not exist, is not a directory, or is not readable; symlinks are resolved before validation — FR-023)
- `409` — Ingestion already in progress (only one ingestion job at a time — FR-022)

---

### 1.2 GET /ingestion/status/{job_id}

Get current status of an ingestion job.

**Response** `200 OK`:
```json
{
  "job_id": "uuid-string",
  "status": "running",
  "total_files": 25,
  "processed_files": 12,
  "new_files": 8,
  "modified_files": 3,
  "deleted_files": 1,
  "skipped_files": 0,
  "current_file": "architecture-guide.pdf",
  "estimated_remaining_seconds": 180,
  "started_at": "2026-03-02T10:00:00Z",
  "completed_at": null
}
```

**Errors**:
- `404` — Job not found

---

### 1.3 WS /ingestion/progress/{job_id}

WebSocket for real-time ingestion progress updates.

**Server → Client Messages**:
```json
{
  "type": "progress",
  "job_id": "uuid-string",
  "processed_files": 13,
  "total_files": 25,
  "current_file": "api-spec.docx",
  "estimated_remaining_seconds": 160
}
```

```json
{
  "type": "file_complete",
  "file_name": "architecture-guide.pdf",
  "chunks_created": 42,
  "duration_seconds": 12.5
}
```

```json
{
  "type": "file_error",
  "file_name": "corrupted.pdf",
  "error": "Failed to parse PDF: file appears corrupted"
}
```

```json
{
  "type": "completed",
  "job_id": "uuid-string",
  "total_files": 25,
  "new_files": 8,
  "modified_files": 3,
  "deleted_files": 1,
  "skipped_files": 1,
  "duration_seconds": 420.3
}
```

```json
{
  "type": "reembed_started",
  "job_id": "uuid-string",
  "reason": "Embedding model changed from nomic-embed-text-v1.5 to nomic-embed-text-v2.0",
  "total_files": 25
}
```

---

### 1.4 GET /documents

List all ingested documents.

**Query Parameters**:
- `status` (optional): Filter by status (`completed`, `failed`, `pending`)
- `page` (optional, default: 1): Page number
- `page_size` (optional, default: 20): Results per page

**Response** `200 OK`:
```json
{
  "documents": [
    {
      "id": "uuid-string",
      "file_name": "architecture-guide.pdf",
      "file_type": "pdf",
      "file_path": "/docs/architecture-guide.pdf",
      "chunk_count": 42,
      "status": "completed",
      "ingested_at": "2026-03-02T10:05:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

---

### 1.5 GET /documents/{document_id}

Get details of a specific document including its chunks summary.

**Response** `200 OK`:
```json
{
  "id": "uuid-string",
  "file_name": "architecture-guide.pdf",
  "file_type": "pdf",
  "file_path": "/docs/architecture-guide.pdf",
  "file_size_bytes": 1048576,
  "chunk_count": 42,
  "status": "completed",
  "ingested_at": "2026-03-02T10:05:00Z",
  "has_summary": true
}
```

**Errors**:
- `404` — Document not found

---

### 1.6 DELETE /documents/{document_id}

Remove a document and all its associated chunks/embeddings.

**Response** `200 OK`:
```json
{
  "message": "Document and 42 chunks removed successfully",
  "document_id": "uuid-string"
}
```

**Errors**:
- `404` — Document not found

---

## 2. Conversation APIs

### 2.1 POST /conversations

Create a new conversation.

**Request Body**: (empty or optional)
```json
{
  "title": "Optional custom title"
}
```

**Response** `201 Created`:
```json
{
  "id": "uuid-string",
  "title": null,
  "preview": null,
  "message_count": 0,
  "created_at": "2026-03-02T11:00:00Z"
}
```

---

### 2.2 GET /conversations

List all conversations.

**Query Parameters**:
- `page` (optional, default: 1): Page number
- `page_size` (optional, default: 20): Results per page

**Response** `200 OK`:
```json
{
  "conversations": [
    {
      "id": "uuid-string",
      "title": "Architecture Questions",
      "preview": "What is the recommended service pattern?",
      "message_count": 8,
      "created_at": "2026-03-02T11:00:00Z",
      "updated_at": "2026-03-02T11:15:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

---

### 2.3 GET /conversations/{conversation_id}

Get a conversation with its full message history.

**Response** `200 OK`:
```json
{
  "id": "uuid-string",
  "title": "Architecture Questions",
  "messages": [
    {
      "id": "uuid-string",
      "role": "user",
      "content": "What is the recommended service pattern?",
      "source_references": null,
      "created_at": "2026-03-02T11:00:05Z"
    },
    {
      "id": "uuid-string",
      "role": "assistant",
      "content": "Based on the architecture guide, the recommended pattern is...",
      "source_references": [
        {
          "document_id": "uuid-string",
          "file_name": "architecture-guide.pdf",
          "page_number": 12,
          "relevance_score": 0.92
        }
      ],
      "created_at": "2026-03-02T11:00:25Z"
    }
  ],
  "created_at": "2026-03-02T11:00:00Z",
  "updated_at": "2026-03-02T11:00:25Z"
}
```

**Errors**:
- `404` — Conversation not found

---

### 2.4 DELETE /conversations/{conversation_id}

Delete a conversation and all its messages.

**Response** `200 OK`:
```json
{
  "message": "Conversation deleted successfully",
  "conversation_id": "uuid-string"
}
```

**Errors**:
- `404` — Conversation not found

---

### 2.5 DELETE /conversations

Delete all conversations and their messages (bulk clear). Requires `confirm=true` query parameter to prevent accidental deletion (FR-024).

**Query Parameters**:
- `confirm` (required, boolean) — Must be `true` to execute the deletion

**Response** `200 OK`:
```json
{
  "message": "All conversations deleted successfully",
  "deleted_count": 15
}
```

**Errors**:
- `400` — Missing or false `confirm` parameter

---

## 3. Chat APIs

### 3.1 POST /conversations/{conversation_id}/messages

Send a user question and receive an LLM-generated answer.

**Request Body**:
```json
{
  "content": "What is the recommended service pattern for microservices?"
}
```

**Response** `200 OK`:
```json
{
  "user_message": {
    "id": "uuid-string",
    "role": "user",
    "content": "What is the recommended service pattern for microservices?",
    "created_at": "2026-03-02T11:05:00Z"
  },
  "assistant_message": {
    "id": "uuid-string",
    "role": "assistant",
    "content": "Based on the architecture guide (page 12-15), the recommended pattern is...",
    "source_references": [
      {
        "document_id": "uuid-string",
        "file_name": "architecture-guide.pdf",
        "page_number": 12,
        "relevance_score": 0.92
      },
      {
        "document_id": "uuid-string",
        "file_name": "design-patterns.md",
        "page_number": null,
        "relevance_score": 0.85
      }
    ],
    "created_at": "2026-03-02T11:05:18Z"
  }
}
```

**Errors**:
- `404` — Conversation not found
- `503` — LLM model unavailable

---

### 3.2 WS /conversations/{conversation_id}/stream

WebSocket for streaming LLM responses token-by-token.

**Client → Server**:
```json
{
  "type": "question",
  "content": "What is the recommended service pattern?"
}
```

**Server → Client**:
```json
{ "type": "user_message_saved", "message_id": "uuid-string" }
```
```json
{ "type": "sources_found", "sources": [{"file_name": "architecture-guide.pdf", "page_number": 12, "relevance_score": 0.92}] }
```
```json
{ "type": "token", "content": "Based " }
{ "type": "token", "content": "on " }
{ "type": "token", "content": "the " }
```
```json
{ "type": "complete", "message_id": "uuid-string" }
```
```json
{ "type": "error", "message": "LLM model unavailable" }
```

---

## 4. Document Summary APIs

### 4.1 POST /documents/{document_id}/summary

Generate or regenerate a summary for a document.

**Response** `200 OK`:
```json
{
  "document_id": "uuid-string",
  "file_name": "architecture-guide.pdf",
  "summary_text": "This document covers the overall system architecture including...",
  "section_references": [
    { "section": "Chapter 1: Overview", "page": 1, "contribution": "System goals and constraints" },
    { "section": "Chapter 3: Service Patterns", "page": 12, "contribution": "Recommended microservice patterns" }
  ],
  "model_version": "phi3.5:3.8b-mini-instruct-q4_K_M",
  "created_at": "2026-03-02T12:00:00Z"
}
```

**Errors**:
- `404` — Document not found
- `409` — Document not yet ingested (status != completed)
- `503` — LLM model unavailable

---

### 4.2 GET /documents/{document_id}/summary

Get the cached summary for a document (if it exists).

**Response** `200 OK`: Same as POST response above.

**Errors**:
- `404` — Document or summary not found

---

## 5. System APIs

### 5.1 GET /health

Health check endpoint.

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "components": {
    "database": "connected",
    "vector_db": "connected",
    "embedding_model": "loaded",
    "llm_model": "loaded"
  },
  "version": "1.0.0",
  "reembedding": {
    "in_progress": false,
    "job_id": null,
    "reason": null
  }
}
```

When a model version mismatch triggers automatic re-embedding (FR-021):
```json
{
  "status": "healthy",
  "components": {
    "database": "connected",
    "vector_db": "connected",
    "embedding_model": "loaded",
    "llm_model": "loaded"
  },
  "version": "1.0.0",
  "reembedding": {
    "in_progress": true,
    "job_id": "uuid-string",
    "reason": "Embedding model changed from nomic-embed-text-v1.5 to nomic-embed-text-v2.0"
  }
}
```

---

### 5.2 GET /config

Get current configuration (non-sensitive).

**Response** `200 OK`:
```json
{
  "embedding": {
    "model": "nomic-embed-text-v1.5",
    "dimensions": 768,
    "provider": "sentence-transformers"
  },
  "llm": {
    "model": "phi3.5:3.8b-mini-instruct-q4_K_M",
    "context_window": 4096,
    "provider": "ollama"
  },
  "retrieval": {
    "top_k": 5,
    "similarity_threshold": 0.7
  },
  "chunking": {
    "chunk_size": 1000,
    "chunk_overlap": 200
  },
  "conversation": {
    "sliding_window_messages": 10
  }
}
```

---

## 6. Common Error Response Format

All error responses follow this structure:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Document with id 'uuid-string' not found",
    "request_id": "uuid-correlation-id",
    "details": {}
  }
}
```

**Standard Error Codes**:

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | VALIDATION_ERROR | Invalid request body or parameters |
| 404 | RESOURCE_NOT_FOUND | Requested entity does not exist |
| 409 | CONFLICT | Operation conflicts with current state |
| 500 | INTERNAL_ERROR | Unexpected server error |
| 503 | SERVICE_UNAVAILABLE | Required service (LLM, embedding) not available |
