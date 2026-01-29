/**
 * Contradictions API Service
 *
 * API client for the Contradictions shard backend.
 */

import { apiFetch } from '../../utils/api';
import type {
  Contradiction,
  ContradictionListResponse,
  StatsResponse,
  ContradictionStatus,
} from './types';

const API_PREFIX = '/api/contradictions';

// Generic fetch wrapper with error handling
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${API_PREFIX}${endpoint}`, {
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

// ============================================
// Bulk Operations
// ============================================

export async function bulkUpdateStatus(
  contradictionIds: string[],
  status: ContradictionStatus,
  notes?: string,
  analystId?: string
): Promise<{
  updated: number;
  failed: number;
  updated_ids: string[];
  failures: Array<{ id: string; error: string }>;
}> {
  return fetchAPI('/bulk-status', {
    method: 'POST',
    body: JSON.stringify({
      contradiction_ids: contradictionIds,
      status,
      notes: notes || null,
      analyst_id: analystId || null,
    }),
  });
}

// ============================================
// Claim Extraction
// ============================================

export async function extractClaims(
  text: string,
  useLLM: boolean = true,
  documentId?: string
): Promise<{
  claims: Array<{
    id: string;
    text: string;
    location: string;
    type: string;
    confidence: number;
  }>;
  count: number;
  document_id: string | null;
}> {
  return fetchAPI('/claims', {
    method: 'POST',
    body: JSON.stringify({
      text,
      use_llm: useLLM,
      document_id: documentId || null,
    }),
  });
}

// ============================================
// Batch Analysis (Multiple Documents)
// ============================================

export async function batchAnalyze(
  documentPairs: Array<[string, string]>,
  threshold: number = 0.7,
  useLLM: boolean = true
): Promise<{
  pairs_analyzed: number;
  contradictions: Array<{
    id: string;
    doc_a_id: string;
    doc_b_id: string;
    claim_a: string;
    claim_b: string;
    contradiction_type: string;
    severity: string;
    status: string;
    explanation: string;
    confidence_score: number;
    created_at: string;
  }>;
  count: number;
}> {
  return fetchAPI('/batch', {
    method: 'POST',
    body: JSON.stringify({
      document_pairs: documentPairs,
      threshold,
      use_llm: useLLM,
    }),
  });
}

// ============================================
// Document Fetching (from documents shard)
// ============================================

export interface DocumentItem {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  status: string;
  created_at: string;
}

export async function fetchDocuments(
  page: number = 1,
  pageSize: number = 100,
  projectId?: string | null
): Promise<{
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}> {
  const params = new URLSearchParams();
  params.set('page', page.toString());
  params.set('page_size', pageSize.toString());
  if (projectId) {
    params.set('project_id', projectId);
  }
  
  const response = await apiFetch(`/api/documents/items?${params.toString()}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch documents: ${response.status}`);
  }
  return response.json();
}
