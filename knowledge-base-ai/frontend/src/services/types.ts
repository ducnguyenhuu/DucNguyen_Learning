/**
 * TypeScript type definitions matching all API request/response contracts.
 *
 * These types mirror the backend Pydantic schemas and must be kept in sync
 * with the API contracts documented in:
 *   specs/001-local-knowledge-base/contracts/api-contracts.md
 */

// ── Shared ────────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
  details: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: ApiError;
}

// ── Documents ─────────────────────────────────────────────────────────────

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type FileType = 'pdf' | 'docx' | 'md';

export interface Document {
  id: string;
  file_path: string;
  file_name: string;
  file_type: FileType;
  file_hash: string;
  file_size_bytes: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  ingested_at: string | null;
  created_at: string;
  updated_at: string;
  has_summary?: boolean;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

// ── Ingestion ─────────────────────────────────────────────────────────────

export type IngestionJobStatus = 'running' | 'completed' | 'failed';
export type TriggerReason = 'user' | 'reembed';

export interface IngestionJob {
  id: string;
  source_folder: string;
  trigger_reason: TriggerReason;
  total_files: number;
  processed_files: number;
  new_files: number;
  modified_files: number;
  deleted_files: number;
  skipped_files: number;
  status: IngestionJobStatus;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  progress_pct: number;
}

export interface StartIngestionRequest {
  source_folder?: string;
}

export interface StartIngestionResponse {
  job_id: string;
  message: string;
}

// ── WebSocket: Ingestion Progress ─────────────────────────────────────────

export type IngestionWsMessageType =
  | 'progress'
  | 'file_complete'
  | 'file_error'
  | 'completed'
  | 'error';

export interface IngestionProgressMessage {
  type: 'progress';
  job_id: string;
  processed_files: number;
  total_files: number;
  progress_pct: number;
  current_file: string;
}

export interface FileCompleteMessage {
  type: 'file_complete';
  job_id: string;
  file_name: string;
  chunk_count: number;
}

export interface FileErrorMessage {
  type: 'file_error';
  job_id: string;
  file_name: string;
  error: string;
}

export interface IngestionCompletedMessage {
  type: 'completed';
  job_id: string;
  total_files: number;
  new_files: number;
  modified_files: number;
  deleted_files: number;
  skipped_files: number;
  duration_ms: number;
}

export type IngestionWsMessage =
  | IngestionProgressMessage
  | FileCompleteMessage
  | FileErrorMessage
  | IngestionCompletedMessage;

// ── Conversations ─────────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string | null;
  preview: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
}

export interface ConversationDetailResponse {
  id: string;
  title: string | null;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface CreateConversationRequest {
  title?: string;
}

// ── Messages & Chat ───────────────────────────────────────────────────────

export type MessageRole = 'user' | 'assistant';

export interface SourceReference {
  document_id: string;
  file_name: string;
  page_number: number | null;
  relevance_score: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  source_references: SourceReference[] | null;
  token_count: number | null;
  created_at: string;
}

export interface SendMessageRequest {
  content: string;
}

export interface SendMessageResponse {
  user_message: Message;
  assistant_message: Message;
}

// ---------------------------------------------------------------------------
// Chat UI types (used by useChat hook and chat components)
// ---------------------------------------------------------------------------

/**
 * A simplified, UI-friendly message type used by the chat hook and
 * rendering components. Unlike the full Message type, this doesn't require
 * conversation_id or token_count (which are server-side concerns).
 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  source_references: SourceReference[] | null;
  created_at: string;
}

// ── WebSocket: Chat Streaming ─────────────────────────────────────────────

export type ChatWsMessageType =
  | 'user_message_saved'
  | 'sources_found'
  | 'token'
  | 'complete'
  | 'error';

export interface UserMessageSavedWs {
  type: 'user_message_saved';
  message_id: string;
}

export interface SourcesFoundWs {
  type: 'sources_found';
  sources: SourceReference[];
}

export interface TokenWs {
  type: 'token';
  content: string;
}

export interface ChatCompleteWs {
  type: 'complete';
  message_id: string;
}

export interface ChatErrorWs {
  type: 'error';
  code: string;
  message: string;
}

export type ChatWsMessage =
  | UserMessageSavedWs
  | SourcesFoundWs
  | TokenWs
  | ChatCompleteWs
  | ChatErrorWs;

// ── Document Summary ──────────────────────────────────────────────────────

export interface SectionReference {
  section: string;
  page: number | null;
  contribution: string;
}

export interface DocumentSummary {
  id: string;
  document_id: string;
  summary_text: string;
  section_references: SectionReference[] | null;
  model_version: string;
  created_at: string;
}

// ── System ────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded';
  database: 'ok' | 'error';
  embedding_model: string;
  llm_model: string;
  ollama: 'ok' | 'unavailable';
  reembedding: boolean;
}

export interface ConfigResponse {
  host: string;
  port: number;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  llm_provider: string;
  llm_model: string;
  llm_base_url: string;
  llm_context_window: number;
  retrieval_top_k: number;
  retrieval_similarity_threshold: number;
  chunk_size: number;
  chunk_overlap: number;
  sliding_window_messages: number;
  chroma_collection_name: string;
  log_level: string;
}
