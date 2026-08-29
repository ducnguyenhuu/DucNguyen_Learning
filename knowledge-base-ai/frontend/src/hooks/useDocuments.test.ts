/**
 * Unit tests for useDocuments hook.
 *
 * Covers:
 *  - Initial fetch on mount (loading → success)
 *  - Populates documents + total from API response
 *  - Loading state is true during fetch, false after
 *  - Error state set when API throws
 *  - Status filter forwarded to listDocuments
 *  - refresh() re-triggers fetch
 *  - deleteDocument removes row optimistically and re-fetches
 *  - deleteDocument sets deleteError and re-throws on failure
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useDocuments } from './useDocuments';
import * as api from '../services/api';
import type { DocumentListResponse } from '../services/types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../services/api', () => ({
  listDocuments: vi.fn(),
  deleteDocument: vi.fn(),
}));

const mockListDocuments = vi.mocked(api.listDocuments);
const mockDeleteDocument = vi.mocked(api.deleteDocument);

function makeDoc(id: string, name = `doc-${id}.pdf`) {
  return {
    id,
    file_name: name,
    file_type: 'pdf' as const,
    file_path: `/docs/${name}`,
    file_hash: 'abc',
    file_size_bytes: 1000,
    chunk_count: 5,
    status: 'completed' as const,
    error_message: null,
    ingested_at: '2026-03-05T12:00:00',
    created_at: '2026-03-05T11:00:00',
    updated_at: '2026-03-05T12:00:00',
  };
}

function makeListResponse(ids: string[]): DocumentListResponse {
  return {
    documents: ids.map((id) => makeDoc(id)),
    total: ids.length,
    page: 1,
    page_size: 20,
  };
}

// ---------------------------------------------------------------------------
// Each test
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('useDocuments — initial fetch', () => {
  it('starts in loading state', async () => {
    let resolveList!: (v: DocumentListResponse) => void;
    mockListDocuments.mockReturnValue(new Promise((res) => { resolveList = res; }));

    const { result } = renderHook(() => useDocuments());

    expect(result.current.loading).toBe(true);
    expect(result.current.documents).toEqual([]);

    // resolve to clean up
    await act(() => { resolveList(makeListResponse(['d1'])); return Promise.resolve(); });
  });

  it('populates documents and total after successful fetch', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1', 'd2']));

    const { result } = renderHook(() => useDocuments());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.documents).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(result.current.error).toBeNull();
  });

  it('sets error and clears loading on fetch failure', async () => {
    mockListDocuments.mockRejectedValue({ message: 'Network Error' });

    const { result } = renderHook(() => useDocuments());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network Error');
    expect(result.current.documents).toEqual([]);
  });

  it('forwards status filter to listDocuments', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse([]));

    const { result } = renderHook(() => useDocuments({ status: 'completed' }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockListDocuments).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'completed' }),
    );
  });

  it('does not forward status when undefined', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse([]));

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callArg = mockListDocuments.mock.calls[0][0];
    expect(callArg).not.toHaveProperty('status');
  });

  it('forwards page and pageSize to listDocuments', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse([]));

    const { result } = renderHook(() => useDocuments({ page: 2, pageSize: 5 }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockListDocuments).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, page_size: 5 }),
    );
  });
});

describe('useDocuments — refresh', () => {
  it('re-fetches when refresh() is called', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1']));

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockListDocuments).toHaveBeenCalledTimes(1);

    await act(() => { result.current.refresh(); return Promise.resolve(); });

    await waitFor(() => expect(mockListDocuments).toHaveBeenCalledTimes(2));
  });
});

describe('useDocuments — deleteDocument', () => {
  it('calls api.deleteDocument with the correct id', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1', 'd2']));
    mockDeleteDocument.mockResolvedValue(undefined);

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteDocument('d1');
    });

    expect(mockDeleteDocument).toHaveBeenCalledWith('d1');
  });

  it('removes deleted document from local list optimistically', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1', 'd2']));
    // Second call (after delete refresh) also returns the remaining doc
    mockListDocuments.mockResolvedValueOnce(makeListResponse(['d1', 'd2']));
    mockListDocuments.mockResolvedValueOnce(makeListResponse(['d2']));
    mockDeleteDocument.mockResolvedValue(undefined);

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      // Fire and forget to capture optimistic state before await
      void result.current.deleteDocument('d1');
    });

    // Optimistic removal
    await waitFor(() =>
      expect(result.current.documents.find((d) => d.id === 'd1')).toBeUndefined(),
    );
  });

  it('triggers a refresh after successful delete', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1']));
    mockDeleteDocument.mockResolvedValue(undefined);

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callsBefore = mockListDocuments.mock.calls.length;

    await act(async () => {
      await result.current.deleteDocument('d1');
    });

    await waitFor(() =>
      expect(mockListDocuments.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it('sets deleteError and rethrows when delete fails', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1']));
    mockDeleteDocument.mockRejectedValue({ message: 'Document not found' });

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await expect(result.current.deleteDocument('d1')).rejects.toMatchObject({
        message: 'Document not found',
      });
    });

    expect(result.current.deleteError).toBe('Document not found');
  });

  it('re-fetches even after delete failure', async () => {
    mockListDocuments.mockResolvedValue(makeListResponse(['d1']));
    mockDeleteDocument.mockRejectedValue({ message: 'Not found' });

    const { result } = renderHook(() => useDocuments());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const callsBefore = mockListDocuments.mock.calls.length;

    await act(async () => {
      await result.current.deleteDocument('d1').catch(() => {});
    });

    await waitFor(() =>
      expect(mockListDocuments.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });
});
