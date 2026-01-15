/**
 * Cytoscape components barrel export
 *
 * Exports all Cytoscape-related UI components for the Graph XPAC.
 */

// ============================================
// CORE COMPONENT
// ============================================

export { CytoscapeGraph, default as CytoscapeGraphDefault } from './CytoscapeGraph';
export type { CytoscapeGraphProps, CytoscapeGraphRef, GraphNode, GraphEdge } from './CytoscapeGraph';

// ============================================
// UI COMPONENTS
// ============================================

export { CytoscapeControls } from './CytoscapeControls';
export type { CytoscapeControlsProps } from './CytoscapeControls';

export { PerformanceModeToggle } from './PerformanceModeToggle';
export type {
  PerformanceModeToggleProps,
  PerformanceModeSettings,
} from './PerformanceModeToggle';

export { ExpandNeighborsPanel } from './ExpandNeighborsPanel';
export type {
  ExpandNeighborsPanelProps,
  ExpandState,
} from './ExpandNeighborsPanel';

export { CytoscapeTooltip } from './CytoscapeTooltip';
export type { CytoscapeTooltipProps } from './CytoscapeTooltip';

// ============================================
// HOOKS
// ============================================

export { useExpandNeighbors } from './useExpandNeighbors';
export type {
  ExpandNeighborsOptions,
  ExpandState as UseExpandNeighborsState,
  UseExpandNeighborsReturn,
} from './useExpandNeighbors';
export { getExpandNeighborsStylesheet } from './useExpandNeighbors';

export {
  usePerformanceMode,
  DEFAULT_PERFORMANCE_SETTINGS,
  AGGRESSIVE_PERFORMANCE_SETTINGS,
  getPerformanceModeStylesheet,
  getRecommendedSettings,
} from './usePerformanceMode';
export type {
  PerformanceModeSettings as UsePerformanceModeSettings,
  PerformanceSettings,
  UsePerformanceModeReturn,
} from './usePerformanceMode';

// ============================================
// STYLES & CONFIGURATION
// ============================================

export { createStylesheet, createPerformanceStylesheet, defaultStylesheet } from './CytoscapeStylesheet';
export {
  LAYOUT_CONFIGS,
  ANALYSIS_LAYOUTS,
  LAYOUT_INFO,
  getLayoutConfig,
  getLayoutInfo,
  createLayoutConfig,
  getAvailableLayouts,
  getLayoutsByCategory,
} from './CytoscapeLayouts';
export type { LayoutInfo } from './CytoscapeLayouts';

export {
  ENTITY_ICONS,
  ENTITY_COLORS,
  ENTITY_LABELS,
  getEntityIcon,
  getEntityColor,
  getEntityLabel,
} from './entityIcons';

export { applyEdgeBundling, calculateCurveDistance } from './edgeBundling';

// Styles - import this in the main CytoscapeGraph component
// import './CytoscapeGraph.css';
