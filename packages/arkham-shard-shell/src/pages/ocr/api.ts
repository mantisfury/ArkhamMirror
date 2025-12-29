/**
 * OCR API Service
 *
 * API client for the OCR shard backend.
 */

import type {
  OCRResponse,
  OCRHealthResponse,
  OCREngine,
} from './types';

const API_PREFIX = '/api/ocr';

// Document info for selection
export interface DocumentInfo {
  id: string;
  name: string;
  file_type: string;
  page_count: number;
  created_at: string;
}

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
// Health Check
// ============================================

export async function getOCRHealth(): Promise<OCRHealthResponse> {
  return fetchAPI<OCRHealthResponse>('/health');
}

// ============================================
// OCR Operations
// ============================================

export async function ocrPage(data: {
  image_path: string;
  engine?: OCREngine;
  language?: string;
}): Promise<OCRResponse> {
  return fetchAPI<OCRResponse>('/page', {
    method: 'POST',
    body: JSON.stringify({
      image_path: data.image_path,
      engine: data.engine || 'paddle',
      language: data.language || 'en',
    }),
  });
}

export async function ocrDocument(data: {
  document_id: string;
  engine?: OCREngine;
  language?: string;
}): Promise<OCRResponse> {
  return fetchAPI<OCRResponse>('/document', {
    method: 'POST',
    body: JSON.stringify({
      document_id: data.document_id,
      engine: data.engine || 'paddle',
      language: data.language || 'en',
    }),
  });
}

export async function ocrUpload(
  file: File,
  engine: OCREngine = 'paddle',
  language: string = 'en'
): Promise<OCRResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(
    `${API_PREFIX}/upload?engine=${engine}&language=${language}`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================
// Document Operations
// ============================================

export async function getDocumentsForOCR(): Promise<DocumentInfo[]> {
  // Fetch documents that can be OCR'd (images, scanned PDFs)
  const response = await fetch('/api/documents/items?limit=100');

  if (!response.ok) {
    throw new Error(`Failed to fetch documents: ${response.statusText}`);
  }

  const data = await response.json();
  // Filter to image-based documents (by file_type or mime pattern)
  const ocrableTypes = ['image', 'pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'application/pdf'];

  return (data.items || [])
    .filter((doc: any) => {
      const fileType = (doc.file_type || '').toLowerCase();
      return ocrableTypes.some(t => fileType.includes(t)) || fileType.startsWith('image/');
    })
    .map((doc: any) => ({
      id: doc.id,
      name: doc.title || doc.filename || 'Untitled',
      file_type: doc.file_type,
      page_count: doc.page_count || 1,
      created_at: doc.created_at,
    }));
}
