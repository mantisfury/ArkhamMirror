/**
 * Parse Types
 *
 * Type definitions matching the backend Parse shard models.
 */

// Entity types
export type EntityType = 'PERSON' | 'ORG' | 'LOCATION' | 'DATE' | 'MONEY' | 'GPE' | 'EVENT' | 'PRODUCT';

// Entity mention
export interface EntityMention {
  text: string;
  entity_type: EntityType;
  start_char: number;
  end_char: number;
  confidence: number;
  doc_id?: string;
  canonical_entity_id?: string;
}

// Date extraction
export interface DateMention {
  text: string;
  normalized_date: string | null;
  start_char: number;
  end_char: number;
  confidence: number;
  doc_id?: string;
}

// Location extraction
export interface LocationMention {
  text: string;
  latitude?: number;
  longitude?: number;
  start_char: number;
  end_char: number;
  confidence: number;
  doc_id?: string;
}

// Relationship
export interface Relationship {
  subject: EntityMention;
  predicate: string;
  object: EntityMention;
  confidence: number;
  doc_id?: string;
}

// Text chunk
export interface TextChunk {
  chunk_id: string;
  text: string;
  start_char: number;
  end_char: number;
  chunk_index: number;
  document_id: string;
  metadata?: Record<string, unknown>;
}

// Parse text request
export interface ParseTextRequest {
  text: string;
  doc_id?: string;
  extract_entities?: boolean;
  extract_dates?: boolean;
  extract_locations?: boolean;
  extract_relationships?: boolean;
}

// Parse text response
export interface ParseTextResponse {
  entities: EntityMention[];
  dates: DateMention[];
  locations: LocationMention[];
  relationships: Relationship[];
  total_entities: number;
  total_dates: number;
  total_locations: number;
  processing_time_ms: number;
}

// Parse document response
export interface ParseDocumentResponse {
  document_id: string;
  entities: EntityMention[];
  dates: DateMention[];
  chunks: TextChunk[];
  total_entities: number;
  total_chunks: number;
  status: string;
  processing_time_ms: number;
}

// Get entities response
export interface GetEntitiesResponse {
  document_id: string;
  entities: EntityMention[];
  total: number;
}

// Get chunks response
export interface GetChunksResponse {
  document_id: string;
  chunks: TextChunk[];
  total: number;
}

// Chunk text request
export interface ChunkTextRequest {
  text: string;
  chunk_size?: number;
  overlap?: number;
  method?: string;
}

// Chunk text response
export interface ChunkTextResponse {
  chunks: TextChunk[];
  total_chunks: number;
  total_chars: number;
}

// Entity link request
export interface EntityLinkRequest {
  entities: EntityMention[];
}

// Entity link response
export interface EntityLinkResponse {
  linked_entities: Array<{
    mention: EntityMention;
    canonical_entity_id: string | null;
    confidence: number;
    reason: string;
  }>;
  new_canonical_entities: number;
}

// Parse stats response
export interface ParseStatsResponse {
  total_entities: number;
  total_chunks: number;
  total_documents_parsed: number;
  entity_types: Record<EntityType, number>;
}

// Entity by type
export interface EntitiesByType {
  PERSON: EntityMention[];
  ORG: EntityMention[];
  LOCATION: EntityMention[];
  DATE: DateMention[];
  MONEY: EntityMention[];
  GPE: EntityMention[];
  EVENT: EntityMention[];
  PRODUCT: EntityMention[];
}
