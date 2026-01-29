/**
 * Graph API - Backend API calls for graph functionality
 */

import { apiGet, apiPost } from '../../utils/api';

// Types
export interface ScoreConfig {
  project_id: string;
  centrality_type: string;
  centrality_weight: number;
  frequency_weight: number;
  recency_weight: number;
  credibility_weight: number;
  corroboration_weight: number;
  recency_half_life_days: number | null;
  entity_type_weights?: Record<string, number>;
  limit?: number;
}

export interface EntityScore {
  entity_id: string;
  label: string;
  entity_type: string;
  composite_score: number;
  centrality_score: number;
  frequency_score: number;
  recency_score: number;
  credibility_score: number;
  corroboration_score: number;
  rank: number;
  degree: number;
  document_count: number;
  source_count: number;
}

export interface ScoreResponse {
  project_id: string;
  scores: EntityScore[];
  config: {
    centrality_type: string;
    weights: Record<string, number>;
    recency_half_life_days: number | null;
  };
  calculation_time_ms: number;
  entity_count: number;
}

/**
 * Fetch composite scores for all entities in a graph.
 */
export async function fetchScores(config: ScoreConfig): Promise<ScoreResponse> {
  return apiPost<ScoreResponse>('/api/graph/scores', config);
}

/**
 * Fetch composite scores with simplified parameters.
 */
export async function fetchScoresSimple(
  projectId: string,
  centralityType: string = 'pagerank',
  limit: number = 100
): Promise<ScoreResponse> {
  const params = new URLSearchParams({
    centrality_type: centralityType,
    limit: String(limit),
  });
  return apiGet<ScoreResponse>(`/api/graph/scores/${projectId}?${params.toString()}`);
}
