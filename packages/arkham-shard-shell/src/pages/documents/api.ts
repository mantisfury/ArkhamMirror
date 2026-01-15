/**
 * Documents API Service
 *
 * API client and hooks for the Documents shard backend.
 */

import { useState, useCallback } from 'react';
import { useFetch } from '../../hooks/useFetch';

const API_PREFIX = '/api/documents';

// --- Types ---

export interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
  page_count: number;
  chunk_count: number;
  entity_count: number;
  created_at: string;
  updated_at: string;
  project_id?: string;
  tags: string[];
  custom_metadata: Record<string, unknown>;
}

export interface DocumentStats {
  total_documents: number;
  processed_documents: number;
  processing_documents: number;
  failed_documents: number;
  total_size_bytes: number;
  total_pages: number;
  total_chunks: number;
}

export interface DocumentContent {
  document_id: string;
  content: string;
  page_number: number | null;
  total_pages: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  page_number: number | null;
  token_count: number;
  embedding_id: string | null;
}

export interface ChunkListResponse {
  items: DocumentChunk[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentEntity {
  id: string;
  document_id: string;
  entity_type: string;
  text: string;
  confidence: number;
  occurrences: number;
  context: string[];
}

export interface EntityListResponse {
  items: DocumentEntity[];
  total: number;
}

export interface RecentlyViewedResponse {
  items: Document[];
  total: number;
}

export interface BatchResult {
  success: boolean;
  processed: number;
  failed: number;
  message: string;
  details?: Array<{ id: string; success?: boolean; error?: string }>;
}

// --- Deduplication Types ---

export interface DocumentHash {
  document_id: string;
  content_md5: string;
  content_sha256: string;
  simhash: number;
  text_length: number;
}

export interface DuplicateResult {
  document_id: string;
  title: string;
  similarity_score: number;
  hamming_distance: number;
  match_type: 'exact' | 'similar';
}

export interface DeduplicationStats {
  total_documents: number;
  documents_with_hash: number;
  unique_content_hashes: number;
  potential_duplicates: number;
}

export interface MergeRequest {
  source_ids: string[];
  target_id: string;
  strategy: 'soft_delete' | 'archive' | 'permanent_delete';
}

// --- API Functions ---

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${endpoint}`, {
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function getDocument(documentId: string): Promise<Document> {
  return fetchAPI<Document>(`/items/${documentId}`);
}

export async function getDocumentContent(
  documentId: string,
  page?: number
): Promise<DocumentContent> {
  const query = page ? `?page=${page}` : '';
  return fetchAPI<DocumentContent>(`/${documentId}/content${query}`);
}

export async function getDocumentPage(
  documentId: string,
  pageNumber: number
): Promise<DocumentContent> {
  return fetchAPI<DocumentContent>(`/${documentId}/pages/${pageNumber}`);
}

export async function getDocumentChunks(
  documentId: string,
  page: number = 1,
  pageSize: number = 50
): Promise<ChunkListResponse> {
  return fetchAPI<ChunkListResponse>(
    `/${documentId}/chunks?page=${page}&page_size=${pageSize}`
  );
}

export async function getDocumentEntities(
  documentId: string,
  entityType?: string
): Promise<EntityListResponse> {
  const query = entityType ? `?entity_type=${entityType}` : '';
  return fetchAPI<EntityListResponse>(`/${documentId}/entities${query}`);
}

export async function getRecentlyViewed(
  limit: number = 10
): Promise<RecentlyViewedResponse> {
  return fetchAPI<RecentlyViewedResponse>(`/recently-viewed?limit=${limit}`);
}

export async function updateDocumentMetadata(
  documentId: string,
  data: { title?: string; tags?: string[]; custom_metadata?: Record<string, unknown> }
): Promise<Document> {
  return fetchAPI<Document>(`/items/${documentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await fetchAPI(`/items/${documentId}`, { method: 'DELETE' });
}

export async function batchUpdateTags(
  documentIds: string[],
  addTags?: string[],
  removeTags?: string[]
): Promise<BatchResult> {
  return fetchAPI<BatchResult>('/batch/update-tags', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_ids: documentIds,
      add_tags: addTags,
      remove_tags: removeTags,
    }),
  });
}

