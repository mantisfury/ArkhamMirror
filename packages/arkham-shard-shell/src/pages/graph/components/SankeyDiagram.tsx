/**
 * SankeyDiagram - Flow visualization using D3-Sankey
 *
 * Displays resource/information flow through entities as a Sankey diagram.
 * Supports multiple flow types and interactive node/link selection.
 */

import { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal, SankeyNode } from 'd3-sankey';
import { Icon } from '../../../components/common/Icon';

// Flow data types
interface FlowNode {
  id: string;
  label: string;
  entity_type: string;
  layer: number;
  value: number;
}

interface FlowLink {
  source: string;
  target: string;
  value: number;
  category: string | null;
  relationship_type: string | null;
}

export interface FlowData {
  nodes: FlowNode[];
  links: FlowLink[];
  total_flow: number;
  layer_count: number;
  node_count: number;
  link_count: number;
}

// Internal types for D3 processing (source/target become indices)
interface ProcessedLink {
  source: number;
  target: number;
  value: number;
  category: string | null;
  relationship_type: string | null;
}

// D3 Sankey types
type SankeyNodeExtended = SankeyNode<FlowNode, ProcessedLink> & FlowNode;

export interface SankeyDiagramProps {
  flowData: FlowData | null;
  width?: number;
  height?: number;
  nodeWidth?: number;
  nodePadding?: number;
  onNodeClick?: (nodeId: string) => void;
  onLinkClick?: (source: string, target: string) => void;
  highlightedNodes?: Set<string>;
  isLoading?: boolean;
  colorByType?: boolean;
}

// Entity type colors
const TYPE_COLORS: Record<string, string> = {
  person: '#4299e1',
  organization: '#48bb78',
  location: '#ed8936',
  event: '#9f7aea',
  document: '#f56565',
  claim: '#f59e0b',
  evidence: '#3b82f6',
  hypothesis: '#8b5cf6',
  other: '#718096',
  default: '#a0aec0',
};

// Category colors for links
const CATEGORY_COLORS: Record<string, string> = {
  works_for: '#3b82f6',
  affiliated_with: '#8b5cf6',
  located_in: '#10b981',
  related_to: '#6b7280',
  transacted_with: '#f59e0b',
  communicated_with: '#ec4899',
  aggregated: '#9ca3af',
  default: '#94a3b8',
};

