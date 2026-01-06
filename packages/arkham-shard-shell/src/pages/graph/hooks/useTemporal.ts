/**
 * useTemporal - Hook for managing temporal graph analysis
 *
 * Handles fetching temporal snapshots and managing playback state.
 */

import { useState, useCallback, useEffect } from 'react';
import type { TemporalSnapshot, EvolutionMetrics, TemporalRange } from '../components/TimeSlider';

export interface UseTemporalOptions {
  projectId: string;
  enabled: boolean;
  intervalDays: number;
  cumulative: boolean;
  maxSnapshots: number;
  autoPlay: boolean;
}

interface UseTemporalReturn {
  // Data
  snapshots: TemporalSnapshot[];
  evolutionMetrics: EvolutionMetrics | null;
  temporalRange: TemporalRange | null;

  // State
  currentIndex: number;
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentIndex: (index: number) => void;
  play: () => void;
  pause: () => void;
  loadSnapshots: () => Promise<void>;
  loadRange: () => Promise<void>;

  // Current snapshot data for rendering
  currentSnapshot: TemporalSnapshot | null;
}

const API_BASE = '/api/graph';

export function useTemporal(options: UseTemporalOptions): UseTemporalReturn {
  const { projectId, enabled, intervalDays, cumulative, maxSnapshots, autoPlay } = options;

  // State
  const [snapshots, setSnapshots] = useState<TemporalSnapshot[]>([]);
  const [evolutionMetrics, setEvolutionMetrics] = useState<EvolutionMetrics | null>(null);
  const [temporalRange, setTemporalRange] = useState<TemporalRange | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load temporal range (available dates)
  const loadRange = useCallback(async () => {
    if (!projectId) return;

    try {
      const response = await fetch(
        `${API_BASE}/temporal/range?project_id=${encodeURIComponent(projectId)}`
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setTemporalRange(data);
    } catch (err) {
      console.error('Failed to load temporal range:', err);
      setTemporalRange(null);
    }
  }, [projectId]);

  // Load snapshots
  const loadSnapshots = useCallback(async () => {
    if (!projectId || !enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/temporal/snapshots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          interval_days: intervalDays,
          cumulative,
          max_snapshots: maxSnapshots,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const data = await response.json();

      setSnapshots(data.snapshots || []);
      setEvolutionMetrics(data.evolution_metrics || null);
      setCurrentIndex(0);

      // Auto-play if enabled
      if (autoPlay && data.snapshots?.length > 0) {
        setIsPlaying(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load temporal data';
      console.error('Failed to load snapshots:', err);
      setError(message);
      setSnapshots([]);
      setEvolutionMetrics(null);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, enabled, intervalDays, cumulative, maxSnapshots, autoPlay]);

  // Playback controls
  const play = useCallback(() => {
    if (snapshots.length > 0) {
      setIsPlaying(true);
    }
  }, [snapshots.length]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  // Load range on mount/project change
  useEffect(() => {
    if (projectId) {
      loadRange();
    }
  }, [projectId, loadRange]);

  // Load snapshots when enabled changes
  useEffect(() => {
    if (enabled) {
      loadSnapshots();
    } else {
      setSnapshots([]);
      setEvolutionMetrics(null);
      setIsPlaying(false);
    }
  }, [enabled, loadSnapshots]);

  // Stop playing if we reach the end
  useEffect(() => {
    if (isPlaying && currentIndex >= snapshots.length - 1) {
      // Loop back to start
      setCurrentIndex(0);
    }
  }, [isPlaying, currentIndex, snapshots.length]);

  // Current snapshot
  const currentSnapshot = snapshots[currentIndex] || null;

  return {
    // Data
    snapshots,
    evolutionMetrics,
    temporalRange,

    // State
    currentIndex,
    isPlaying,
    isLoading,
    error,

    // Actions
    setCurrentIndex,
    play,
    pause,
    loadSnapshots,
    loadRange,

    // Derived
    currentSnapshot,
  };
}
