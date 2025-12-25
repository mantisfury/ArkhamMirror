/**
 * Contradictions API Service
 *
 * API client for the Contradictions shard backend.
 */

import type {
  Contradiction,
  ContradictionListResponse,
  StatsResponse,
  ContradictionStatus,
  Severity,
} from './types';

const API_PREFIX = '/api/contradictions';

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
// Contradiction Operations
// ============================================

export async function analyzeDocuments(
  docAId: string,
  docBId: string,
  threshold: number = 0.7,
  useLLM: boolean = true
): Promise<{
  doc_a_id: string;
  doc_b_id: string;
  contradictions: Contradiction[];
  count: number;
}> {
  return fetchAPI('/analyze', {
    method: 'POST',
    body: JSON.stringify({
      doc_a_id: docAId,
      doc_b_id: docBId,
      threshold,
      use_llm: useLLM,
    }),
  });
}

export async function listContradictions(
  page: number = 1,
  pageSize: number = 50,
  status?: string,
  severity?: string,
  type?: string
): Promise<ContradictionListResponse> {
  const params = new URLSearchParams();
  params.set('page', page.toString());
  params.set('page_size', pageSize.toString());
  if (status) params.set('status', status);
  if (severity) params.set('severity', severity);
  if (type) params.set('type', type);

  const query = params.toString();
  return fetchAPI<ContradictionListResponse>(`/list${query ? `?${query}` : ''}`);
}

export async function getContradiction(contradictionId: string): Promise<Contradiction> {
  return fetchAPI<Contradiction>(`/${contradictionId}`);
}

export async function updateStatus(
  contradictionId: string,
  status: ContradictionStatus,
  notes?: string,
  analystId?: string
): Promise<Contradiction> {
  return fetchAPI(`/${contradictionId}/status`, {
    method: 'PUT',
    body: JSON.stringify({
      status,
      notes: notes || '',
      analyst_id: analystId,
    }),
  });
}

export async function addNote(
  contradictionId: string,
  notes: string,
  analystId?: string
): Promise<Contradiction> {
  return fetchAPI(`/${contradictionId}/notes`, {
    method: 'POST',
    body: JSON.stringify({
      notes,
      analyst_id: analystId,
    }),
  });
}

export async function getStats(): Promise<StatsResponse> {
  return fetchAPI<StatsResponse>('/stats');
}

export async function getDocumentContradictions(
  docId: string,
  includeChains: boolean = false
): Promise<{
  document_id: string;
  contradictions: Contradiction[];
  count: number;
}> {
  const params = new URLSearchParams();
  if (includeChains) params.set('include_chains', 'true');
  const query = params.toString();
  return fetchAPI(`/document/${docId}${query ? `?${query}` : ''}`);
}

export async function deleteContradiction(
  contradictionId: string
): Promise<{ status: string; contradiction_id: string }> {
  return fetchAPI(`/${contradictionId}`, {
    method: 'DELETE',
  });
}

// ============================================
// Chain Operations
// ============================================

export async function detectChains(): Promise<{
  chains_detected: number;
  chains: Array<{
    id: string;
    contradiction_count: number;
    contradictions: string[];
  }>;
}> {
  return fetchAPI('/detect-chains', {
    method: 'POST',
  });
}

export async function listChains(): Promise<{
  count: number;
  chains: Array<{
    id: string;
    contradiction_count: number;
    contradictions: string[];
    description: string;
    severity: string;
    created_at: string;
  }>;
}> {
  return fetchAPI('/chains');
}

export async function getChain(chainId: string): Promise<{
  id: string;
  description: string;
  severity: string;
  contradiction_count: number;
  contradictions: Contradiction[];
  created_at: string;
  updated_at: string;
}> {
  return fetchAPI(`/chains/${chainId}`);
}
