/**
 * useFetch - Generic data fetching hook
 *
 * Async Hook Error Contract:
 * - Catches errors internally
 * - Returns { data, loading, error } - never throws
 * - Never throws during render phase
 * - Logs warnings to console, not errors (unless truly fatal)
 */

import { useState, useEffect, useCallback, useRef } from 'react';

interface UseFetchOptions {
  /** Timeout in milliseconds (default: 30000) */
  timeout?: number;
}

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

const DEFAULT_TIMEOUT = 30000; // 30 seconds

export function useFetch<T>(url: string | null, options?: UseFetchOptions): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const timeout = options?.timeout ?? DEFAULT_TIMEOUT;

  const fetchData = useCallback(async () => {
    if (!url) {
      setLoading(false);
      return;
    }

    // Abort previous request and clear timeout
    abortRef.current?.abort();
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    // Set up timeout
    timeoutRef.current = setTimeout(() => {
      abortRef.current?.abort();
    }, timeout);

    try {
      const response = await fetch(url, {
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      // Don't set error for aborted requests (unless it was a timeout)
      if (err instanceof Error && err.name === 'AbortError') {
        // Check if this was a timeout abort
        if (timeoutRef.current === null) {
          setError(new Error(`Request timed out after ${timeout / 1000}s`));
        }
        return;
      }
      setError(err instanceof Error ? err : new Error('Unknown error'));
      // Keep existing data on error (stale-while-revalidate pattern)
    } finally {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setLoading(false);
    }
  }, [url, timeout]);

  useEffect(() => {
    fetchData();
    return () => {
      abortRef.current?.abort();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}
