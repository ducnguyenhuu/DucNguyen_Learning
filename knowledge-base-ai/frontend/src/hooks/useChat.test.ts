/**
 * Unit tests for useChat hook.
 *
 * Covers:
 *  - Initial state: empty messages, not streaming, no error
 *  - sendMessage creates a conversation when no activeConversationId
 *  - sendMessage adds an optimistic user message immediately
 *  - WS connection established with correct path
 *  - Question sent over WS after onOpen fires
 *  - user_message_saved updates the optimistic user message ID
 *  - sources_found populates activeSources
 *  - token events build up assistant message content
 *  - complete event finalises assistant message ID + source_references
 *  - error event sets hook error and stops streaming
 *  - streaming flag transitions (false → true → false)
 *  - clearError resets error state
 *  - state reset when initialConversationId prop changes
 *  - does not start concurrent sends while streaming
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChat } from './useChat';
import * as api from '../services/api';
import type { Conversation } from '../services/types';

// ---------------------------------------------------------------------------
// Mock WebSocketManager
// ---------------------------------------------------------------------------

type Handler = (data: unknown) => void;

const { MockWebSocketManager } = vi.hoisted(() => {
  class MockWebSocketManager {
    private handlers: Map<string, Handler[]> = new Map();
    static lastInstance: MockWebSocketManager | null = null;

    constructor() {
      MockWebSocketManager.lastInstance = this;
    }

    connect = vi.fn();
    disconnect = vi.fn();
    send = vi.fn();

    onMessage<T>(type: string, handler: (data: T) => void): () => void {
      const list = this.handlers.get(type) ?? [];
      list.push(handler as Handler);
      this.handlers.set(type, list);
      return () => {};
    }

    onOpen(handler: () => void): () => void {
      return this.onMessage('__open', handler);
    }

    emit(type: string, data: unknown) {
      const list = this.handlers.get(type) ?? [];
      list.forEach((h) => h(data));
    }

    /** Simulate the WebSocket connection opening. */
    triggerOpen() {
      this.emit('__open', null);
    }
  }

  return { MockWebSocketManager };
});

vi.mock('../services/websocket', () => ({
  WebSocketManager: MockWebSocketManager,
}));

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

vi.mock('../services/api', () => ({
  createConversation: vi.fn(),
  sendMessage: vi.fn(),
  getConversation: vi.fn(),
}));

const mockCreateConversation = vi.mocked(api.createConversation);
const mockGetConversation = vi.mocked(api.getConversation);

function makeConversation(id = 'conv-1'): Conversation {
  return {
    id,
    title: null,
    preview: null,
    message_count: 0,
    created_at: '2026-03-05T12:00:00Z',
    updated_at: '2026-03-05T12:00:00Z',
  };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  MockWebSocketManager.lastInstance = null;
  // Default: getConversation returns an empty conversation detail
  mockGetConversation.mockResolvedValue({
    id: 'conv-1',
    title: null,
    messages: [],
    created_at: '2026-03-05T12:00:00Z',
    updated_at: '2026-03-05T12:00:00Z',
  });
});

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('useChat — initial state', () => {
  it('starts with empty messages', () => {
    const { result } = renderHook(() => useChat(null));
    expect(result.current.messages).toEqual([]);
  });

  it('starts with streaming=false', () => {
    const { result } = renderHook(() => useChat(null));
    expect(result.current.streaming).toBe(false);
  });

  it('starts with error=null', () => {
    const { result } = renderHook(() => useChat(null));
    expect(result.current.error).toBeNull();
  });

  it('starts with empty activeSources', () => {
    const { result } = renderHook(() => useChat(null));
    expect(result.current.activeSources).toEqual([]);
  });

  it('reflects the initial conversationId', () => {
    const { result } = renderHook(() => useChat('conv-abc'));
    expect(result.current.activeConversationId).toBe('conv-abc');
  });
});

