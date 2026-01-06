/**
 * ArgumentationView - Visualize ACH matrices as argumentation graphs
 *
 * Features:
 * - Hierarchical layout: Hypotheses at top, evidence below
 * - Green edges = supports, Red edges = attacks
 * - Node opacity based on acceptance status
 * - Matrix selector to choose which ACH matrix to visualize
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';
import { Icon } from '../../../components/common/Icon';

// Types
export interface ArgumentNode {
  id: string;
  node_type: 'hypothesis' | 'evidence' | 'claim' | 'assumption';
  label: string;
  description: string;
  confidence: number | null;
  consistency_score: number | null;
  rank: number | null;
  is_lead: boolean;
  credibility: number | null;
  evidence_type: string | null;
  source: string | null;
}

export interface ArgumentEdge {
  source: string;
  target: string;
  edge_type: 'supports' | 'attacks' | 'neutral';
  strength: number;
  rating_value: string;
  reasoning: string;
  confidence: number;
}

export interface ArgumentStatus {
  node_id: string;
  status: 'accepted' | 'rejected' | 'undecided';
  support_count: number;
  attack_count: number;
  net_score: number;
}

export interface ArgumentationData {
  matrix_id: string;
  matrix_title: string;
  nodes: ArgumentNode[];
  edges: ArgumentEdge[];
  statuses: ArgumentStatus[];
  leading_hypothesis_id: string | null;
  summary: {
    hypothesis_count: number;
    evidence_count: number;
    support_edges: number;
    attack_edges: number;
    neutral_edges: number;
  };
}

export interface ACHMatrixInfo {
  id: string;
  title: string;
  description: string;
  status: string;
  hypothesis_count: number;
  evidence_count: number;
  created_at: string | null;
}

export interface ArgumentationViewProps {
  projectId: string;
  onNodeClick?: (nodeId: string, nodeType: string) => void;
  onEdgeClick?: (source: string, target: string, edgeType: string) => void;
  width?: number;
  height?: number;
}

// Position type for D3
interface NodePosition {
  id: string;
  x: number;
  y: number;
  node: ArgumentNode;
  status?: ArgumentStatus;
}

export function ArgumentationView({
  projectId,
  onNodeClick,
  onEdgeClick,
  width = 900,
  height = 600,
}: ArgumentationViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [matrices, setMatrices] = useState<ACHMatrixInfo[]>([]);
  const [selectedMatrixId, setSelectedMatrixId] = useState<string | null>(null);
  const [data, setData] = useState<ArgumentationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    content: React.ReactNode;
  }>({ visible: false, x: 0, y: 0, content: null });

  // Fetch available matrices
  useEffect(() => {
    async function fetchMatrices() {
      try {
        const response = await fetch(`/api/graph/argumentation/matrices/${projectId}`);
        if (!response.ok) throw new Error('Failed to fetch matrices');
        const result = await response.json();
        setMatrices(result.matrices || []);
        // Auto-select first matrix if available
        if (result.matrices?.length > 0 && !selectedMatrixId) {
          setSelectedMatrixId(result.matrices[0].id);
        }
      } catch (err) {
        console.error('Error fetching matrices:', err);
      }
    }
    fetchMatrices();
  }, [projectId]);

  // Fetch argumentation data for selected matrix
  useEffect(() => {
    if (!selectedMatrixId) return;

    async function fetchArgumentation() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/graph/argumentation/${selectedMatrixId}`);
        if (!response.ok) throw new Error('Failed to fetch argumentation data');
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchArgumentation();
  }, [selectedMatrixId]);

  // Calculate node positions
  const positions = useMemo(() => {
    if (!data) return [];

    const hypotheses = data.nodes.filter(n => n.node_type === 'hypothesis');
    const evidence = data.nodes.filter(n => n.node_type === 'evidence');

    const positions: NodePosition[] = [];
    const margin = { top: 80, bottom: 80, left: 100, right: 100 };
    const layerGap = (height - margin.top - margin.bottom) / 2;

    // Position hypotheses at top
    const hypSpacing = (width - margin.left - margin.right) / Math.max(hypotheses.length, 1);
    hypotheses.forEach((node, i) => {
      const status = data.statuses.find(s => s.node_id === node.id);
      positions.push({
        id: node.id,
        x: margin.left + hypSpacing * (i + 0.5),
        y: margin.top,
        node,
        status,
      });
    });

    // Position evidence at bottom
    const evSpacing = (width - margin.left - margin.right) / Math.max(evidence.length, 1);
    evidence.forEach((node, i) => {
      positions.push({
        id: node.id,
        x: margin.left + evSpacing * (i + 0.5),
        y: margin.top + layerGap,
        node,
      });
    });

    return positions;
  }, [data, width, height]);

  // Render D3 visualization
  useEffect(() => {
    if (!svgRef.current || !data || positions.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const positionMap = new Map(positions.map(p => [p.id, p]));

    // Create defs for markers (arrowheads)
    const defs = svg.append('defs');

    // Support arrow (green)
    defs.append('marker')
      .attr('id', 'arrow-support')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#22c55e');

    // Attack arrow (red)
    defs.append('marker')
      .attr('id', 'arrow-attack')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#ef4444');

    // Draw edges
    const edgeGroup = svg.append('g').attr('class', 'edges');

    data.edges.forEach(edge => {
      const sourcePos = positionMap.get(edge.source);
      const targetPos = positionMap.get(edge.target);

      if (!sourcePos || !targetPos) return;

      const isSupport = edge.edge_type === 'supports';
      const isAttack = edge.edge_type === 'attacks';
      const color = isSupport ? '#22c55e' : isAttack ? '#ef4444' : '#94a3b8';
      const strokeWidth = Math.max(1, Math.min(4, Math.abs(edge.strength) * 1.5));

      edgeGroup.append('line')
        .attr('x1', sourcePos.x)
        .attr('y1', sourcePos.y)
        .attr('x2', targetPos.x)
        .attr('y2', targetPos.y)
        .attr('stroke', color)
        .attr('stroke-width', strokeWidth)
        .attr('stroke-opacity', 0.6)
        .attr('marker-end', isSupport ? 'url(#arrow-support)' : isAttack ? 'url(#arrow-attack)' : '')
        .attr('stroke-dasharray', isAttack ? '5,3' : 'none')
        .attr('cursor', 'pointer')
        .on('click', () => {
          onEdgeClick?.(edge.source, edge.target, edge.edge_type);
        })
        .on('mouseenter', (event) => {
          setTooltip({
            visible: true,
            x: event.clientX + 10,
            y: event.clientY + 10,
            content: (
              <div>
                <div style={{ fontWeight: 600 }}>
                  {edge.edge_type === 'supports' ? '✓ Supports' : edge.edge_type === 'attacks' ? '✗ Attacks' : '○ Neutral'}
                </div>
                <div>Rating: {edge.rating_value}</div>
                <div>Strength: {edge.strength.toFixed(1)}</div>
                {edge.reasoning && <div style={{ marginTop: 4, fontSize: '0.7rem', maxWidth: 200 }}>{edge.reasoning}</div>}
              </div>
            ),
          });
        })
        .on('mouseleave', () => setTooltip(prev => ({ ...prev, visible: false })));
    });

    // Draw nodes
    const nodeGroup = svg.append('g').attr('class', 'nodes');

    positions.forEach(pos => {
      const isHypothesis = pos.node.node_type === 'hypothesis';
      const isLead = pos.node.is_lead;
      const status = pos.status?.status;

      // Determine node appearance
      let fillColor = isHypothesis ? '#3b82f6' : '#64748b';
      let opacity = 1;

      if (status === 'accepted') {
        fillColor = '#22c55e';
      } else if (status === 'rejected') {
        fillColor = '#ef4444';
        opacity = 0.5;
      } else if (status === 'undecided') {
        fillColor = '#f59e0b';
        opacity = 0.8;
      }

      const nodeSize = isHypothesis ? 20 : 14;
      const g = nodeGroup.append('g')
        .attr('transform', `translate(${pos.x}, ${pos.y})`)
        .attr('cursor', 'pointer')
        .on('click', () => onNodeClick?.(pos.node.id, pos.node.node_type))
        .on('mouseenter', (event) => {
          setTooltip({
            visible: true,
            x: event.clientX + 10,
            y: event.clientY + 10,
            content: (
              <div>
                <div style={{ fontWeight: 600 }}>{pos.node.label}</div>
                <div style={{ fontSize: '0.7rem', color: '#888', textTransform: 'capitalize' }}>
                  {pos.node.node_type}
                </div>
                {isHypothesis && pos.status && (
                  <>
                    <div>Status: {pos.status.status}</div>
                    <div>Support: {pos.status.support_count} | Attack: {pos.status.attack_count}</div>
                    <div>Net Score: {pos.status.net_score.toFixed(1)}</div>
                  </>
                )}
                {!isHypothesis && pos.node.credibility !== null && (
                  <div>Credibility: {(pos.node.credibility * 100).toFixed(0)}%</div>
                )}
                {pos.node.description && (
                  <div style={{ marginTop: 4, fontSize: '0.7rem', maxWidth: 200 }}>{pos.node.description}</div>
                )}
              </div>
            ),
          });
        })
        .on('mouseleave', () => setTooltip(prev => ({ ...prev, visible: false })));

      // Node shape: rectangle for hypotheses, circle for evidence
      if (isHypothesis) {
        g.append('rect')
          .attr('x', -nodeSize * 2)
          .attr('y', -nodeSize)
          .attr('width', nodeSize * 4)
          .attr('height', nodeSize * 2)
          .attr('rx', 6)
          .attr('fill', fillColor)
          .attr('fill-opacity', opacity)
          .attr('stroke', isLead ? '#fbbf24' : '#fff')
          .attr('stroke-width', isLead ? 3 : 2);

        // Lead hypothesis crown indicator
        if (isLead) {
          g.append('text')
            .attr('y', -nodeSize - 5)
            .attr('text-anchor', 'middle')
            .attr('font-size', 14)
            .text('👑');
        }
      } else {
        g.append('circle')
          .attr('r', nodeSize)
          .attr('fill', fillColor)
          .attr('fill-opacity', opacity)
          .attr('stroke', '#fff')
          .attr('stroke-width', 1.5);
      }

      // Node label
      g.append('text')
        .attr('y', isHypothesis ? nodeSize + 16 : nodeSize + 12)
        .attr('text-anchor', 'middle')
        .attr('font-size', isHypothesis ? 11 : 9)
        .attr('fill', 'var(--text-primary)')
        .text(pos.node.label.length > 20 ? pos.node.label.slice(0, 20) + '...' : pos.node.label);
    });

    // Add layer labels
    svg.append('text')
      .attr('x', 20)
      .attr('y', 30)
      .attr('font-size', 12)
      .attr('fill', 'var(--text-secondary)')
      .attr('font-weight', 600)
      .text('HYPOTHESES');

    svg.append('text')
      .attr('x', 20)
      .attr('y', height / 2 + 30)
      .attr('font-size', 12)
      .attr('fill', 'var(--text-secondary)')
      .attr('font-weight', 600)
      .text('EVIDENCE');

  }, [data, positions, width, height, onNodeClick, onEdgeClick]);

  // Empty state
  if (matrices.length === 0 && !loading) {
    return (
      <div className="argumentation-empty">
        <Icon name="GitBranch" size={48} />
        <h3>No ACH Matrices</h3>
        <p>Create an ACH matrix in the Analysis shard to visualize argumentation structure.</p>
      </div>
    );
  }

  return (
    <div className="argumentation-view">
      {/* Matrix Selector */}
      <div className="argumentation-header">
        <div className="matrix-selector">
          <label>ACH Matrix:</label>
          <select
            value={selectedMatrixId || ''}
            onChange={(e) => setSelectedMatrixId(e.target.value)}
          >
            {matrices.map(m => (
              <option key={m.id} value={m.id}>
                {m.title} ({m.hypothesis_count}H / {m.evidence_count}E)
              </option>
            ))}
          </select>
        </div>

        {data && (
          <div className="argumentation-stats">
            <span>{data.summary.hypothesis_count} hypotheses</span>
            <span>{data.summary.evidence_count} evidence</span>
            <span className="stat-support">{data.summary.support_edges} supports</span>
            <span className="stat-attack">{data.summary.attack_edges} attacks</span>
          </div>
        )}
      </div>

      {/* Visualization */}
      <div className="argumentation-canvas">
        {loading ? (
          <div className="argumentation-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading argumentation graph...</span>
          </div>
        ) : error ? (
          <div className="argumentation-error">
            <Icon name="AlertCircle" size={32} />
            <span>{error}</span>
          </div>
        ) : (
          <svg
            ref={svgRef}
            width={width}
            height={height}
            className="argumentation-svg"
          />
        )}
      </div>

      {/* Legend */}
      <div className="argumentation-legend">
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#22c55e' }} />
          <span>Supports</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#ef4444' }} />
          <span>Attacks</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ background: '#fbbf24' }} />
          <span>Leading Hypothesis</span>
        </div>
        <div className="legend-item">
          <span className="legend-shape hypothesis" />
          <span>Hypothesis</span>
        </div>
        <div className="legend-item">
          <span className="legend-shape evidence" />
          <span>Evidence</span>
        </div>
      </div>

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="argumentation-tooltip"
          style={{
            position: 'fixed',
            left: tooltip.x,
            top: tooltip.y,
          }}
        >
          {tooltip.content}
        </div>
      )}
    </div>
  );
}

/**
 * Controls for the ArgumentationView
 */
export interface ArgumentationControlsProps {
  showLabels: boolean;
  onShowLabelsChange: (show: boolean) => void;
  highlightLeading: boolean;
  onHighlightLeadingChange: (highlight: boolean) => void;
}

export function ArgumentationControls({
  showLabels,
  onShowLabelsChange,
  highlightLeading,
  onHighlightLeadingChange,
}: ArgumentationControlsProps) {
  return (
    <div className="argumentation-controls">
      <div className="control-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showLabels}
            onChange={(e) => onShowLabelsChange(e.target.checked)}
          />
          Show Labels
        </label>
      </div>

      <div className="control-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={highlightLeading}
            onChange={(e) => onHighlightLeadingChange(e.target.checked)}
          />
          Highlight Leading Hypothesis
        </label>
      </div>

      <div className="control-info">
        <Icon name="Info" size={14} />
        <p>Argumentation graphs show how evidence supports or attacks hypotheses from ACH matrices.</p>
      </div>
    </div>
  );
}
