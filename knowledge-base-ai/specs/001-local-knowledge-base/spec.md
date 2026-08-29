# Feature Specification: Local Knowledge Base Application

**Feature Branch**: `001-local-knowledge-base`  
**Created**: 2026-03-02  
**Status**: Draft  
**Input**: User description: "Create a local knowledge base app similar to NotebookLM that manages application knowledge locally with a two-phase approach: document ingestion with embedding, and conversational querying with a distilled LLM — designed for cost efficiency with a migration path to commercial models."

## Clarifications

### Session 2026-03-02

- Q: When a source document is removed from the knowledge folder, should the system detect this and remove its chunks/embeddings from the vector database? → A: Auto-detect deletions and remove associated data from vector DB.
- Q: Should the application support on-demand summarization of documents (a core NotebookLM feature), or Q&A only? → A: Summarize individual documents on demand (user selects a document → gets summary).
- Q: How many chunks should the system retrieve per query, and should low-relevance results be excluded? → A: Configurable top-K with a minimum similarity threshold (exclude low-relevance results).
- Q: How should the system manage conversation history when it exceeds the distilled LLM's context window? → A: Sliding window of most recent N messages (configurable).
- Q: Should users see real-time ingestion progress in the web UI, or only in logs? → A: Real-time progress indicator in web UI (document count, current file, estimated time remaining).
- Q: If the backend crashes mid-ingestion, what happens when the user restarts and triggers ingestion again? → A: Resume-safe — re-process only incomplete documents by leveraging Document.status (completed documents are skipped; processing/pending documents are re-processed from scratch).
- Q: Should the backend restrict network access to localhost only, or be accessible from the local network? → A: Bind to 127.0.0.1 (localhost only) by default; configurable via HOST env var to 0.0.0.0 for LAN/server deployment.
- Q: When the embedding model is upgraded, what should happen to existing vectors in the vector database? → A: Automatically re-embed all documents in the background when a model version mismatch is detected on startup.
- Q: What should happen if a user triggers ingestion while another job is already running? → A: Reject with 409 Conflict — only one ingestion job at a time; user must wait for the current job to complete.
- Q: Should the system restrict which directories the user can point ingestion at? → A: Validate the path exists and is a directory, resolve symlinks, and log the resolved path. No allowlist — trust the local user.
- Q: Should users be able to clear conversation history so the LLM reasons with a completely fresh context? → A: Yes — users can delete individual conversations or clear all conversations at once. Deleting a conversation removes it from the database permanently. Starting a query after clearing ensures zero prior context influences the LLM.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Document Ingestion & Indexing (Priority: P1)

As a knowledge base owner, I want to point the application at a folder of documents (Word, Markdown, PDF, Excel) so that all content is automatically chunked, embedded, and stored in a local vector database — making it searchable later.

**Why this priority**: Without ingested and indexed documents, no querying can happen. This is the foundational data pipeline that everything else depends on.

**Independent Test**: Can be fully tested by pointing the application at a folder containing sample Word, MD, PDF, and Excel files, running the ingestion process, and verifying that all documents are chunked, embedded, and retrievable from the vector database.

**Acceptance Scenarios**:

1. **Given** a folder containing 10 mixed-format documents (Word, MD, PDF, Excel), **When** I trigger the ingestion process, **Then** all documents are parsed, chunked, embedded, and stored in the vector database with no errors.
2. **Given** a folder containing a 100-page PDF, **When** I trigger ingestion, **Then** the document is split into appropriately sized chunks (preserving paragraph/section boundaries where possible) and each chunk is embedded and stored.
3. **Given** a folder with an unsupported file type (e.g., `.pptx`), **When** I trigger ingestion, **Then** the unsupported file is skipped with a clear log message, and all supported files are still processed.
7. **Given** an Excel file (`.xlsx`) with multiple sheets, **When** I trigger ingestion, **Then** all sheets are parsed with sheet names preserved as section headings, and the merged content is chunked and embedded.
4. **Given** a previously ingested folder with 1 new document added, **When** I trigger ingestion again, **Then** only the new or modified documents are processed (incremental ingestion), and existing data is not duplicated.
5. **Given** a previously ingested folder with 1 document removed, **When** I trigger ingestion again, **Then** the system detects the deletion and removes all associated chunks and embeddings from the vector database.
6. **Given** a folder of 20 documents, **When** I trigger ingestion, **Then** the web UI displays a real-time progress indicator showing the current file, documents completed vs total, and estimated time remaining.

---

### User Story 2 - Conversational Query via Web Chatbot (Priority: P2)

As a user, I want to open a web-based chatbot, type a question about my documents, and receive an accurate, context-grounded answer — so I can quickly find information without reading through dozens of files.

**Why this priority**: This is the core value proposition — once documents are indexed, users need a natural-language interface to query them. This story delivers the end-to-end user experience.

