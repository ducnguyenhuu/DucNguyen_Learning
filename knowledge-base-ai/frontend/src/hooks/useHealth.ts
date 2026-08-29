/**
 * useHealth — polls GET /health on an interval and exposes the response.
 *
 * Used by the ReembedBanner component (and the Dashboard) to reflect the
 * current backend health without requiring a manual refresh.
 *
 * Polling interval: 10 seconds (configurable via the `intervalMs` option).
 * Polling stops automatically when the component using the hook unmounts.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { getHealth } from '../services/api';
import type { HealthResponse } from '../services/types';

export interface UseHealthResult {
  /** Latest health data, or null while the first fetch is in-flight. */
  health: HealthResponse | null;
  /** True while the first fetch hasn't completed yet. */
  loading: boolean;
  /** Error from the most recent failed fetch attempt. */
  error: Error | null;
  /** Manually trigger an immediate re-fetch (resets the interval timer). */
  refresh: () => void;
}

export function useHealth(intervalMs = 10_000): UseHealthResult {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getHealth();
      if (mountedRef.current) {
        setHealth(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  /** Schedule the next poll. Previous timer is cleared first. */
  const schedule = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(async () => {
      await fetchHealth();
      if (mountedRef.current) {
        schedule();
      }
    }, intervalMs);
  }, [fetchHealth, intervalMs]);

  const refresh = useCallback(() => {
    void fetchHealth().then(() => {
      if (mountedRef.current) {
        schedule();
      }
    });
  }, [fetchHealth, schedule]);

  useEffect(() => {
    mountedRef.current = true;
    // Initial fetch, then start the polling loop
    void fetchHealth().then(() => {
      if (mountedRef.current) {
        schedule();
      }
    });

    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { health, loading, error, refresh };
}
