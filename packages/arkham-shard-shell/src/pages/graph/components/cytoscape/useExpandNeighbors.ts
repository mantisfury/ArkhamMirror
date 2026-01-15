/**
 * Progressive Disclosure / Expand Neighbors Hook for Cytoscape.js
 *
 * The core OSINT workflow: start with a single entity (or small set of seed nodes),
 * then progressively expand the network to discover connections. This hook manages
 * expansion state, tracks depth from seed nodes, and handles the visual animation
 * of new nodes appearing in the graph.
 */

import { useState, useCallback, useRef } from 'react';
import type { Core, NodeSingular, EdgeSingular, Position } from 'cytoscape';

/**
 * Represents a node in the graph
 */
export interface GraphNode {
  id: string;
  label: string;
  type?: string;
  entity_type?: string;
  degree?: number;
  document_count?: number;
  [key: string]: unknown;
}

/**
 * Represents an edge in the graph
 */
export interface GraphEdge {
  source: string | { id: string };
  target: string | { id: string };
  relationship_type?: string;
  type?: string;
  weight?: number;
  [key: string]: unknown;
}

/**
 * State tracking for node expansion
 */
export interface ExpandState {
  /** Set of node IDs that have been expanded (their neighbors fetched) */
  expandedNodes: Set<string>;
  /** Map of node ID to expansion depth (hops from nearest seed node) */
  expansionDepth: Map<string, number>;
  /** Set of original query/seed node IDs */
  seedNodes: Set<string>;
  /** Maximum depth reached in the current expansion */
  maxDepth: number;
}

/**
 * Options for the useExpandNeighbors hook
 */
export interface ExpandNeighborsOptions {
  /**
   * Callback to fetch neighbors for a given node from the backend.
   * Should return the neighboring nodes and edges.
   */
  onFetchNeighbors: (nodeId: string) => Promise<{
    nodes: GraphNode[];
    edges: GraphEdge[];
  }>;
  /** Maximum expansion depth allowed (default: 3) */
  maxExpandDepth?: number;
  /** Whether to animate new nodes appearing (default: true) */
  animateExpansion?: boolean;
  /** Animation duration in milliseconds (default: 500) */
  animationDuration?: number;
}

/**
 * Return type for the useExpandNeighbors hook
 */
export interface UseExpandNeighborsReturn {
  /** Current expansion state */
  expandState: ExpandState;
  /** Whether an expansion operation is in progress */
  isExpanding: boolean;
  /** Mark initial seed nodes (from original query) */
  setSeedNodes: (nodeIds: string[]) => void;
  /** Expand a node's neighbors */
  expandNode: (nodeId: string) => Promise<void>;
  /** Collapse a node (hide expanded neighbors) */
  collapseNode: (nodeId: string) => void;
  /** Check if a node can be expanded */
  canExpand: (nodeId: string) => boolean;
  /** Get expansion indicator for a node */
  getExpansionIndicator: (nodeId: string) => 'expandable' | 'expanded' | 'max-depth' | 'seed';
  /** Reset all expansion state */
  resetExpansion: () => void;
  /** Get all nodes at a specific depth */
  getNodesAtDepth: (depth: number) => string[];
}

/**
 * Initial empty expansion state
 */
const INITIAL_EXPAND_STATE: ExpandState = {
  expandedNodes: new Set<string>(),
  expansionDepth: new Map<string, number>(),
  seedNodes: new Set<string>(),
  maxDepth: 0,
};

/**
 * Hook for managing progressive disclosure / expand neighbors workflow.
 *
 * @param cy - Cytoscape Core instance (can be null during initialization)
 * @param options - Configuration options
 * @returns Expansion state and control functions
 *
 * @example
 * ```tsx
 * const {
 *   expandState,
 *   isExpanding,
 *   setSeedNodes,
 *   expandNode,
 *   collapseNode,
 *   canExpand,
 *   getExpansionIndicator,
 * } = useExpandNeighbors(cyRef.current, {
 *   onFetchNeighbors: async (nodeId) => {
 *     const response = await fetch(`/api/graph/neighbors/${nodeId}`);
 *     return response.json();
 *   },
 *   maxExpandDepth: 3,
 * });
 *
 * // Mark initial query results as seeds
 * useEffect(() => {
 *   if (initialNodes.length > 0) {
 *     setSeedNodes(initialNodes.map(n => n.id));
 *   }
 * }, [initialNodes]);
 * ```
 */
