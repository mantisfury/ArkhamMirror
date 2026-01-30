/**
 * Ingest API Service
 *
 * API client and hooks for the Ingest shard backend.
 */

import { useState, useCallback } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { apiFetch, apiUpload } from '../../utils/api';

const API_PREFIX = '/api/ingest';

// --- Types ---

export interface UploadResponse {
  job_id: string;
  filename: string;
  category: string;
  status: string;
  route: string[];
  quality?: {
    classification: string;
    issues: string[];
    dpi?: number;
    skew?: number;
    contrast?: number;
    layout?: string;
  } | null;
}

export interface BatchUploadResponse {
  batch_id: string;
  total_files: number;
  jobs: UploadResponse[];
  failed: number;
}

export interface JobStatusResponse {
  job_id: string;
  filename: string;
  status: string;
  current_worker: string | null;
  route: string[];
  route_position: number;
  quality: {
    classification: string;
    issues: string[];
  } | null;
  error: string | null;
  retry_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BatchStatusResponse {
  batch_id: string;
  total_files: number;
  completed: number;
  failed: number;
  pending: number;
  jobs: JobStatusResponse[];
}

export interface QueueStatsResponse {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  by_priority: {
    user: number;
    batch: number;
    reprocess: number;
  };
}

export interface PendingJob {
  job_id: string;
  filename: string;
  category: string;
  priority: string;
  status: string;
  route: string[];
  created_at: string;
}

export interface PendingJobsResponse {
  count: number;
  jobs: PendingJob[];
}

export interface IngestSettings {
  // Ingest settings
  ingest_ocr_mode: OcrMode;
  ingest_max_file_size_mb: number;
  ingest_min_file_size_bytes: number;
  ingest_enable_validation: boolean;
  ingest_enable_deduplication: boolean;
  ingest_enable_downscale: boolean;
  ingest_skip_blank_pages: boolean;

