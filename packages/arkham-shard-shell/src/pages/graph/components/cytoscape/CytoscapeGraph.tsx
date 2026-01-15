/**
 * CytoscapeGraph - Main Cytoscape.js React Component
 *
 * Professional OSINT-grade graph visualization with:
 * - Icon-based entity rendering (Maltego-style)
 * - Multiple layout algorithms
 * - Context menus for node operations
 * - Selection and path highlighting
 * - Cluster expand/collapse
 * - Performance optimizations for large graphs
 *
 * This is a side-by-side alternative to react-force-graph,
 * not a replacement. Users can compare both engines.
 */

import { useRef, useEffect, useCallback, useMemo, useState, forwardRef, useImperativeHandle } from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular, EventObject } from 'cytoscape';
import fcose from 'cytoscape-fcose';
import dagre from 'cytoscape-dagre';

// Import local modules
import { createStylesheet, createPerformanceStylesheet } from './CytoscapeStylesheet';
import { getLayoutConfig } from './CytoscapeLayouts';

// ============================================
// TYPE DEFINITIONS
// ============================================

export interface GraphNode {
  id: string;
  label: string;
  type?: string;
  entity_type?: string;
  degree?: number;
  document_count?: number;
  clusterId?: string;
  properties?: Record<string, any>;
}

export interface GraphEdge {
  id?: string;
  source: string | { id: string };
  target: string | { id: string };
  relationship_type?: string;
  type?: string;
  weight?: number;
  properties?: Record<string, any>;
}

export interface CytoscapeGraphProps {
  /** Array of graph nodes */
  nodes: GraphNode[];
  /** Array of graph edges */
  edges: GraphEdge[];
  /** Layout algorithm to use */
  layout: string;
  /** Callback when a node is clicked */
  onNodeClick?: (nodeId: string, node: GraphNode) => void;
  /** Callback when a node is right-clicked */
  onNodeRightClick?: (nodeId: string, position: { x: number; y: number }) => void;
  /** Callback when an edge is clicked */
  onEdgeClick?: (edgeId: string, edge: GraphEdge) => void;
  /** Callback when background is clicked */
  onBackgroundClick?: () => void;
  /** Currently selected node ID */
  selectedNodeId?: string;
  /** Set of node IDs in the highlighted path */
  highlightedPath?: Set<string>;
  /** Whether to show node labels */
  showLabels?: boolean;
  /** Whether to show edge labels */
  showEdgeLabels?: boolean;
  /** Enable performance mode for large graphs */
  performanceMode?: boolean;
  /** Custom CSS class for container */
  className?: string;
}

export interface CytoscapeGraphRef {
  /** Get the underlying Cytoscape instance */
  getCy: () => Core | null;
  /** Fit graph to viewport */
  zoomToFit: () => void;
  /** Center on a specific node */
  centerOnNode: (nodeId: string) => void;
  /** Run a new layout */
  runLayout: (layoutName: string) => void;
  /** Export as PNG */
  exportPng: () => Promise<Blob | null>;
  /** Highlight a path between nodes */
  highlightPath: (nodeIds: string[]) => void;
  /** Clear all highlighting */
  clearHighlights: () => void;
  /** Get current zoom level */
  getZoom: () => number;
  /** Set zoom level */
  setZoom: (level: number) => void;
}

// ============================================
// REGISTER CYTOSCAPE EXTENSIONS
// ============================================

// Register extensions only once (check if already registered)
let extensionsRegistered = false;

function registerExtensions() {
  if (extensionsRegistered) return;

  try {
    cytoscape.use(fcose);
  } catch (e) {
    // Extension might already be registered
  }

  try {
    cytoscape.use(dagre);
  } catch (e) {
    // Extension might already be registered
  }

  extensionsRegistered = true;
}

// ============================================
// MAIN COMPONENT
// ============================================

