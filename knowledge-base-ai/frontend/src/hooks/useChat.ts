/**
 * useChat — manages the full chat session lifecycle.
 *
 * Responsibilities:
 *  - Create a new Conversation automatically on first message send (if none)
 *  - Add an optimistic user message to the list immediately
 *  - Stream the assistant response token-by-token via WebSocket
 *  - Handle WebSocket events: user_message_saved, sources_found, token, complete, error
 *  - Track streaming state, error, and active source references
 *  - Reset message list when initialConversationId changes (navigating to different chat)
 *
 * Usage:
 *   const {
 *     messages, streaming, error, activeSources,
 *     sendMessage, setActiveSources, clearError, activeConversationId,
 *   } = useChat(conversationIdFromRoute);
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { createConversation, getConversation } from '../services/api';
import { WebSocketManager } from '../services/websocket';
import type {
  ChatMessage,
  SourceReference,
  UserMessageSavedWs,
  SourcesFoundWs,
  TokenWs,
  ChatCompleteWs,
  ChatErrorWs,
} from '../services/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseChatResult {
  /** Ordered list of messages in the current conversation. */
  messages: ChatMessage[];
  /** True while an assistant response is being streamed. */
  streaming: boolean;
  /** Error message from the most recent failed operation. */
  error: string | null;
  /** Source references from the most recently streamed response. */
  activeSources: SourceReference[];
  /** The active conversation ID (may differ from prop when auto-created). */
  activeConversationId: string | null;
  /** Send a user message and stream the assistant response. */
  sendMessage: (content: string) => Promise<void>;
  /** Override the active sources (e.g. when a citation badge is clicked). */
  setActiveSources: React.Dispatch<React.SetStateAction<SourceReference[]>>;
  /** Dismiss the current error. */
  clearError: () => void;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function extractMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as Record<string, unknown>;
    if (typeof e['message'] === 'string') return e['message'];
  }
  return 'An unexpected error occurred.';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChat(initialConversationId: string | null = null): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSources, setActiveSources] = useState<SourceReference[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    initialConversationId,
  );

  // Guard against concurrent sends
  const isStreamingRef = useRef(false);

  // Mutable ref to accumulate sources during a streaming response (avoids
  // stale closure in the 'complete' event handler)
  const pendingSourcesRef = useRef<SourceReference[]>([]);

  // ---------------------------------------------------------------------------
  // Sync conversation ID when the route param changes & load history
  // ---------------------------------------------------------------------------

  useEffect(() => {
    setActiveConversationId(initialConversationId);
    setMessages([]);
    setActiveSources([]);
    setError(null);
    pendingSourcesRef.current = [];

    if (!initialConversationId) return;

    let cancelled = false;
    getConversation(initialConversationId)
      .then((detail) => {
        if (cancelled || isStreamingRef.current) return;
        setMessages(
          detail.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            source_references: m.source_references,
            created_at: m.created_at,
          })),
        );
      })
      .catch((err: unknown) => {
        if (cancelled || isStreamingRef.current) return;
        setError(extractMessage(err));
      });

    return () => {
      cancelled = true;
    };
  }, [initialConversationId]);

  // ---------------------------------------------------------------------------
  // Core send logic
  // ---------------------------------------------------------------------------

  const sendMessage = useCallback(
    async (content: string) => {
      if (isStreamingRef.current) return;

      // ---- Ensure a conversation exists -----------------------------------
      let convId = activeConversationId;
      if (!convId) {
        try {
          const conv = await createConversation();
          convId = conv.id;
          setActiveConversationId(convId);
        } catch (err) {
          setError(extractMessage(err));
          return;
        }
      }

      // ---- Optimistic user message ----------------------------------------
      const optimisticUserId = crypto.randomUUID();
      const userMsg: ChatMessage = {
        id: optimisticUserId,
        role: 'user',
        content,
        source_references: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // ---- WebSocket streaming --------------------------------------------
      setStreaming(true);
      isStreamingRef.current = true;
      pendingSourcesRef.current = [];

      const ws = new WebSocketManager(`/api/v1/conversations/${convId}/stream`, {
        maxRetries: 0, // per-message connections should not auto-reconnect
      });

      // Placeholder ID for the assistant message while tokens arrive.
      // Will be replaced with the real DB id on the 'complete' event.
      let assistantId = '';

      ws.onMessage('user_message_saved', (data: unknown) => {
        const { message_id } = data as UserMessageSavedWs;
        setMessages((prev) =>
          prev.map((m) => (m.id === optimisticUserId ? { ...m, id: message_id } : m)),
        );
      });

      ws.onMessage('sources_found', (data: unknown) => {
        const { sources } = data as SourcesFoundWs;
        pendingSourcesRef.current = sources;
        setActiveSources(sources);
      });

      ws.onMessage('token', (data: unknown) => {
        const { content: token } = data as TokenWs;
        if (!assistantId) {
          assistantId = crypto.randomUUID();
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: 'assistant',
              content: token,
              source_references: null,
              created_at: new Date().toISOString(),
            },
          ]);
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          );
        }
      });

      ws.onMessage('complete', (data: unknown) => {
        const { message_id } = data as ChatCompleteWs;
        const finalSources =
          pendingSourcesRef.current.length > 0 ? pendingSourcesRef.current : null;

        if (assistantId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, id: message_id, source_references: finalSources }
                : m,
            ),
          );
        }

        setStreaming(false);
        isStreamingRef.current = false;
        ws.disconnect();
      });

      ws.onMessage('error', (data: unknown) => {
        const { message: errMsg } = data as ChatErrorWs;
        setError(errMsg);
        setStreaming(false);
        isStreamingRef.current = false;
        ws.disconnect();
      });

      // Connect and send question once the socket is open
      ws.onOpen(() => {
        ws.send({ type: 'question', content });
      });

      ws.connect();
    },
    [activeConversationId],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    messages,
    streaming,
    error,
    activeSources,
    activeConversationId,
    sendMessage,
    setActiveSources,
    clearError,
  };
}