**Independent Test**: Can be fully tested by opening the web chatbot, asking a question about a known piece of information from ingested documents, and verifying the response is accurate and relevant.

**Acceptance Scenarios**:

1. **Given** documents have been ingested, **When** I type a question in the chatbot, **Then** the system retrieves relevant text chunks from the vector database and returns an LLM-generated answer grounded in those chunks.
2. **Given** I ask a question with no relevant information in the knowledge base, **When** the system processes the query, **Then** it responds honestly that no relevant information was found rather than fabricating an answer.
3. **Given** I am in an active conversation, **When** I ask a follow-up question that references context from earlier in the conversation, **Then** the system uses the conversation history to provide a coherent follow-up answer.
4. **Given** I ask a question, **When** the response is generated, **Then** the answer includes references or citations indicating which source document(s) contributed to the answer.

---

### User Story 3 - Conversation History & Session Management (Priority: P3)

As a user, I want my conversation history to be persisted across sessions so I can revisit previous questions and answers without losing context.

**Why this priority**: While not essential for basic functionality, conversation persistence significantly improves usability by allowing users to resume work, review past queries, and maintain ongoing research threads.

**Independent Test**: Can be fully tested by having a conversation, closing the browser, reopening the chatbot, and verifying that the previous conversation is accessible and context is maintained.

**Acceptance Scenarios**:

1. **Given** I have had a previous conversation, **When** I reopen the chatbot, **Then** I can see a list of my past conversations and select one to continue.
2. **Given** I am in an active conversation, **When** I choose to start a new conversation, **Then** a fresh session begins without mixing in previous context.
3. **Given** multiple conversations exist, **When** I view the conversation list, **Then** they are displayed with timestamps and a preview of the first question.
4. **Given** I want a completely fresh start, **When** I choose to delete a single conversation or clear all conversations, **Then** the selected conversations are permanently removed from the database and the LLM operates with zero prior context on subsequent queries.
5. **Given** I have cleared all conversations, **When** I open the chatbot, **Then** the conversation list is empty and any new question is answered without any prior conversation context influencing the response.

---

### User Story 4 - On-Demand Document Summarization (Priority: P4)

As a user, I want to select an ingested document and request a summary so I can quickly understand its key points without reading the entire file.

**Why this priority**: Summarization is a core NotebookLM-like capability that adds significant value beyond Q&A. Per-document summaries are feasible with a distilled LLM since input is bounded by a single document's chunks.

**Independent Test**: Can be fully tested by ingesting a document, selecting it in the UI, requesting a summary, and verifying the output captures the document's main topics and conclusions.

**Acceptance Scenarios**:

1. **Given** a document has been ingested, **When** I select it and request a summary, **Then** the system generates a concise summary covering the document's key points using the local LLM.
2. **Given** a large document (100+ pages), **When** I request a summary, **Then** the system processes its chunks iteratively and produces a coherent summary within a reasonable time.
3. **Given** a summary has been generated, **When** I view it, **Then** it includes references to the sections/pages that contributed to each key point.

---

### User Story 5 - Model Provider Abstraction (Priority: P5)

As a developer, I want the embedding and LLM model integrations to be abstracted behind a provider interface so that I can switch from local distilled models to commercial APIs (Copilot, Claude) without refactoring the core application.

**Why this priority**: While the initial implementation uses local distilled models for cost efficiency, the architecture must be designed to accommodate commercial models in the future. This is an architectural concern that should be addressed early.

**Independent Test**: Can be fully tested by configuring the application to use a mock commercial provider and verifying that the system operates identically (ingestion, querying, answering) without any changes to the core logic.

**Acceptance Scenarios**:

1. **Given** the application is configured to use local distilled models, **When** I change the configuration to a different model provider, **Then** the application uses the new provider without code changes to the ingestion or query pipelines.
2. **Given** a new model provider is added (e.g., Claude API), **When** I implement only the provider adapter, **Then** the rest of the application works seamlessly with the new provider.

---

### Edge Cases

