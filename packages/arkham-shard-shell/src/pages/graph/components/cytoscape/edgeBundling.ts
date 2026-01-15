/**
 * Edge Bundling Utilities for Cytoscape.js
 *
 * This module handles detection and styling of multi-edges (parallel edges between
 * the same node pairs). Essential for dense OSINT graphs where entities may have
 * multiple relationship types (e.g., "works_for" AND "communicated_with").
 */

import type { Core, EdgeSingular } from 'cytoscape';

/**
 * Detect and classify multi-edges (parallel edges between same node pairs).
 * Applies CSS classes to enable distinct visual styling for each parallel edge.
 *
 * The function groups edges by their source-target pair (undirected), then
 * applies appropriate classes:
 * - multi-edge: First edge in a parallel set (curves one direction)
 * - multi-edge-2: Second edge (curves opposite direction)
 * - multi-edge-3: Third+ edges (curves further out)
 *
 * @param cy - The Cytoscape instance to process
 */
export function applyEdgeBundling(cy: Core): void {
  // Group edges by their source-target pair (undirected)
  const edgeGroups = new Map<string, EdgeSingular[]>();

  cy.edges().forEach((edge) => {
    const sourceId = edge.source().id();
    const targetId = edge.target().id();

    // Create undirected key (smaller id first for consistency)
    const key = sourceId < targetId
      ? `${sourceId}|${targetId}`
      : `${targetId}|${sourceId}`;

    if (!edgeGroups.has(key)) {
      edgeGroups.set(key, []);
    }
    edgeGroups.get(key)!.push(edge);
  });

  // Apply classes to multi-edges within a batch for performance
  cy.batch(() => {
    edgeGroups.forEach((edges) => {
      if (edges.length === 1) {
        // Single edge - remove any multi-edge classes, use default bezier
        edges[0].removeClass('multi-edge multi-edge-2 multi-edge-3 multi-edge-4');
      } else {
        // Multiple edges - curve them away from each other
        edges.forEach((edge, index) => {
          // Clear existing multi-edge classes first
          edge.removeClass('multi-edge multi-edge-2 multi-edge-3 multi-edge-4');

          // Apply appropriate class based on position in the group
          switch (index) {
            case 0:
              edge.addClass('multi-edge');
              break;
            case 1:
              edge.addClass('multi-edge-2');
              break;
            case 2:
              edge.addClass('multi-edge-3');
              break;
            default:
              // For 4+ edges, use the furthest curve class
              edge.addClass('multi-edge-4');
              break;
          }
        });
      }
    });
  });
}

/**
 * Remove all edge bundling classes from the graph.
 * Useful when resetting the graph or before reapplying bundling.
 *
 * @param cy - The Cytoscape instance to process
 */
export function clearEdgeBundling(cy: Core): void {
  cy.batch(() => {
    cy.edges().removeClass('multi-edge multi-edge-2 multi-edge-3 multi-edge-4');
  });
}

/**
 * Calculate adaptive curve distance based on graph density.
 * Denser graphs need tighter curves to avoid visual chaos, while sparse
 * graphs can use wider curves for better readability.
 *
 * Graph density is calculated as: edges / (nodes * (nodes - 1) / 2)
 * This represents the ratio of actual edges to maximum possible edges.
 *
 * @param nodeCount - Number of nodes in the graph
 * @param edgeCount - Number of edges in the graph
 * @returns Recommended curve control point distance in pixels
 */
export function calculateCurveDistance(
  nodeCount: number,
  edgeCount: number
): number {
  // Avoid division by zero for tiny graphs
  if (nodeCount < 2) return 40;

  // Calculate graph density (0 to 1 scale)
  const maxPossibleEdges = (nodeCount * (nodeCount - 1)) / 2;
  const density = maxPossibleEdges > 0 ? edgeCount / maxPossibleEdges : 0;

  // Return tighter curves for denser graphs
  if (density > 0.3) return 25;    // Very dense: tight curves
  if (density > 0.15) return 35;   // Moderately dense
  if (density > 0.05) return 45;   // Average density
  return 55;                        // Sparse: wider curves for clarity
}

/**
 * Get statistics about multi-edges in the graph.
 * Useful for displaying info to users or making layout decisions.
 *
 * @param cy - The Cytoscape instance to analyze
 * @returns Object containing multi-edge statistics
 */
export function getMultiEdgeStats(cy: Core): {
  totalEdges: number;
  uniquePairs: number;
  multiEdgePairs: number;
  maxParallelEdges: number;
  selfLoops: number;
} {
  const edgeGroups = new Map<string, number>();
  let selfLoops = 0;

  cy.edges().forEach((edge) => {
    const sourceId = edge.source().id();
    const targetId = edge.target().id();

    // Count self-loops separately
    if (sourceId === targetId) {
      selfLoops++;
      return;
    }

    // Create undirected key
    const key = sourceId < targetId
      ? `${sourceId}|${targetId}`
      : `${targetId}|${sourceId}`;

    edgeGroups.set(key, (edgeGroups.get(key) || 0) + 1);
  });

  const counts = Array.from(edgeGroups.values());
  const multiEdgePairs = counts.filter(c => c > 1).length;
  const maxParallelEdges = counts.length > 0 ? Math.max(...counts) : 0;

  return {
    totalEdges: cy.edges().length,
    uniquePairs: edgeGroups.size,
    multiEdgePairs,
    maxParallelEdges,
    selfLoops,
  };
}

/**
 * Generate stylesheet entries for multi-edge styling.
 * Returns an array of Cytoscape stylesheet objects that can be merged
 * with the main stylesheet.
 *
 * @param curveDistance - Base distance for curve control points
 * @returns Array of stylesheet entries for multi-edge styling
 */
export function getMultiEdgeStylesheet(curveDistance: number = 40) {
  return [
    // Multi-edge handling (multiple edges between same node pair)
    // Use unbundled-bezier to curve parallel edges away from each other
    {
      selector: 'edge.multi-edge',
      style: {
        'curve-style': 'unbundled-bezier' as const,
        'control-point-distances': [curveDistance],
        'control-point-weights': [0.5],
      },
    },

    // Second parallel edge curves opposite direction
    {
      selector: 'edge.multi-edge-2',
      style: {
        'curve-style': 'unbundled-bezier' as const,
        'control-point-distances': [-curveDistance],
        'control-point-weights': [0.5],
      },
    },

    // Third parallel edge (curves further out)
    {
      selector: 'edge.multi-edge-3',
      style: {
        'curve-style': 'unbundled-bezier' as const,
        'control-point-distances': [curveDistance * 2],
        'control-point-weights': [0.5],
      },
    },

    // Fourth+ parallel edges
    {
      selector: 'edge.multi-edge-4',
      style: {
        'curve-style': 'unbundled-bezier' as const,
        'control-point-distances': [-curveDistance * 2],
        'control-point-weights': [0.5],
      },
    },

    // Self-loops (entity references itself)
    {
      selector: 'edge[source = target]',
      style: {
        'curve-style': 'bezier' as const,
        'loop-direction': '45deg',
        'loop-sweep': '-90deg',
        'control-point-step-size': 50,
      },
    },
  ];
}
