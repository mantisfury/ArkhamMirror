/**
 * AssociationMatrix - Grid-based visualization of entity relationships
 *
 * Displays relationships as a heat map matrix where:
 * - Rows and columns represent entities (or documents/entities in bipartite mode)
 * - Cell color intensity indicates relationship strength
 * - Supports sorting, filtering, and interaction with the main graph
 */

import { useRef, useEffect, useMemo, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { Icon } from '../../../components/common/Icon';

interface MatrixNode {
  id: string;
  label: string;
  type: string;
  degree?: number;
}

interface MatrixEdge {
  source: string;
  target: string;
  weight: number;
  type?: string;
}

export interface AssociationMatrixProps {
  nodes: MatrixNode[];
  edges: MatrixEdge[];
  rowEntityType?: string;
  colEntityType?: string;
  sortBy: 'alphabetical' | 'degree' | 'cluster' | 'type';
  colorScale: 'linear' | 'log' | 'sqrt';
  showLabels: boolean;
  cellSize: number;
  onCellClick?: (rowId: string, colId: string, weight: number) => void;
  onNodeClick?: (nodeId: string) => void;
  highlightedNodes?: Set<string>;
  bipartiteMode?: boolean;
  bipartiteRowType?: string;
  bipartiteColType?: string;
}

// Entity type colors for row/column headers
const TYPE_COLORS: Record<string, string> = {
  person: '#4299e1',
  organization: '#48bb78',
  location: '#ed8936',
  event: '#9f7aea',
  document: '#f56565',
  claim: '#f59e0b',
  evidence: '#3b82f6',
  hypothesis: '#8b5cf6',
  default: '#718096',
};

export function AssociationMatrix({
  nodes,
  edges,
  rowEntityType,
  colEntityType,
  sortBy = 'degree',
  colorScale = 'sqrt',
  showLabels = true,
  cellSize = 20,
  onCellClick,
  onNodeClick,
  highlightedNodes,
  bipartiteMode = false,
  bipartiteRowType,
  bipartiteColType,
}: AssociationMatrixProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    content: string;
  }>({ visible: false, x: 0, y: 0, content: '' });

  // Build adjacency matrix data
  const matrixData = useMemo(() => {
    // Filter nodes based on entity types
    let rowNodes = nodes;
    let colNodes = nodes;

    if (bipartiteMode && bipartiteRowType && bipartiteColType) {
      rowNodes = nodes.filter(n => n.type?.toLowerCase() === bipartiteRowType.toLowerCase());
      colNodes = nodes.filter(n => n.type?.toLowerCase() === bipartiteColType.toLowerCase());
    } else {
      if (rowEntityType) {
        rowNodes = nodes.filter(n => n.type?.toLowerCase() === rowEntityType.toLowerCase());
      }
      if (colEntityType) {
        colNodes = nodes.filter(n => n.type?.toLowerCase() === colEntityType.toLowerCase());
      }
    }

    // Sort nodes
    const sortNodes = (nodeList: MatrixNode[]) => {
      switch (sortBy) {
        case 'alphabetical':
          return [...nodeList].sort((a, b) => a.label.localeCompare(b.label));
        case 'degree':
          return [...nodeList].sort((a, b) => (b.degree || 0) - (a.degree || 0));
        case 'type':
          return [...nodeList].sort((a, b) => a.type.localeCompare(b.type) || a.label.localeCompare(b.label));
        case 'cluster':
          // Group by type, then by degree within type
          return [...nodeList].sort((a, b) => {
            const typeCompare = a.type.localeCompare(b.type);
            if (typeCompare !== 0) return typeCompare;
            return (b.degree || 0) - (a.degree || 0);
          });
        default:
          return nodeList;
      }
    };

    const sortedRows = sortNodes(rowNodes);
    const sortedCols = bipartiteMode ? sortNodes(colNodes) : sortedRows;

    // Build edge lookup for fast access
    // Note: d3-force mutates links, so source/target may be objects or strings
    const edgeMap = new Map<string, number>();
    edges.forEach(edge => {
      // Handle both string IDs and object references (d3-force mutates links)
      const sourceId = typeof edge.source === 'string' ? edge.source : (edge.source as any)?.id;
      const targetId = typeof edge.target === 'string' ? edge.target : (edge.target as any)?.id;

      if (!sourceId || !targetId) return;

      // Store both directions for undirected graph
      const key1 = `${sourceId}|${targetId}`;
      const key2 = `${targetId}|${sourceId}`;
      edgeMap.set(key1, edge.weight);
      edgeMap.set(key2, edge.weight);
    });

    // Build matrix cells
    const cells: Array<{
      row: number;
      col: number;
      rowId: string;
      colId: string;
      rowLabel: string;
      colLabel: string;
      weight: number;
    }> = [];

    let maxWeight = 0;

    sortedRows.forEach((rowNode, rowIdx) => {
      sortedCols.forEach((colNode, colIdx) => {
        if (!bipartiteMode && rowNode.id === colNode.id) {
          // Skip diagonal in non-bipartite mode
          return;
        }

        const key = `${rowNode.id}|${colNode.id}`;
        const weight = edgeMap.get(key) || 0;

        if (weight > 0) {
          maxWeight = Math.max(maxWeight, weight);
          cells.push({
            row: rowIdx,
            col: colIdx,
            rowId: rowNode.id,
            colId: colNode.id,
            rowLabel: rowNode.label,
            colLabel: colNode.label,
            weight,
          });
        }
      });
    });

    return {
      rows: sortedRows,
      cols: sortedCols,
      cells,
      maxWeight,
    };
  }, [nodes, edges, rowEntityType, colEntityType, sortBy, bipartiteMode, bipartiteRowType, bipartiteColType]);

  // Create color scale
  const getColorScale = useCallback(() => {
    const { maxWeight } = matrixData;
    if (maxWeight === 0) return () => '#e2e8f0';

    const colorInterpolator = d3.interpolateBlues;

    switch (colorScale) {
      case 'log':
        return d3.scaleSequentialLog([1, maxWeight + 1], colorInterpolator);
      case 'sqrt':
        return d3.scaleSequentialSqrt([0, maxWeight], colorInterpolator);
      case 'linear':
      default:
        return d3.scaleSequential([0, maxWeight], colorInterpolator);
    }
  }, [matrixData, colorScale]);

  // Render matrix
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const { rows, cols, cells } = matrixData;
    if (rows.length === 0 || cols.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // Calculate dimensions
    const labelWidth = showLabels ? 120 : 0;
    const labelHeight = showLabels ? 100 : 0;
    const matrixWidth = cols.length * cellSize;
    const matrixHeight = rows.length * cellSize;
    const totalWidth = labelWidth + matrixWidth + 20;
    const totalHeight = labelHeight + matrixHeight + 20;

    svg
      .attr('width', totalWidth)
      .attr('height', totalHeight);

    const colorScaleFn = getColorScale();

    // Create main group with offset for labels
    const g = svg.append('g')
      .attr('transform', `translate(${labelWidth}, ${labelHeight})`);

    // Draw cells
    const cellGroup = g.append('g').attr('class', 'cells');

    cellGroup.selectAll('rect')
      .data(cells)
      .enter()
      .append('rect')
      .attr('x', d => d.col * cellSize)
      .attr('y', d => d.row * cellSize)
      .attr('width', cellSize - 1)
      .attr('height', cellSize - 1)
      .attr('fill', d => colorScaleFn(d.weight))
      .attr('rx', 2)
      .attr('class', d => {
        const classes = ['matrix-cell'];
        if (highlightedNodes?.has(d.rowId) || highlightedNodes?.has(d.colId)) {
          classes.push('highlighted');
        }
        return classes.join(' ');
      })
      .style('cursor', 'pointer')
      .on('mouseover', (event, d) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect) {
          setTooltip({
            visible: true,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top - 10,
            content: `${d.rowLabel} - ${d.colLabel}: ${d.weight.toFixed(2)}`,
          });
        }

        // Highlight row and column
        d3.selectAll('.row-label').classed('highlighted', (_, i) => i === d.row);
        d3.selectAll('.col-label').classed('highlighted', (_, i) => i === d.col);
      })
      .on('mouseout', () => {
        setTooltip(prev => ({ ...prev, visible: false }));
        d3.selectAll('.row-label, .col-label').classed('highlighted', false);
      })
      .on('click', (_, d) => {
        onCellClick?.(d.rowId, d.colId, d.weight);
      });

    // Draw row labels
    if (showLabels) {
      const rowLabelGroup = svg.append('g')
        .attr('class', 'row-labels')
        .attr('transform', `translate(${labelWidth - 5}, ${labelHeight})`);

      rowLabelGroup.selectAll('text')
        .data(rows)
        .enter()
        .append('text')
        .attr('class', 'row-label')
        .attr('x', 0)
        .attr('y', (_, i) => i * cellSize + cellSize / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'end')
        .attr('fill', d => TYPE_COLORS[d.type?.toLowerCase()] || TYPE_COLORS.default)
        .style('font-size', `${Math.min(cellSize - 2, 11)}px`)
        .style('cursor', 'pointer')
        .text(d => d.label.length > 15 ? d.label.slice(0, 14) + '...' : d.label)
        .on('click', (_, d) => onNodeClick?.(d.id))
        .append('title')
        .text(d => d.label);

      // Draw column labels (rotated)
      const colLabelGroup = svg.append('g')
        .attr('class', 'col-labels')
        .attr('transform', `translate(${labelWidth}, ${labelHeight - 5})`);

      colLabelGroup.selectAll('text')
        .data(cols)
        .enter()
        .append('text')
        .attr('class', 'col-label')
        .attr('x', 0)
        .attr('y', 0)
        .attr('transform', (_, i) => `translate(${i * cellSize + cellSize / 2}, 0) rotate(-45)`)
        .attr('text-anchor', 'start')
        .attr('fill', d => TYPE_COLORS[d.type?.toLowerCase()] || TYPE_COLORS.default)
        .style('font-size', `${Math.min(cellSize - 2, 11)}px`)
        .style('cursor', 'pointer')
        .text(d => d.label.length > 12 ? d.label.slice(0, 11) + '...' : d.label)
        .on('click', (_, d) => onNodeClick?.(d.id))
        .append('title')
        .text(d => d.label);
    }

    // Draw grid lines for better readability
    if (cellSize >= 15) {
      const gridGroup = g.append('g').attr('class', 'grid');

      // Horizontal grid lines
      gridGroup.selectAll('.h-line')
        .data(d3.range(rows.length + 1))
        .enter()
        .append('line')
        .attr('class', 'h-line')
        .attr('x1', 0)
        .attr('x2', matrixWidth)
        .attr('y1', d => d * cellSize)
        .attr('y2', d => d * cellSize)
        .attr('stroke', 'var(--border-color)')
        .attr('stroke-width', 0.5)
        .attr('stroke-opacity', 0.3);

      // Vertical grid lines
      gridGroup.selectAll('.v-line')
        .data(d3.range(cols.length + 1))
        .enter()
        .append('line')
        .attr('class', 'v-line')
        .attr('x1', d => d * cellSize)
        .attr('x2', d => d * cellSize)
        .attr('y1', 0)
        .attr('y2', matrixHeight)
        .attr('stroke', 'var(--border-color)')
        .attr('stroke-width', 0.5)
        .attr('stroke-opacity', 0.3);
    }

  }, [matrixData, cellSize, showLabels, getColorScale, highlightedNodes, onCellClick, onNodeClick]);

  // Calculate container dimensions
  const containerWidth = useMemo(() => {
    const labelWidth = showLabels ? 120 : 0;
    return labelWidth + matrixData.cols.length * cellSize + 40;
  }, [matrixData.cols.length, cellSize, showLabels]);

  const containerHeight = useMemo(() => {
    const labelHeight = showLabels ? 100 : 0;
    return labelHeight + matrixData.rows.length * cellSize + 40;
  }, [matrixData.rows.length, cellSize, showLabels]);

  if (nodes.length === 0) {
    return (
      <div className="matrix-empty">
        <Icon name="Grid3X3" size={48} />
        <p>No data available for matrix view</p>
      </div>
    );
  }

  if (matrixData.rows.length === 0 || matrixData.cols.length === 0) {
    return (
      <div className="matrix-empty">
        <Icon name="Grid3X3" size={48} />
        <p>No entities match the selected filters</p>
      </div>
    );
  }

  return (
    <div className="association-matrix" ref={containerRef}>
      <div
        className="matrix-scroll-container"
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          overflow: 'auto',
        }}
      >
        <svg
          ref={svgRef}
          style={{
            minWidth: containerWidth,
            minHeight: containerHeight,
          }}
        />
      </div>

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="matrix-tooltip"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend */}
      <div className="matrix-legend">
        <span className="legend-label">Weak</span>
        <div className="legend-gradient" />
        <span className="legend-label">Strong</span>
      </div>

      {/* Stats */}
      <div className="matrix-stats">
        <span>{matrixData.rows.length} rows</span>
        <span>{matrixData.cols.length} cols</span>
        <span>{matrixData.cells.length} connections</span>
      </div>
    </div>
  );
}

