/**
 * Parse API Service
 *
 * API client and hooks for the Parse shard backend.
 */

import { useState, useCallback } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { apiFetch } from '../../utils/api';
import type {
  ParseTextRequest,
  ParseTextResponse,
  ParseDocumentResponse,
  GetEntitiesResponse,
  GetChunksResponse,
  ChunkTextRequest,
  ChunkTextResponse,
  EntityLinkRequest,
  EntityLinkResponse,
  ParseStatsResponse,
} from './types';

const API_PREFIX = '/api/parse';

// --- API Functions ---

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${API_PREFIX}${endpoint}`, {
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

export async function parseText(request: ParseTextRequest): Promise<ParseTextResponse> {
  return fetchAPI<ParseTextResponse>('/text', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function parseDocument(docId: string): Promise<ParseDocumentResponse> {
  return fetchAPI<ParseDocumentResponse>(`/document/${docId}`, {
    method: 'POST',
  });
}

export async function getEntities(docId: string): Promise<GetEntitiesResponse> {
  return fetchAPI<GetEntitiesResponse>(`/entities/${docId}`);
}

export async function getChunks(docId: string): Promise<GetChunksResponse> {
  return fetchAPI<GetChunksResponse>(`/chunks/${docId}`);
}

export async function chunkText(request: ChunkTextRequest): Promise<ChunkTextResponse> {
  return fetchAPI<ChunkTextResponse>('/chunk', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function linkEntities(request: EntityLinkRequest): Promise<EntityLinkResponse> {
  return fetchAPI<EntityLinkResponse>('/link', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getParseStats(): Promise<ParseStatsResponse> {
  return fetchAPI<ParseStatsResponse>('/stats');
}

// --- Response Types ---

export interface AllChunksResponse {
  chunks: Array<{
    id: string;
    document_id: string;
    document_name: string;
    chunk_index: number;
    text: string;
    full_text: string;
    page_number: number | null;
    start_char: number;
    end_char: number;
    token_count: number;
    vector_id: string | null;
  }>;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// --- Hooks ---

/**
 * Hook for parsing text and extracting entities
 */
export function useParseText() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const parse = useCallback(async (request: ParseTextRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await parseText(request);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Parse failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { parse, loading, error };
}

/**
 * Hook for parsing a document
 */
export function useParseDocument() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const parse = useCallback(async (docId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await parseDocument(docId);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Parse document failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { parse, loading, error };
}

/**
 * Hook for fetching entities for a document
 */
export function useEntities(docId: string | null) {
  const url = docId ? `${API_PREFIX}/entities/${docId}` : null;
  return useFetch<GetEntitiesResponse>(url);
}

/**
 * Hook for fetching chunks for a document
 */
export function useChunks(docId: string | null) {
  const url = docId ? `${API_PREFIX}/chunks/${docId}` : null;
  return useFetch<GetChunksResponse>(url);
}

/**
 * Hook for chunking text
 */
export function useChunkText() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const chunk = useCallback(async (request: ChunkTextRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await chunkText(request);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Chunk failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { chunk, loading, error };
}

/**
 * Hook for linking entities
 */
export function useLinkEntities() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const link = useCallback(async (request: EntityLinkRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await linkEntities(request);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Link failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { link, loading, error };
}

/**
 * Hook for fetching parse statistics
 */
export function useParseStats() {
  return useFetch<ParseStatsResponse>(`${API_PREFIX}/stats`);
}

/**
 * Hook for fetching all chunks with pagination
 */
export function useAllChunks(limit: number = 50, offset: number = 0, documentId?: string) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (documentId) {
    params.append('document_id', documentId);
  }
  return useFetch<AllChunksResponse>(`${API_PREFIX}/chunks?${params.toString()}`);
}

// --- Chunking Configuration ---

export interface ChunkingConfig {
  chunk_size: number;
  chunk_overlap: number;
  chunk_method: 'fixed' | 'sentence' | 'semantic';
  available_methods: string[];
}

export async function getChunkingConfig(): Promise<ChunkingConfig> {
  return fetchAPI<ChunkingConfig>('/config/chunking');
}

export async function updateChunkingConfig(config: {
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_method?: string;
}): Promise<ChunkingConfig> {
  return fetchAPI<ChunkingConfig>('/config/chunking', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export function useChunkingConfig() {
  return useFetch<ChunkingConfig>(`${API_PREFIX}/config/chunking`);
}