export const CytoscapeGraph = forwardRef<CytoscapeGraphRef, CytoscapeGraphProps>(({
  nodes,
  edges,
  layout,
  onNodeClick,
  onNodeRightClick,
  onEdgeClick,
  onBackgroundClick,
  selectedNodeId,
  highlightedPath,
  showLabels = true,
  showEdgeLabels = true,
  performanceMode = false,
  className = '',
}, ref) => {
  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // State
  const [isInitialized, setIsInitialized] = useState(false);

  // Register extensions on mount
  useEffect(() => {
    registerExtensions();
  }, []);

  // ============================================
  // TRANSFORM DATA TO CYTOSCAPE FORMAT
  // ============================================

  const elements = useMemo(() => {
    // Transform nodes
    const cyNodes = nodes.map(node => ({
      data: {
        id: node.id,
        label: node.label || node.id,
        type: (node.type || node.entity_type || 'unknown').toLowerCase(),
        degree: node.degree || 0,
        documentCount: node.document_count || 0,
        // For compound nodes (clusters)
        parent: node.clusterId || undefined,
        // Store original node data
        _original: node,
      },
    }));

    // Transform edges with unique IDs
    const edgeMap = new Map<string, number>();
    const cyEdges = edges.map((edge) => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id;
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id;

      // Create unique edge ID
      const baseId = edge.id || `edge-${sourceId}-${targetId}`;
      const count = edgeMap.get(baseId) || 0;
      edgeMap.set(baseId, count + 1);
      const edgeId = count > 0 ? `${baseId}-${count}` : baseId;

      // Detect self-loops
      const isSelfLoop = sourceId === targetId;

      return {
        data: {
          id: edgeId,
          source: sourceId,
          target: targetId,
          label: edge.relationship_type || edge.type || 'related',
          weight: edge.weight || 1,
          type: (edge.relationship_type || edge.type || 'co_occurrence').toLowerCase().replace(/-/g, '_'),
          selfLoop: isSelfLoop,
          // Store original edge data
          _original: edge,
        },
      };
    });

    return [...cyNodes, ...cyEdges];
  }, [nodes, edges]);

  // ============================================
  // INITIALIZE CYTOSCAPE
  // ============================================

  useEffect(() => {
    if (!containerRef.current) return;

    // Determine if we should use performance settings
    const usePerformanceSettings = performanceMode || nodes.length > 500;

    // Create Cytoscape instance
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: usePerformanceSettings
        ? createPerformanceStylesheet()
        : createStylesheet(showLabels, showEdgeLabels),

      // Layout will be run after init
      layout: { name: 'preset', positions: undefined } as any,

      // Viewport settings
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3,

      // Performance optimizations
      pixelRatio: usePerformanceSettings ? 1 : window.devicePixelRatio,
      hideEdgesOnViewport: nodes.length > 500,
      textureOnViewport: nodes.length > 500,

      // Selection
      selectionType: 'single',
      boxSelectionEnabled: false,

      // Rendering
      styleEnabled: true,
    });

    cyRef.current = cy;

    // ============================================
    // EVENT HANDLERS
    // ============================================

    // Node click
    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target as NodeSingular;
      const nodeData = node.data('_original') as GraphNode;
      onNodeClick?.(node.id(), nodeData);
    });

    // Node right-click (context menu trigger)
    cy.on('cxttap', 'node', (evt: EventObject) => {
      const node = evt.target as NodeSingular;
      const renderedPos = evt.renderedPosition;
      onNodeRightClick?.(node.id(), { x: renderedPos.x, y: renderedPos.y });
    });

    // Edge click
    cy.on('tap', 'edge', (evt: EventObject) => {
      const edge = evt.target as EdgeSingular;
      const edgeData = edge.data('_original') as GraphEdge;
      onEdgeClick?.(edge.id(), edgeData);
    });

    // Background click
    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        onBackgroundClick?.();
      }
    });

    // Run initial layout
    const layoutConfig = getLayoutConfig(layout);
    cy.layout(layoutConfig).run();

    setIsInitialized(true);

    // ============================================
    // CLEANUP
    // ============================================

    return () => {
      cy.destroy();
      cyRef.current = null;
      setIsInitialized(false);
    };
  }, []); // Only run once on mount

  // ============================================
  // UPDATE ELEMENTS WHEN DATA CHANGES
  // ============================================

  useEffect(() => {
    if (!cyRef.current || !isInitialized) return;

    const cy = cyRef.current;

    // Batch element updates
    cy.batch(() => {
      // Get existing element IDs
      const existingNodeIds = new Set(cy.nodes().map(n => n.id()));
      const existingEdgeIds = new Set(cy.edges().map(e => e.id()));

      // Determine new element IDs
      const newNodeIds = new Set(elements.filter(e => !('source' in e.data)).map(e => e.data.id));
      const newEdgeIds = new Set(elements.filter(e => 'source' in e.data).map(e => e.data.id));

      // Remove elements that no longer exist
      existingNodeIds.forEach(id => {
        if (!newNodeIds.has(id)) {
          cy.$id(id).remove();
        }
      });
      existingEdgeIds.forEach(id => {
        if (!newEdgeIds.has(id)) {
          cy.$id(id).remove();
        }
      });

      // Add/update elements
      elements.forEach(element => {
        const existing = cy.$id(element.data.id);
        if (existing.length > 0) {
          // Update existing element data
          existing.data(element.data);
        } else {
          // Add new element
          cy.add(element);
        }
      });
    });

    // Run layout after data change
    const layoutConfig = getLayoutConfig(layout);
    cy.layout(layoutConfig).run();
  }, [elements, isInitialized]);

  // ============================================
  // UPDATE LAYOUT WHEN CHANGED
  // ============================================

  useEffect(() => {
    if (!cyRef.current || !isInitialized) return;

    const layoutConfig = getLayoutConfig(layout);
    cyRef.current.layout(layoutConfig).run();
  }, [layout, isInitialized]);

  // ============================================
  // UPDATE SELECTION HIGHLIGHTING
  // ============================================

  useEffect(() => {
    if (!cyRef.current || !isInitialized) return;

    const cy = cyRef.current;

    // Clear previous selection
    cy.nodes().removeClass('selected');

    // Highlight selected node
    if (selectedNodeId) {
      const selectedNode = cy.$id(selectedNodeId);
      if (selectedNode.length > 0) {
        selectedNode.addClass('selected');
      }
    }
  }, [selectedNodeId, isInitialized]);

  // ============================================
  // UPDATE PATH HIGHLIGHTING
  // ============================================

  useEffect(() => {
    if (!cyRef.current || !isInitialized) return;

    const cy = cyRef.current;

    // Clear previous path highlighting
    cy.elements().removeClass('in-path highlighted');

    // Highlight path nodes and edges
    if (highlightedPath && highlightedPath.size > 0) {
      const pathArray = Array.from(highlightedPath);

      // Highlight nodes in path
      pathArray.forEach(nodeId => {
        cy.$id(nodeId).addClass('in-path');
      });

      // Highlight edges between consecutive path nodes
      for (let i = 0; i < pathArray.length - 1; i++) {
        const sourceId = pathArray[i];
        const targetId = pathArray[i + 1];

        cy.edges().forEach(edge => {
          const edgeSource = edge.source().id();
          const edgeTarget = edge.target().id();

          if ((edgeSource === sourceId && edgeTarget === targetId) ||
              (edgeSource === targetId && edgeTarget === sourceId)) {
            edge.addClass('highlighted');
          }
        });
      }
    }
  }, [highlightedPath, isInitialized]);

  // ============================================
  // UPDATE STYLESHEET WHEN LABEL SETTINGS CHANGE
  // ============================================

  useEffect(() => {
    if (!cyRef.current || !isInitialized) return;

    const usePerformanceSettings = performanceMode || nodes.length > 500;
    const stylesheet = usePerformanceSettings
      ? createPerformanceStylesheet()
      : createStylesheet(showLabels, showEdgeLabels);

    cyRef.current.style(stylesheet);
  }, [showLabels, showEdgeLabels, performanceMode, isInitialized, nodes.length]);

  // ============================================
  // CONTAINER RESIZE HANDLING
  // ============================================

  useEffect(() => {
    if (!containerRef.current || !cyRef.current) return;

    const resizeObserver = new ResizeObserver(() => {
      cyRef.current?.resize();
    });

    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  // ============================================
  // IMPERATIVE HANDLE METHODS
  // ============================================

  const zoomToFit = useCallback(() => {
    cyRef.current?.fit(undefined, 50);
  }, []);

  const centerOnNode = useCallback((nodeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const node = cy.$id(nodeId);
    if (node.length > 0) {
      cy.center(node);
      cy.zoom({ level: 2, position: node.position() });
    }
  }, []);

  const runLayout = useCallback((layoutName: string) => {
    if (!cyRef.current) return;

    const layoutConfig = getLayoutConfig(layoutName);
    cyRef.current.layout(layoutConfig).run();
  }, []);

  const exportPng = useCallback(async (): Promise<Blob | null> => {
    if (!cyRef.current) return null;

    try {
      const blob = await cyRef.current.png({
        output: 'blob-promise',
        full: true,
        scale: 2,
        bg: '#ffffff',
      });
      return blob;
    } catch (error) {
      console.error('Failed to export PNG:', error);
      return null;
    }
  }, []);

  const highlightPathFn = useCallback((nodeIds: string[]) => {
    if (!cyRef.current) return;

    const cy = cyRef.current;

    // Clear previous highlighting
    cy.elements().removeClass('in-path highlighted');

    // Highlight nodes
    nodeIds.forEach(nodeId => {
      cy.$id(nodeId).addClass('in-path');
    });

    // Highlight edges between consecutive nodes
    for (let i = 0; i < nodeIds.length - 1; i++) {
      const sourceId = nodeIds[i];
      const targetId = nodeIds[i + 1];

      cy.edges().forEach(edge => {
        const edgeSource = edge.source().id();
        const edgeTarget = edge.target().id();

        if ((edgeSource === sourceId && edgeTarget === targetId) ||
            (edgeSource === targetId && edgeTarget === sourceId)) {
          edge.addClass('highlighted');
        }
      });
    }

    // Fit view to highlighted path
    const pathNodes = cy.nodes().filter(n => nodeIds.includes(n.id()));
    if (pathNodes.length > 0) {
      cy.fit(pathNodes, 50);
    }
  }, []);

  const clearHighlights = useCallback(() => {
    cyRef.current?.elements().removeClass('selected in-path highlighted dimmed');
  }, []);

  const getZoom = useCallback(() => {
    return cyRef.current?.zoom() ?? 1;
  }, []);

  const setZoom = useCallback((level: number) => {
    cyRef.current?.zoom(level);
  }, []);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getCy: () => cyRef.current,
    zoomToFit,
    centerOnNode,
    runLayout,
    exportPng,
    highlightPath: highlightPathFn,
    clearHighlights,
    getZoom,
    setZoom,
  }), [zoomToFit, centerOnNode, runLayout, exportPng, highlightPathFn, clearHighlights, getZoom, setZoom]);

  // ============================================
  // RENDER
  // ============================================

  return (
    <div
      ref={containerRef}
      className={`cytoscape-container ${className}`}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '400px',
        position: 'relative',
        backgroundColor: '#fafafa',
      }}
    />
  );
});

CytoscapeGraph.displayName = 'CytoscapeGraph';

export default CytoscapeGraph;