export function SankeyDiagram({
  flowData,
  width = 800,
  height = 500,
  nodeWidth = 20,
  nodePadding = 10,
  onNodeClick,
  onLinkClick,
  highlightedNodes,
  isLoading = false,
  colorByType = true,
}: SankeyDiagramProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    content: string;
  }>({ visible: false, x: 0, y: 0, content: '' });
  const [_hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Get node color
  const getNodeColor = useCallback((node: FlowNode) => {
    if (colorByType) {
      return TYPE_COLORS[node.entity_type?.toLowerCase()] || TYPE_COLORS.default;
    }
    // Color by layer
    const layerColors = ['#4299e1', '#48bb78', '#ed8936', '#9f7aea'];
    return layerColors[node.layer % layerColors.length];
  }, [colorByType]);

  // Get link color
  const getLinkColor = useCallback((link: FlowLink) => {
    const category = link.category || link.relationship_type || 'default';
    return CATEGORY_COLORS[category.toLowerCase()] || CATEGORY_COLORS.default;
  }, []);

  // Process flow data for D3 Sankey
  const sankeyData = useMemo(() => {
    if (!flowData || flowData.nodes.length === 0 || flowData.links.length === 0) {
      return null;
    }

    // Create node index map
    const nodeIndexMap = new Map<string, number>();
    flowData.nodes.forEach((node, i) => {
      nodeIndexMap.set(node.id, i);
    });

    // Convert links to use indices
    const links = flowData.links
      .filter(link => {
        const sourceIdx = nodeIndexMap.get(link.source);
        const targetIdx = nodeIndexMap.get(link.target);
        return sourceIdx !== undefined && targetIdx !== undefined && sourceIdx !== targetIdx;
      })
      .map(link => ({
        ...link,
        source: nodeIndexMap.get(link.source)!,
        target: nodeIndexMap.get(link.target)!,
      }));

    if (links.length === 0) {
      return null;
    }

    return {
      nodes: flowData.nodes.map(n => ({ ...n })),
      links,
    };
  }, [flowData]);

  // Render Sankey diagram
  useEffect(() => {
    if (!svgRef.current || !sankeyData) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 20, right: 20, bottom: 20, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Create Sankey generator
    const sankeyGenerator = sankey<FlowNode, ProcessedLink>()
      .nodeId((d: any) => d.id)
      .nodeWidth(nodeWidth)
      .nodePadding(nodePadding)
      .extent([[0, 0], [innerWidth, innerHeight]]);

    // Generate layout
    const { nodes, links } = sankeyGenerator({
      nodes: sankeyData.nodes.map(d => ({ ...d })),
      links: sankeyData.links.map(d => ({ ...d })),
    });

    // Create main group
    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Draw links
    const linkGroup = g.append('g')
      .attr('class', 'sankey-links')
      .attr('fill', 'none');

    linkGroup.selectAll('path')
      .data(links)
      .enter()
      .append('path')
      .attr('class', 'sankey-link')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', (d: any) => getLinkColor(d))
      .attr('stroke-width', (d: any) => Math.max(1, d.width || 1))
      .attr('stroke-opacity', 0.5)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d: any) {
        d3.select(this)
          .attr('stroke-opacity', 0.8);

        const sourceNode = d.source as SankeyNodeExtended;
        const targetNode = d.target as SankeyNodeExtended;

        setTooltip({
          visible: true,
          x: event.offsetX,
          y: event.offsetY - 10,
          content: `${sourceNode.label} → ${targetNode.label}: ${d.value.toFixed(2)}`,
        });
      })
      .on('mouseout', function() {
        d3.select(this)
          .attr('stroke-opacity', 0.5);
        setTooltip(prev => ({ ...prev, visible: false }));
      })
      .on('click', (_, d: any) => {
        const sourceNode = d.source as SankeyNodeExtended;
        const targetNode = d.target as SankeyNodeExtended;
        onLinkClick?.(sourceNode.id, targetNode.id);
      });

    // Draw nodes
    const nodeGroup = g.append('g')
      .attr('class', 'sankey-nodes');

    const nodeRects = nodeGroup.selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'sankey-node')
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d: any) {
        setHoveredNode(d.id);
        setTooltip({
          visible: true,
          x: event.offsetX,
          y: event.offsetY - 10,
          content: `${d.label} (${d.entity_type})\nFlow: ${d.value?.toFixed(2) || 0}`,
        });

        // Highlight connected links
        linkGroup.selectAll('path')
          .attr('stroke-opacity', (link: any) => {
            const sourceNode = link.source as SankeyNodeExtended;
            const targetNode = link.target as SankeyNodeExtended;
            return sourceNode.id === d.id || targetNode.id === d.id ? 0.8 : 0.2;
          });
      })
      .on('mouseout', function() {
        setHoveredNode(null);
        setTooltip(prev => ({ ...prev, visible: false }));
        linkGroup.selectAll('path')
          .attr('stroke-opacity', 0.5);
      })
      .on('click', (_, d: any) => {
        onNodeClick?.(d.id);
      });

    // Node rectangles
    nodeRects.append('rect')
      .attr('x', (d: any) => d.x0)
      .attr('y', (d: any) => d.y0)
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('height', (d: any) => Math.max(1, d.y1 - d.y0))
      .attr('fill', (d: any) => getNodeColor(d))
      .attr('stroke', (d: any) => {
        if (highlightedNodes?.has(d.id)) return '#f59e0b';
        return d3.color(getNodeColor(d))?.darker(0.5)?.toString() || '#000';
      })
      .attr('stroke-width', (d: any) => highlightedNodes?.has(d.id) ? 2 : 1)
      .attr('rx', 3);

    // Node labels
    nodeRects.append('text')
      .attr('x', (d: any) => d.x0 < innerWidth / 2 ? d.x1 + 6 : d.x0 - 6)
      .attr('y', (d: any) => (d.y0 + d.y1) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', (d: any) => d.x0 < innerWidth / 2 ? 'start' : 'end')
      .attr('fill', 'var(--text-primary)')
      .attr('font-size', '11px')
      .attr('font-weight', (d: any) => highlightedNodes?.has(d.id) ? '600' : '400')
      .text((d: any) => d.label.length > 20 ? d.label.slice(0, 18) + '...' : d.label);

  }, [sankeyData, width, height, nodeWidth, nodePadding, getNodeColor, getLinkColor, highlightedNodes, onNodeClick, onLinkClick]);

  // Loading state
  if (isLoading) {
    return (
      <div className="sankey-loading">
        <Icon name="Loader2" size={48} className="spin" />
        <span>Loading flow data...</span>
      </div>
    );
  }

  // Empty state
  if (!flowData || flowData.nodes.length === 0) {
    return (
      <div className="sankey-empty">
        <Icon name="GitBranch" size={48} />
        <h3>No Flow Data</h3>
        <p>Configure source and target entity types to visualize flows</p>
      </div>
    );
  }

  if (!sankeyData) {
    return (
      <div className="sankey-empty">
        <Icon name="AlertCircle" size={48} />
        <h3>Unable to Generate Flows</h3>
        <p>The selected configuration doesn't produce valid flow paths</p>
      </div>
    );
  }

  return (
    <div className="sankey-diagram">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="sankey-svg"
      />

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="sankey-tooltip"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.content.split('\n').map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}

      {/* Stats bar */}
      <div className="sankey-stats">
        <span>{flowData.node_count} nodes</span>
        <span>{flowData.link_count} flows</span>
        <span>Total: {flowData.total_flow.toFixed(2)}</span>
        <span>{flowData.layer_count} layers</span>
      </div>
    </div>
  );
}

