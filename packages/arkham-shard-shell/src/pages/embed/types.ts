/**
 * Embed Shard Types
 *
 * TypeScript interfaces for the Embed shard API.
 */

// --- API Request/Response Types ---

export interface EmbedResult {
  embedding: number[];
  dimensions: number;
  model: string;
  doc_id?: string;
  chunk_id?: string;
  text_length: number;
  success: boolean;
}

export interface BatchEmbedResult {
  embeddings: number[][];
  dimensions: number;
  model: string;
  count: number;
  success: boolean;
}

export interface SimilarityResult {
  similarity: number;
  method: string;
  success: boolean;
  error?: string;
}

export interface NearestNeighbor {
  id: string;
  score: number;
  payload?: Record<string, unknown>;
}

export interface NearestResult {
  neighbors: NearestNeighbor[];
  total: number;
  query_dimensions: number;
  success: boolean;
  error?: string;
}

export interface ModelInfo {
  name: string;
  dimensions: number;
  max_length: number;
  size_mb: number;
  loaded: boolean;
  description?: string;
}

export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
  max_size: number;
  hit_rate: number;
}

export interface DocumentEmbedJobResponse {
  job_id: string;
  doc_id: string;
  status: string;
  message: string;
}

export interface DocumentEmbeddingsResponse {
  doc_id: string;
  embeddings: unknown[];
  count: number;
}

// --- Request Types ---

export interface TextEmbedRequest {
  text: string;
  doc_id?: string;
  chunk_id?: string;
  use_cache?: boolean;
}

export interface BatchTextsRequest {
  texts: string[];
  batch_size?: number;
}

export interface SimilarityRequest {
  text1: string;
  text2: string;
  method?: 'cosine' | 'euclidean' | 'dot';
}

export interface NearestRequest {
  query: string | number[];
  limit?: number;
  min_similarity?: number;
  collection?: string;
  filters?: Record<string, unknown>;
}

export interface DocumentEmbedRequest {
  doc_id: string;
  force?: boolean;
  chunk_size?: number;
  chunk_overlap?: number;
}
