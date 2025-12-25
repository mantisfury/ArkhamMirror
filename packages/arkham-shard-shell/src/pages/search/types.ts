/**
 * Search Types
 *
 * Type definitions matching the backend Search shard models.
 */

// Search modes
export type SearchMode = 'hybrid' | 'semantic' | 'keyword';

// Sort options
export type SortBy = 'relevance' | 'date' | 'title';
export type SortOrder = 'asc' | 'desc';

// Search result item
export interface SearchResultItem {
  doc_id: string;
  chunk_id: string | null;
  title: string;
  excerpt: string;
  score: number;
  file_type: string | null;
  created_at: string | null;
  page_number: number | null;
  highlights: string[];
  entities: string[];
  project_ids: string[];
  metadata: Record<string, unknown>;
}

// Search filters
export interface SearchFilters {
  date_from?: string;
  date_to?: string;
  entity_types?: string[];
  file_types?: string[];
  project_id?: string;
}

// Search request
export interface SearchRequest {
  query: string;
  mode?: SearchMode;
  filters?: SearchFilters;
  limit?: number;
  offset?: number;
  sort_by?: SortBy;
  sort_order?: SortOrder;
  semantic_weight?: number;
  keyword_weight?: number;
}

// Search response
export interface SearchResponse {
  query: string;
  mode: SearchMode;
  total: number;
  items: SearchResultItem[];
  duration_ms: number;
  facets: Record<string, unknown>;
  offset: number;
  limit: number;
  has_more: boolean;
}

// Autocomplete suggestion
export interface Suggestion {
  text: string;
  score: number;
  type: string;
}

// Similar documents response
export interface SimilarResponse {
  doc_id: string;
  similar: SearchResultItem[];
  total: number;
}

// Available filters response
export interface AvailableFilters {
  file_types?: { value: string; count: number }[];
  entity_types?: { value: string; count: number }[];
  projects?: { value: string; label: string; count: number }[];
  date_range?: { min: string; max: string };
}