// ---------------------------------------------------------------------------
// Conversation creation
// ---------------------------------------------------------------------------

describe('useChat — conversation creation', () => {
  it('creates a conversation when none exists before first send', async () => {
    mockCreateConversation.mockResolvedValue(makeConversation('new-conv'));
    const { result } = renderHook(() => useChat(null));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(mockCreateConversation).toHaveBeenCalledTimes(1);
  });

  it('sets activeConversationId to the new conversation id', async () => {
    mockCreateConversation.mockResolvedValue(makeConversation('new-conv'));
    const { result } = renderHook(() => useChat(null));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(result.current.activeConversationId).toBe('new-conv');
  });

  it('does NOT create a conversation when one already exists', async () => {
    const { result } = renderHook(() => useChat('existing-conv'));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(mockCreateConversation).not.toHaveBeenCalled();
  });

  it('sets error when conversation creation fails', async () => {
    mockCreateConversation.mockRejectedValue({ message: 'Network error' });
    const { result } = renderHook(() => useChat(null));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(result.current.error).toBe('Network error');
  });
});

// ---------------------------------------------------------------------------
// Optimistic user message
// ---------------------------------------------------------------------------

describe('useChat — optimistic user message', () => {
  it('adds a user message immediately before WS response', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Test question');
    });

    const userMsg = result.current.messages.find((m) => m.role === 'user');
    expect(userMsg).toBeDefined();
    expect(userMsg?.content).toBe('Test question');
  });

  it('user message role is "user"', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q?');
    });

    expect(result.current.messages[0].role).toBe('user');
  });
});

// ---------------------------------------------------------------------------
// WebSocket connection
// ---------------------------------------------------------------------------

describe('useChat — WebSocket setup', () => {
  it('connects WebSocket after sendMessage', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });

    expect(MockWebSocketManager.lastInstance?.connect).toHaveBeenCalled();
  });

  it('sends question via WS when connection opens', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('My question');
    });

    const ws = MockWebSocketManager.lastInstance!;
    act(() => ws.triggerOpen());

    expect(ws.send).toHaveBeenCalledWith({ type: 'question', content: 'My question' });
  });

  it('streaming is true after sendMessage starts', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });

    expect(result.current.streaming).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// WebSocket events
// ---------------------------------------------------------------------------

describe('useChat — WS: user_message_saved', () => {
  it('updates the optimistic user message id', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('user_message_saved', { type: 'user_message_saved', message_id: 'real-user-id' });
    });

    const userMsg = result.current.messages.find((m) => m.role === 'user');
    expect(userMsg?.id).toBe('real-user-id');
  });
});

describe('useChat — WS: sources_found', () => {
  it('populates activeSources', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('sources_found', {
        type: 'sources_found',
        sources: [
          { document_id: 'd1', file_name: 'guide.pdf', page_number: 3, relevance_score: 0.9 },
        ],
      });
    });

    expect(result.current.activeSources).toHaveLength(1);
    expect(result.current.activeSources[0].file_name).toBe('guide.pdf');
  });
});

describe('useChat — WS: token', () => {
  it('creates assistant message on first token', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('token', { type: 'token', content: 'Hello' });
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant).toBeDefined();
    expect(assistant?.content).toBe('Hello');
  });

  it('accumulates subsequent tokens', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('token', { type: 'token', content: 'Hel' });
      ws.emit('token', { type: 'token', content: 'lo ' });
      ws.emit('token', { type: 'token', content: 'world' });
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant?.content).toBe('Hello world');
  });
});

describe('useChat — WS: complete', () => {
  it('finalises assistant message with real id', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('token', { type: 'token', content: 'Answer.' });
      ws.emit('complete', { type: 'complete', message_id: 'final-asst-id' });
    });

    const assistant = result.current.messages.find((m) => m.role === 'assistant');
    expect(assistant?.id).toBe('final-asst-id');
  });

  it('stops streaming on complete', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('complete', { type: 'complete', message_id: 'id' });
    });

    expect(result.current.streaming).toBe(false);
  });

  it('disconnects WS on complete', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('complete', { type: 'complete', message_id: 'id' });
    });

    expect(ws.disconnect).toHaveBeenCalled();
  });
});