export function useExpandNeighbors(
  cy: Core | null,
  options: ExpandNeighborsOptions
): UseExpandNeighborsReturn {
  const {
    onFetchNeighbors,
    maxExpandDepth = 3,
    animateExpansion = true,
    animationDuration = 500,
  } = options;

  const [expandState, setExpandState] = useState<ExpandState>(INITIAL_EXPAND_STATE);
  const [isExpanding, setIsExpanding] = useState(false);

  // Use ref to track the latest state in async operations
  const expandStateRef = useRef(expandState);
  expandStateRef.current = expandState;

  /**
   * Mark initial seed nodes (from the original query).
   * These are the starting points for expansion, shown with special styling.
   */
  const setSeedNodes = useCallback((nodeIds: string[]) => {
    const seedSet = new Set(nodeIds);
    const depthMap = new Map<string, number>();

    // All seed nodes start at depth 0
    nodeIds.forEach((id) => {
      depthMap.set(id, 0);
    });

    setExpandState({
      seedNodes: seedSet,
      expandedNodes: new Set<string>(), // Seeds are not yet expanded
      expansionDepth: depthMap,
      maxDepth: 0,
    });

    // Add visual indicator for seed nodes
    if (cy) {
      cy.batch(() => {
        // Remove seed class from all nodes first
        cy.nodes().removeClass('seed-node');
        // Add seed class to specified nodes
        nodeIds.forEach((id) => {
          const node = cy.$id(id);
          if (node.length > 0) {
            node.addClass('seed-node expandable');
          }
        });
      });
    }
  }, [cy]);

  /**
   * Expand a single node's neighbors.
   * Fetches neighbors from the backend, adds them to the graph, and animates the layout.
   */
  const expandNode = useCallback(async (nodeId: string) => {
    if (!cy || isExpanding) return;

    const currentState = expandStateRef.current;
    const currentDepth = currentState.expansionDepth.get(nodeId) ?? 0;

    // Check if max depth reached
    if (currentDepth >= maxExpandDepth) {
      console.warn(`Max expansion depth (${maxExpandDepth}) reached for node ${nodeId}`);
      return;
    }

    // Check if already expanded
    if (currentState.expandedNodes.has(nodeId)) {
      console.warn(`Node ${nodeId} is already expanded`);
      return;
    }

    setIsExpanding(true);

    try {
      // Fetch neighbors from backend
      const { nodes: newNodes, edges: newEdges } = await onFetchNeighbors(nodeId);

      // Filter out already-existing nodes
      const existingNodeIds = new Set(cy.nodes().map((n) => n.id()));
      const nodesToAdd = newNodes.filter((n) => !existingNodeIds.has(n.id));

      // Filter edges - only add edges where at least one endpoint will exist
      const futureNodeIds = new Set([...existingNodeIds, ...nodesToAdd.map((n) => n.id)]);
      const edgesToAdd = newEdges.filter((e) => {
        const sourceId = typeof e.source === 'string' ? e.source : e.source.id;
        const targetId = typeof e.target === 'string' ? e.target : e.target.id;
        return futureNodeIds.has(sourceId) && futureNodeIds.has(targetId);
      });

      // Get source node position for animation
      const sourceNode = cy.$id(nodeId);
      const sourcePos: Position = sourceNode.length > 0
        ? sourceNode.position()
        : { x: 0, y: 0 };

      // Add new elements to the graph
      cy.batch(() => {
        // Add nodes positioned around the expanded node
        nodesToAdd.forEach((node, i) => {
          const angle = (2 * Math.PI * i) / Math.max(nodesToAdd.length, 1);
          const radius = 80; // Initial placement radius

          cy.add({
            group: 'nodes',
            data: {
              id: node.id,
              label: node.label,
              type: node.type || node.entity_type || 'unknown',
              degree: node.degree || 0,
              documentCount: node.document_count || 0,
            },
            position: {
              x: sourcePos.x + radius * Math.cos(angle),
              y: sourcePos.y + radius * Math.sin(angle),
            },
            classes: 'newly-expanded expandable',
          });
        });

        // Add edges
        edgesToAdd.forEach((edge, index) => {
          const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id;
          const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id;

          cy.add({
            group: 'edges',
            data: {
              id: `edge-expand-${Date.now()}-${index}`,
              source: sourceId,
              target: targetId,
              label: edge.relationship_type || edge.type || 'related',
              weight: edge.weight || 1,
              type: edge.relationship_type || edge.type || 'co_occurrence',
            },
            classes: 'newly-expanded',
          });
        });

        // Mark source node as expanded
        sourceNode.addClass('expanded').removeClass('expandable');
      });

      // Update expansion state
      const newDepth = currentDepth + 1;
      setExpandState((prev) => {
        const newExpanded = new Set(prev.expandedNodes);
        newExpanded.add(nodeId);

        const newDepthMap = new Map(prev.expansionDepth);
        nodesToAdd.forEach((n) => {
          // Only set depth if not already set (preserve original depth)
          if (!newDepthMap.has(n.id)) {
            newDepthMap.set(n.id, newDepth);
          }
        });

        return {
          ...prev,
          expandedNodes: newExpanded,
          expansionDepth: newDepthMap,
          maxDepth: Math.max(prev.maxDepth, newDepth),
        };
      });

      // Animate layout to incorporate new nodes
      if (animateExpansion && nodesToAdd.length > 0) {
        // Get positions of existing nodes to keep them fixed
        const fixedNodes = cy.nodes().not('.newly-expanded');
        const fixedPositions = fixedNodes.map((n: NodeSingular) => ({
          nodeId: n.id(),
          position: n.position(),
        }));

        // Run incremental layout
        const layout = cy.layout({
          name: 'fcose',
          animate: true,
          animationDuration,
          randomize: false,
          fit: false,
          // Keep existing nodes in place
          fixedNodeConstraint: fixedPositions,
          // Layout parameters
          nodeRepulsion: () => 4500,
          idealEdgeLength: () => 80,
          edgeElasticity: () => 0.45,
          numIter: 1000,
        } as any);

        layout.run();

        // Remove temporary class after animation
        setTimeout(() => {
          cy.$('.newly-expanded').removeClass('newly-expanded');
        }, animationDuration + 100);
      } else {
        // Remove class immediately if not animating
        cy.$('.newly-expanded').removeClass('newly-expanded');
      }

      // Mark as fully expanded if no new nodes were added
      if (nodesToAdd.length === 0) {
        cy.$id(nodeId).addClass('fully-expanded');
      }
    } catch (error) {
      console.error('Failed to expand node:', error);
      // Re-enable expand capability on error
      cy.$id(nodeId).removeClass('expanded').addClass('expandable');
    } finally {
      setIsExpanding(false);
    }
  }, [cy, isExpanding, maxExpandDepth, onFetchNeighbors, animateExpansion, animationDuration]);

  /**
   * Collapse a node (hide its expanded neighbors).
   * Only hides nodes that were added as a direct result of expanding this node.
   */
  const collapseNode = useCallback((nodeId: string) => {
    if (!cy) return;

    const currentState = expandStateRef.current;
    const nodeDepth = currentState.expansionDepth.get(nodeId) ?? 0;

    // Find nodes that should be hidden (connected to this node with higher depth)
    const nodesToHide: string[] = [];

    cy.nodes().forEach((node: NodeSingular) => {
      const depth = currentState.expansionDepth.get(node.id());
      if (depth !== undefined && depth > nodeDepth) {
        // Check if this node is directly connected to the collapsing node
        const connectedEdges = node.connectedEdges();
        let isConnected = false;
        connectedEdges.forEach((edge: EdgeSingular) => {
          if (edge.source().id() === nodeId || edge.target().id() === nodeId) {
            isConnected = true;
          }
        });
        if (isConnected) {
          nodesToHide.push(node.id());
        }
      }
    });

    // Hide nodes and update visual state
    cy.batch(() => {
      nodesToHide.forEach((id) => {
        cy.$id(id).addClass('collapsed-neighbor');
      });
      cy.$id(nodeId).removeClass('expanded fully-expanded').addClass('expandable');
    });

    // Update state to mark node as no longer expanded
    setExpandState((prev) => {
      const newExpanded = new Set(prev.expandedNodes);
      newExpanded.delete(nodeId);

      return {
        ...prev,
        expandedNodes: newExpanded,
      };
    });
  }, [cy]);

  /**
   * Check if a node can be expanded (not at max depth and not already expanded).
   */
  const canExpand = useCallback((nodeId: string): boolean => {
    const depth = expandState.expansionDepth.get(nodeId) ?? 0;
    const isExpanded = expandState.expandedNodes.has(nodeId);
    return depth < maxExpandDepth && !isExpanded;
  }, [expandState, maxExpandDepth]);

  /**
   * Get the expansion indicator for a node.
   * Used to determine visual styling and UI state.
   */
  const getExpansionIndicator = useCallback((nodeId: string): 'expandable' | 'expanded' | 'max-depth' | 'seed' => {
    const isSeed = expandState.seedNodes.has(nodeId);
    const isExpanded = expandState.expandedNodes.has(nodeId);
    const depth = expandState.expansionDepth.get(nodeId) ?? 0;

    if (isExpanded) return 'expanded';
    if (depth >= maxExpandDepth) return 'max-depth';
    if (isSeed && depth === 0) return 'seed';
    return 'expandable';
  }, [expandState, maxExpandDepth]);

  /**
   * Reset all expansion state to initial values.
   */
  const resetExpansion = useCallback(() => {
    setExpandState(INITIAL_EXPAND_STATE);

    if (cy) {
      cy.batch(() => {
        cy.nodes().removeClass('seed-node expanded expandable fully-expanded collapsed-neighbor newly-expanded');
        cy.edges().removeClass('newly-expanded');
      });
    }
  }, [cy]);

  /**
   * Get all node IDs at a specific depth.
   * Useful for highlighting or filtering by expansion depth.
   */
  const getNodesAtDepth = useCallback((depth: number): string[] => {
    const result: string[] = [];
    expandState.expansionDepth.forEach((d, nodeId) => {
      if (d === depth) {
        result.push(nodeId);
      }
    });
    return result;
  }, [expandState]);

  return {
    expandState,
    isExpanding,
    setSeedNodes,
    expandNode,
    collapseNode,
    canExpand,
    getExpansionIndicator,
    resetExpansion,
    getNodesAtDepth,
  };
}

