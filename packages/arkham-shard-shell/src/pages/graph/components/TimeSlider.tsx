/**
 * TimeSlider - Temporal navigation control for graph visualization
 *
 * Allows users to scrub through time to see how the network evolved.
 * Supports playback animation and displays change indicators.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Icon } from '../../../components/common/Icon';

export interface TemporalSnapshot {
  timestamp: string;
  nodes: any[];
  edges: any[];
  added_nodes: string[];
  removed_nodes: string[];
  added_edges: { source: string; target: string }[];
  removed_edges: { source: string; target: string }[];
  node_count: number;
  edge_count: number;
  density: number;
}

export interface EvolutionMetrics {
  total_nodes_added: number;
  total_nodes_removed: number;
  total_edges_added: number;
  total_edges_removed: number;
  node_growth_rate: number;
  edge_growth_rate: number;
  peak_node_count: number;
  peak_edge_count: number;
  peak_timestamp: string | null;
}

export interface TemporalRange {
  available: boolean;
  start_date?: string;
  end_date?: string;
  interval_days?: number;
  snapshot_count?: number;
}

interface TimeSliderProps {
  snapshots: TemporalSnapshot[];
  currentIndex: number;
  onChange: (index: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  isPlaying: boolean;
  playbackSpeed: number;  // ms between frames
  onSpeedChange?: (speed: number) => void;
  temporalRange?: TemporalRange;
  evolutionMetrics?: EvolutionMetrics;
  isLoading?: boolean;
}

const SPEED_OPTIONS = [
  { value: 2000, label: '0.5x' },
  { value: 1000, label: '1x' },
  { value: 500, label: '2x' },
  { value: 250, label: '4x' },
];

export function TimeSlider({
  snapshots,
  currentIndex,
  onChange,
  onPlay,
  onPause,
  isPlaying,
  playbackSpeed,
  onSpeedChange,
  evolutionMetrics,
  isLoading = false,
}: TimeSliderProps) {
  const [showMetrics, setShowMetrics] = useState(false);
  const playbackRef = useRef<number | null>(null);

  // Auto-advance playback
  useEffect(() => {
    if (isPlaying && snapshots.length > 0) {
      playbackRef.current = window.setInterval(() => {
        onChange((currentIndex + 1) % snapshots.length);
      }, playbackSpeed);
    }

    return () => {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
        playbackRef.current = null;
      }
    };
  }, [isPlaying, playbackSpeed, currentIndex, snapshots.length, onChange]);

  // Format date for display
  const formatDate = useCallback((isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  }, []);

  // Format short date for slider labels
  const formatShortDate = useCallback((isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return '';
    }
  }, []);

  if (!snapshots.length) {
    return (
      <div className="time-slider-container">
        <div className="time-slider-empty">
          {isLoading ? (
            <>
              <Icon name="Loader2" size={20} className="spin" />
              <span>Loading temporal data...</span>
            </>
          ) : (
            <>
              <Icon name="Clock" size={20} />
              <span>No temporal data available</span>
            </>
          )}
        </div>
      </div>
    );
  }

  const currentSnapshot = snapshots[currentIndex];
  const hasChanges = currentSnapshot && (
    currentSnapshot.added_nodes.length > 0 ||
    currentSnapshot.removed_nodes.length > 0 ||
    currentSnapshot.added_edges.length > 0 ||
    currentSnapshot.removed_edges.length > 0
  );

  return (
    <div className="time-slider-container">
      {/* Header with date and controls */}
      <div className="time-slider-header">
        <div className="time-slider-date">
          <Icon name="Calendar" size={14} />
          <span className="date-display">
            {currentSnapshot ? formatDate(currentSnapshot.timestamp) : '---'}
          </span>
        </div>

        <div className="time-slider-controls">
          {/* Skip to start */}
          <button
            className="time-control-btn"
            onClick={() => onChange(0)}
            disabled={currentIndex === 0}
            title="Go to start"
          >
            <Icon name="SkipBack" size={16} />
          </button>

          {/* Previous */}
          <button
            className="time-control-btn"
            onClick={() => onChange(Math.max(0, currentIndex - 1))}
            disabled={currentIndex === 0}
            title="Previous snapshot"
          >
            <Icon name="ChevronLeft" size={16} />
          </button>

          {/* Play/Pause */}
          <button
            className="time-control-btn play-btn"
            onClick={isPlaying ? onPause : onPlay}
            title={isPlaying ? 'Pause' : 'Play'}
          >
            <Icon name={isPlaying ? 'Pause' : 'Play'} size={18} />
          </button>

          {/* Next */}
          <button
            className="time-control-btn"
            onClick={() => onChange(Math.min(snapshots.length - 1, currentIndex + 1))}
            disabled={currentIndex === snapshots.length - 1}
            title="Next snapshot"
          >
            <Icon name="ChevronRight" size={16} />
          </button>

          {/* Skip to end */}
          <button
            className="time-control-btn"
            onClick={() => onChange(snapshots.length - 1)}
            disabled={currentIndex === snapshots.length - 1}
            title="Go to end"
          >
            <Icon name="SkipForward" size={16} />
          </button>

          {/* Speed selector */}
          <select
            className="speed-select"
            value={playbackSpeed}
            onChange={(e) => onSpeedChange?.(Number(e.target.value))}
            title="Playback speed"
          >
            {SPEED_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Slider track */}
      <div className="time-slider-track-container">
        <input
          type="range"
          className="time-slider-input"
          min={0}
          max={snapshots.length - 1}
          value={currentIndex}
          onChange={(e) => onChange(Number(e.target.value))}
        />

        {/* Change markers on track */}
        <div className="time-slider-markers">
          {snapshots.map((snapshot, idx) => {
            const hasAdditions = snapshot.added_nodes.length > 0 || snapshot.added_edges.length > 0;
            const hasRemovals = snapshot.removed_nodes.length > 0 || snapshot.removed_edges.length > 0;
            const position = (idx / (snapshots.length - 1)) * 100;

            if (!hasAdditions && !hasRemovals) return null;

            return (
              <div
                key={idx}
                className={`time-marker ${hasAdditions ? 'addition' : ''} ${hasRemovals ? 'removal' : ''}`}
                style={{ left: `${position}%` }}
                title={`${formatShortDate(snapshot.timestamp)}: +${snapshot.added_nodes.length} nodes, -${snapshot.removed_nodes.length} nodes`}
              />
            );
          })}
        </div>

        {/* Date labels */}
        <div className="time-slider-labels">
          <span>{formatShortDate(snapshots[0].timestamp)}</span>
          <span>{formatShortDate(snapshots[snapshots.length - 1].timestamp)}</span>
        </div>
      </div>

      {/* Current snapshot stats */}
      <div className="time-slider-stats">
        <div className="stat-item">
          <Icon name="Circle" size={12} />
          <span>{currentSnapshot?.node_count || 0} nodes</span>
        </div>
        <div className="stat-item">
          <Icon name="Link" size={12} />
          <span>{currentSnapshot?.edge_count || 0} edges</span>
        </div>

        {/* Change indicators */}
        {hasChanges && (
          <>
            {currentSnapshot.added_nodes.length > 0 && (
              <div className="stat-item change-add">
                <Icon name="Plus" size={12} />
                <span>+{currentSnapshot.added_nodes.length}</span>
              </div>
            )}
            {currentSnapshot.removed_nodes.length > 0 && (
              <div className="stat-item change-remove">
                <Icon name="Minus" size={12} />
                <span>-{currentSnapshot.removed_nodes.length}</span>
              </div>
            )}
          </>
        )}

        {/* Metrics toggle */}
        <button
          className="metrics-toggle"
          onClick={() => setShowMetrics(!showMetrics)}
          title="Show evolution metrics"
        >
          <Icon name={showMetrics ? 'ChevronUp' : 'BarChart2'} size={14} />
        </button>
      </div>

      {/* Evolution metrics panel */}
      {showMetrics && evolutionMetrics && (
        <div className="time-slider-metrics">
          <div className="metrics-grid">
            <div className="metric">
              <span className="metric-label">Peak Size</span>
              <span className="metric-value">{evolutionMetrics.peak_node_count} nodes</span>
            </div>
            <div className="metric">
              <span className="metric-label">Growth Rate</span>
              <span className="metric-value">
                +{evolutionMetrics.node_growth_rate.toFixed(1)}/interval
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Total Added</span>
              <span className="metric-value add">{evolutionMetrics.total_nodes_added}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Total Removed</span>
              <span className="metric-value remove">{evolutionMetrics.total_nodes_removed}</span>
            </div>
          </div>
          {evolutionMetrics.peak_timestamp && (
            <div className="peak-info">
              Peak at {formatDate(evolutionMetrics.peak_timestamp)}
            </div>
          )}
        </div>
      )}

      {/* Index indicator */}
      <div className="time-slider-index">
        {currentIndex + 1} / {snapshots.length}
      </div>
    </div>
  );
}
