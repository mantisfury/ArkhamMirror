/**
 * PerformanceModeToggle - Performance mode UI for large graphs
 *
 * Provides:
 * - Toggle switch for performance mode
 * - Auto-suggest when node count exceeds threshold
 * - Expandable settings for fine-grained control
 * - Node/edge count statistics
 */

import React, { useState } from 'react';
import { Icon } from '../../../../components/common/Icon';

export interface PerformanceModeSettings {
  hideEdgeLabels: boolean;
  simplifyEdges: boolean;
  hideEdgesOnPan: boolean;
  lowerPixelRatio: boolean;
}

export interface PerformanceModeToggleProps {
  performanceMode: boolean;
  onToggle: (enabled: boolean) => void;
  onSettingsChange: (settings: Partial<PerformanceModeSettings>) => void;
  settings: PerformanceModeSettings;
  nodeCount: number;
  edgeCount: number;
  autoDetected: boolean;
  nodeThreshold?: number;
}

const DEFAULT_NODE_THRESHOLD = 500;

export const PerformanceModeToggle: React.FC<PerformanceModeToggleProps> = ({
  performanceMode,
  onToggle,
  onSettingsChange,
  settings,
  nodeCount,
  edgeCount,
  autoDetected,
  nodeThreshold = DEFAULT_NODE_THRESHOLD,
}) => {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="performance-mode-panel">
      {/* Header with toggle */}
      <div className="performance-header">
        <div className="performance-toggle">
          <label className="switch">
            <input
              type="checkbox"
              checked={performanceMode}
              onChange={(e) => onToggle(e.target.checked)}
            />
            <span className="slider"></span>
          </label>
          <span className="toggle-label">
            Performance Mode
            {autoDetected && !performanceMode && (
              <span className="auto-suggest">
                (Recommended for {nodeCount} nodes)
              </span>
            )}
          </span>
        </div>

        {performanceMode && (
          <div className="performance-indicator">
            <Icon name="Zap" size={14} />
            <span>Optimized</span>
          </div>
        )}
      </div>

      {/* Expandable settings when enabled */}
      {performanceMode && (
        <>
          <button
            className="settings-expand-btn"
            onClick={() => setShowSettings(!showSettings)}
          >
            <Icon name={showSettings ? 'ChevronUp' : 'ChevronDown'} size={14} />
            {showSettings ? 'Hide Settings' : 'Show Settings'}
          </button>

          {showSettings && (
            <div className="performance-options">
              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={settings.hideEdgeLabels}
                  onChange={(e) =>
                    onSettingsChange({ hideEdgeLabels: e.target.checked })
                  }
                />
                <span>Hide edge labels</span>
              </label>

              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={settings.simplifyEdges}
                  onChange={(e) =>
                    onSettingsChange({ simplifyEdges: e.target.checked })
                  }
                />
                <span>Simplify edge rendering</span>
              </label>

              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={settings.hideEdgesOnPan}
                  onChange={(e) =>
                    onSettingsChange({ hideEdgesOnPan: e.target.checked })
                  }
                />
                <span>Hide edges while panning</span>
              </label>

              <label className="checkbox-option">
                <input
                  type="checkbox"
                  checked={settings.lowerPixelRatio}
                  onChange={(e) =>
                    onSettingsChange({ lowerPixelRatio: e.target.checked })
                  }
                />
                <span>Lower render quality</span>
              </label>
            </div>
          )}
        </>
      )}

      {/* Stats display */}
      <div className="performance-stats">
        <span className="stat">
          <Icon name="Circle" size={12} />
          {nodeCount.toLocaleString()} nodes
          {nodeCount > nodeThreshold && (
            <Icon
              name="AlertTriangle"
              size={12}
              className="stat-warning"
              title={`Above ${nodeThreshold} node threshold`}
            />
          )}
        </span>
        <span className="stat">
          <Icon name="Minus" size={12} />
          {edgeCount.toLocaleString()} edges
        </span>
      </div>

      {/* Performance tip when auto-detected but not enabled */}
      {autoDetected && !performanceMode && (
        <div className="performance-tip">
          <Icon name="Info" size={14} />
          <span>
            Enable performance mode for smoother interaction with large graphs.
          </span>
        </div>
      )}
    </div>
  );
};

export default PerformanceModeToggle;
