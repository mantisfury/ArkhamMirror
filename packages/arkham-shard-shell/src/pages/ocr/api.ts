/**
 * OCR API Service
 *
 * API client for the OCR shard backend.
 */

import type {
  OCRResponse,
  OCRHealthResponse,
  OCRRequest,
  OCREngine,
} from './types';

const API_PREFIX = '/api/ocr';

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
