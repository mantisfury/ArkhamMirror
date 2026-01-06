/**
 * Graph API - Backend API calls for graph functionality
 */

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
  const response = await fetch('/api/graph/scores', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to calculate scores' }));
    throw new Error(error.detail || 'Failed to calculate scores');
  }

  return response.json();
}

/**
 * Fetch composite scores with simplified parameters.
 */
export async function fetchScoresSimple(
  projectId: string,
  centralityType: string = 'pagerank',
  limit: number = 100
): Promise<ScoreResponse> {
  const response = await fetch(
    `/api/graph/scores/${projectId}?centrality_type=${centralityType}&limit=${limit}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch scores' }));
    throw new Error(error.detail || 'Failed to fetch scores');
  }

  return response.json();
}