- What happens when the document folder is empty? → The system should log a warning and exit gracefully with a message indicating no documents were found.
- What happens when a document is corrupted or unreadable? → The system should skip the file, log the error with the filename, and continue processing remaining documents.
- What happens when the vector database storage exceeds available disk space? → The system should detect low disk space and warn the user before ingestion fails mid-process.
- What happens when the local LLM model file is missing or corrupted? → The system should display a clear error message with instructions to re-download the model.
- What happens when a very large document (500+ pages) is ingested? → The system should handle it with streaming/chunked processing to avoid memory exhaustion.
- What happens when two users access the chatbot simultaneously? → The system should maintain separate conversation contexts per session.
- What happens when a previously ingested document is deleted from the source folder? → On the next ingestion run, the system detects the deletion and removes all associated chunks and embeddings from the vector database.
- What happens when a conversation exceeds the LLM's context window? → The system uses a sliding window of the most recent N messages (configurable), ensuring older messages are excluded from the LLM prompt but remain persisted in the SQL database for browsing.
- What happens when the backend crashes mid-ingestion? → On restart, the system leverages Document.status to skip completed documents and re-process any documents still marked as processing or pending. No chunk-level checkpointing is needed.
- What happens when another device on the local network tries to access the application? → By default, the backend binds to 127.0.0.1 (localhost only), so external devices cannot connect. Users can set the HOST env var to 0.0.0.0 to allow LAN access.
- What happens when the embedding model is upgraded to a new version? → On startup, the system compares the configured model version against the version stored in existing vectors. If they differ, it automatically re-embeds all documents in the background, notifying the user via the UI and logs.
- What happens when a user triggers ingestion while another ingestion job is already running? → The system rejects the request with HTTP 409 Conflict and returns a message indicating the active job's ID and status. Only one ingestion job can run at a time.
- What happens when the user provides an invalid or non-existent source folder path? → The system validates the path, returning HTTP 400 if it does not exist, is not a directory, or is not readable. Symlinks are resolved and the absolute path is logged.
- What happens when a user clears all conversations? → All conversation records and their associated messages are permanently deleted from the database. The system confirms the action before proceeding. The chatbot returns to an empty state with no prior context.
- What happens when a user deletes the currently active conversation? → The conversation is deleted and the user is redirected to a new empty conversation. No prior context from the deleted conversation is carried over.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse and extract text from Word (.docx), Markdown (.md), and PDF (.pdf) files.
- **FR-002**: System MUST split extracted text into chunks of configurable size with configurable overlap, preserving paragraph and section boundaries where possible.
- **FR-003**: System MUST generate vector embeddings for each text chunk using a locally hosted distilled embedding model.
- **FR-004**: System MUST store all embedding vectors and their associated metadata (source file, chunk position, text content) in a local vector database.
- **FR-005**: System MUST support incremental ingestion — detecting new, modified, and deleted files. When a source file is removed from the knowledge folder, the system MUST automatically remove its associated chunks and embeddings from the vector database. If ingestion is interrupted (crash, restart), the system MUST be resume-safe: documents with status `completed` are skipped, while documents with status `processing` or `pending` are re-processed from scratch on the next run.
- **FR-006**: System MUST provide a web-based chatbot interface where users can type questions and receive answers.
- **FR-007**: System MUST convert user questions into embedding vectors using the same embedding model used during ingestion.
- **FR-008**: System MUST perform similarity search against the vector database to retrieve the most relevant text chunks for a given query, using a configurable top-K parameter and a configurable minimum similarity threshold. Chunks scoring below the threshold MUST be excluded from the results even if fewer than K chunks are returned.
- **FR-009**: System MUST send the retrieved context and the user's question to a locally hosted distilled LLM model for answer generation.
- **FR-010**: System MUST include source document references in generated answers so users can trace information back to original files.
- **FR-011**: System MUST maintain conversation history in-memory during an active session and persist it to a SQL database for cross-session retrieval. When sending context to the LLM, the system MUST use a configurable sliding window of the most recent N messages to stay within the model's context limit.
- **FR-012**: System MUST allow users to start new conversations and navigate between past conversations.
- **FR-013**: System MUST abstract the embedding model and LLM model behind a provider interface, allowing future replacement with commercial APIs (e.g., Copilot, Claude) via configuration only.
- **FR-014**: System MUST automatically download and cache the required local distilled models on first run if they are not already present.
- **FR-015**: System MUST log all processing events (ingestion progress, errors, query processing) using structured JSON logging via `structlog`. Every HTTP request MUST carry a correlation `request_id` propagated through all downstream log entries. Log entries MUST include contextual fields (`job_id`, `document_id`, `conversation_id`, `file_name`, `duration_ms`) as applicable. Log levels MUST be used consistently: INFO for normal operations, WARNING for recoverable issues, ERROR for failures.
- **FR-016**: System MUST handle unsupported file types gracefully by skipping them and logging a warning.
- **FR-017**: System MUST allow users to select an ingested document and generate an on-demand summary of its content using the local distilled LLM model.
- **FR-018**: System MUST produce document summaries that reference the source sections or pages that contributed to each key point.
- **FR-019**: System MUST display real-time ingestion progress in the web UI, including the current document being processed, the number of documents completed vs total, and an estimated time remaining.
- **FR-020**: System MUST bind the backend server to `127.0.0.1` (localhost only) by default to prevent unintended network exposure. The bind address MUST be configurable via a `HOST` environment variable (e.g., set to `0.0.0.0` for LAN or server deployment).
- **FR-021**: System MUST track the embedding model version used for each vector in the vector database. On startup, if the configured embedding model version differs from the version stored in existing vectors, the system MUST automatically trigger a background re-ingestion to re-embed all documents with the new model. The system MUST notify the user via the UI and logs that re-embedding is in progress.
- **FR-022**: System MUST enforce that only one ingestion job can run at a time. If a user triggers ingestion while a job is already running, the system MUST reject the request with HTTP 409 Conflict and a message indicating the current job's status.
- **FR-023**: System MUST validate that the ingestion `source_folder` path exists, is a directory, and is readable. Symbolic links MUST be resolved before processing. The resolved absolute path MUST be logged at INFO level. No allowlist restriction is applied — the local user is trusted.
- **FR-024**: System MUST allow users to delete individual conversations or clear all conversations at once. Deleting a conversation MUST permanently remove the conversation record and all associated messages from the database. After deletion, the LLM MUST operate with zero prior context from deleted conversations. The system MUST prompt for user confirmation before executing a bulk "clear all" operation.

