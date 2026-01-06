/**
 * LinkAnalysisMode - i2 Analyst's Notebook-style manual graph positioning
 *
 * Features:
 * - Toggle between Analysis Mode (manual) and Auto Layout (physics)
 * - Drag nodes to pin positions (saved to backend)
 * - Right-click context menu for annotations
 * - Export to PNG/SVG
 */

import { useState, useCallback, useRef } from 'react';
import { Icon } from '../../../components/common/Icon';

export interface Position {
  x: number;
  y: number;
  pinned: boolean;
}

export interface LinkAnalysisModeProps {
  projectId: string;
  isAnalysisMode: boolean;
  onModeChange: (isAnalysis: boolean) => void;
  positions: Map<string, Position>;
  onPositionChange: (nodeId: string, position: Position) => void;
  onSavePositions: () => Promise<void>;
  onClearPositions: () => Promise<void>;
  onLoadPositions: () => Promise<void>;
  savingPositions: boolean;
  hasUnsavedChanges: boolean;
  // Context menu callbacks
  onAddNote?: (nodeId: string | null, edgeKey?: { source: string; target: string }) => void;
  onAddLabel?: (nodeId: string | null, edgeKey?: { source: string; target: string }) => void;
  onHighlight?: (nodeId: string | null, color: string) => void;
  onGroupSelected?: (nodeIds: string[]) => void;
  // Export callbacks
  onExportPng?: () => void;
  onExportSvg?: () => void;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  nodeId: string | null;
  edgeKey: { source: string; target: string } | null;
}

