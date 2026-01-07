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

// --- Model Management Types ---

export interface AvailableModel {
  name: string;
  dimensions: number;
  max_length: number;
  size_mb: number;
  description: string;
  loaded: boolean;
  is_current: boolean;
}

export interface VectorCollection {
  name: string;
  vector_size: number;
  points_count: number;
  status: string;
}

export interface ModelSwitchCheckResult {
  success: boolean;
  requires_wipe: boolean | null;
  message: string;
  current_model: string;
  current_dimensions: number;
  new_model: string;
  new_dimensions: number | null;
  affected_collections: string[];
  total_vectors_affected?: number;
}

export interface ModelSwitchResult {
  success: boolean;
  message: string;
  previous_model: string | null;
  new_model: string | null;
  previous_dimensions: number | null;
  new_dimensions: number | null;
  collections_wiped: boolean;
  requires_wipe: boolean;
  affected_collections: string[];
}

export interface CurrentModelInfo {
  model: string;
  dimensions: number;
  max_length: number;
  loaded: boolean;
  device: string | null;
  description: string;
}

// --- Document Embedding Types ---

export interface DocumentForEmbedding {
  id: string;
  title: string;
  filename: string | null;
  mime_type: string | null;
  file_size: number | null;
  created_at: string;
  status: string;
  chunk_count: number;
  embedding_count: number;
  has_embeddings: boolean;
}

export interface DocumentsForEmbeddingResponse {
  documents: DocumentForEmbedding[];
  total: number;
  limit: number;
  offset: number;
}

export interface BatchEmbedQueuedItem {
  job_id: string;
  doc_id: string;
  chunk_count: number;
}

export interface BatchEmbedSkippedItem {
  doc_id: string;
  reason: string;
}

export interface BatchEmbedFailedItem {
  doc_id: string;
  error: string;
}

export interface BatchEmbedDocumentsResponse {
  success: boolean;
  message: string;
  queued: BatchEmbedQueuedItem[];
  skipped: BatchEmbedSkippedItem[];
  failed: BatchEmbedFailedItem[];
  summary: {
    queued_count: number;
    skipped_count: number;
    failed_count: number;
    total_chunks: number;
  };
}
