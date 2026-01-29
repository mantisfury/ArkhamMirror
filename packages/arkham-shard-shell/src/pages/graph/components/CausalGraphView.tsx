/**
 * CausalGraphView - Visualize and analyze causal graphs
 *
 * Features:
 * - DAG validation with cycle detection
 * - Causal path visualization
 * - Intervention simulation (do-calculus)
 * - Confounder identification
 * - Directed arrows showing causation
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import { Icon } from '../../../components/common/Icon';
import { apiGet, apiPost } from '../../../utils/api';

// Types
export interface CausalNode {
  id: string;
  label: string;
  description: string;
  states: string[];
  observed_state: string | null;
  prior_probability: number | null;
  is_intervention: boolean;
  node_type: string;  // variable, treatment, outcome, confounder
}

export interface CausalEdge {
  cause: string;
  effect: string;
  strength: number;
  edge_type: string;
  confidence: number;
  mechanism: string;
}

export interface CausalGraphData {
  id: string;
  name: string;
  description: string;
  is_valid_dag: boolean;
  cycles: string[][];
  causal_ordering: string[];
  nodes: CausalNode[];
  edges: CausalEdge[];
  summary: {
    node_count: number;
    edge_count: number;
    has_cycles: boolean;
  };
}

export interface CausalPath {
  nodes: string[];
  path_type: string;
  total_strength: number;
  length: number;
}

export interface ConfounderInfo {
  id: string;
  label: string;
  affects_treatment: boolean;
  affects_outcome: boolean;
  path_to_treatment: string[];
  path_to_outcome: string[];
}

export interface InterventionResult {
  intervention: { node: string; value: string };
  target: string;
  estimated_effect: number;
  confidence_interval: [number, number] | null;
  confounders_adjusted: string[];
  causal_paths: Array<{ nodes: string[]; strength: number }>;
  explanation: string;
}

export interface CausalGraphViewProps {
  projectId: string;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (cause: string, effect: string) => void;
  width?: number;
  height?: number;
}

interface NodePosition {
  id: string;
  x: number;
  y: number;
  node: CausalNode;
}

export function CausalGraphView({
  projectId,
  onNodeClick,
  onEdgeClick,
  width = 900,
  height = 600,
}: CausalGraphViewProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<CausalGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Intervention state
  const [selectedTreatment, setSelectedTreatment] = useState<string | null>(null);
  const [selectedOutcome, setSelectedOutcome] = useState<string | null>(null);
  const [interventionResult, setInterventionResult] = useState<InterventionResult | null>(null);
  const [confounders, setConfounders] = useState<ConfounderInfo[]>([]);
  const [highlightedPaths, setHighlightedPaths] = useState<string[][]>([]);

  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    content: React.ReactNode;
  }>({ visible: false, x: 0, y: 0, content: null });

  // Fetch causal graph
  useEffect(() => {
    async function fetchCausalGraph() {
      setLoading(true);
      setError(null);
      try {
        const result = await apiPost<any>(`/api/graph/causal/${projectId}`, {});
        if (result.success) {
          setData(result.causal_graph);
        } else {
          setError(result.error || 'Failed to build causal graph');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchCausalGraph();
  }, [projectId]);

  // Calculate positions - use grid layout for large graphs
  const positions = useMemo(() => {
    if (!data) return [];

    const positions: NodePosition[] = [];
    const nodeCount = data.nodes.length;

    // For large graphs (>50 nodes), always use grid layout
    // Otherwise try to use causal ordering if it makes sense
    const useGridLayout = nodeCount > 50 || data.causal_ordering.length === nodeCount;

    // Calculate grid dimensions for proper spacing
    const cols = Math.ceil(Math.sqrt(nodeCount));
    const rows = Math.ceil(nodeCount / cols);
    const nodeSpacing = 80; // Fixed spacing between nodes

    // Calculate actual canvas size needed (allow scrolling)
    const canvasWidth = Math.max(width, cols * nodeSpacing + 160);
    const canvasHeight = Math.max(height, rows * nodeSpacing + 120);
    const margin = { top: 60, bottom: 60, left: 80, right: 80 };

    if (useGridLayout) {
      // Grid layout for large graphs - better visibility
      const nodeMap = new Map(data.nodes.map(n => [n.id, n]));
      const ordering = data.causal_ordering.length > 0 ? data.causal_ordering : data.nodes.map(n => n.id);

      ordering.forEach((nodeId, i) => {
        const node = nodeMap.get(nodeId);
        if (!node) return;

        const row = Math.floor(i / cols);
        const col = i % cols;
        positions.push({
          id: node.id,
          x: margin.left + col * nodeSpacing + nodeSpacing / 2,
          y: margin.top + row * nodeSpacing + nodeSpacing / 2,
          node,
        });
      });
    } else {
      // Layered layout for smaller graphs with meaningful ordering
      const layerSpacing = (canvasHeight - margin.top - margin.bottom) / Math.max(data.causal_ordering.length - 1, 1);
      const nodeMap = new Map(data.nodes.map(n => [n.id, n]));

      // Group nodes by their position in ordering
      const layers: Map<number, CausalNode[]> = new Map();
      data.causal_ordering.forEach((nodeId, layerIndex) => {
        const node = nodeMap.get(nodeId);
        if (node) {
          if (!layers.has(layerIndex)) layers.set(layerIndex, []);
          layers.get(layerIndex)!.push(node);
        }
      });

      layers.forEach((layerNodes, layerIndex) => {
        const nodeSpacingH = (canvasWidth - margin.left - margin.right) / Math.max(layerNodes.length, 1);
        layerNodes.forEach((node, nodeIndex) => {
          positions.push({
            id: node.id,
            x: margin.left + (nodeIndex + 0.5) * nodeSpacingH,
            y: margin.top + layerIndex * layerSpacing,
            node,
          });
        });
      });
    }

    return positions;
  }, [data, width, height]);

  // Run intervention analysis
  const runIntervention = useCallback(async () => {
    if (!selectedTreatment || !selectedOutcome) return;

    try {
      // Get confounders
      const confResult = await apiGet<any>(
        `/api/graph/causal/${projectId}/confounders?treatment=${selectedTreatment}&outcome=${selectedOutcome}`
      );
      if (confResult.success) {
        setConfounders(confResult.confounders);
      }

      // Run intervention
      const intResult = await apiPost<any>(`/api/graph/causal/${projectId}/intervention`, {
        intervention_node: selectedTreatment,
        intervention_value: 'true',
        target_node: selectedOutcome,
      });
      if (intResult.success) {
        setInterventionResult(intResult);
        // Highlight causal paths
        const paths = intResult.causal_paths.map((p: { nodes: string[] }) => p.nodes);
        setHighlightedPaths(paths);
      }
    } catch (err) {
      console.error('Error running intervention:', err);
    }
  }, [projectId, selectedTreatment, selectedOutcome]);

  // Render D3 visualization with zoom support
  useEffect(() => {
    if (!svgRef.current || !data || positions.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const positionMap = new Map(positions.map(p => [p.id, p]));

    // Calculate required canvas size
    const nodeCount = data.nodes.length;
    const cols = Math.ceil(Math.sqrt(nodeCount));
    const rows = Math.ceil(nodeCount / cols);
    const nodeSpacing = 80;
    const canvasWidth = Math.max(width, cols * nodeSpacing + 200);
    const canvasHeight = Math.max(height, rows * nodeSpacing + 200);

    // Create main container group for zoom/pan
    const container = svg.append('g').attr('class', 'container');

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Fit to view initially if many nodes
    if (nodeCount > 30) {
      const scale = Math.min(width / canvasWidth, height / canvasHeight) * 0.9;
      const initialTransform = d3.zoomIdentity
        .translate(width / 2 - canvasWidth * scale / 2, 20)
        .scale(scale);
      svg.call(zoom.transform, initialTransform);
    }

    // Check if edge is on highlighted path
    const isEdgeHighlighted = (cause: string, effect: string): boolean => {
      return highlightedPaths.some(path => {
        for (let i = 0; i < path.length - 1; i++) {
          if (path[i] === cause && path[i + 1] === effect) return true;
        }
        return false;
      });
    };

    // Create arrow marker
    const defs = container.append('defs');
    defs.append('marker')
      .attr('id', 'arrow-causal')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#64748b');

    defs.append('marker')
      .attr('id', 'arrow-causal-highlight')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#3b82f6');

    // Draw edges
    const edgeGroup = container.append('g').attr('class', 'edges');

    data.edges.forEach(edge => {
      const sourcePos = positionMap.get(edge.cause);
      const targetPos = positionMap.get(edge.effect);

      if (!sourcePos || !targetPos) return;

      const highlighted = isEdgeHighlighted(edge.cause, edge.effect);
      const strokeWidth = Math.max(1.5, Math.min(4, edge.strength * 3));

      edgeGroup.append('line')
        .attr('x1', sourcePos.x)
        .attr('y1', sourcePos.y)
        .attr('x2', targetPos.x)
        .attr('y2', targetPos.y)
        .attr('stroke', highlighted ? '#3b82f6' : '#64748b')
        .attr('stroke-width', highlighted ? strokeWidth + 1 : strokeWidth)
        .attr('stroke-opacity', highlighted ? 1 : 0.5)
        .attr('marker-end', highlighted ? 'url(#arrow-causal-highlight)' : 'url(#arrow-causal)')
        .attr('cursor', 'pointer')
        .on('click', () => onEdgeClick?.(edge.cause, edge.effect))
        .on('mouseenter', (event) => {
          setTooltip({
            visible: true,
            x: event.clientX + 10,
            y: event.clientY + 10,
            content: (
              <div>
                <div style={{ fontWeight: 600 }}>{edge.cause} → {edge.effect}</div>
                <div>Strength: {(edge.strength * 100).toFixed(0)}%</div>
                <div>Confidence: {(edge.confidence * 100).toFixed(0)}%</div>
                {edge.mechanism && <div style={{ fontSize: '0.7rem', marginTop: 4 }}>{edge.mechanism}</div>}
              </div>
            ),
          });
        })
        .on('mouseleave', () => setTooltip(prev => ({ ...prev, visible: false })));
    });

    // Draw nodes
    const nodeGroup = container.append('g').attr('class', 'nodes');

    positions.forEach(pos => {
      const isConfounder = confounders.some(c => c.id === pos.node.id);
      const isTreatment = pos.node.id === selectedTreatment;
      const isOutcome = pos.node.id === selectedOutcome;
      const isIntervention = pos.node.is_intervention;

      // Determine node color
      let fillColor = '#64748b';
      if (isTreatment) fillColor = '#22c55e';
      else if (isOutcome) fillColor = '#ef4444';
      else if (isConfounder) fillColor = '#f59e0b';
      else if (isIntervention) fillColor = '#8b5cf6';

      const nodeSize = 16;
      const g = nodeGroup.append('g')
        .attr('transform', `translate(${pos.x}, ${pos.y})`)
        .attr('cursor', 'pointer')
        .on('click', () => {
          onNodeClick?.(pos.node.id);
          // Toggle selection
          if (!selectedTreatment) {
            setSelectedTreatment(pos.node.id);
          } else if (!selectedOutcome && pos.node.id !== selectedTreatment) {
            setSelectedOutcome(pos.node.id);
          } else {
            setSelectedTreatment(null);
            setSelectedOutcome(null);
            setInterventionResult(null);
            setConfounders([]);
            setHighlightedPaths([]);
          }
        })
        .on('mouseenter', (event) => {
          setTooltip({
            visible: true,
            x: event.clientX + 10,
            y: event.clientY + 10,
            content: (
              <div>
                <div style={{ fontWeight: 600 }}>{pos.node.label}</div>
                <div style={{ fontSize: '0.7rem', color: '#888' }}>{pos.node.node_type}</div>
                {pos.node.states.length > 0 && (
                  <div>States: {pos.node.states.join(', ')}</div>
                )}
                {pos.node.observed_state && (
                  <div>Observed: {pos.node.observed_state}</div>
                )}
                {pos.node.description && (
                  <div style={{ marginTop: 4, fontSize: '0.7rem' }}>{pos.node.description}</div>
                )}
              </div>
            ),
          });
        })
        .on('mouseleave', () => setTooltip(prev => ({ ...prev, visible: false })));

      // Node shape (circle for variables)
      g.append('circle')
        .attr('r', nodeSize)
        .attr('fill', fillColor)
        .attr('stroke', isTreatment || isOutcome ? '#fff' : 'none')
        .attr('stroke-width', 3);

      // Selection ring
      if (isTreatment || isOutcome) {
        g.append('circle')
          .attr('r', nodeSize + 4)
          .attr('fill', 'none')
          .attr('stroke', fillColor)
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '4,2');
      }

      // Label
      g.append('text')
        .attr('y', nodeSize + 14)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10)
        .attr('fill', 'var(--text-primary)')
        .text(pos.node.label.length > 15 ? pos.node.label.slice(0, 15) + '...' : pos.node.label);
    });

    // DAG validation warning
    if (!data.is_valid_dag && data.cycles.length > 0) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('font-size', 12)
        .attr('fill', '#ef4444')
        .attr('font-weight', 600)
        .text('⚠ Graph contains cycles - not a valid DAG');
    }

  }, [data, positions, width, height, highlightedPaths, confounders, selectedTreatment, selectedOutcome, onNodeClick, onEdgeClick]);

  // Run intervention when both nodes selected
  useEffect(() => {
    if (selectedTreatment && selectedOutcome) {
      runIntervention();
    }
  }, [selectedTreatment, selectedOutcome, runIntervention]);

  // Empty state
  if (!loading && !data && !error) {
    return (
      <div className="causal-empty">
        <Icon name="GitBranch" size={48} />
        <h3>No Causal Graph</h3>
        <p>Build a graph to analyze causal relationships between entities.</p>
      </div>
    );
  }

  return (
    <div className="causal-view">
      {/* Header */}
      <div className="causal-header">
        <div className="causal-info">
          {data && (
            <>
              <span className={`dag-status ${data.is_valid_dag ? 'valid' : 'invalid'}`}>
                <Icon name={data.is_valid_dag ? 'Check' : 'AlertTriangle'} size={14} />
                {data.is_valid_dag ? 'Valid DAG' : 'Contains Cycles'}
              </span>
              <span>{data.summary.node_count} variables</span>
              <span>{data.summary.edge_count} causal links</span>
            </>
          )}
        </div>

        <div className="causal-selection">
          {selectedTreatment ? (
            <span className="selection-badge treatment">
              Treatment: {selectedTreatment}
            </span>
          ) : (
            <span className="selection-hint">Click node to set treatment</span>
          )}
          {selectedOutcome && (
            <span className="selection-badge outcome">
              Outcome: {selectedOutcome}
            </span>
          )}
          {(selectedTreatment || selectedOutcome) && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => {
                setSelectedTreatment(null);
                setSelectedOutcome(null);
                setInterventionResult(null);
                setConfounders([]);
                setHighlightedPaths([]);
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="causal-content">
        {/* Canvas */}
        <div className="causal-canvas">
          {loading ? (
            <div className="causal-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Building causal graph...</span>
            </div>
          ) : error ? (
            <div className="causal-error">
              <Icon name="AlertCircle" size={32} />
              <span>{error}</span>
            </div>
          ) : (
            <svg ref={svgRef} width={width} height={height} className="causal-svg" />
          )}
        </div>

        {/* Intervention Results Panel */}
        {interventionResult && (
          <div className="intervention-panel">
            <h4>
              <Icon name="Zap" size={16} />
              Intervention Analysis
            </h4>
            <div className="intervention-result">
              <div className="intervention-formula">
                do({interventionResult.intervention.node} = {interventionResult.intervention.value})
                → {interventionResult.target}
              </div>
              <div className="effect-display">
                <span className="effect-label">Estimated Effect:</span>
                <span className="effect-value">
                  {(interventionResult.estimated_effect * 100).toFixed(1)}%
                </span>
              </div>
              {interventionResult.confidence_interval && (
                <div className="confidence-interval">
                  95% CI: [{(interventionResult.confidence_interval[0] * 100).toFixed(1)}% -
                  {(interventionResult.confidence_interval[1] * 100).toFixed(1)}%]
                </div>
              )}
              {confounders.length > 0 && (
                <div className="confounders-list">
                  <span className="label">Confounders:</span>
                  {confounders.map(c => (
                    <span key={c.id} className="confounder-badge">{c.label}</span>
                  ))}
                </div>
              )}
              <div className="paths-info">
                {interventionResult.causal_paths.length} causal path(s) found
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="causal-legend">
        <div className="legend-item">
          <span className="legend-circle treatment" />
          <span>Treatment</span>
        </div>
        <div className="legend-item">
          <span className="legend-circle outcome" />
          <span>Outcome</span>
        </div>
        <div className="legend-item">
          <span className="legend-circle confounder" />
          <span>Confounder</span>
        </div>
        <div className="legend-item">
          <span className="legend-circle variable" />
          <span>Variable</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" />
          <span>Causes</span>
        </div>
      </div>

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="causal-tooltip"
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
 * Controls for CausalGraphView
 */
export interface CausalGraphControlsProps {
  showLabels: boolean;
  onShowLabelsChange: (show: boolean) => void;
  showStrength: boolean;
  onShowStrengthChange: (show: boolean) => void;
}

export function CausalGraphControls({
  showLabels,
  onShowLabelsChange,
  showStrength,
  onShowStrengthChange,
}: CausalGraphControlsProps) {
  return (
    <div className="causal-controls">
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
            checked={showStrength}
            onChange={(e) => onShowStrengthChange(e.target.checked)}
          />
          Show Strength
        </label>
      </div>

      <div className="control-info">
        <Icon name="Info" size={14} />
        <div>
          <p><strong>To analyze causation:</strong></p>
          <p>1. Click a node to set as Treatment</p>
          <p>2. Click another to set as Outcome</p>
          <p>3. View intervention effect estimate</p>
        </div>
      </div>
    </div>
  );
}