describe('useChat — WS: error', () => {
  it('sets error message from error event', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('error', { type: 'error', message: 'LLM unavailable', code: 'model_unavailable' });
    });

    expect(result.current.error).toBe('LLM unavailable');
  });

  it('stops streaming on error event', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;

    act(() => {
      ws.emit('error', { type: 'error', message: 'Fail', code: 'e' });
    });

    expect(result.current.streaming).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// clearError
// ---------------------------------------------------------------------------

describe('useChat — clearError', () => {
  it('resets error to null', async () => {
    const { result } = renderHook(() => useChat('conv-1'));

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;
    act(() => ws.emit('error', { type: 'error', message: 'Fail', code: 'e' }));

    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// State reset on conversationId change
// ---------------------------------------------------------------------------

describe('useChat — conversationId prop change', () => {
  it('clears messages when conversationId changes', async () => {
    const { result, rerender } = renderHook(
      ({ convId }: { convId: string | null }) => useChat(convId),
      { initialProps: { convId: 'conv-1' } },
    );

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;
    act(() => ws.emit('token', { type: 'token', content: 'Hi' }));

    // Navigate to a different conversation
    act(() => rerender({ convId: 'conv-2' }));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(0);
    });
  });

  it('clears activeSources when conversationId changes', async () => {
    const { result, rerender } = renderHook(
      ({ convId }: { convId: string | null }) => useChat(convId),
      { initialProps: { convId: 'conv-1' } },
    );

    await act(async () => {
      await result.current.sendMessage('Q');
    });
    const ws = MockWebSocketManager.lastInstance!;
    act(() => {
      ws.emit('sources_found', {
        type: 'sources_found',
        sources: [{ document_id: 'd1', file_name: 'a.pdf', page_number: 1, relevance_score: 0.9 }],
      });
    });

    act(() => rerender({ convId: 'conv-2' }));

    await waitFor(() => {
      expect(result.current.activeSources).toHaveLength(0);
    });
  });
});

// ---------------------------------------------------------------------------
// Load conversation history
// ---------------------------------------------------------------------------

describe('useChat — conversation history loading', () => {
  it('fetches messages when initialConversationId is provided', async () => {
    mockGetConversation.mockResolvedValue({
      id: 'conv-existing',
      title: 'Test Chat',
      messages: [
        {
          id: 'msg-1',
          conversation_id: 'conv-existing',
          role: 'user',
          content: 'Hello',
          source_references: null,
          token_count: null,
          created_at: '2026-03-05T12:00:00Z',
        },
        {
          id: 'msg-2',
          conversation_id: 'conv-existing',
          role: 'assistant',
          content: 'Hi there!',
          source_references: [{ document_id: 'd1', file_name: 'a.pdf', page_number: 1, relevance_score: 0.9 }],
          token_count: 5,
          created_at: '2026-03-05T12:00:01Z',
        },
      ],
      created_at: '2026-03-05T12:00:00Z',
      updated_at: '2026-03-05T12:00:01Z',
    });

    const { result } = renderHook(() => useChat('conv-existing'));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    expect(mockGetConversation).toHaveBeenCalledWith('conv-existing');
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('Hello');
    expect(result.current.messages[1].role).toBe('assistant');
    expect(result.current.messages[1].content).toBe('Hi there!');
    expect(result.current.messages[1].source_references).toHaveLength(1);
  });

  it('does NOT fetch when initialConversationId is null', () => {
    renderHook(() => useChat(null));
    expect(mockGetConversation).not.toHaveBeenCalled();
  });

  it('sets error when fetch fails', async () => {
    mockGetConversation.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useChat('conv-bad'));

    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
    });
  });
});
