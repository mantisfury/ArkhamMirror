/**
 * ACH API Service
 *
 * API client for the ACH shard backend.
 */

import type {
  ACHMatrix,
  MatricesListResponse,
  ScoresResponse,
  DevilsAdvocateResponse,
  AIStatusResponse,
  ConsistencyRating,
  EvidenceType,
} from './types';

const API_PREFIX = '/api/ach';

// Generic fetch wrapper with error handling
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

// ============================================
// Matrix Operations
// ============================================

export async function listMatrices(
  projectId?: string,
  status?: string
): Promise<MatricesListResponse> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (status) params.set('status', status);

  const query = params.toString();
  return fetchAPI<MatricesListResponse>(`/matrices${query ? `?${query}` : ''}`);
}

export async function getMatrix(matrixId: string): Promise<ACHMatrix> {
  return fetchAPI<ACHMatrix>(`/matrix/${matrixId}`);
}

export async function createMatrix(data: {
  title: string;
  description?: string;
  project_id?: string;
  created_by?: string;
}): Promise<{ matrix_id: string; title: string; status: string; created_at: string }> {
  return fetchAPI('/matrix', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateMatrix(
  matrixId: string,
  data: {
    title?: string;
    description?: string;
    status?: string;
    notes?: string;
  }
): Promise<{ matrix_id: string; title: string; status: string; updated_at: string }> {
  return fetchAPI(`/matrix/${matrixId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteMatrix(matrixId: string): Promise<{ status: string; matrix_id: string }> {
  return fetchAPI(`/matrix/${matrixId}`, {
    method: 'DELETE',
  });
}

// ============================================
// Hypothesis Operations
// ============================================

export async function addHypothesis(data: {
  matrix_id: string;
  title: string;
  description?: string;
  author?: string;
}): Promise<{ hypothesis_id: string; matrix_id: string; title: string; column_index: number }> {
  return fetchAPI('/hypothesis', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function removeHypothesis(
  matrixId: string,
  hypothesisId: string
): Promise<{ status: string; hypothesis_id: string }> {
  return fetchAPI(`/hypothesis/${matrixId}/${hypothesisId}`, {
    method: 'DELETE',
  });
}

// ============================================
// Evidence Operations
// ============================================

export async function addEvidence(data: {
  matrix_id: string;
  description: string;
  source?: string;
  evidence_type?: EvidenceType;
  credibility?: number;
  relevance?: number;
  author?: string;
  document_ids?: string[];
}): Promise<{ evidence_id: string; matrix_id: string; description: string; row_index: number }> {
  return fetchAPI('/evidence', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function removeEvidence(
  matrixId: string,
  evidenceId: string
): Promise<{ status: string; evidence_id: string }> {
  return fetchAPI(`/evidence/${matrixId}/${evidenceId}`, {
    method: 'DELETE',
  });
}

// ============================================
// Rating Operations
// ============================================

export async function updateRating(data: {
  matrix_id: string;
  evidence_id: string;
  hypothesis_id: string;
  rating: ConsistencyRating;
  reasoning?: string;
  confidence?: number;
  author?: string;
}): Promise<{
  matrix_id: string;
  evidence_id: string;
  hypothesis_id: string;
  rating: string;
  confidence: number;
}> {
  return fetchAPI('/rating', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ============================================
// Scoring Operations
// ============================================

export async function calculateScores(matrixId: string): Promise<ScoresResponse> {
  return fetchAPI(`/score?matrix_id=${matrixId}`, {
    method: 'POST',
  });
}

export async function getDiagnosticity(matrixId: string): Promise<unknown> {
  return fetchAPI(`/diagnosticity/${matrixId}`);
}

export async function getSensitivity(matrixId: string): Promise<unknown> {
  return fetchAPI(`/sensitivity/${matrixId}`);
}

export async function getEvidenceGaps(matrixId: string): Promise<unknown> {
  return fetchAPI(`/evidence-gaps/${matrixId}`);
}

// ============================================
// Export Operations
// ============================================

export async function exportMatrix(
  matrixId: string,
  format: 'json' | 'csv' | 'html' | 'markdown' = 'json'
): Promise<{
  matrix_id: string;
  format: string;
  content_type: string;
  content: unknown;
  generated_at: string;
}> {
  return fetchAPI(`/export/${matrixId}?format=${format}`);
}

// ============================================
// AI Operations
// ============================================

export async function getAIStatus(): Promise<AIStatusResponse> {
  return fetchAPI('/ai/status');
}

export async function suggestHypotheses(data: {
  focus_question: string;
  matrix_id?: string;
  context?: string;
}): Promise<{ suggestions: { title: string; description: string }[]; count: number }> {
  return fetchAPI('/ai/hypotheses', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function suggestEvidence(data: {
  matrix_id: string;
  focus_question?: string;
}): Promise<{
  matrix_id: string;
  suggestions: { description: string; evidence_type: string; source: string }[];
  count: number;
}> {
  return fetchAPI('/ai/evidence', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function suggestRatings(data: {
  matrix_id: string;
  evidence_id: string;
}): Promise<{
  matrix_id: string;
  evidence_id: string;
  suggestions: {
    hypothesis_id: string;
    hypothesis_label: string;
    rating: ConsistencyRating;
    explanation: string;
  }[];
  count: number;
}> {
  return fetchAPI('/ai/ratings', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getAnalysisInsights(matrixId: string): Promise<{
  matrix_id: string;
  insights: string;
  leading_hypothesis: string;
  key_evidence: string[];
  evidence_gaps: string[];
  cognitive_biases: string[];
  recommendations: string[];
}> {
  return fetchAPI('/ai/insights', {
    method: 'POST',
    body: JSON.stringify({ matrix_id: matrixId }),
  });
}

export async function runDevilsAdvocate(data: {
  matrix_id: string;
  hypothesis_id?: string;
}): Promise<DevilsAdvocateResponse> {
  return fetchAPI('/ai/devils-advocate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function suggestMilestones(matrixId: string): Promise<{
  matrix_id: string;
  suggestions: {
    hypothesis_id: string;
    hypothesis_label: string;
    description: string;
  }[];
  count: number;
}> {
  return fetchAPI('/ai/milestones', {
    method: 'POST',
    body: JSON.stringify({ matrix_id: matrixId }),
  });
}

export async function extractEvidence(data: {
  matrix_id: string;
  text: string;
  document_id?: string;
  max_items?: number;
}): Promise<{
  matrix_id: string;
  document_id: string | null;
  suggestions: { description: string; evidence_type: string; source: string }[];
  count: number;
}> {
  return fetchAPI('/ai/extract-evidence', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ============================================
// Linked Documents Operations
// ============================================

export interface LinkedDocumentsResponse {
  matrix_id: string;
  document_ids: string[];
  count: number;
}

export async function getLinkedDocuments(matrixId: string): Promise<LinkedDocumentsResponse> {
  return fetchAPI(`/matrix/${matrixId}/documents`);
}

export async function linkDocuments(
  matrixId: string,
  documentIds: string[]
): Promise<{ matrix_id: string; linked: string[]; total_linked: number }> {
  return fetchAPI(`/matrix/${matrixId}/documents`, {
    method: 'POST',
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export async function unlinkDocument(
  matrixId: string,
  documentId: string
): Promise<{ matrix_id: string; unlinked: string; total_linked: number }> {
  return fetchAPI(`/matrix/${matrixId}/documents/${documentId}`, {
    method: 'DELETE',
  });
}