  // OCR settings
  ocr_parallel_pages: number;
  ocr_confidence_threshold: number;
  ocr_enable_escalation: boolean;
  ocr_enable_cache: boolean;
  ocr_cache_ttl_days: number;
}

export type IngestSettingsUpdate = Partial<IngestSettings>;

// --- API Functions ---

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${API_PREFIX}${endpoint}`, options);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export type OcrMode = 'auto' | 'paddle_only' | 'qwen_only';

/** Optional provenance info stored in document metadata */
export interface ProvenanceOptions {
  source_url?: string;
  source_description?: string;
  custodian?: string;
  acquisition_date?: string;
  [key: string]: string | undefined;
}

export async function uploadFile(
  file: File,
  priority: 'user' | 'batch' = 'user',
  ocrMode: OcrMode = 'auto',
  projectId?: string,
  options?: { original_file_path?: string; provenance?: ProvenanceOptions; extract_archives?: boolean }
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('priority', priority);
  formData.append('ocr_mode', ocrMode);
  if (projectId) {
    formData.append('project_id', projectId);
  }
  if (options?.original_file_path) {
    formData.append('original_file_path', options.original_file_path);
  }
  if (options?.provenance && Object.keys(options.provenance).length > 0) {
    formData.append('provenance', JSON.stringify(options.provenance));
  }
  if (options?.extract_archives) {
    formData.append('extract_archives', 'true');
  }

  return apiUpload<UploadResponse>(`${API_PREFIX}/upload`, formData);
}

export async function uploadBatch(
  files: File[],
  priority: 'user' | 'batch' = 'batch',
  ocrMode: OcrMode = 'auto',
  projectId?: string,
  options?: { provenance?: ProvenanceOptions; extract_archives?: boolean }
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('priority', priority);
  formData.append('ocr_mode', ocrMode);
  if (projectId) {
    formData.append('project_id', projectId);
  }
  if (options?.provenance && Object.keys(options.provenance).length > 0) {
    formData.append('provenance', JSON.stringify(options.provenance));
  }
  if (options?.extract_archives) {
    formData.append('extract_archives', 'true');
  }

  return apiUpload<BatchUploadResponse>(`${API_PREFIX}/upload/batch`, formData);
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return fetchAPI<JobStatusResponse>(`/job/${jobId}`);
}

export async function getBatchStatus(batchId: string): Promise<BatchStatusResponse> {
  return fetchAPI<BatchStatusResponse>(`/batch/${batchId}`);
}

export async function retryJob(jobId: string): Promise<{ status: string; job_id: string }> {
  return fetchAPI(`/job/${jobId}/retry`, {
    method: 'POST',
  });
}

export async function getQueueStats(): Promise<QueueStatsResponse> {
  return fetchAPI<QueueStatsResponse>('/queue');
}

export async function getPendingJobs(limit: number = 50, status?: string): Promise<PendingJobsResponse> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (status && status !== 'all') {
    params.append('status', status);
  }
  return fetchAPI<PendingJobsResponse>(`/pending?${params.toString()}`);
}

export async function getIngestSettings(): Promise<IngestSettings> {
  return fetchAPI<IngestSettings>('/settings');
}

export async function updateIngestSettings(
  settings: IngestSettingsUpdate
): Promise<IngestSettings> {
  return fetchAPI<IngestSettings>('/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
}

// --- Hooks ---

/**
 * Hook for uploading a file
 */
export function useUpload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const upload = useCallback(
    async (file: File, priority: 'user' | 'batch' = 'user', ocrMode: OcrMode = 'auto') => {
      setLoading(true);
      setError(null);
      try {
        const result = await uploadFile(file, priority, ocrMode);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Upload failed');
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { upload, loading, error };
}

/**
 * Hook for uploading multiple files as a batch
 */
export function useUploadBatch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const uploadBatchFiles = useCallback(
    async (
      files: File[],
      priority: 'user' | 'batch' = 'batch',
      ocrMode: OcrMode = 'auto',
      projectId?: string,
      options?: { provenance?: ProvenanceOptions }
    ) => {
      setLoading(true);
      setError(null);
      try {
        const result = await uploadBatch(files, priority, ocrMode, projectId, options);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Batch upload failed');
        setError(error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { uploadBatch: uploadBatchFiles, loading, error };
}

/**
 * Hook for fetching queue statistics.
 * Uses backgroundRefetch so polling does not flash loading state.
 */
export function useQueue() {
  return useFetch<QueueStatsResponse>(`${API_PREFIX}/queue`, { backgroundRefetch: true });
}

/**
 * Hook for fetching pending jobs.
 * Uses backgroundRefetch so polling does not flash loading state.
 */
export function usePending(limit: number = 50, status?: string) {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (status && status !== 'all') {
    params.append('status', status);
  }
  return useFetch<PendingJobsResponse>(`${API_PREFIX}/pending?${params.toString()}`, { backgroundRefetch: true });
}

/**
 * Hook for fetching a specific job status
 */
export function useJob(jobId: string | null) {
  const url = jobId ? `${API_PREFIX}/job/${jobId}` : null;
  return useFetch<JobStatusResponse>(url);
}

/**
 * Hook for fetching a batch status
 */
export function useBatch(batchId: string | null) {
  const url = batchId ? `${API_PREFIX}/batch/${batchId}` : null;
  return useFetch<BatchStatusResponse>(url);
}

/**
 * Hook for retrying a failed job
 */
export function useRetryJob() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const retry = useCallback(async (jobId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await retryJob(jobId);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Retry failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { retry, loading, error };
}

/**
 * Hook for fetching ingest settings
 */
export function useIngestSettings() {
  return useFetch<IngestSettings>(`${API_PREFIX}/settings`);
}

/**
 * Hook for updating ingest settings
 */
export function useUpdateIngestSettings() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const update = useCallback(async (settings: IngestSettingsUpdate) => {
    setLoading(true);
    setError(null);
    try {
      const result = await updateIngestSettings(settings);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Update failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { update, loading, error };
}
