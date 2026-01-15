/**
 * Search Types
 *
 * Type definitions matching the backend Search shard models.
 */

// Search modes
export type SearchMode = 'hybrid' | 'semantic' | 'keyword' | 'regex';

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

// Regex search types
export interface RegexPreset {
  id: string;
  name: string;
  pattern: string;
  description: string;
  category: string;
  flags: string[];
  is_system: boolean;
}

export interface RegexMatch {
  document_id: string;
  document_title: string;
  page_number: number | null;
  chunk_id: string;
  match_text: string;
  context: string;
  start_offset: number;
  end_offset: number;
  line_number: number;
}

export interface RegexSearchRequest {
  pattern: string;
  flags?: string[];
  project_id?: string;
  document_ids?: string[];
  limit?: number;
  offset?: number;
  context_chars?: number;
}

export interface RegexSearchResponse {
  pattern: string;
  matches: RegexMatch[];
  total_matches: number;
  total_chunks_with_matches: number;
  documents_searched: number;
  duration_ms: number;
  error: string | null;
}

export interface PatternValidation {
  valid: boolean;
  error: string | null;
  estimated_performance: 'fast' | 'moderate' | 'slow' | 'dangerous' | 'invalid';
}

export interface PatternExtraction {
  id: string;
  document_id: string;
  preset_id: string;
  preset_name: string | null;
  category: string | null;
  match_text: string;
  context: string | null;
  page_number: number | null;
  chunk_id: string | null;
  start_offset: number | null;
  end_offset: number | null;
  line_number: number | null;
  extracted_at: string | null;
}

export interface ExtractionStats {
  total_extractions: number;
  documents_with_patterns: number;
  by_category: Record<string, number>;
  by_preset: Record<string, number>;
}

// Detected pattern from patterns shard (auto-extracted during ingest)
export interface DetectedPattern {
  id: string;
  name: string;
  description: string | null;
  pattern_type: string;
  status: 'detected' | 'confirmed' | 'dismissed' | 'archived';
  confidence: number;
  match_count: number;
  document_count: number;
  first_detected: string | null;
  last_matched: string | null;
  detection_method: string;
  criteria: {
    keywords?: string[];
    regex_patterns?: string[];
    entity_types?: string[];
    min_occurrences?: number;
  } | null;
}
