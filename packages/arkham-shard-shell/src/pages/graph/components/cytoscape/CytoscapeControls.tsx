/**
 * CytoscapeControls - Layout and view controls panel for Cytoscape graph
 *
 * Provides controls for:
 * - Layout algorithm selection (fcose, hierarchical, concentric, etc.)
 * - Edge label visibility toggle
 * - Cluster expand/collapse all
 * - Fit to view button
 */

import React from 'react';
import { Icon } from '../../../../components/common/Icon';

export interface CytoscapeControlsProps {
  layout: string;
  onLayoutChange: (layout: string) => void;
  showEdgeLabels: boolean;
  onShowEdgeLabelsChange: (show: boolean) => void;
  onZoomToFit: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}

// Layout options with descriptions
const LAYOUT_OPTIONS = [
  { value: 'fcose', label: 'Force-Directed (fCoSE)', description: 'General exploration' },
  { value: 'hierarchical', label: 'Hierarchical (Dagre)', description: 'Org charts, chains' },
  { value: 'concentric', label: 'Radial (Concentric)', description: 'Ego networks' },
  { value: 'circle', label: 'Circular', description: 'All nodes on ring' },
  { value: 'grid', label: 'Grid', description: 'Side-by-side' },
  { value: 'breadthfirst', label: 'Tree (Breadth-First)', description: 'Hierarchies' },
  { value: 'cose', label: 'Clustered (CoSE)', description: 'Community groups' },
];

export const CytoscapeControls: React.FC<CytoscapeControlsProps> = ({
  layout,
  onLayoutChange,
  showEdgeLabels,
  onShowEdgeLabelsChange,
  onZoomToFit,
  onExpandAll,
  onCollapseAll,
}) => {
  return (
    <div className="cytoscape-controls">
      {/* Layout Selection */}
      <div className="control-section">
        <h4>
          <Icon name="LayoutGrid" size={16} />
          Layout Algorithm
        </h4>
        <select
          value={layout}
          onChange={(e) => onLayoutChange(e.target.value)}
          className="select"
        >
          {LAYOUT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <p className="control-hint">
          {LAYOUT_OPTIONS.find((o) => o.value === layout)?.description}
        </p>
      </div>

      {/* Display Options */}
      <div className="control-section">
        <h4>
          <Icon name="Eye" size={16} />
          Display Options
        </h4>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showEdgeLabels}
            onChange={(e) => onShowEdgeLabelsChange(e.target.checked)}
          />
          <span>Show relationship labels</span>
        </label>
      </div>

      {/* Cluster Controls */}
      <div className="control-section">
        <h4>
          <Icon name="Boxes" size={16} />
          Clusters
        </h4>
        <div className="button-group">
          <button
            className="btn btn-sm btn-secondary"
            onClick={onExpandAll}
            title="Expand all collapsed clusters"
          >
            <Icon name="Maximize2" size={14} />
            Expand All
          </button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={onCollapseAll}
            title="Collapse all expanded clusters"
          >
            <Icon name="Minimize2" size={14} />
            Collapse All
          </button>
        </div>
      </div>

      {/* View Controls */}
      <div className="control-section">
        <h4>
          <Icon name="Move" size={16} />
          View
        </h4>
        <button
          className="btn btn-secondary"
          onClick={onZoomToFit}
          title="Fit entire graph in view"
        >
          <Icon name="Maximize" size={14} />
          Fit to View
        </button>
      </div>

      {/* Keyboard Shortcuts Help */}
      <div className="control-section shortcuts-section">
        <h4>
          <Icon name="Keyboard" size={16} />
          Shortcuts
        </h4>
        <div className="shortcuts-list">
          <div className="shortcut-item">
            <kbd>Esc</kbd>
            <span>Clear selection</span>
          </div>
          <div className="shortcut-item">
            <kbd>Ctrl+F</kbd>
            <span>Fit to view</span>
          </div>
          <div className="shortcut-item">
            <kbd>+</kbd> / <kbd>-</kbd>
            <span>Zoom in/out</span>
          </div>
          <div className="shortcut-item">
            <kbd>Del</kbd>
            <span>Hide selected</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CytoscapeControls;
