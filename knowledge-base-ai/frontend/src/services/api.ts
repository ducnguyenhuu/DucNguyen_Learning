/**
 * Axios API client — pre-configured for the backend at /api/v1.
 *
 * All requests automatically include a unique X-Request-ID header for
 * traceability.  Error responses are surfaced as structured ApiError objects
 * that include the request_id for display in the UI.
 */
import axios, { type AxiosInstance, type AxiosResponse } from 'axios';
import { v4 as uuidv4 } from 'uuid';
import type {
  ConfigResponse,
  Conversation,
  ConversationDetailResponse,
  ConversationListResponse,
  CreateConversationRequest,
  Document,
  DocumentListResponse,
  DocumentSummary,
  ErrorResponse,
  HealthResponse,
  IngestionJob,
  SendMessageRequest,
  SendMessageResponse,
  StartIngestionRequest,
  StartIngestionResponse,
} from './types';

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
});

// Inject a unique X-Request-ID on every outgoing request
apiClient.interceptors.request.use((config) => {
  config.headers['X-Request-ID'] = uuidv4();
  return config;
});

// Normalise error responses into ApiError shape
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.data) {
      const data = error.response.data as ErrorResponse;
      if (data.error) {
        return Promise.reject(data.error);
      }
    }
    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// System endpoints
// ---------------------------------------------------------------------------

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health');
  return data;
}

export async function getConfig(): Promise<ConfigResponse> {
  const { data } = await apiClient.get<ConfigResponse>('/config');
  return data;
}

// ---------------------------------------------------------------------------
// Ingestion endpoints
// ---------------------------------------------------------------------------

export async function startIngestion(
  body: StartIngestionRequest = {},
): Promise<StartIngestionResponse> {
  const { data } = await apiClient.post<StartIngestionResponse>('/ingestion/start', body);
  return data;
}

export async function getIngestionStatus(jobId: string): Promise<IngestionJob> {
  const { data } = await apiClient.get<IngestionJob>(`/ingestion/status/${jobId}`);
  return data;
}

// ---------------------------------------------------------------------------
// Document endpoints
// ---------------------------------------------------------------------------

export async function listDocuments(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<DocumentListResponse> {
  const { data } = await apiClient.get<DocumentListResponse>('/documents', { params });
  return data;
}

export async function getDocument(id: string): Promise<Document> {
  const { data } = await apiClient.get<Document>(`/documents/${id}`);
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/documents/${id}`);
}

// ---------------------------------------------------------------------------
// Conversation endpoints
// ---------------------------------------------------------------------------

export async function listConversations(): Promise<ConversationListResponse> {
  const { data } = await apiClient.get<ConversationListResponse>('/conversations');
  return data;
}

export async function createConversation(
  body: CreateConversationRequest = {},
): Promise<Conversation> {
  const { data } = await apiClient.post<Conversation>('/conversations', body);
  return data;
}

export async function getConversation(id: string): Promise<ConversationDetailResponse> {
  const { data } = await apiClient.get<ConversationDetailResponse>(`/conversations/${id}`);
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await apiClient.delete(`/conversations/${id}`);
}

export async function clearAllConversations(): Promise<void> {
  await apiClient.delete('/conversations', { params: { confirm: true } });
}

// ---------------------------------------------------------------------------
// Chat endpoints
// ---------------------------------------------------------------------------

export async function sendMessage(
  conversationId: string,
  body: SendMessageRequest,
): Promise<SendMessageResponse> {
  const { data } = await apiClient.post<SendMessageResponse>(
    `/conversations/${conversationId}/messages`,
    body,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Summary endpoints
// ---------------------------------------------------------------------------

export async function generateSummary(documentId: string): Promise<DocumentSummary> {
  const { data } = await apiClient.post<DocumentSummary>(
    `/documents/${documentId}/summary`,
  );
  return data;
}

export async function getSummary(documentId: string): Promise<DocumentSummary> {
  const { data } = await apiClient.get<DocumentSummary>(
    `/documents/${documentId}/summary`,
  );
  return data;
}

export default apiClient;