/**
 * Sankey Controls component for configuring the flow visualization
 */
export interface SankeyControlsProps {
  entityTypes: string[];
  sourceTypes: string[];
  onSourceTypesChange: (types: string[]) => void;
  targetTypes: string[];
  onTargetTypesChange: (types: string[]) => void;
  intermediateTypes: string[];
  onIntermediateTypesChange: (types: string[]) => void;
  flowType: 'entity' | 'relationship';
  onFlowTypeChange: (type: 'entity' | 'relationship') => void;
  aggregateByType: boolean;
  onAggregateByTypeChange: (aggregate: boolean) => void;
  minWeight: number;
  onMinWeightChange: (weight: number) => void;
  maxLinks: number;
  onMaxLinksChange: (max: number) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export function SankeyControls({
  entityTypes,
  sourceTypes,
  onSourceTypesChange,
  targetTypes,
  onTargetTypesChange,
  intermediateTypes,
  onIntermediateTypesChange,
  flowType,
  onFlowTypeChange,
  aggregateByType,
  onAggregateByTypeChange,
  minWeight,
  onMinWeightChange,
  maxLinks,
  onMaxLinksChange,
  onRefresh,
  isLoading,
}: SankeyControlsProps) {
  // Handle multi-select for entity types
  const toggleType = (types: string[], setTypes: (t: string[]) => void, type: string) => {
    if (types.includes(type)) {
      setTypes(types.filter(t => t !== type));
    } else {
      setTypes([...types, type]);
    }
  };

  return (
    <div className="sankey-controls">
      <div className="control-group">
        <label>Flow Type</label>
        <select
          value={flowType}
          onChange={(e) => onFlowTypeChange(e.target.value as 'entity' | 'relationship')}
        >
          <option value="entity">Entity Flows</option>
          <option value="relationship">Relationship Flows</option>
        </select>
      </div>

      {flowType === 'entity' && (
        <>
          <div className="control-group">
            <label>Source Types (Left)</label>
            <div className="type-checkboxes">
              {entityTypes.map(type => (
                <label key={type} className="checkbox-label small">
                  <input
                    type="checkbox"
                    checked={sourceTypes.includes(type)}
                    onChange={() => toggleType(sourceTypes, onSourceTypesChange, type)}
                  />
                  {type}
                </label>
              ))}
            </div>
          </div>

          <div className="control-group">
            <label>Target Types (Right)</label>
            <div className="type-checkboxes">
              {entityTypes.map(type => (
                <label key={type} className="checkbox-label small">
                  <input
                    type="checkbox"
                    checked={targetTypes.includes(type)}
                    onChange={() => toggleType(targetTypes, onTargetTypesChange, type)}
                  />
                  {type}
                </label>
              ))}
            </div>
          </div>

          <div className="control-group">
            <label>Intermediate Types (Middle)</label>
            <div className="type-checkboxes">
              {entityTypes.map(type => (
                <label key={type} className="checkbox-label small">
                  <input
                    type="checkbox"
                    checked={intermediateTypes.includes(type)}
                    onChange={() => toggleType(intermediateTypes, onIntermediateTypesChange, type)}
                  />
                  {type}
                </label>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="control-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={aggregateByType}
            onChange={(e) => onAggregateByTypeChange(e.target.checked)}
          />
          Aggregate by Type
        </label>
      </div>

      <div className="control-group">
        <label>Min Weight: {minWeight.toFixed(1)}</label>
        <input
          type="range"
          min={0}
          max={5}
          step={0.1}
          value={minWeight}
          onChange={(e) => onMinWeightChange(Number(e.target.value))}
        />
      </div>

      <div className="control-group">
        <label>Max Links: {maxLinks}</label>
        <input
          type="range"
          min={10}
          max={200}
          step={10}
          value={maxLinks}
          onChange={(e) => onMaxLinksChange(Number(e.target.value))}
        />
      </div>

      <button
        className="btn btn-primary"
        onClick={onRefresh}
        disabled={isLoading}
        style={{ width: '100%', marginTop: '0.5rem' }}
      >
        {isLoading ? (
          <>
            <Icon name="Loader2" size={16} className="spin" />
            Loading...
          </>
        ) : (
          <>
            <Icon name="RefreshCw" size={16} />
            Refresh Flows
          </>
        )}
      </button>
    </div>
  );
}
