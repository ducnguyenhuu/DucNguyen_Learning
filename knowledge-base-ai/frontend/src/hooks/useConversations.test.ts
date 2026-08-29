/**
 * Unit tests for useConversations hook.
 *
 * Covers:
 *  - Initial fetch on mount (loading → success / error)
 *  - Populates conversations + total
 *  - Loading state transitions
 *  - refresh() re-triggers fetch
 *  - deleteConversation calls API, refreshes, tracks deleting/deleteError
 *  - clearAll calls API with confirm, refreshes, tracks clearing/clearError
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../services/api';
import type { Conversation, ConversationListResponse } from '../services/types';
import { useConversations } from './useConversations';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../services/api', () => ({
  listConversations: vi.fn(),
  deleteConversation: vi.fn(),
  clearAllConversations: vi.fn(),
}));

const mockListConversations = vi.mocked(api.listConversations);
const mockDeleteConversation = vi.mocked(api.deleteConversation);
const mockClearAllConversations = vi.mocked(api.clearAllConversations);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConv(id: string, title: string | null = null): Conversation {
  return {
    id,
    title,
    preview: 'Preview text…',
    message_count: 3,
    created_at: '2026-03-05T10:00:00Z',
    updated_at: '2026-03-05T11:00:00Z',
  };
}

function makeListResponse(ids: string[]): ConversationListResponse {
  return {
    conversations: ids.map((id) => makeConv(id, `Chat ${id}`)),
    total: ids.length,
  };
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Initial fetch
// ---------------------------------------------------------------------------

describe('useConversations — initial fetch', () => {
  it('starts in loading state with empty conversations', async () => {
    let resolve!: (v: ConversationListResponse) => void;
    mockListConversations.mockReturnValue(new Promise((res) => { resolve = res; }));

    const { result } = renderHook(() => useConversations());

    expect(result.current.loading).toBe(true);
    expect(result.current.conversations).toEqual([]);

    // clean up
    await act(() => { resolve(makeListResponse([])); return Promise.resolve(); });
  });

  it('populates conversations and total on success', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1', 'c2', 'c3']));

    const { result } = renderHook(() => useConversations());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.conversations).toHaveLength(3);
    expect(result.current.total).toBe(3);
    expect(result.current.error).toBeNull();
  });

  it('sets error on fetch failure', async () => {
    mockListConversations.mockRejectedValue({ message: 'Network Error' });

    const { result } = renderHook(() => useConversations());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network Error');
    expect(result.current.conversations).toEqual([]);
  });

  it('uses fallback error message for non-Error objects', async () => {
    mockListConversations.mockRejectedValue('oops');

    const { result } = renderHook(() => useConversations());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('An unexpected error occurred.');
  });

  it('loading is false after fetch completes', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));

    const { result } = renderHook(() => useConversations());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.loading).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('useConversations — initial state', () => {
  it('deleting is false initially', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.deleting).toBe(false);
  });

  it('deleteError is null initially', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.deleteError).toBeNull();
  });

  it('clearing is false initially', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.clearing).toBe(false);
  });

  it('clearError is null initially', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.clearError).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// refresh()
// ---------------------------------------------------------------------------

describe('useConversations — refresh', () => {
  it('re-triggers fetch when refresh() is called', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1']));

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockListConversations).toHaveBeenCalledTimes(1);

    act(() => { result.current.refresh(); });

    await waitFor(() => expect(mockListConversations).toHaveBeenCalledTimes(2));
  });
});

// ---------------------------------------------------------------------------
// deleteConversation
// ---------------------------------------------------------------------------

describe('useConversations — deleteConversation', () => {
  it('calls deleteConversation API with the correct id', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1', 'c2']));
    mockDeleteConversation.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteConversation('c1');
    });

    expect(mockDeleteConversation).toHaveBeenCalledWith('c1');
  });

  it('refreshes list after successful delete', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1', 'c2']));
    mockDeleteConversation.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callsBefore = mockListConversations.mock.calls.length;

    await act(async () => {
      await result.current.deleteConversation('c1');
    });

    await waitFor(() =>
      expect(mockListConversations.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it('sets deleteError on failure', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1']));
    mockDeleteConversation.mockRejectedValue({ message: 'Delete failed' });

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteConversation('c1');
    });

    expect(result.current.deleteError).toBe('Delete failed');
  });

  it('clears deleteError before each delete attempt', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1']));
    mockDeleteConversation
      .mockRejectedValueOnce({ message: 'First error' })
      .mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteConversation('c1');
    });
    expect(result.current.deleteError).toBe('First error');

    await act(async () => {
      await result.current.deleteConversation('c1');
    });
    expect(result.current.deleteError).toBeNull();
  });

  it('deleting is false after operation completes', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1']));
    mockDeleteConversation.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteConversation('c1');
    });

    expect(result.current.deleting).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// clearAll
// ---------------------------------------------------------------------------

describe('useConversations — clearAll', () => {
  it('calls clearAllConversations API', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1', 'c2']));
    mockClearAllConversations.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.clearAll();
    });

    expect(mockClearAllConversations).toHaveBeenCalledOnce();
  });

  it('refreshes list after successful clearAll', async () => {
    mockListConversations.mockResolvedValue(makeListResponse(['c1']));
    mockClearAllConversations.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callsBefore = mockListConversations.mock.calls.length;

    await act(async () => {
      await result.current.clearAll();
    });

    await waitFor(() =>
      expect(mockListConversations.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it('sets clearError on failure', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    mockClearAllConversations.mockRejectedValue({ message: 'Clear failed' });

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.clearAll();
    });

    expect(result.current.clearError).toBe('Clear failed');
  });

  it('clears clearError before each attempt', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    mockClearAllConversations
      .mockRejectedValueOnce({ message: 'First clear error' })
      .mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => { await result.current.clearAll(); });
    expect(result.current.clearError).toBe('First clear error');

    await act(async () => { await result.current.clearAll(); });
    expect(result.current.clearError).toBeNull();
  });

  it('clearing is false after operation completes', async () => {
    mockListConversations.mockResolvedValue(makeListResponse([]));
    mockClearAllConversations.mockResolvedValue(undefined);

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => { await result.current.clearAll(); });

    expect(result.current.clearing).toBe(false);
  });
});
