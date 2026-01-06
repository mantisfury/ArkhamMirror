/**
 * Type declarations for react-force-graph-2d
 *
 * Simplified declarations for the force-graph library
 */

declare module 'react-force-graph-2d' {
  import { FC, RefObject } from 'react';

  export interface ForceGraphMethods<N = any, L = any> {
    centerAt: (x?: number, y?: number, ms?: number) => void;
    zoom: (zoom?: number, ms?: number) => void;
    zoomToFit: (ms?: number, padding?: number, nodeFilter?: (node: N) => boolean) => void;
    d3Force: (forceName: string, force?: any) => any;
    d3ReheatSimulation: () => void;
    pauseAnimation: () => void;
    resumeAnimation: () => void;
    refresh: () => void;
    getGraphBbox: () => { x: [number, number]; y: [number, number] } | null;
    screen2GraphCoords: (x: number, y: number) => { x: number; y: number };
    graph2ScreenCoords: (x: number, y: number) => { x: number; y: number };
  }

  export interface ForceGraph2DProps {
    graphData?: { nodes: any[]; links: any[] };
    ref?: any;
    width?: number;
    height?: number;
    backgroundColor?: string;

    // Node
    nodeId?: string;
    nodeLabel?: string | ((node: any) => string);
    nodeVal?: string | number | ((node: any) => number);
    nodeColor?: string | ((node: any) => string);
    nodeAutoColorBy?: string | ((node: any) => string | null);
    nodeCanvasObject?: (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => void;
    nodeCanvasObjectMode?: string | ((node: any) => string);
    nodePointerAreaPaint?: (node: any, color: string, ctx: CanvasRenderingContext2D) => void;
    nodeRelSize?: number;

    // Link
    linkSource?: string;
    linkTarget?: string;
    linkLabel?: string | ((link: any) => string);
    linkColor?: string | ((link: any) => string);
    linkAutoColorBy?: string | ((link: any) => string | null);
    linkWidth?: number | ((link: any) => number);
    linkCurvature?: number | ((link: any) => number);
    linkCanvasObject?: (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => void;
    linkDirectionalArrowLength?: number | ((link: any) => number);
    linkDirectionalArrowColor?: string | ((link: any) => string);
    linkDirectionalArrowRelPos?: number | ((link: any) => number);
    linkDirectionalParticles?: number | ((link: any) => number);
    linkDirectionalParticleSpeed?: number | ((link: any) => number);
    linkDirectionalParticleWidth?: number | ((link: any) => number);
    linkDirectionalParticleColor?: string | ((link: any) => string);
    linkPointerAreaPaint?: (link: any, color: string, ctx: CanvasRenderingContext2D) => void;

    // Interaction
    onNodeClick?: (node: any, event: MouseEvent) => void;
    onNodeRightClick?: (node: any, event: MouseEvent) => void;
    onNodeHover?: (node: any | null, previousNode: any | null) => void;
    onNodeDrag?: (node: any, translate: { x: number; y: number }) => void;
    onNodeDragEnd?: (node: any, translate: { x: number; y: number }) => void;
    onLinkClick?: (link: any, event: MouseEvent) => void;
    onLinkRightClick?: (link: any, event: MouseEvent) => void;
    onLinkHover?: (link: any | null, previousLink: any | null) => void;
    onBackgroundClick?: (event: MouseEvent) => void;
    onBackgroundRightClick?: (event: MouseEvent) => void;
    onZoom?: (zoom: { k: number; x: number; y: number }) => void;
    onZoomEnd?: (zoom: { k: number; x: number; y: number }) => void;

    // Controls
    enableNodeDrag?: boolean;
    enableZoomInteraction?: boolean;
    enablePanInteraction?: boolean;
    enablePointerInteraction?: boolean;

    // Force simulation
    d3AlphaMin?: number;
    d3AlphaDecay?: number;
    d3VelocityDecay?: number;
    warmupTicks?: number;
    cooldownTicks?: number;
    cooldownTime?: number;
    onEngineStop?: () => void;
    onEngineTick?: () => void;

    // Misc
    autoPauseRedraw?: boolean;
    minZoom?: number;
    maxZoom?: number;
  }

  const ForceGraph2D: FC<ForceGraph2DProps>;
  export default ForceGraph2D;
  export { ForceGraph2D };
}
