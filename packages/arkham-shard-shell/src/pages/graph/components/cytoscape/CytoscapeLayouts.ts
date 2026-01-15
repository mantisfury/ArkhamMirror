/**
 * Cytoscape.js Layout Configurations
 *
 * Provides pre-configured layouts for different analysis scenarios.
 * All layouts support animation for smooth transitions.
 *
 * Layout categories:
 * - Force-directed: fcose, cose (general exploration, organic structure)
 * - Hierarchical: dagre, breadthfirst (org charts, chains, trees)
 * - Geometric: concentric, circle, grid (structured arrangements)
 * - Custom: preset (user-defined positions)
 */

import { LayoutOptions } from 'cytoscape';

/**
 * Layout configuration with animation defaults
 */
export const LAYOUT_CONFIGS: Record<string, LayoutOptions> = {
  // ============================================
  // FORCE-DIRECTED LAYOUTS
  // ============================================

  /**
   * fCoSE (Fast Compound Spring Embedder)
   * Best for: General exploration, organic structure, unknown relationships
   * Features: Fast, handles compound nodes, good edge lengths
   */
  fcose: {
    name: 'fcose',
    quality: 'default',
    randomize: true,
    animate: true,
    animationDuration: 800,
    animationEasing: 'ease-out',
    nodeDimensionsIncludeLabels: true,

    // Force simulation parameters
    nodeRepulsion: 4500,
    idealEdgeLength: 80,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.25,
    numIter: 2500,

    // Performance for large graphs
    tile: true,
    tilingPaddingVertical: 10,
    tilingPaddingHorizontal: 10,

    // Fit to viewport after layout
    fit: true,
    padding: 50,
  } as any,

  /**
   * CoSE (Compound Spring Embedder)
   * Best for: Clustered data, community detection visualization
   * Features: Respects compound parent nodes, good for groups
   */
  cose: {
    name: 'cose',
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',

    // Force parameters
    nodeRepulsion: 400000,
    nodeOverlap: 10,
    idealEdgeLength: 100,
    edgeElasticity: 100,
    nestingFactor: 5,
    gravity: 80,

    // Iteration settings
    numIter: 1000,
    initialTemp: 200,
    coolingFactor: 0.95,
    minTemp: 1.0,

    // Fit settings
    fit: true,
    padding: 50,
    nodeDimensionsIncludeLabels: true,
    randomize: false,
  } as any,

  // ============================================
  // HIERARCHICAL LAYOUTS
  // ============================================

  /**
   * Dagre (Directed Acyclic Graph)
   * Best for: Org charts, chain of command, process flows
   * Features: Clear hierarchy, customizable direction
   */
  hierarchical: {
    name: 'dagre',
    rankDir: 'TB',  // TB (top-bottom), BT, LR, RL
    nodeSep: 50,    // Horizontal separation between nodes
    edgeSep: 10,    // Separation between edges
    rankSep: 80,    // Vertical separation between ranks
    ranker: 'network-simplex',  // 'tight-tree', 'longest-path'
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    fit: true,
    padding: 50,
  } as any,

  /**
   * Horizontal Hierarchical (Dagre LR)
   * Best for: Timelines, process flows, left-to-right reading
   */
  'hierarchical-lr': {
    name: 'dagre',
    rankDir: 'LR',
    nodeSep: 50,
    edgeSep: 10,
    rankSep: 100,
    ranker: 'network-simplex',
    animate: true,
    animationDuration: 500,
    fit: true,
    padding: 50,
  } as any,

  /**
   * Breadth-First (Tree)
   * Best for: Tree structures, hierarchies with single root
   * Features: Layered levels, avoids crossings
   */
  breadthfirst: {
    name: 'breadthfirst',
    directed: false,  // Set to false to avoid root determination issues
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    spacingFactor: 1.5,
    avoidOverlap: true,
    maximal: false,  // Disable maximal to avoid null node errors
    fit: true,
    padding: 50,
    circle: false,
    grid: false,
    // Let cytoscape auto-determine roots based on node degree
    roots: undefined,
  } as any,

  // ============================================
  // GEOMETRIC LAYOUTS
  // ============================================

  /**
   * Concentric (Radial)
   * Best for: Ego networks, "who's connected to X", centrality visualization
   * Features: High-degree nodes at center, rings by connectivity
   */
  concentric: {
    name: 'concentric',
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    // Nodes with higher degree go toward center
    concentric: (node: any) => node.degree(),
    levelWidth: () => 2,  // Nodes per concentric ring
    minNodeSpacing: 50,
    equidistant: true,
    fit: true,
    padding: 50,
    startAngle: 3 / 2 * Math.PI,  // Start at top
    sweep: 2 * Math.PI,  // Full circle
    clockwise: true,
  } as any,

  /**
   * Circle
   * Best for: Equal emphasis on all nodes, small networks
   * Features: All nodes on single ring
   */
  circle: {
    name: 'circle',
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    avoidOverlap: true,
    spacingFactor: 1.5,
    fit: true,
    padding: 50,
    startAngle: 3 / 2 * Math.PI,
    sweep: 2 * Math.PI,
    clockwise: true,
    sort: (a: any, b: any) => b.degree() - a.degree(),  // Sort by degree
  } as any,

  /**
   * Grid
   * Best for: Comparison, orderly arrangement, sparse networks
   * Features: Aligned rows and columns
   */
  grid: {
    name: 'grid',
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    avoidOverlap: true,
    avoidOverlapPadding: 20,
    condense: true,
    rows: undefined,  // Auto-calculate
    cols: undefined,  // Auto-calculate
    fit: true,
    padding: 50,
    sort: (a: any, b: any) => {
      // Sort by type, then by label
      const typeA = a.data('type') || '';
      const typeB = b.data('type') || '';
      if (typeA !== typeB) return typeA.localeCompare(typeB);
      const labelA = a.data('label') || '';
      const labelB = b.data('label') || '';
      return labelA.localeCompare(labelB);
    },
  } as any,

  // ============================================
  // CUSTOM LAYOUTS
  // ============================================

  /**
   * Preset
   * Best for: Saved positions, manual arrangement, reproducible layouts
   * Features: Uses pre-defined node positions
   */
  preset: {
    name: 'preset',
    animate: true,
    animationDuration: 500,
    animationEasing: 'ease-out',
    positions: undefined,  // Set dynamically: { nodeId: { x, y } }
    fit: true,
    padding: 50,
  } as any,

  /**
   * Random
   * Best for: Initial exploration, breaking out of local minima
   * Features: Random positions, useful before force-directed
   */
  random: {
    name: 'random',
    animate: true,
    animationDuration: 300,
    fit: true,
    padding: 50,
  } as any,
};

