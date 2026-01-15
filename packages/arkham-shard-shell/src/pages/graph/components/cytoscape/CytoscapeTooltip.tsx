/**
 * CytoscapeTooltip - Hover tooltip for graph nodes
 *
 * Displays:
 * - Node label and type icon
 * - Type name
 * - Connection count
 * - Document count
 *
 * Follows the mouse position with proper offset to avoid occlusion.
 */

import React, { useEffect, useState, useRef } from 'react';
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

export interface CytoscapeTooltipProps {
  node: GraphNode | null;
  position: { x: number; y: number } | null;
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
  artifact: 'Archive',
  timeline_event: 'Clock',
  unknown: 'HelpCircle',
};

// Entity type colors for the badge
const TYPE_COLORS: Record<string, string> = {
  person: '#4299e1',
  organization: '#48bb78',
  location: '#ed8936',
  gpe: '#ed8936',
  event: '#9f7aea',
  document: '#f56565',
  money: '#68d391',
  phone: '#63b3ed',
  email: '#63b3ed',
  claim: '#f59e0b',
  evidence: '#3b82f6',
  hypothesis: '#8b5cf6',
  artifact: '#10b981',
  timeline_event: '#ec4899',
  unknown: '#718096',
};

// Offset from cursor
const TOOLTIP_OFFSET_X = 15;
const TOOLTIP_OFFSET_Y = 15;

export const CytoscapeTooltip: React.FC<CytoscapeTooltipProps> = ({
  node,
  position,
}) => {
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [adjustedPosition, setAdjustedPosition] = useState<{ x: number; y: number } | null>(null);

  // Adjust position to keep tooltip within viewport
  useEffect(() => {
    if (!position || !tooltipRef.current) {
      setAdjustedPosition(null);
      return;
    }

    const tooltip = tooltipRef.current;
    const rect = tooltip.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let x = position.x + TOOLTIP_OFFSET_X;
    let y = position.y + TOOLTIP_OFFSET_Y;

    // Adjust if tooltip goes beyond right edge
    if (x + rect.width > viewportWidth - 10) {
      x = position.x - rect.width - TOOLTIP_OFFSET_X;
    }

    // Adjust if tooltip goes beyond bottom edge
    if (y + rect.height > viewportHeight - 10) {
      y = position.y - rect.height - TOOLTIP_OFFSET_Y;
    }

    // Ensure tooltip stays within left/top bounds
    x = Math.max(10, x);
    y = Math.max(10, y);

    setAdjustedPosition({ x, y });
  }, [position]);

  if (!node || !position) {
    return null;
  }

  const nodeType = (node.type || node.entity_type || 'unknown').toLowerCase();
  const iconName = TYPE_ICONS[nodeType] || TYPE_ICONS.unknown;
  const typeColor = TYPE_COLORS[nodeType] || TYPE_COLORS.unknown;

  return (
    <div
      ref={tooltipRef}
      className="cytoscape-tooltip"
      style={{
        position: 'fixed',
        left: adjustedPosition?.x ?? position.x + TOOLTIP_OFFSET_X,
        top: adjustedPosition?.y ?? position.y + TOOLTIP_OFFSET_Y,
        zIndex: 10000,
        visibility: adjustedPosition ? 'visible' : 'hidden',
      }}
    >
      {/* Header with icon and label */}
      <div className="tooltip-header">
        <div
          className="tooltip-type-icon"
          style={{ backgroundColor: typeColor }}
        >
          <Icon name={iconName as any} size={16} />
        </div>
        <span className="tooltip-label">{node.label}</span>
      </div>

      {/* Content rows */}
      <div className="tooltip-content">
        <div className="tooltip-row">
          <span className="tooltip-key">
            <Icon name="Tag" size={12} />
            Type
          </span>
          <span className="tooltip-value" style={{ color: typeColor }}>
            {nodeType}
          </span>
        </div>

        <div className="tooltip-row">
          <span className="tooltip-key">
            <Icon name="GitBranch" size={12} />
            Connections
          </span>
          <span className="tooltip-value">
            {node.degree ?? 0}
          </span>
        </div>

        <div className="tooltip-row">
          <span className="tooltip-key">
            <Icon name="FileText" size={12} />
            Documents
          </span>
          <span className="tooltip-value">
            {node.document_count ?? 0}
          </span>
        </div>
      </div>

      {/* Click hint */}
      <div className="tooltip-hint">
        Click to select | Right-click for options
      </div>
    </div>
  );
};

export default CytoscapeTooltip;
