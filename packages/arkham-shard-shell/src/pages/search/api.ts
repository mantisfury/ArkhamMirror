/**
 * Search API Service
 *
 * API client for the Search shard backend.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  SearchRequest,
  SearchResponse,
  Suggestion,
  SimilarResponse,
  AvailableFilters,
  RegexPreset,
  RegexSearchRequest,
  RegexSearchResponse,
  PatternValidation,
  PatternExtraction,
  ExtractionStats,
  DetectedPattern,
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
// Regex Search Operations
// ============================================

export async function performRegexSearch(request: RegexSearchRequest): Promise<RegexSearchResponse> {
  return fetchAPI<RegexSearchResponse>('/regex', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function validatePattern(pattern: string): Promise<PatternValidation> {
  return fetchAPI<PatternValidation>('/regex/validate', {
    method: 'POST',
    body: JSON.stringify({ pattern }),
  });
}

export async function getRegexPresets(category?: string): Promise<RegexPreset[]> {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  return fetchAPI<RegexPreset[]>(`/regex/presets?${params.toString()}`);
}

export async function createRegexPreset(preset: {
  name: string;
  pattern: string;
  description?: string;
  category?: string;
  flags?: string[];
}): Promise<RegexPreset> {
  return fetchAPI<RegexPreset>('/regex/presets', {
    method: 'POST',
    body: JSON.stringify(preset),
  });
}

export async function deleteRegexPreset(presetId: string): Promise<{ success: boolean }> {
  return fetchAPI<{ success: boolean }>(`/regex/presets/${presetId}`, {
    method: 'DELETE',
  });
}

export async function getPatternExtractions(params: {
  document_id?: string;
  preset_id?: string;
  category?: string;
  limit?: number;
  offset?: number;
}): Promise<{ extractions: PatternExtraction[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params.document_id) searchParams.set('document_id', params.document_id);
  if (params.preset_id) searchParams.set('preset_id', params.preset_id);
  if (params.category) searchParams.set('category', params.category);
  if (params.limit) searchParams.set('limit', params.limit.toString());
  if (params.offset) searchParams.set('offset', params.offset.toString());
  return fetchAPI<{ extractions: PatternExtraction[]; total: number }>(
    `/regex/extractions?${searchParams.toString()}`
  );
}

export async function getExtractionStats(): Promise<ExtractionStats> {
  return fetchAPI<ExtractionStats>('/regex/extractions/stats');
}

export async function triggerPatternExtraction(
  documentId: string,
  presetIds?: string[]
): Promise<{ document_id: string; extractions: number; presets_used: string[] }> {
  const body = presetIds ? JSON.stringify({ preset_ids: presetIds }) : '{}';
  return fetchAPI<{ document_id: string; extractions: number; presets_used: string[] }>(
    `/regex/extract/${documentId}`,
    {
      method: 'POST',
      body,
    }
  );
}

// ============================================
// Detected Patterns from Patterns Shard
// ============================================

export async function getDetectedPatterns(params?: {
  status?: string;
  pattern_type?: string;
  has_regex?: boolean;
  limit?: number;
}): Promise<{ items: DetectedPattern[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.pattern_type) searchParams.set('type', params.pattern_type);
  if (params?.limit) searchParams.set('page_size', params.limit.toString());

  const response = await fetch(`/api/patterns/?${searchParams.toString()}`, {
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
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

  // Serialize request to avoid infinite re-renders from object reference changes
  const requestJson = JSON.stringify(options.request || {});

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request = JSON.parse(requestJson);
      const result = await performSearch({
        query: options.query,
        ...request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, requestJson, options.enabled]);

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

  const requestJson = JSON.stringify(options.request || {});

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request = JSON.parse(requestJson);
      const result = await performSemanticSearch({
        query: options.query,
        ...request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, requestJson, options.enabled]);

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

  const requestJson = JSON.stringify(options.request || {});

  const fetchData = useCallback(async () => {
    if (!options.query || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request = JSON.parse(requestJson);
      const result = await performKeywordSearch({
        query: options.query,
        ...request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.query, requestJson, options.enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}

// ============================================
// Regex Search Hooks
// ============================================

interface UseRegexSearchOptions {
  pattern: string;
  request?: Partial<RegexSearchRequest>;
  enabled?: boolean;
}

interface UseRegexSearchResult {
  data: RegexSearchResponse | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useRegexSearch(options: UseRegexSearchOptions): UseRegexSearchResult {
  const [data, setData] = useState<RegexSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const requestJson = JSON.stringify(options.request || {});

  const fetchData = useCallback(async () => {
    if (!options.pattern || options.enabled === false) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request = JSON.parse(requestJson);
      const result = await performRegexSearch({
        pattern: options.pattern,
        ...request,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [options.pattern, requestJson, options.enabled]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}

export function useRegexPresets(category?: string) {
  const [data, setData] = useState<RegexPreset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getRegexPresets(category);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

export function useExtractionStats() {
  const [data, setData] = useState<ExtractionStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getExtractionStats();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
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

export function useDetectedPatterns(params?: {
  status?: string;
  pattern_type?: string;
  has_regex?: boolean;
  limit?: number;
}) {
  const [data, setData] = useState<DetectedPattern[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const paramsJson = JSON.stringify(params || {});

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const parsedParams = JSON.parse(paramsJson);
      const result = await getDetectedPatterns(parsedParams);
      setData(result.items || []);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [paramsJson]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
