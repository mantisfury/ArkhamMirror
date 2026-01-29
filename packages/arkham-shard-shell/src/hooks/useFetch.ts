/**
 * useFetch - Generic data fetching hook
 *
 * Async Hook Error Contract:
 * - Catches errors internally
 * - Returns { data, loading, error } - never throws
 * - Never throws during render phase
 * - Logs warnings to console, not errors (unless truly fatal)
 *
 * When using with polling (setInterval + refetch): pass { backgroundRefetch: true }
 * so refetches do not set loading — avoids UI flash. Data is only updated when the
 * response actually changes (shallow compare).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch } from '../utils/api';

interface UseFetchOptions<T = unknown> {
  /** Timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** When true, refetch does not set loading — keeps showing previous data until new data arrives. Use for polling/stats to avoid UI flash. */
  backgroundRefetch?: boolean;
  /** When provided, used instead of JSON.stringify to decide if data changed. Use for responses with extra fields or floats to avoid unnecessary re-renders. */
  isDataEqual?: (a: T, b: T) => boolean;
}

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

const DEFAULT_TIMEOUT = 30000; // 30 seconds

export function useFetch<T>(url: string | null, options?: UseFetchOptions<T>): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDataEqualRef = useRef(options?.isDataEqual);
  isDataEqualRef.current = options?.isDataEqual;

  const timeout = options?.timeout ?? DEFAULT_TIMEOUT;
  const backgroundRefetch = options?.backgroundRefetch ?? false;

  const fetchData = useCallback(async (silent = false) => {
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

    if (!silent) {
      setLoading(true);
      setError(null);
    }

    // Set up timeout
    timeoutRef.current = setTimeout(() => {
      abortRef.current?.abort();
    }, timeout);

    try {
      const response = await apiFetch(url, {
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = (await response.json()) as T;
      // Only update state when data actually changed to avoid unnecessary re-renders
      setData((prev) => {
        if (prev === null) return result;
        const eq = isDataEqualRef.current
          ? isDataEqualRef.current(prev, result)
          : JSON.stringify(prev) === JSON.stringify(result);
        if (eq) return prev;
        return result;
      });
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
      // Always update errors, even during background refetches, so connection status updates correctly
      // This is important for polling scenarios where we need to detect disconnections
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
    fetchData(false);
    return () => {
      abortRef.current?.abort();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData(backgroundRefetch);
  }, [fetchData, backgroundRefetch]);

  return { data, loading, error, refetch };
}