/**
 * Matrix Controls component for configuring the matrix view
 */
interface MatrixControlsProps {
  sortBy: 'alphabetical' | 'degree' | 'cluster' | 'type';
  onSortByChange: (sortBy: 'alphabetical' | 'degree' | 'cluster' | 'type') => void;
  colorScale: 'linear' | 'log' | 'sqrt';
  onColorScaleChange: (scale: 'linear' | 'log' | 'sqrt') => void;
  cellSize: number;
  onCellSizeChange: (size: number) => void;
  showLabels: boolean;
  onShowLabelsChange: (show: boolean) => void;
  entityTypes: string[];
  rowEntityType: string;
  onRowEntityTypeChange: (type: string) => void;
  colEntityType: string;
  onColEntityTypeChange: (type: string) => void;
  bipartiteMode: boolean;
  onBipartiteModeChange: (enabled: boolean) => void;
}

export function MatrixControls({
  sortBy,
  onSortByChange,
  colorScale,
  onColorScaleChange,
  cellSize,
  onCellSizeChange,
  showLabels,
  onShowLabelsChange,
  entityTypes,
  rowEntityType,
  onRowEntityTypeChange,
  colEntityType,
  onColEntityTypeChange,
  bipartiteMode,
  onBipartiteModeChange,
}: MatrixControlsProps) {
  return (
    <div className="matrix-controls">
      <div className="control-group">
        <label>Sort By</label>
        <select
          value={sortBy}
          onChange={(e) => onSortByChange(e.target.value as typeof sortBy)}
        >
          <option value="degree">Degree</option>
          <option value="alphabetical">Alphabetical</option>
          <option value="type">Entity Type</option>
          <option value="cluster">Clustered</option>
        </select>
      </div>

      <div className="control-group">
        <label>Color Scale</label>
        <select
          value={colorScale}
          onChange={(e) => onColorScaleChange(e.target.value as typeof colorScale)}
        >
          <option value="sqrt">Square Root</option>
          <option value="linear">Linear</option>
          <option value="log">Logarithmic</option>
        </select>
      </div>

      <div className="control-group">
        <label>Cell Size: {cellSize}px</label>
        <input
          type="range"
          min={10}
          max={40}
          value={cellSize}
          onChange={(e) => onCellSizeChange(Number(e.target.value))}
        />
      </div>

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
            checked={bipartiteMode}
            onChange={(e) => onBipartiteModeChange(e.target.checked)}
          />
          Bipartite Mode
        </label>
      </div>

      {bipartiteMode ? (
        <>
          <div className="control-group">
            <label>Row Type</label>
            <select
              value={rowEntityType}
              onChange={(e) => onRowEntityTypeChange(e.target.value)}
            >
              <option value="">All Types</option>
              {entityTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label>Column Type</label>
            <select
              value={colEntityType}
              onChange={(e) => onColEntityTypeChange(e.target.value)}
            >
              <option value="">All Types</option>
              {entityTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </>
      ) : (
        <div className="control-group">
          <label>Filter Type</label>
          <select
            value={rowEntityType}
            onChange={(e) => {
              onRowEntityTypeChange(e.target.value);
              onColEntityTypeChange(e.target.value);
            }}
          >
            <option value="">All Types</option>
            {entityTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
