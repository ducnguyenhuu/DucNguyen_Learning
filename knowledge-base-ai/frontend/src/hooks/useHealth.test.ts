/**
 * Unit tests for useHealth hook.
 *
 * Covers:
 * - Initial loading=true until first fetch resolves
 * - Populates health from API response
 * - loading=false after first fetch
 * - error set when API throws
 * - refresh() triggers an immediate re-fetch
 * - Polling schedules a second fetch after the interval
 * - Cleanup cancels pending timer on unmount
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useHealth } from './useHealth';
import * as api from '../services/api';
import type { HealthResponse } from '../services/types';

vi.mock('../services/api', () => ({
  getHealth: vi.fn(),
}));

const mockGetHealth = vi.mocked(api.getHealth);

function makeHealth(overrides: Partial<HealthResponse> = {}): HealthResponse {
  return {
    status: 'ok',
    database: 'ok',
    embedding_model: 'nomic-embed-text-v1.5',
    llm_model: 'phi3.5',
    ollama: 'ok',
    reembedding: false,
    ...overrides,
  };
}

describe('useHealth', () => {
  beforeEach(() => {
    mockGetHealth.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts with loading=true and health=null', () => {
    mockGetHealth.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useHealth(60_000));
    expect(result.current.loading).toBe(true);
    expect(result.current.health).toBeNull();
  });

  it('sets health and clears loading after successful fetch', async () => {
    const expected = makeHealth();
    mockGetHealth.mockResolvedValue(expected);

    const { result } = renderHook(() => useHealth(60_000));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.health).toEqual(expected);
    expect(result.current.error).toBeNull();
  });

  it('sets error when fetch fails', async () => {
    mockGetHealth.mockRejectedValue(new Error('network error'));

    const { result } = renderHook(() => useHealth(60_000));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('network error');
    expect(result.current.health).toBeNull();
  });

  it('reflects reembedding=true from health response', async () => {
    mockGetHealth.mockResolvedValue(makeHealth({ reembedding: true }));

    const { result } = renderHook(() => useHealth(60_000));

    await waitFor(() => {
      expect(result.current.health?.reembedding).toBe(true);
    });
  });

  it('reflects reembedding=false from health response', async () => {
    mockGetHealth.mockResolvedValue(makeHealth({ reembedding: false }));

    const { result } = renderHook(() => useHealth(60_000));

    await waitFor(() => {
      expect(result.current.health?.reembedding).toBe(false);
    });
  });

  it('refresh() triggers a new fetch immediately', async () => {
    mockGetHealth.mockResolvedValueOnce(makeHealth({ reembedding: false }));

    const { result } = renderHook(() => useHealth(60_000));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockGetHealth).toHaveBeenCalledTimes(1);

    // Second call returns updated data
    mockGetHealth.mockResolvedValueOnce(makeHealth({ reembedding: true }));

    act(() => { result.current.refresh(); });

    await waitFor(() => {
      expect(result.current.health?.reembedding).toBe(true);
    });
    expect(mockGetHealth).toHaveBeenCalledTimes(2);
  });

  it('polls again after the interval', async () => {
    // Use a very short interval so real timers fire quickly
    const INTERVAL = 50;
    mockGetHealth
      .mockResolvedValueOnce(makeHealth({ reembedding: true }))
      .mockResolvedValueOnce(makeHealth({ reembedding: false }));

    const { result } = renderHook(() => useHealth(INTERVAL));

    // Wait for initial fetch
    await waitFor(() => expect(result.current.health?.reembedding).toBe(true));

    // Wait for poll to fire and second fetch to land
    await waitFor(
      () => {
        expect(mockGetHealth).toHaveBeenCalledTimes(2);
        expect(result.current.health?.reembedding).toBe(false);
      },
      { timeout: 1000 },
    );
  });

  it('does not update state after unmount', async () => {
    let resolveFirst!: (v: HealthResponse) => void;
    mockGetHealth.mockReturnValueOnce(
      new Promise<HealthResponse>((r) => {
        resolveFirst = r;
      }),
    );

    const { result, unmount } = renderHook(() => useHealth(60_000));
    unmount();

    // Resolving after unmount should not throw or update
    await act(() => { resolveFirst(makeHealth()); return Promise.resolve(); });

    // Health stays null — no state update after unmount
    expect(result.current.health).toBeNull();
  });
});