export function LinkAnalysisMode({
  projectId: _projectId,
  isAnalysisMode,
  onModeChange,
  positions,
  onPositionChange: _onPositionChange,
  onSavePositions,
  onClearPositions,
  onLoadPositions,
  savingPositions,
  hasUnsavedChanges,
  onAddNote,
  onAddLabel,
  onHighlight,
  onGroupSelected: _onGroupSelected,
  onExportPng,
  onExportSvg,
}: LinkAnalysisModeProps) {
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    nodeId: null,
    edgeKey: null,
  });
  const menuRef = useRef<HTMLDivElement>(null);

  // Close context menu
  const closeContextMenu = useCallback(() => {
    setContextMenu(prev => ({ ...prev, visible: false }));
  }, []);

  // Handle context menu actions
  const handleAddNote = useCallback(() => {
    onAddNote?.(contextMenu.nodeId, contextMenu.edgeKey || undefined);
    closeContextMenu();
  }, [contextMenu, onAddNote, closeContextMenu]);

  const handleAddLabel = useCallback(() => {
    onAddLabel?.(contextMenu.nodeId, contextMenu.edgeKey || undefined);
    closeContextMenu();
  }, [contextMenu, onAddLabel, closeContextMenu]);

  const handleHighlight = useCallback((color: string) => {
    onHighlight?.(contextMenu.nodeId, color);
    closeContextMenu();
  }, [contextMenu, onHighlight, closeContextMenu]);

  return (
    <div className="link-analysis-mode">
      {/* Mode Toggle */}
      <div className="mode-section">
        <h4>Layout Mode</h4>
        <div className="mode-toggle">
          <button
            className={`mode-btn ${!isAnalysisMode ? 'active' : ''}`}
            onClick={() => onModeChange(false)}
            title="Automatic physics-based layout"
          >
            <Icon name="Sparkles" size={14} />
            Auto Layout
          </button>
          <button
            className={`mode-btn ${isAnalysisMode ? 'active' : ''}`}
            onClick={() => onModeChange(true)}
            title="Manual positioning with saved positions"
          >
            <Icon name="MousePointer" size={14} />
            Analysis Mode
          </button>
        </div>
        <p className="mode-hint">
          {isAnalysisMode
            ? 'Drag nodes to position. Positions are saved.'
            : 'Physics simulation positions nodes automatically.'}
        </p>
      </div>

      {/* Position Management (only in Analysis Mode) */}
      {isAnalysisMode && (
        <div className="position-section">
          <h4>Positions</h4>
          <div className="position-stats">
            <span>{positions.size} pinned</span>
            {hasUnsavedChanges && (
              <span className="unsaved-indicator">
                <Icon name="AlertCircle" size={12} />
                Unsaved
              </span>
            )}
          </div>
          <div className="position-actions">
            <button
              className="btn btn-sm btn-primary"
              onClick={onSavePositions}
              disabled={savingPositions || !hasUnsavedChanges}
              title="Save positions to database"
            >
              {savingPositions ? (
                <Icon name="Loader2" size={14} className="spin" />
              ) : (
                <Icon name="Save" size={14} />
              )}
              Save
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={onLoadPositions}
              disabled={savingPositions}
              title="Load saved positions"
            >
              <Icon name="Download" size={14} />
              Load
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={onClearPositions}
              disabled={savingPositions || positions.size === 0}
              title="Clear all positions"
            >
              <Icon name="Trash2" size={14} />
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Export Options */}
      <div className="export-section">
        <h4>Export</h4>
        <div className="export-actions">
          {onExportPng && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={onExportPng}
              title="Export graph as PNG image"
            >
              <Icon name="Image" size={14} />
              PNG
            </button>
          )}
          {onExportSvg && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={onExportSvg}
              title="Export graph as SVG vector"
            >
              <Icon name="FileCode" size={14} />
              SVG
            </button>
          )}
        </div>
      </div>

      {/* Annotation Section */}
      <div className="annotation-section">
        <h4>Quick Actions</h4>
        <p className="annotation-hint">
          Right-click on nodes or edges to add annotations.
        </p>
        <div className="quick-actions">
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => onAddNote?.(null)}
            title="Add a graph-level note"
          >
            <Icon name="StickyNote" size={14} />
            Add Note
          </button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => onAddLabel?.(null)}
            title="Add a graph-level label"
          >
            <Icon name="Tag" size={14} />
            Add Label
          </button>
        </div>
      </div>

      {/* Context Menu (rendered at document level) */}
      {contextMenu.visible && (
        <div
          ref={menuRef}
          className="graph-context-menu"
          style={{
            position: 'fixed',
            left: contextMenu.x,
            top: contextMenu.y,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="context-menu-item" onClick={handleAddNote}>
            <Icon name="StickyNote" size={14} />
            Add Note
          </button>
          <button className="context-menu-item" onClick={handleAddLabel}>
            <Icon name="Tag" size={14} />
            Add Label
          </button>
          <div className="context-menu-divider" />
          <div className="context-menu-submenu">
            <span className="context-menu-label">Highlight</span>
            <div className="highlight-colors">
              <button
                className="highlight-color"
                style={{ backgroundColor: '#ef4444' }}
                onClick={() => handleHighlight('#ef4444')}
                title="Red"
              />
              <button
                className="highlight-color"
                style={{ backgroundColor: '#f59e0b' }}
                onClick={() => handleHighlight('#f59e0b')}
                title="Orange"
              />
              <button
                className="highlight-color"
                style={{ backgroundColor: '#22c55e' }}
                onClick={() => handleHighlight('#22c55e')}
                title="Green"
              />
              <button
                className="highlight-color"
                style={{ backgroundColor: '#3b82f6' }}
                onClick={() => handleHighlight('#3b82f6')}
                title="Blue"
              />
              <button
                className="highlight-color"
                style={{ backgroundColor: '#8b5cf6' }}
                onClick={() => handleHighlight('#8b5cf6')}
                title="Purple"
              />
            </div>
          </div>
          <div className="context-menu-divider" />
          <button className="context-menu-item" onClick={closeContextMenu}>
            <Icon name="X" size={14} />
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Hook for managing link analysis mode state
 */
export function useLinkAnalysisMode(projectId: string) {
  const [isAnalysisMode, setIsAnalysisMode] = useState(false);
  const [positions, setPositions] = useState<Map<string, Position>>(new Map());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [savingPositions, setSavingPositions] = useState(false);
  const initialPositionsRef = useRef<string>('');

  // Update position for a node
  const updatePosition = useCallback((nodeId: string, position: Position) => {
    setPositions(prev => {
      const next = new Map(prev);
      next.set(nodeId, position);
      return next;
    });
    setHasUnsavedChanges(true);
  }, []);

  // Save positions to backend
  const savePositions = useCallback(async () => {
    if (positions.size === 0) return;

    setSavingPositions(true);
    try {
      const positionsArray = Array.from(positions.entries()).map(([nodeId, pos]) => ({
        node_id: nodeId,
        x: pos.x,
        y: pos.y,
        pinned: pos.pinned,
      }));

      const response = await fetch('/api/graph/positions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          positions: positionsArray,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save positions');
      }

      setHasUnsavedChanges(false);
      initialPositionsRef.current = JSON.stringify(Array.from(positions.entries()));
    } catch (error) {
      console.error('Error saving positions:', error);
      throw error;
    } finally {
      setSavingPositions(false);
    }
  }, [projectId, positions]);

  // Load positions from backend
  const loadPositions = useCallback(async () => {
    try {
      const response = await fetch(`/api/graph/positions/${projectId}`);
      if (!response.ok) {
        throw new Error('Failed to load positions');
      }

      const data = await response.json();
      const loadedPositions = new Map<string, Position>();

      for (const [nodeId, pos] of Object.entries(data.positions)) {
        const { x, y, pinned } = pos as { x: number; y: number; pinned: boolean };
        loadedPositions.set(nodeId, { x, y, pinned });
      }

      setPositions(loadedPositions);
      setHasUnsavedChanges(false);
      initialPositionsRef.current = JSON.stringify(Array.from(loadedPositions.entries()));
    } catch (error) {
      console.error('Error loading positions:', error);
      throw error;
    }
  }, [projectId]);

  // Clear all positions
  const clearPositions = useCallback(async () => {
    try {
      const response = await fetch(`/api/graph/positions/${projectId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to clear positions');
      }

      setPositions(new Map());
      setHasUnsavedChanges(false);
      initialPositionsRef.current = '';
    } catch (error) {
      console.error('Error clearing positions:', error);
      throw error;
    }
  }, [projectId]);

  return {
    isAnalysisMode,
    setIsAnalysisMode,
    positions,
    updatePosition,
    savePositions,
    loadPositions,
    clearPositions,
    hasUnsavedChanges,
    savingPositions,
  };
}
