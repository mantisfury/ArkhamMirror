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
}

export interface DatabaseInfo {
  available: boolean;
  url: string;
  schemas: string[];
}

export interface QueueStats {
  name: string;
  pending: number;
  active: number;
  completed: number;
  failed: number;
}

export interface SystemEvent {
  timestamp: string;
  event_type: string;
  source: string;
  payload: Record<string, unknown>;
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
      const res = await fetch('/api/dashboard/health', {
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
      const res = await fetch('/api/dashboard/llm');
      if (!res.ok) throw new Error('Failed to fetch LLM config');
      const data = await res.json();
      setConfig(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = async (endpoint?: string, model?: string) => {
    const res = await fetch('/api/dashboard/llm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint, model }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update LLM config');
    }
    await refresh();
    return res.json();
  };

  const testConnection = async (): Promise<{ success: boolean; response?: { text: string; model?: string } | string; error?: string }> => {
    const res = await fetch('/api/dashboard/llm/test', { method: 'POST' });
    return res.json();
  };

  const resetConfig = async (): Promise<LLMConfig> => {
    const res = await fetch('/api/dashboard/llm/reset', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to reset LLM config');
    }
    const data = await res.json();
    setConfig(data);
    return data;
  };

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { config, loading, error, refresh, updateConfig, testConnection, resetConfig };
}

// Database hook
export function useDatabase() {
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/dashboard/database');
      if (!res.ok) throw new Error('Failed to fetch database info');
      setInfo(await res.json());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const runMigrations = async (): Promise<{ success: boolean; message: string }> => {
    const res = await fetch('/api/dashboard/database/migrate', { method: 'POST' });
    return res.json();
  };

  const resetDatabase = async (confirm: boolean): Promise<{ success: boolean; message: string }> => {
    const res = await fetch('/api/dashboard/database/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm }),
    });
    return res.json();
  };

  const vacuumDatabase = async (): Promise<{ success: boolean; message: string }> => {
    const res = await fetch('/api/dashboard/database/vacuum', { method: 'POST' });
    return res.json();
  };

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { info, loading, error, refresh, runMigrations, resetDatabase, vacuumDatabase };
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
      const res = await fetch('/api/dashboard/queues', {
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

// Events hook with auto-refresh
export function useEvents(limit = 50, refreshInterval = 5000) {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await fetch(`/api/dashboard/events?limit=${limit}`, {
        signal: abortRef.current.signal,
      });
      if (!res.ok) throw new Error('Failed to fetch events');
      const data = await res.json();
      setEvents(data.events || []);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, refreshInterval);
    return () => {
      clearInterval(interval);
      abortRef.current?.abort();
    };
  }, [refresh, refreshInterval]);

  return { events, loading, error, refresh };
}
