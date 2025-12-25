/**
 * Anomalies API Service
 *
 * API client for the Anomalies shard backend.
 */

import type {
  DetectRequest,
  DetectResponse,
  AnomalyListResponse,
  Anomaly,
  StatsResponse,
  PatternRequest,
  PatternsResponse,
} from './types';

const API_PREFIX = '/api/anomalies';

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
// Detection Operations
// ============================================

export async function detectAnomalies(request: DetectRequest): Promise<DetectResponse> {
  return fetchAPI<DetectResponse>('/detect', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function detectDocumentAnomalies(docId: string): Promise<DetectResponse> {
  return fetchAPI<DetectResponse>(`/document/${docId}`, {
    method: 'POST',
  });
}

// ============================================
// List Operations
// ============================================

export async function listAnomalies(filters?: {
  offset?: number;
  limit?: number;
  anomaly_type?: string;
  status?: string;
  severity?: string;
  doc_id?: string;
}): Promise<AnomalyListResponse> {
  const params = new URLSearchParams();
  if (filters?.offset !== undefined) params.set('offset', filters.offset.toString());
  if (filters?.limit !== undefined) params.set('limit', filters.limit.toString());
  if (filters?.anomaly_type) params.set('anomaly_type', filters.anomaly_type);
  if (filters?.status) params.set('status', filters.status);
  if (filters?.severity) params.set('severity', filters.severity);
  if (filters?.doc_id) params.set('doc_id', filters.doc_id);

  const query = params.toString();
  return fetchAPI<AnomalyListResponse>(`/list${query ? `?${query}` : ''}`);
}

export async function getAnomaly(anomalyId: string): Promise<{ anomaly: Anomaly }> {
  return fetchAPI<{ anomaly: Anomaly }>(`/${anomalyId}`);
}

// ============================================
// Status Operations
// ============================================

export async function updateAnomalyStatus(
  anomalyId: string,
  status: string,
  notes?: string,
  reviewedBy?: string
): Promise<{ anomaly: Anomaly }> {
  return fetchAPI<{ anomaly: Anomaly }>(`/${anomalyId}/status`, {
    method: 'PUT',
    body: JSON.stringify({
      status,
      notes: notes || '',
      reviewed_by: reviewedBy,
    }),
  });
}

export async function addNote(
  anomalyId: string,
  content: string,
  author: string
): Promise<{ success: boolean; note_id: string }> {
  return fetchAPI<{ success: boolean; note_id: string }>(`/${anomalyId}/notes`, {
    method: 'POST',
    body: JSON.stringify({
      content,
      author,
    }),
  });
}

// ============================================
// Analysis Operations
// ============================================

export async function getOutliers(
  limit?: number,
  minZScore?: number
): Promise<AnomalyListResponse> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set('limit', limit.toString());
  if (minZScore !== undefined) params.set('min_z_score', minZScore.toString());

  const query = params.toString();
  return fetchAPI<AnomalyListResponse>(`/outliers${query ? `?${query}` : ''}`);
}

export async function detectPatterns(request: PatternRequest): Promise<PatternsResponse> {
  return fetchAPI<PatternsResponse>('/patterns', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getStats(): Promise<StatsResponse> {
  return fetchAPI<StatsResponse>('/stats');
}
