/**
 * Ingest API Service
 *
 * API client and hooks for the Ingest shard backend.
 */

import { useState, useCallback } from 'react';
import { useFetch } from '../../hooks/useFetch';

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
  route: string[];
  created_at: string;
}

export interface PendingJobsResponse {
  count: number;
  jobs: PendingJob[];
}

// --- API Functions ---

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${endpoint}`, {
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function uploadFile(
  file: File,
  priority: 'user' | 'batch' = 'user'
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('priority', priority);

  return fetchAPI<UploadResponse>('/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function uploadBatch(
  files: File[],
  priority: 'user' | 'batch' = 'batch'
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('priority', priority);

  return fetchAPI<BatchUploadResponse>('/upload/batch', {
    method: 'POST',
    body: formData,
  });
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

export async function getPendingJobs(limit: number = 50): Promise<PendingJobsResponse> {
  return fetchAPI<PendingJobsResponse>(`/pending?limit=${limit}`);
}

// --- Hooks ---

/**
 * Hook for uploading a file
 */
export function useUpload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const upload = useCallback(async (file: File, priority: 'user' | 'batch' = 'user') => {
    setLoading(true);
    setError(null);
    try {
      const result = await uploadFile(file, priority);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Upload failed');
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  return { upload, loading, error };
}

/**
 * Hook for uploading multiple files as a batch
 */
export function useUploadBatch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const uploadBatchFiles = useCallback(
    async (files: File[], priority: 'user' | 'batch' = 'batch') => {
      setLoading(true);
      setError(null);
      try {
        const result = await uploadBatch(files, priority);
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
 * Hook for fetching queue statistics
 */
export function useQueue() {
  return useFetch<QueueStatsResponse>(`${API_PREFIX}/queue`);
}

/**
 * Hook for fetching pending jobs
 */
export function usePending(limit: number = 50) {
  return useFetch<PendingJobsResponse>(`${API_PREFIX}/pending?limit=${limit}`);
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