### Key Entities

- **Document**: A source file (Word, MD, PDF, Excel (.xlsx)) from the knowledge folder. Key attributes: file path, file type, file hash (for change detection), last ingested timestamp.
- **Chunk**: A segment of text extracted from a Document. Key attributes: text content, position/order within document, parent document reference.
- **Embedding**: A vector representation of a Chunk. Key attributes: vector data, associated chunk reference, model version used.
- **Conversation**: A session of questions and answers between a user and the system. Key attributes: creation timestamp, title/preview, list of messages.
- **Message**: A single exchange within a Conversation. Key attributes: role (user/assistant), content, timestamp, source references (for assistant messages).
- **Model Provider**: An abstraction representing the embedding or LLM service. Key attributes: provider type (local/commercial), model name, configuration parameters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can ingest a folder of 50 mixed-format documents (totaling ~500 pages, including Excel spreadsheets) in under 30 minutes on a standard consumer laptop.
- **SC-002**: Users receive answers to questions within 30 seconds of submitting them (including embedding, retrieval, and LLM generation).
- **SC-003**: Answers reference the correct source documents at least 80% of the time when the information exists in the knowledge base.
- **SC-004**: The system correctly identifies and responds "no relevant information found" for at least 90% of queries about topics not covered in the knowledge base.
- **SC-005**: Users can resume a previous conversation and the system correctly uses prior context for follow-up questions.
- **SC-006**: Switching from local distilled models to a commercial provider requires only configuration changes — no modifications to core application logic.
- **SC-007**: The application runs entirely locally with no external network dependencies during normal operation (after initial model download).
- **SC-008**: All three supported document formats (Word, MD, PDF) are parsed and indexed with at least 95% text extraction accuracy.
- **SC-009**: Users can generate a summary of a single ingested document in under 60 seconds on a standard consumer laptop.

### Quality Gates

- **QG-001**: All Python code MUST pass type checking (`mypy --strict`) and linting (`ruff`) before merge.
- **QG-002**: All TypeScript code MUST pass type checking (`tsc --noEmit`) and linting (`eslint`) before merge.
- **QG-003**: Test coverage MUST NOT decrease with new changes.
- **QG-004**: API contract changes MUST be reflected in `contracts/api-contracts.md` before implementation.

## Assumptions

- The user has a consumer-grade laptop or desktop with at least 8GB RAM and 10GB free disk space for models and vector storage.
- The initial deployment is single-user (one person running the application on their local machine). Multi-user support is out of scope for the first release.
- The user accepts reduced answer quality from distilled models compared to commercial alternatives — this is an explicit trade-off for cost efficiency and local operation.
- Internet access is required only for the initial setup (downloading models). All subsequent operations run offline.
- The document folder structure is flat or shallow — the system will recursively scan subfolders.
- The user is comfortable with a web browser interface (no native desktop app required).

## Scope & Boundaries

### In Scope

- Document parsing for Word, Markdown, and PDF formats
- Text chunking with configurable parameters
- Local embedding generation using distilled models
- Vector storage and similarity search
- Web-based conversational chatbot interface
- Context-grounded answer generation using a local distilled LLM
- Conversation history persistence in a SQL database
- Provider abstraction layer for future commercial model integration
- Incremental document ingestion (change detection)
- Source citation in answers
- On-demand per-document summarization

### Out of Scope

- Support for additional file formats (spreadsheets, images, audio, video)
- Multi-user authentication and access control
- Cloud-hosted SaaS or managed service (note: self-hosted server deployment via Docker Compose IS in scope)
- Fine-tuning or training custom models
- Real-time collaborative editing of the knowledge base
- Mobile application
- Document editing or annotation through the application
- Integration with external knowledge management systems
- Collection-level summarization (summarizing the entire knowledge base at once)
