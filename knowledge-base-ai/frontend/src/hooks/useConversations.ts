/**
 * useConversations — manages conversation list state.
 *
 * Responsibilities:
 *  - Fetch paginated conversation list via GET /conversations
 *  - Expose deleteConversation handler (DELETE /conversations/{id})
 *  - Expose clearAll handler (DELETE /conversations?confirm=true)
 *  - Track loading and error state for all operations
 *  - Auto-refresh the list after mutations
 *
 * Usage:
 *   const {
 *     conversations, total, loading, error,
 *     deleteConversation, clearAll, refresh,
 *   } = useConversations();
 */
import { useCallback, useEffect, useState } from 'react';
import {
  clearAllConversations,
  deleteConversation as apiDeleteConversation,
  listConversations,
} from '../services/api';
import type { ApiError, Conversation } from '../services/types';

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

export interface UseConversationsOptions {
  page?: number;
  pageSize?: number;
}

export interface UseConversationsResult {
  conversations: Conversation[];
  total: number;
  loading: boolean;
  error: string | null;
  /** True while a single-delete request is in-flight. */
  deleting: boolean;
  deleteError: string | null;
  /** True while a clear-all request is in-flight. */
  clearing: boolean;
  clearError: string | null;
  deleteConversation: (id: string) => Promise<void>;
  clearAll: () => Promise<void>;
  refresh: () => void;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function extractMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const apiErr = err as Partial<ApiError>;
    if (typeof apiErr.message === 'string') return apiErr.message;
    const nativeErr = err as Partial<Error>;
    if (typeof nativeErr.message === 'string') return nativeErr.message;
  }
  return 'An unexpected error occurred.';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useConversations(
  options: UseConversationsOptions = {},
): UseConversationsResult {
  const { page = 1, pageSize = 20 } = options;

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);

  // Bump to retrigger the fetch effect without duplicating deps
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => {
    setRefreshTick((n) => n + 1);
  }, []);

  // ---------------------------------------------------------------------------
  // Fetch
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function fetchConversations() {
      setLoading(true);
      setError(null);
      try {
        const result = await listConversations();
        if (!cancelled) {
          setConversations(result.conversations);
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

    void fetchConversations();

    return () => {
      cancelled = true;
    };
  }, [page, pageSize, refreshTick]);

  // ---------------------------------------------------------------------------
  // Delete single conversation
  // ---------------------------------------------------------------------------

  const deleteConversation = useCallback(
    async (id: string): Promise<void> => {
      setDeleting(true);
      setDeleteError(null);
      try {
        await apiDeleteConversation(id);
        refresh();
      } catch (err: unknown) {
        setDeleteError(extractMessage(err));
      } finally {
        setDeleting(false);
      }
    },
    [refresh],
  );

  // ---------------------------------------------------------------------------
  // Clear all conversations
  // ---------------------------------------------------------------------------

  const clearAll = useCallback(async (): Promise<void> => {
    setClearing(true);
    setClearError(null);
    try {
      await clearAllConversations();
      refresh();
    } catch (err: unknown) {
      setClearError(extractMessage(err));
    } finally {
      setClearing(false);
    }
  }, [refresh]);

  return {
    conversations,
    total,
    loading,
    error,
    deleting,
    deleteError,
    clearing,
    clearError,
    deleteConversation,
    clearAll,
    refresh,
  };
}
