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
  BulkStatusResponse,
  RelatedAnomaliesResponse,
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

export async function getRelatedAnomalies(
  anomalyId: string,
  limit?: number
): Promise<RelatedAnomaliesResponse> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set('limit', limit.toString());
  const query = params.toString();
  return fetchAPI<RelatedAnomaliesResponse>(`/${anomalyId}/related${query ? `?${query}` : ''}`);
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

// ============================================
// Bulk Operations
// ============================================

export async function bulkUpdateStatus(
  anomalyIds: string[],
  status: string,
  notes?: string,
  reviewedBy?: string
): Promise<BulkStatusResponse> {
  return fetchAPI<BulkStatusResponse>('/bulk-status', {
    method: 'POST',
    body: JSON.stringify({
      anomaly_ids: anomalyIds,
      status,
      notes: notes || '',
      reviewed_by: reviewedBy,
    }),
  });
}

// ============================================
// Hidden Content Detection Operations
// ============================================

export interface HiddenContentScanRequest {
  doc_id: string;
  scan_type?: string;
  config?: Record<string, unknown>;
}

export interface EntropyRegion {
  start_offset: number;
  end_offset: number;
  entropy_value: number;
  is_anomalous: boolean;
  description: string;
}

export interface LSBAnalysisResult {
  bit_ratio: number;
  chi_square_value: number;
  chi_square_p_value: number;
  is_suspicious: boolean;
  confidence: number;
  sample_size: number;
}

export interface StegoIndicator {
  indicator_type: string;
  confidence: number;
  location: string;
  details: Record<string, unknown>;
}

export interface HiddenContentScan {
  id: string;
  doc_id: string;
  scan_type: string;
  scan_status: string;
  entropy_global: number;
  entropy_regions: EntropyRegion[];
  magic_expected: string;
  magic_actual: string;
  file_mismatch: boolean;
  lsb_result: LSBAnalysisResult | null;
  stego_indicators: StegoIndicator[];
  stego_confidence: number;
  findings: string[];
  created_at: string;
  completed_at: string | null;
}

export interface HiddenContentScanResponse {
  scan: HiddenContentScan;
  anomaly_created: boolean;
}

export interface HiddenContentQuickScanRequest {
  doc_ids: string[];
}

export interface QuickScanResult {
  doc_id: string;
  entropy_global?: number;
  requires_full_scan?: boolean;
  error?: string;
}

export interface HiddenContentQuickScanResponse {
  scanned: number;
  results: QuickScanResult[];
  requires_full_scan_count: number;
  requires_full_scan: string[];
}

export interface HiddenContentStats {
  total_scans: number;
  scans_by_type: Record<string, number>;
  documents_with_findings: number;
  high_entropy_files: number;
  stego_candidates: number;
}

export async function scanHiddenContent(
  request: HiddenContentScanRequest
): Promise<HiddenContentScanResponse> {
  return fetchAPI<HiddenContentScanResponse>('/hidden-content/scan', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function quickScanHiddenContent(
  docIds: string[]
): Promise<HiddenContentQuickScanResponse> {
  return fetchAPI<HiddenContentQuickScanResponse>('/hidden-content/quick-scan', {
    method: 'POST',
    body: JSON.stringify({ doc_ids: docIds }),
  });
}

export async function getHiddenContentScan(
  scanId: string
): Promise<{ scan: HiddenContentScan }> {
  return fetchAPI<{ scan: HiddenContentScan }>(`/hidden-content/${scanId}`);
}

export async function getDocumentHiddenScans(
  docId: string
): Promise<{ scans: HiddenContentScan[]; total: number }> {
  return fetchAPI<{ scans: HiddenContentScan[]; total: number }>(
    `/hidden-content/document/${docId}`
  );
}

export async function getHiddenContentStats(): Promise<{ stats: HiddenContentStats }> {
  return fetchAPI<{ stats: HiddenContentStats }>('/hidden-content/stats');
}
