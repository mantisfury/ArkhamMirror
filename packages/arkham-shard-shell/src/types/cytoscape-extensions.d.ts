/**
 * Type declarations for Cytoscape.js extension packages
 * These packages don't have @types definitions available
 */

declare module 'cytoscape-fcose' {
  import cytoscape from 'cytoscape';

  const fcose: cytoscape.Ext;
  export default fcose;

  export interface FcoseLayoutOptions extends cytoscape.BaseLayoutOptions {
    name: 'fcose';
    /** Whether to fit the viewport to the graph */
    fit?: boolean;
    /** Padding around the graph when fit=true */
    padding?: number;
    /** Whether to animate the layout */
    animate?: boolean;
    /** Duration of animation in ms */
    animationDuration?: number;
    /** Easing of animation */
    animationEasing?: string;
    /** Whether to randomize node positions initially */
    randomize?: boolean;
    /** Node repulsion multiplier */
    nodeRepulsion?: number | ((node: any) => number);
    /** Ideal edge length */
    idealEdgeLength?: number | ((edge: any) => number);
    /** Edge elasticity multiplier */
    edgeElasticity?: number | ((edge: any) => number);
    /** Number of iterations */
    numIter?: number;
    /** Whether to use multi-level scaling */
    useMultiLevelScaling?: boolean;
    /** Nesting factor */
    nestingFactor?: number;
    /** Gravity force */
    gravity?: number;
    /** Gravity range */
    gravityRange?: number;
    /** Gravity compound */
    gravityCompound?: number;
    /** Gravity range for compound nodes */
    gravityRangeCompound?: number;
    /** Initial energy on incremental */
    initialEnergyOnIncremental?: number;
    /** Fixed node constraint */
    fixedNodeConstraint?: Array<{ nodeId: string; position: { x: number; y: number } }>;
    /** Alignment constraint */
    alignmentConstraint?: { vertical?: string[][]; horizontal?: string[][] };
    /** Relative placement constraint */
    relativePlacementConstraint?: Array<{ top?: string; left?: string; bottom?: string; right?: string; gap?: number }>;
    /** Quality: 'draft' | 'default' | 'proof' */
    quality?: 'draft' | 'default' | 'proof';
    /** Tile padding */
    tile?: boolean;
    /** Tile padding horizontal */
    tilingPaddingHorizontal?: number;
    /** Tile padding vertical */
    tilingPaddingVertical?: number;
    /** Separate connected components */
    packComponents?: boolean;
    /** Component spacing */
    componentSpacing?: number;
    /** Sampling type */
    samplingType?: boolean;
    /** Sample size */
    sampleSize?: number;
    /** Node dimensions include labels */
    nodeDimensionsIncludeLabels?: boolean;
    /** Simple nodes only */
    simpleNodes?: boolean;
  }
}

declare module 'cytoscape-dagre' {
  import cytoscape from 'cytoscape';

  const dagre: cytoscape.Ext;
  export default dagre;

  export interface DagreLayoutOptions extends cytoscape.BaseLayoutOptions {
    name: 'dagre';
    /** Whether to fit the viewport to the graph */
    fit?: boolean;
    /** Padding around the graph when fit=true */
    padding?: number;
    /** Whether to animate the layout */
    animate?: boolean;
    /** Duration of animation in ms */
    animationDuration?: number;
    /** Easing of animation */
    animationEasing?: string;
    /** Whether to use bounding box */
    boundingBox?: { x1: number; y1: number; w: number; h: number } | { x1: number; y1: number; x2: number; y2: number };
    /** Dagre layout options */
    rankDir?: 'TB' | 'BT' | 'LR' | 'RL';
    /** Alignment of nodes within ranks */
    align?: 'UL' | 'UR' | 'DL' | 'DR';
    /** Rank separation */
    rankSep?: number;
    /** Node separation */
    nodeSep?: number;
    /** Edge separation */
    edgeSep?: number;
    /** Ranker algorithm */
    ranker?: 'network-simplex' | 'tight-tree' | 'longest-path';
    /** Minimum length of edge */
    minLen?: (edge: any) => number;
    /** Edge weight */
    edgeWeight?: (edge: any) => number;
    /** Node dimensions include labels */
    nodeDimensionsIncludeLabels?: boolean;
    /** Spacer between components */
    spacingFactor?: number;
  }
}

declare module 'cytoscape-expand-collapse' {
  import cytoscape from 'cytoscape';

  const expandCollapse: cytoscape.Ext;
  export default expandCollapse;
}

declare module 'cytoscape-context-menus' {
  import cytoscape from 'cytoscape';

  const contextMenus: cytoscape.Ext;
  export default contextMenus;
}

declare module 'cytoscape-svg' {
  import cytoscape from 'cytoscape';

  const svg: cytoscape.Ext;
  export default svg;
}
