/**
 * Media Forensics API Service
 *
 * API client for the Media Forensics shard backend.
 */

import type {
  MediaAnalysis,
  AnalysisListResponse,
  AnalyzeDocumentRequest,
  AnalyzeDocumentResponse,
  GenerateELARequest,
  GenerateELAResponse,
  SunPositionRequest,
  SunPositionResponse,
  FindSimilarRequest,
  FindSimilarResponse,
  StatsResponse,
  C2PASupportResponse,
  ELAResult,
} from './types';

const API_PREFIX = '/api/media-forensics';

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
// Analysis Operations
// ============================================

/**
 * Get list of media analyses with optional filters
 */
export async function listAnalyses(filters?: {
  offset?: number;
  limit?: number;
  status?: string;
  verification_status?: string;
  has_findings?: boolean;
  doc_id?: string;
}): Promise<AnalysisListResponse> {
  const params = new URLSearchParams();
  if (filters?.offset !== undefined) params.set('offset', filters.offset.toString());
  if (filters?.limit !== undefined) params.set('limit', filters.limit.toString());
  if (filters?.status) params.set('status', filters.status);
  if (filters?.verification_status) params.set('verification_status', filters.verification_status);
  if (filters?.has_findings !== undefined) params.set('has_findings', filters.has_findings.toString());
  if (filters?.doc_id) params.set('doc_id', filters.doc_id);

  const query = params.toString();
  return fetchAPI<AnalysisListResponse>(`/analyses${query ? `?${query}` : ''}`);
}

/**
 * Get a single analysis by ID
 */
export async function getAnalysis(analysisId: string): Promise<{ analysis: MediaAnalysis }> {
  return fetchAPI<{ analysis: MediaAnalysis }>(`/analyses/${analysisId}`);
}

/**
 * Get analysis for a specific document
 */
export async function getDocumentAnalysis(docId: string): Promise<{ analysis: MediaAnalysis | null }> {
  return fetchAPI<{ analysis: MediaAnalysis | null }>(`/document/${docId}`);
}

/**
 * Analyze a document for media forensics
 */
export async function analyzeDocument(request: AnalyzeDocumentRequest): Promise<AnalyzeDocumentResponse> {
  return fetchAPI<AnalyzeDocumentResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Upload and analyze an image file directly
 */
export async function uploadAndAnalyze(
  file: File,
  options?: { run_ela?: boolean }
): Promise<MediaAnalysis> {
  const formData = new FormData();
  formData.append('file', file);

  const params = new URLSearchParams();
  if (options?.run_ela) params.set('run_ela', 'true');

  const query = params.toString();
  const response = await fetch(`${API_PREFIX}/upload${query ? `?${query}` : ''}`, {
    method: 'POST',
    body: formData,
    // Note: Don't set Content-Type header - browser sets it with boundary for FormData
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Re-analyze an existing analysis
 */
export async function reanalyze(analysisId: string): Promise<AnalyzeDocumentResponse> {
  return fetchAPI<AnalyzeDocumentResponse>(`/${analysisId}/reanalyze`, {
    method: 'POST',
  });
}

/**
 * Delete an analysis
 */
export async function deleteAnalysis(analysisId: string): Promise<{ success: boolean }> {
  return fetchAPI<{ success: boolean }>(`/${analysisId}`, {
    method: 'DELETE',
  });
}

// ============================================
// ELA (Error Level Analysis) Operations
// ============================================

/**
 * Generate ELA for an analysis
 */
export async function generateELA(request: GenerateELARequest): Promise<GenerateELAResponse> {
  return fetchAPI<GenerateELAResponse>('/ela', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get ELA result for an analysis
 */
export async function getELA(analysisId: string): Promise<{ result: ELAResult | null }> {
  return fetchAPI<{ result: ELAResult | null }>(`/${analysisId}/ela`);
}

/**
 * Regenerate ELA with different quality settings
 */
export async function regenerateELA(
  analysisId: string,
  qualityLevel: number
): Promise<GenerateELAResponse> {
  return fetchAPI<GenerateELAResponse>(`/${analysisId}/ela/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ quality_level: qualityLevel }),
  });
}

// ============================================
// Sun Position Operations
// ============================================

/**
 * Calculate sun position verification
 */
export async function getSunPosition(request: SunPositionRequest): Promise<SunPositionResponse> {
  return fetchAPI<SunPositionResponse>('/sun-position', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get existing sun position analysis
 */
export async function getSunPositionResult(
  analysisId: string
): Promise<{ result: SunPositionResponse['result'] | null }> {
  return fetchAPI<{ result: SunPositionResponse['result'] | null }>(`/${analysisId}/sun-position`);
}

// ============================================
// Similar Images Operations
// ============================================

/**
 * Find similar images
 */
export async function findSimilar(request: FindSimilarRequest): Promise<FindSimilarResponse> {
  return fetchAPI<FindSimilarResponse>('/similar', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get existing similar images search results
 */
export async function getSimilarResults(
  analysisId: string
): Promise<{ result: FindSimilarResponse['result'] | null }> {
  return fetchAPI<{ result: FindSimilarResponse['result'] | null }>(`/${analysisId}/similar`);
}

// ============================================
// Statistics & Support
// ============================================

/**
 * Get media forensics statistics
 */
export async function getStats(): Promise<StatsResponse> {
  return fetchAPI<StatsResponse>('/stats');
}

/**
 * Check if C2PA is supported
 */
export async function checkC2PASupport(): Promise<C2PASupportResponse> {
  return fetchAPI<C2PASupportResponse>('/c2pa/supported');
}

// ============================================
// Notes & Findings Operations
// ============================================

/**
 * Add a note to an analysis
 */
export async function addNote(
  analysisId: string,
  content: string,
  author: string
): Promise<{ success: boolean }> {
  return fetchAPI<{ success: boolean }>(`/${analysisId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content, author }),
  });
}

/**
 * Update verification status
 */
export async function updateVerificationStatus(
  analysisId: string,
  status: string,
  reason?: string
): Promise<{ analysis: MediaAnalysis }> {
  return fetchAPI<{ analysis: MediaAnalysis }>(`/${analysisId}/verification`, {
    method: 'PUT',
    body: JSON.stringify({ status, reason }),
  });
}

/**
 * Dismiss a finding
 */
export async function dismissFinding(
  analysisId: string,
  findingId: string,
  reason: string,
  dismissedBy: string
): Promise<{ success: boolean }> {
  return fetchAPI<{ success: boolean }>(`/${analysisId}/findings/${findingId}/dismiss`, {
    method: 'POST',
    body: JSON.stringify({ reason, dismissed_by: dismissedBy }),
  });
}

// ============================================
// Batch Operations
// ============================================

/**
 * Analyze multiple documents
 */
export async function batchAnalyze(
  docIds: string[],
  options?: {
    run_ela?: boolean;
    run_sun_position?: boolean;
    run_similar_search?: boolean;
  }
): Promise<{ job_id: string; queued_count: number }> {
  return fetchAPI<{ job_id: string; queued_count: number }>('/batch/analyze', {
    method: 'POST',
    body: JSON.stringify({ doc_ids: docIds, ...options }),
  });
}

/**
 * Get batch job status
 */
export async function getBatchStatus(
  jobId: string
): Promise<{
  job_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  results: Array<{ doc_id: string; analysis_id: string | null; error: string | null }>;
}> {
  return fetchAPI(`/batch/${jobId}`);
}
