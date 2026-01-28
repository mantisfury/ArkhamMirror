/**
 * Dashboard API hooks
 *
 * Provides hooks for fetching and managing dashboard data:
 * - Service health monitoring
 * - LLM configuration
 * - Database operations
 * - Worker/queue management
 * - Event log
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, apiGet, apiPost } from '../../utils/api';

// Types
export interface ServiceHealth {
  database: { available: boolean; info: { url?: string } | null };
  vectors: { available: boolean; info: Record<string, unknown> | null };
  llm: { available: boolean; info: { endpoint?: string; model?: string } | null };
  workers: { available: boolean; info: QueueStats[] | null };
  events: { available: boolean; info: Record<string, unknown> | null };
}

export interface LLMConfig {
  endpoint: string;
  model: string;
  available: boolean;
  api_key_configured: boolean;
  api_key_source: string | null;
  is_docker: boolean;
  default_lm_studio_endpoint: string;
  default_ollama_endpoint: string;
  // OpenRouter fallback routing
  is_openrouter?: boolean;
  fallback_routing_enabled?: boolean;
  fallback_models?: string[];
}

export interface DatabaseInfo {
  available: boolean;
  url: string;
  schemas: string[];
}

export interface SchemaStats {
  name: string;
  tables: number;
  rows: number;
  size_bytes: number;
}

export interface DatabaseStats {
  connected: boolean;
  database_size_bytes?: number;
  schemas?: SchemaStats[];
  total_tables?: number;
  total_rows?: number;
  error?: string;
}

export interface TableInfo {
  name: string;
  row_count: number;
  size_bytes: number;
  last_vacuum: string | null;
  last_analyze: string | null;
}

export interface QueueStats {
  name: string;
  pending: number;
  active: number;
  completed: number;
  failed: number;
  type?: string;
  max_workers?: number;
}

export interface PoolInfo {
  name: string;
  type: string;
  max_workers: number;
  vram_mb?: number;
  current_workers: number;
  target_workers: number;
}

export interface WorkerInfo {
  id: string;
  pool: string;
  status: string;
  started_at: string;
  current_job_id: string | null;
  jobs_completed: number;
  jobs_failed: number;
  uptime_seconds?: number;
}

export interface JobInfo {
  id: string;
  pool: string;
  status: string;
  priority: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
}

export interface SystemEvent {
  timestamp: string;
  event_type: string;
  source: string;
  payload: Record<string, unknown>;
  sequence: number;
}

export interface EventFilters {
  source?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
}

// Health hook with auto-refresh
export function useHealth(refreshInterval = 5000) {
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await apiFetch('/api/dashboard/health', {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch health');
      const data = await res.json();
      setHealth(data);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { health, loading, error, refresh };
}

// LLM config hook
export function useLLMConfig() {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<LLMConfig>('/api/dashboard/llm');
      setConfig(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = async (endpoint?: string, model?: string) => {
    const data = await apiPost<any>('/api/dashboard/llm', { endpoint, model });
    await refresh();
    return data;
  };

  const testConnection = async (): Promise<{ success: boolean; response?: { text: string; model?: string } | string; error?: string }> => {
    return apiPost('/api/dashboard/llm/test');
  };

  const resetConfig = async (): Promise<LLMConfig> => {
    const data = await apiPost<LLMConfig>('/api/dashboard/llm/reset');
    setConfig(data);
    return data;
  };

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setFallbackModels = async (models: string[], enabled: boolean = true): Promise<{ success: boolean; error?: string }> => {
    const data = await apiPost<{ success: boolean; error?: string }>('/api/dashboard/llm/fallback', { models, enabled });
    if (data.success) {
      await refresh();
    }
    return data;
  };

  return { config, loading, error, refresh, updateConfig, testConnection, resetConfig, setFallbackModels };
}

// Database hook
export function useDatabase() {
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [stats, setStats] = useState<DatabaseStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [infoRes, statsRes] = await Promise.all([
        apiFetch('/api/dashboard/database'),
        apiFetch('/api/dashboard/database/stats'),
      ]);
      if (!infoRes.ok) throw new Error('Failed to fetch database info');
      setInfo(await infoRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const runMigrations = async (): Promise<{ success: boolean; message: string }> => {
    return apiPost('/api/dashboard/database/migrate');
  };

  const resetDatabase = async (confirm: boolean): Promise<{ success: boolean; message: string }> => {
    return apiPost('/api/dashboard/database/reset', { confirm });
  };

  const vacuumDatabase = async (): Promise<{ success: boolean; message: string }> => {
    return apiPost('/api/dashboard/database/vacuum');
  };

  const getTableInfo = async (schema: string): Promise<TableInfo[]> => {
    try {
      const res = await apiFetch(`/api/dashboard/database/tables/${encodeURIComponent(schema)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.tables || [];
    } catch {
      return [];
    }
  };

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { info, stats, loading, error, refresh, runMigrations, resetDatabase, vacuumDatabase, getTableInfo };
}

// Queues hook with auto-refresh
export function useQueues(refreshInterval = 3000) {
  const [queues, setQueues] = useState<QueueStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await apiFetch('/api/dashboard/queues', {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch queues');
      const data = await res.json();
      setQueues(data.queues || []);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { queues, loading, error, refresh };
}

// Events hook with auto-refresh and filtering
export function useEvents(filters: EventFilters = {}, refreshInterval = 5000) {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const params = new URLSearchParams();
      params.set('limit', String(filters.limit || 50));
      if (filters.offset) params.set('offset', String(filters.offset));
      if (filters.source) params.set('source', filters.source);
      if (filters.event_type) params.set('event_type', filters.event_type);

      const res = await apiFetch(`/api/dashboard/events?${params}`, {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch events');
      const data = await res.json();
      setEvents(data.events || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters.limit, filters.offset, filters.source, filters.event_type]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { events, total, loading, error, refresh };
}

// Event types hook
export function useEventTypes() {
  const [types, setTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await apiFetch('/api/dashboard/events/types');
      if (!res.ok) throw new Error('Failed to fetch event types');
      const data = await res.json();
      setTypes(data.types || []);
    } catch {
      // Ignore errors for filter options
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { types, loading, refresh };
}

// Event sources hook
export function useEventSources() {
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await apiFetch('/api/dashboard/events/sources');
      if (!res.ok) throw new Error('Failed to fetch event sources');
      const data = await res.json();
      setSources(data.sources || []);
    } catch {
      // Ignore errors for filter options
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { sources, loading, refresh };
}

// Event actions
export const eventActions = {
  clear: async (): Promise<{ success: boolean; cleared?: number; error?: string }> => {
    return apiPost('/api/dashboard/events/clear');
  },
};

// Workers hook with auto-refresh
export function useWorkers(refreshInterval = 3000) {
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await apiFetch('/api/dashboard/workers', {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch workers');
      const data = await res.json();
      setWorkers(data.workers || []);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { workers, loading, error, refresh };
}

// Pools hook
export function usePools() {
  const [pools, setPools] = useState<PoolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await apiGet<{ pools?: PoolInfo[] }>('/api/dashboard/pools');
      setPools(data.pools || []);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { pools, loading, error, refresh };
}

// Worker management actions
export const workerActions = {
  scale: async (queue: string, count: number): Promise<{ success: boolean; error?: string }> => {
    return apiPost('/api/dashboard/workers/scale', { queue, count });
  },

  start: async (queue: string): Promise<{ success: boolean; worker_id?: string; error?: string }> => {
    return apiPost('/api/dashboard/workers/start', { queue });
  },

  stop: async (worker_id: string): Promise<{ success: boolean; error?: string }> => {
    return apiPost('/api/dashboard/workers/stop', { worker_id });
  },

  stopAll: async (pool?: string): Promise<{ success: boolean; count?: number; error?: string }> => {
    return apiPost('/api/dashboard/workers/stop-all', { pool });
  },
};

// Queue management actions
export const queueActions = {
  clear: async (pool: string, status?: string): Promise<{ success: boolean; cleared?: number; error?: string }> => {
    return apiPost('/api/dashboard/queues/clear', { pool, status });
  },

  retryFailed: async (pool: string, job_ids?: string[]): Promise<{ success: boolean; count?: number; error?: string }> => {
    return apiPost('/api/dashboard/jobs/retry', { pool, job_ids });
  },

  cancelJob: async (job_id: string): Promise<{ success: boolean; error?: string }> => {
    return apiPost('/api/dashboard/jobs/cancel', { job_id });
  },
};

// Jobs hook
export function useJobs(pool?: string, status?: string, refreshInterval = 5000) {
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const params = new URLSearchParams();
      if (pool) params.set('pool', pool);
      if (status) params.set('status', status);

      const res = await apiFetch(`/api/dashboard/jobs?${params}`, {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch jobs');
      const data = await res.json();
      setJobs(data.jobs || []);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [pool, status]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { jobs, loading, error, refresh };
}
