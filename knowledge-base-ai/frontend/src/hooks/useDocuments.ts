/**
 * useDocuments — manages document list state.
 *
 * Responsibilities:
 *  - Fetch paginated document list via GET /documents
 *  - Expose delete handler that removes a document and refreshes the list
 *  - Track loading and error state for both operations
 *  - Support optional status filter
 *
 * Usage:
 *   const { documents, total, loading, error, deleteDocument, refresh } = useDocuments();
 */
import { useState, useEffect, useCallback } from 'react';
import { listDocuments, deleteDocument as apiDeleteDocument } from '../services/api';
import type { Document, ApiError } from '../services/types';

export interface UseDocumentsOptions {
  page?: number;
  pageSize?: number;
  status?: string;
}

export interface UseDocumentsResult {
  documents: Document[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  deleting: boolean;
  deleteError: string | null;
  deleteDocument: (id: string) => Promise<void>;
  refresh: () => void;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function extractMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    // Normalised ApiError shape from the axios interceptor
    const apiErr = err as Partial<ApiError>;
    if (typeof apiErr.message === 'string') return apiErr.message;
    // Fallback: native Error
    const nativeErr = err as Partial<Error>;
    if (typeof nativeErr.message === 'string') return nativeErr.message;
  }
  return 'An unexpected error occurred.';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDocuments(options: UseDocumentsOptions = {}): UseDocumentsResult {
  const { page = 1, pageSize = 20, status } = options;

  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // A counter bumped by refresh() to retrigger the effect without extra state
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => {
    setRefreshTick((n) => n + 1);
  }, []);

  // ---------------------------------------------------------------------------
  // Fetch
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function fetchDocs() {
      setLoading(true);
      setError(null);
      try {
        const result = await listDocuments({
          page,
          page_size: pageSize,
          ...(status ? { status } : {}),
        });
        if (!cancelled) {
          setDocuments(result.documents);
          setTotal(result.total);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(extractMessage(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchDocs();

    return () => {
      cancelled = true;
    };
  }, [page, pageSize, status, refreshTick]);

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------

  const deleteDocument = useCallback(async (id: string): Promise<void> => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await apiDeleteDocument(id);
      // Optimistic update: remove the row immediately, then refresh to sync
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      setTotal((prev) => Math.max(0, prev - 1));
      // Full refresh to ensure consistent server state
      setRefreshTick((n) => n + 1);
    } catch (err: unknown) {
      setDeleteError(extractMessage(err));
      // Refresh the list regardless — document may not exist anymore (404)
      setRefreshTick((n) => n + 1);
      throw err; // re-throw so the caller (DocumentTable confirm dialog) can surface the error
    } finally {
      setDeleting(false);
    }
  }, []);

  return {
    documents,
    total,
    page,
    pageSize,
    loading,
    error,
    deleting,
    deleteError,
    deleteDocument,
    refresh,
  };
}
