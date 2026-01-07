/**
 * Embed API Service
 *
 * API client and hooks for the Embed shard backend.
 */

import { useState, useCallback } from 'react';
import { useFetch } from '../../hooks/useFetch';
import type {
  EmbedResult,
  BatchEmbedResult,
  SimilarityResult,
  NearestResult,
  ModelInfo,
  CacheStats,
  DocumentEmbedJobResponse,
  DocumentEmbeddingsResponse,
  TextEmbedRequest,
  BatchTextsRequest,
  SimilarityRequest,
  NearestRequest,
  DocumentEmbedRequest,
  AvailableModel,
  VectorCollection,
  ModelSwitchCheckResult,
  ModelSwitchResult,
  CurrentModelInfo,
  DocumentsForEmbeddingResponse,
  BatchEmbedDocumentsResponse,
} from './types';

const API_PREFIX = '/api/embed';

// --- Generic fetch wrapper ---

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

// --- API Functions ---

export async function embedText(request: TextEmbedRequest): Promise<EmbedResult> {
  return fetchAPI<EmbedResult>('/text', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function embedBatch(request: BatchTextsRequest): Promise<BatchEmbedResult> {
  return fetchAPI<BatchEmbedResult>('/batch', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function calculateSimilarity(request: SimilarityRequest): Promise<SimilarityResult> {
  return fetchAPI<SimilarityResult>('/similarity', {
    method: 'POST',
    body: JSON.stringify({
      text1: request.text1,
      text2: request.text2,
      method: request.method || 'cosine',
    }),
  });
}

export async function findNearest(request: NearestRequest): Promise<NearestResult> {
  return fetchAPI<NearestResult>('/nearest', {
    method: 'POST',
    body: JSON.stringify({
      query: request.query,
      limit: request.limit || 10,
      min_similarity: request.min_similarity || 0.5,
      collection: request.collection || 'documents',
      filters: request.filters || null,
    }),
  });
}

export async function embedDocument(request: DocumentEmbedRequest): Promise<DocumentEmbedJobResponse> {
  return fetchAPI<DocumentEmbedJobResponse>(`/document/${request.doc_id}`, {
    method: 'POST',
    body: JSON.stringify({
      force: request.force || false,
      chunk_size: request.chunk_size || 512,
      chunk_overlap: request.chunk_overlap || 50,
    }),
  });
}

export async function getDocumentEmbeddings(docId: string): Promise<DocumentEmbeddingsResponse> {
  return fetchAPI<DocumentEmbeddingsResponse>(`/document/${docId}`);
}

export async function getModels(): Promise<ModelInfo[]> {
  return fetchAPI<ModelInfo[]>('/models');
}

export async function getCacheStats(): Promise<CacheStats> {
  return fetchAPI<CacheStats>('/cache/stats');
}

export async function clearCache(): Promise<{ success: boolean; message: string }> {
  return fetchAPI('/cache/clear', {
    method: 'POST',
  });
}

// --- React Hooks ---

/**
 * Hook for embedding a single text
 */
export function useEmbedText() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<EmbedResult | null>(null);

  const embed = useCallback(async (text: string, options?: Partial<TextEmbedRequest>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await embedText({ text, ...options });
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Embed failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { embed, data, loading, error };
}

/**
 * Hook for embedding multiple texts in batch
 */
export function useEmbedBatch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<BatchEmbedResult | null>(null);

  const embed = useCallback(async (texts: string[], batchSize?: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await embedBatch({ texts, batch_size: batchSize });
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Batch embed failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { embed, data, loading, error };
}

/**
 * Hook for calculating similarity between two texts
 */
export function useSimilarity() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<SimilarityResult | null>(null);

  const calculate = useCallback(async (text1: string, text2: string, method?: 'cosine' | 'euclidean' | 'dot') => {
    setLoading(true);
    setError(null);
    try {
      const result = await calculateSimilarity({ text1, text2, method });
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Similarity calculation failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { calculate, data, loading, error };
}

/**
 * Hook for finding nearest neighbors
 */
export function useNearest() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<NearestResult | null>(null);

  const search = useCallback(async (query: string | number[], options?: Partial<NearestRequest>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await findNearest({ query, ...options });
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Nearest neighbor search failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { search, data, loading, error };
}

/**
 * Hook for embedding a document
 */
export function useEmbedDocument() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const embed = useCallback(async (docId: string, options?: Partial<DocumentEmbedRequest>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await embedDocument({ doc_id: docId, ...options });
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Document embed failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { embed, loading, error };
}

/**
 * Hook for fetching available models
 */
export function useModels() {
  return useFetch<ModelInfo[]>(`${API_PREFIX}/models`);
}

/**
 * Hook for fetching cache statistics
 */
export function useCacheStats() {
  return useFetch<CacheStats>(`${API_PREFIX}/cache/stats`);
}

/**
 * Hook for clearing cache
 */
export function useClearCache() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clear = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await clearCache();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Clear cache failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { clear, loading, error };
}

// --- Model Management API Functions ---

export async function getCurrentModel(): Promise<CurrentModelInfo> {
  return fetchAPI<CurrentModelInfo>('/model/current');
}

export async function getAvailableModels(): Promise<AvailableModel[]> {
  return fetchAPI<AvailableModel[]>('/model/available');
}

export async function getVectorCollections(): Promise<VectorCollection[]> {
  return fetchAPI<VectorCollection[]>('/model/collections');
}

export async function checkModelSwitch(model: string): Promise<ModelSwitchCheckResult> {
  return fetchAPI<ModelSwitchCheckResult>('/model/check-switch', {
    method: 'POST',
    body: JSON.stringify({ model }),
  });
}

export async function switchModel(model: string, confirmWipe: boolean = false): Promise<ModelSwitchResult> {
  return fetchAPI<ModelSwitchResult>('/model/switch', {
    method: 'POST',
    body: JSON.stringify({ model, confirm_wipe: confirmWipe }),
  });
}

// --- Model Management Hooks ---

/**
 * Hook for fetching current model info
 */
export function useCurrentModel() {
  return useFetch<CurrentModelInfo>(`${API_PREFIX}/model/current`);
}

/**
 * Hook for fetching available models
 */
export function useAvailableModels() {
  return useFetch<AvailableModel[]>(`${API_PREFIX}/model/available`);
}

/**
 * Hook for fetching vector collections
 */
export function useVectorCollections() {
  return useFetch<VectorCollection[]>(`${API_PREFIX}/model/collections`);
}

/**
 * Hook for checking model switch impact
 */
export function useCheckModelSwitch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<ModelSwitchCheckResult | null>(null);

  const check = useCallback(async (model: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await checkModelSwitch(model);
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Check failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { check, data, loading, error };
}

/**
 * Hook for switching embedding model
 */
export function useSwitchModel() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<ModelSwitchResult | null>(null);

  const switchTo = useCallback(async (model: string, confirmWipe: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const result = await switchModel(model, confirmWipe);
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Switch failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { switchTo, data, loading, error };
}

// --- Document Embedding API Functions ---

export async function getDocumentsForEmbedding(
  limit: number = 100,
  offset: number = 0,
  onlyUnembedded: boolean = false
): Promise<DocumentsForEmbeddingResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    only_unembedded: String(onlyUnembedded),
  });
  return fetchAPI<DocumentsForEmbeddingResponse>(`/documents/available?${params}`);
}

export async function embedDocumentsBatch(docIds: string[]): Promise<BatchEmbedDocumentsResponse> {
  return fetchAPI<BatchEmbedDocumentsResponse>('/documents/batch', {
    method: 'POST',
    body: JSON.stringify({ doc_ids: docIds }),
  });
}

// --- Document Embedding Hooks ---

/**
 * Hook for fetching documents available for embedding
 */
export function useDocumentsForEmbedding(onlyUnembedded: boolean = false) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<DocumentsForEmbeddingResponse | null>(null);

  const fetch = useCallback(async (limit: number = 100, offset: number = 0) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getDocumentsForEmbedding(limit, offset, onlyUnembedded);
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch documents');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [onlyUnembedded]);

  const refetch = useCallback(() => {
    return fetch();
  }, [fetch]);

  return { fetch, refetch, data, loading, error };
}

/**
 * Hook for batch embedding multiple documents
 */
export function useBatchEmbedDocuments() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<BatchEmbedDocumentsResponse | null>(null);

  const embed = useCallback(async (docIds: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const result = await embedDocumentsBatch(docIds);
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Batch embed failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { embed, data, loading, error };
}
