/**
 * ExpandNeighborsPanel - Network exploration panel for progressive disclosure
 *
 * Core OSINT workflow: start with a seed entity, progressively expand its network.
 *
 * Features:
 * - Node label and type display
 * - Seed node and depth badges
 * - Expand/Collapse buttons with loading state
 * - Expansion statistics
 * - Depth legend with color coding
 */

import React from 'react';
import { Icon } from '../../../../components/common/Icon';

// GraphNode type (should match the main graph types)
interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree?: number;
  entity_type?: string;
  document_count?: number;
}

export interface ExpandState {
  expandedNodes: Set<string>;
  expansionDepth: Map<string, number>;
  seedNodes: Set<string>;
  maxDepth: number;
}

export interface ExpandNeighborsPanelProps {
  selectedNode: GraphNode | null;
  expandState: ExpandState;
  onExpand: (nodeId: string) => void;
  onCollapse: (nodeId: string) => void;
  canExpand: (nodeId: string) => boolean;
  isExpanding: boolean;
  maxDepth: number;
}

// Icon mapping for entity types
const TYPE_ICONS: Record<string, string> = {
  person: 'User',
  organization: 'Building2',
  location: 'MapPin',
  gpe: 'MapPin',
  event: 'Calendar',
  document: 'FileText',
  money: 'DollarSign',
  phone: 'Phone',
  email: 'Mail',
  claim: 'Target',
  evidence: 'CheckCircle',
  hypothesis: 'Lightbulb',
  unknown: 'HelpCircle',
};

export const ExpandNeighborsPanel: React.FC<ExpandNeighborsPanelProps> = ({
  selectedNode,
  expandState,
  onExpand,
  onCollapse,
  canExpand,
  isExpanding,
  maxDepth,
}) => {
  if (!selectedNode) {
    return (
      <div className="expand-neighbors-panel expand-neighbors-empty">
        <div className="expand-header">
          <h4>
            <Icon name="Network" size={16} />
            Network Exploration
          </h4>
        </div>
        <p className="empty-message">
          Select a node to explore its network connections.
        </p>
      </div>
    );
  }

  const nodeDepth = expandState.expansionDepth.get(selectedNode.id) ?? 0;
  const isExpanded = expandState.expandedNodes.has(selectedNode.id);
  const isSeed = expandState.seedNodes.has(selectedNode.id);
  const canExpandNode = canExpand(selectedNode.id);
  const nodeType = (selectedNode.type || selectedNode.entity_type || 'unknown').toLowerCase();
  const iconName = TYPE_ICONS[nodeType] || TYPE_ICONS.unknown;

  return (
    <div className="expand-neighbors-panel">
      {/* Header */}
      <div className="expand-header">
        <h4>
          <Icon name="Network" size={16} />
          Network Exploration
        </h4>
      </div>

      {/* Selected node info */}
      <div className="node-info">
        <div className="node-type-icon">
          <Icon name={iconName as any} size={20} />
        </div>
        <div className="node-details">
          <span className="node-label">{selectedNode.label}</span>
          <span className="node-type-name">{nodeType}</span>
        </div>
      </div>

      {/* Badges */}
      <div className="node-badges">
        {isSeed && (
          <span className="badge badge-seed">
            <Icon name="Star" size={12} />
            Seed
          </span>
        )}
        <span className="badge badge-depth">
          <Icon name="Layers" size={12} />
          Depth: {nodeDepth}/{maxDepth}
        </span>
        {selectedNode.degree !== undefined && (
          <span className="badge badge-connections">
            <Icon name="GitBranch" size={12} />
            {selectedNode.degree} connections
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div className="expand-actions">
        {canExpandNode && (
          <button
            className="btn btn-primary"
            onClick={() => onExpand(selectedNode.id)}
            disabled={isExpanding}
          >
            {isExpanding ? (
              <>
                <Icon name="Loader2" size={14} className="spin" />
                Expanding...
              </>
            ) : (
              <>
                <Icon name="Plus" size={14} />
                Expand Neighbors
              </>
            )}
          </button>
        )}

        {isExpanded && (
          <button
            className="btn btn-secondary"
            onClick={() => onCollapse(selectedNode.id)}
            disabled={isExpanding}
          >
            <Icon name="Minus" size={14} />
            Collapse
          </button>
        )}

        {!canExpandNode && !isExpanded && nodeDepth >= maxDepth && (
          <div className="max-depth-notice">
            <Icon name="AlertCircle" size={14} />
            Maximum depth reached
          </div>
        )}

        {!canExpandNode && isExpanded && (
          <div className="fully-expanded-notice">
            <Icon name="CheckCircle" size={14} />
            Fully expanded
          </div>
        )}
      </div>

      {/* Expansion statistics */}
      <div className="expansion-stats">
        <div className="stat-row">
          <span className="stat-label">Nodes explored:</span>
          <span className="stat-value">{expandState.expandedNodes.size}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Current depth:</span>
          <span className="stat-value">{expandState.maxDepth}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Seed nodes:</span>
          <span className="stat-value">{expandState.seedNodes.size}</span>
        </div>
      </div>

      {/* Depth legend */}
      <div className="depth-legend">
        <h5>Depth Legend</h5>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-color depth-0"></span>
            <span>Seed (original query)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color depth-1"></span>
            <span>1 hop away</span>
          </div>
          <div className="legend-item">
            <span className="legend-color depth-2"></span>
            <span>2 hops away</span>
          </div>
          <div className="legend-item">
            <span className="legend-color depth-3"></span>
            <span>3+ hops away</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExpandNeighborsPanel;
