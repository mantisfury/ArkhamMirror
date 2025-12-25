/**
 * Search API Service
 *
 * API client for the Search shard backend.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  SearchRequest,
  SearchResponse,
  SearchResultItem,
  Suggestion,
  SimilarResponse,
  AvailableFilters,
} from './types';

const API_PREFIX = '/api/search';

// Generic fetch wrapper with error handling
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================
// Search Operations
// ============================================

export async function performSearch(request: SearchRequest): Promise<SearchResponse> {
  return fetchAPI<SearchResponse>('/', {
    method: 'POST',
    body: JSON.stringify({
      query: request.query,
      mode: request.mode || 'hybrid',
      filters: request.filters || null,
      limit: request.limit || 20,
      offset: request.offset || 0,
      sort_by: request.sort_by || 'relevance',
      sort_order: request.sort_order || 'desc',
      semantic_weight: request.semantic_weight || 0.7,
      keyword_weight: request.keyword_weight || 0.3,
    }),
  });
}

export async function performSemanticSearch(request: SearchRequest): Promise<SearchResponse> {
  return fetchAPI<SearchResponse>('/semantic', {
    method: 'POST',
    body: JSON.stringify({
      ...request,
      mode: 'semantic',
    }),
  });
}

export async function performKeywordSearch(request: SearchRequest): Promise<SearchResponse> {
  return fetchAPI<SearchResponse>('/keyword', {
    method: 'POST',
    body: JSON.stringify({
      ...request,
      mode: 'keyword',
    }),
  });
}

export async function getSuggestions(query: string, limit = 10): Promise<Suggestion[]> {
  const params = new URLSearchParams();
  params.set('q', query);
  params.set('limit', limit.toString());

  const response = await fetchAPI<{ suggestions: Suggestion[] }>(`/suggest?${params.toString()}`);
  return response.suggestions;
}

export async function findSimilar(
  docId: string,
  limit = 10,
  minSimilarity = 0.5,
  filters?: Record<string, unknown>
): Promise<SimilarResponse> {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());
  params.set('min_similarity', minSimilarity.toString());

  return fetchAPI<SimilarResponse>(`/similar/${docId}?${params.toString()}`, {
    method: 'POST',
    body: JSON.stringify({ filters: filters || null }),
  });
}

export async function getAvailableFilters(query?: string): Promise<AvailableFilters> {
  const params = new URLSearchParams();
  if (query) params.set('q', query);

  const response = await fetchAPI<{ available: AvailableFilters }>(`/filters?${params.toString()}`);
  return response.available;
}

// ============================================
// React Hooks
// ============================================

interface UseSearchOptions {
  query: string;
  request?: Partial<SearchRequest>;
  enabled?: boolean;
}

interface UseSearchResult {
  data: SearchResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useSearch(options: UseSearchOptions): UseSearchResult {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await performSearch({
        query: options.query,
        ...options.request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, options.request, options.enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}

export function useSemantic(options: UseSearchOptions): UseSearchResult {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await performSemanticSearch({
        query: options.query,
        ...options.request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, options.request, options.enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}

export function useKeyword(options: UseSearchOptions): UseSearchResult {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await performKeywordSearch({
        query: options.query,
        ...options.request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, options.request, options.enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}

interface UseSimilarResult {
  data: SimilarResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useSimilar(docId: string | null, limit = 10): UseSimilarResult {
  const [data, setData] = useState<SimilarResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    if (!docId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await findSimilar(docId, limit);
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [docId, limit]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}
