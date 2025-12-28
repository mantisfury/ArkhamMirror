/**
 * usePaginatedFetch - Paginated data fetching with settings integration
 *
 * Wraps useFetch with automatic pagination support:
 * - Reads default page_size from settings
 * - Handles page/page_size URL params
 * - Allows per-component override
 * - Provides pagination controls
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePageSize } from './useSettings';

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

interface UsePaginatedFetchOptions {
  /** Override the global page_size setting for this component */
  defaultPageSize?: number;
  /** Whether to sync pagination to URL params (default: true) */
  syncToUrl?: boolean;
  /** Additional query params to include */
  params?: Record<string, string | number | boolean | undefined>;
}

interface UsePaginatedFetchResult<T> {
  /** The fetched items */
  items: T[];
  /** Total count of items (for pagination) */
  total: number;
  /** Current page number (1-indexed) */
  page: number;
  /** Current page size */
  pageSize: number;
  /** Total number of pages */
  totalPages: number;
  /** Whether data is being fetched */
  loading: boolean;
  /** Error if fetch failed */
  error: Error | null;
  /** Go to a specific page */
  setPage: (page: number) => void;
  /** Change the page size */
  setPageSize: (size: number) => void;
  /** Go to next page */
  nextPage: () => void;
  /** Go to previous page */
  prevPage: () => void;
  /** Refetch the current page */
  refetch: () => void;
  /** Whether there's a next page */
  hasNextPage: boolean;
  /** Whether there's a previous page */
  hasPrevPage: boolean;
}

export function usePaginatedFetch<T>(
  baseUrl: string | null,
  options: UsePaginatedFetchOptions = {}
): UsePaginatedFetchResult<T> {
  const { defaultPageSize, syncToUrl = true, params = {} } = options;

  // Get global page size from settings
  const globalPageSize = usePageSize();
  const effectiveDefaultPageSize = defaultPageSize ?? globalPageSize;

  // URL params for syncing (only used if syncToUrl is true)
  const [searchParams, setSearchParams] = useSearchParams();

  // Local state for pagination (used when not syncing to URL)
  const [localPage, setLocalPage] = useState(1);
  const [localPageSize, setLocalPageSize] = useState(effectiveDefaultPageSize);

  // Determine current page and pageSize based on sync mode
  const page = syncToUrl
    ? parseInt(searchParams.get('page') || '1', 10)
    : localPage;
  const pageSize = syncToUrl
    ? parseInt(searchParams.get('page_size') || String(effectiveDefaultPageSize), 10)
    : localPageSize;

  // State for fetch
  const [data, setData] = useState<PaginatedResponse<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Build the full URL with pagination and additional params
  const fullUrl = useMemo(() => {
    if (!baseUrl) return null;

    const url = new URL(baseUrl, window.location.origin);

    // Add pagination params
    url.searchParams.set('page', String(page));
    url.searchParams.set('page_size', String(pageSize));

    // Add additional params
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });

    return url.pathname + url.search;
  }, [baseUrl, page, pageSize, params]);

  // Fetch data
  const fetchData = useCallback(async () => {
    if (!fullUrl) {
      setLoading(false);
      return;
    }

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(fullUrl, {
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [fullUrl]);

  useEffect(() => {
    fetchData();
    return () => abortRef.current?.abort();
  }, [fetchData]);

  // Pagination controls
  const setPage = useCallback((newPage: number) => {
    if (syncToUrl) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.set('page', String(newPage));
        return next;
      });
    } else {
      setLocalPage(newPage);
    }
  }, [syncToUrl, setSearchParams]);

  const setPageSizeHandler = useCallback((newSize: number) => {
    if (syncToUrl) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.set('page_size', String(newSize));
        next.set('page', '1'); // Reset to first page
        return next;
      });
    } else {
      setLocalPageSize(newSize);
      setLocalPage(1);
    }
  }, [syncToUrl, setSearchParams]);

  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  const nextPage = useCallback(() => {
    if (page < totalPages) {
      setPage(page + 1);
    }
  }, [page, totalPages, setPage]);

  const prevPage = useCallback(() => {
    if (page > 1) {
      setPage(page - 1);
    }
  }, [page, setPage]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return {
    items: data?.items ?? [],
    total,
    page,
    pageSize,
    totalPages,
    loading,
    error,
    setPage,
    setPageSize: setPageSizeHandler,
    nextPage,
    prevPage,
    refetch,
    hasNextPage: page < totalPages,
    hasPrevPage: page > 1,
  };
}