export async function batchDeleteDocuments(documentIds: string[]): Promise<BatchResult> {
  return fetchAPI<BatchResult>('/batch/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

// --- Deduplication API Functions ---

export async function computeDocumentHash(documentId: string): Promise<DocumentHash> {
  return fetchAPI<DocumentHash>(`/${documentId}/compute-hash`, {
    method: 'POST',
  });
}

export async function findExactDuplicates(documentId: string): Promise<DuplicateResult[]> {
  return fetchAPI<DuplicateResult[]>(`/${documentId}/duplicates/exact`);
}

export async function findSimilarDuplicates(
  documentId: string,
  threshold: number = 0.8
): Promise<DuplicateResult[]> {
  return fetchAPI<DuplicateResult[]>(`/${documentId}/duplicates/similar?threshold=${threshold}`);
}

export async function getDeduplicationStats(): Promise<DeduplicationStats> {
  return fetchAPI<DeduplicationStats>('/deduplication/stats');
}

export async function scanForDuplicates(
  projectId: string,
  similarityThreshold: number = 0.8
): Promise<DuplicateResult[]> {
  return fetchAPI<DuplicateResult[]>(
    `/deduplication/scan?project_id=${projectId}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ similarity_threshold: similarityThreshold }),
    }
  );
}

export async function mergeDuplicates(request: MergeRequest): Promise<BatchResult> {
  return fetchAPI<BatchResult>('/deduplication/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

// --- Hooks ---

/**
 * Hook for fetching document content
 */
export function useDocumentContent(documentId: string | null, page?: number) {
  const query = page ? `?page=${page}` : '';
  const url = documentId ? `${API_PREFIX}/${documentId}/content${query}` : null;
  return useFetch<DocumentContent>(url);
}

/**
 * Hook for fetching document chunks
 */
export function useDocumentChunks(
  documentId: string | null,
  page: number = 1,
  pageSize: number = 50
) {
  const url = documentId
    ? `${API_PREFIX}/${documentId}/chunks?page=${page}&page_size=${pageSize}`
    : null;
  return useFetch<ChunkListResponse>(url);
}

/**
 * Hook for fetching document entities
 */
export function useDocumentEntities(documentId: string | null, entityType?: string) {
  const query = entityType ? `?entity_type=${entityType}` : '';
  const url = documentId ? `${API_PREFIX}/${documentId}/entities${query}` : null;
  return useFetch<EntityListResponse>(url);
}

/**
 * Hook for fetching a single document
 */
export function useDocument(documentId: string | null) {
  const url = documentId ? `${API_PREFIX}/items/${documentId}` : null;
  return useFetch<Document>(url);
}

/**
 * Hook for fetching recently viewed documents
 */
export function useRecentlyViewed(limit: number = 10) {
  return useFetch<RecentlyViewedResponse>(`${API_PREFIX}/recently-viewed?limit=${limit}`);
}

/**
 * Hook for updating document metadata
 */
export function useUpdateDocument() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const update = useCallback(
    async (
      documentId: string,
      data: { title?: string; tags?: string[]; custom_metadata?: Record<string, unknown> }
    ) => {
      setLoading(true);
      setError(null);
      try {
        const result = await updateDocumentMetadata(documentId, data);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Update failed');
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { update, loading, error };
}

/**
 * Hook for batch tag operations
 */
export function useBatchTags() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const updateTags = useCallback(
    async (documentIds: string[], addTags?: string[], removeTags?: string[]) => {
      setLoading(true);
      setError(null);
      try {
        const result = await batchUpdateTags(documentIds, addTags, removeTags);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Batch update failed');
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { updateTags, loading, error };
}

/**
 * Hook for batch delete
 */
export function useBatchDelete() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const deleteDocuments = useCallback(async (documentIds: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const result = await batchDeleteDocuments(documentIds);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Batch delete failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { deleteDocuments, loading, error };
}

// --- Deduplication Hooks ---

/**
 * Hook for fetching deduplication stats
 */
export function useDeduplicationStats() {
  return useFetch<DeduplicationStats>(`${API_PREFIX}/deduplication/stats`);
}

/**
 * Hook for finding exact duplicates of a document
 */
export function useExactDuplicates(documentId: string | null) {
  const url = documentId ? `${API_PREFIX}/${documentId}/duplicates/exact` : null;
  return useFetch<DuplicateResult[]>(url);
}

/**
 * Hook for finding similar duplicates of a document
 */
export function useSimilarDuplicates(documentId: string | null, threshold: number = 0.8) {
  const url = documentId
    ? `${API_PREFIX}/${documentId}/duplicates/similar?threshold=${threshold}`
    : null;
  return useFetch<DuplicateResult[]>(url);
}

/**
 * Hook for computing document hash
 */
export function useComputeHash() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const computeHash = useCallback(async (documentId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await computeDocumentHash(documentId);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Hash computation failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { computeHash, loading, error };
}

/**
 * Hook for merging duplicates
 */
export function useMergeDuplicates() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const merge = useCallback(async (request: MergeRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await mergeDuplicates(request);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Merge failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { merge, loading, error };
}