/**
 * Analysis mode to layout mapping
 * Provides recommended layouts for specific analysis scenarios
 */
export const ANALYSIS_LAYOUTS: Record<string, keyof typeof LAYOUT_CONFIGS> = {
  exploration: 'fcose',           // General discovery
  hierarchy: 'hierarchical',      // Org structure, chains
  ego: 'concentric',              // Person-centric analysis
  clusters: 'cose',               // Community detection
  timeline: 'hierarchical-lr',    // Temporal flow (LR direction)
  comparison: 'grid',             // Side-by-side entities
  tree: 'breadthfirst',           // Family trees, org trees
  network: 'circle',              // Small network overview
};

/**
 * Layout metadata for UI display
 */
export interface LayoutInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'force' | 'hierarchical' | 'geometric' | 'custom';
  bestFor: string[];
}

export const LAYOUT_INFO: Record<string, LayoutInfo> = {
  fcose: {
    id: 'fcose',
    name: 'Force-Directed',
    description: 'Organic layout using physics simulation',
    icon: 'Workflow',
    category: 'force',
    bestFor: ['General exploration', 'Unknown relationships', 'Organic structure'],
  },
  cose: {
    id: 'cose',
    name: 'Clustered',
    description: 'Force layout respecting compound groups',
    icon: 'Group',
    category: 'force',
    bestFor: ['Community detection', 'Grouped entities', 'Clustered data'],
  },
  hierarchical: {
    id: 'hierarchical',
    name: 'Hierarchical',
    description: 'Top-down tree structure',
    icon: 'GitBranch',
    category: 'hierarchical',
    bestFor: ['Org charts', 'Chain of command', 'Reporting structures'],
  },
  'hierarchical-lr': {
    id: 'hierarchical-lr',
    name: 'Horizontal Tree',
    description: 'Left-to-right hierarchical layout',
    icon: 'ArrowRight',
    category: 'hierarchical',
    bestFor: ['Timelines', 'Process flows', 'Sequential events'],
  },
  breadthfirst: {
    id: 'breadthfirst',
    name: 'Tree',
    description: 'Layered tree from root nodes',
    icon: 'Network',
    category: 'hierarchical',
    bestFor: ['Family trees', 'File systems', 'Single-root hierarchies'],
  },
  concentric: {
    id: 'concentric',
    name: 'Radial',
    description: 'Concentric circles by importance',
    icon: 'Target',
    category: 'geometric',
    bestFor: ['Ego networks', 'Centrality analysis', 'Person of interest'],
  },
  circle: {
    id: 'circle',
    name: 'Circular',
    description: 'All nodes on a ring',
    icon: 'Circle',
    category: 'geometric',
    bestFor: ['Small networks', 'Equal emphasis', 'Ring topology'],
  },
  grid: {
    id: 'grid',
    name: 'Grid',
    description: 'Organized rows and columns',
    icon: 'Grid3X3',
    category: 'geometric',
    bestFor: ['Comparison', 'Sorted display', 'Orderly arrangement'],
  },
  preset: {
    id: 'preset',
    name: 'Custom',
    description: 'Saved or manual positions',
    icon: 'Save',
    category: 'custom',
    bestFor: ['Saved layouts', 'Manual arrangement', 'Reproducible views'],
  },
  random: {
    id: 'random',
    name: 'Random',
    description: 'Random node positions',
    icon: 'Shuffle',
    category: 'custom',
    bestFor: ['Reset layout', 'Break patterns', 'Fresh start'],
  },
};

/**
 * Get layout configuration by name
 */
export function getLayoutConfig(layoutName: string): LayoutOptions {
  return LAYOUT_CONFIGS[layoutName] || LAYOUT_CONFIGS.fcose;
}

/**
 * Get layout info by name
 */
export function getLayoutInfo(layoutName: string): LayoutInfo | undefined {
  return LAYOUT_INFO[layoutName];
}

/**
 * Create a modified layout config with custom options
 */
export function createLayoutConfig(
  baseName: string,
  overrides: Partial<LayoutOptions>
): LayoutOptions {
  const base = LAYOUT_CONFIGS[baseName] || LAYOUT_CONFIGS.fcose;
  return { ...base, ...overrides };
}

/**
 * Get all available layout names
 */
export function getAvailableLayouts(): string[] {
  return Object.keys(LAYOUT_CONFIGS);
}

/**
 * Get layouts by category
 */
export function getLayoutsByCategory(category: LayoutInfo['category']): string[] {
  return Object.entries(LAYOUT_INFO)
    .filter(([_, info]) => info.category === category)
    .map(([name]) => name);
}