/**
 * Generate stylesheet entries for progressive disclosure styling.
 * These should be merged with the main Cytoscape stylesheet.
 */
export function getExpandNeighborsStylesheet() {
  return [
    // Seed nodes (original query results) - prominent styling
    {
      selector: 'node.seed-node',
      style: {
        'border-width': 4,
        'border-color': '#f59e0b', // Amber
        'border-style': 'double',
      },
    },

    // Expandable nodes (have unexplored neighbors)
    {
      selector: 'node.expandable',
      style: {
        // Add pulsing glow to indicate expandability
        'overlay-color': '#4299e1',
        'overlay-opacity': 0.15,
        'overlay-padding': 4,
      },
    },

    // Expanded nodes (neighbors already fetched)
    {
      selector: 'node.expanded',
      style: {
        'border-style': 'solid',
        'overlay-opacity': 0,
      },
    },

    // Fully expanded (no more neighbors to fetch)
    {
      selector: 'node.fully-expanded',
      style: {
        'opacity': 0.7,
        'border-style': 'dotted',
      },
    },

    // Newly expanded nodes (animation state)
    {
      selector: 'node.newly-expanded',
      style: {
        // Animation is handled via JS, but we can set initial state
        'opacity': 0.8,
      },
    },

    // Collapsed neighbors (hidden but not removed)
    {
      selector: 'node.collapsed-neighbor',
      style: {
        'display': 'none',
      },
    },

    // Newly expanded edges
    {
      selector: 'edge.newly-expanded',
      style: {
        'opacity': 0.8,
      },
    },
  ];
}
