/**
 * Performance Mode Hook for Cytoscape.js
 *
 * Provides adaptive rendering settings for large graphs (500+ nodes).
 * Automatically detects when performance mode should be suggested and
 * applies optimizations to maintain interactive frame rates.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { Core } from 'cytoscape';

/**
 * Individual performance optimization settings
 */
export interface PerformanceSettings {
  /** Hide node labels to reduce text rendering overhead */
  hideLabels: boolean;
  /** Hide edge labels (relationship types) */
  hideEdgeLabels: boolean;
  /** Use haystack curve style instead of bezier for faster edge rendering */
  simplifyEdges: boolean;
  /** Reduce node visual complexity (overlays, shadows) */
  reduceNodeDetail: boolean;
  /** Use lower pixel ratio for canvas rendering */
  lowerPixelRatio: boolean;
  /** Temporarily hide edges during pan/zoom operations */
  hideEdgesOnPan: boolean;
}

/**
 * Complete performance mode configuration
 */
export interface PerformanceModeSettings {
  /** Whether performance mode is currently active */
  enabled: boolean;
  /** Node count threshold for auto-suggesting performance mode */
  nodeThreshold: number;
  /** Individual optimization settings */
  settings: PerformanceSettings;
}

/**
 * Return type for the usePerformanceMode hook
 */
export interface UsePerformanceModeReturn {
  /** Current performance mode settings */
  performanceMode: PerformanceModeSettings;
  /** Update performance mode settings (partial updates supported) */
  setPerformanceMode: (settings: Partial<PerformanceModeSettings>) => void;
  /** Update individual performance settings */
  updateSettings: (settings: Partial<PerformanceSettings>) => void;
  /** Whether auto-detection suggests enabling performance mode */
  autoDetectedMode: boolean;
  /** Reset to default settings */
  resetToDefaults: () => void;
}

/**
 * Default performance mode settings
 * Balanced defaults that preserve some visual quality while improving performance
 */
export const DEFAULT_PERFORMANCE_SETTINGS: PerformanceModeSettings = {
  enabled: false,
  nodeThreshold: 500,
  settings: {
    hideLabels: false,
    hideEdgeLabels: true,
    simplifyEdges: true,
    reduceNodeDetail: true,
    lowerPixelRatio: true,
    hideEdgesOnPan: true,
  },
};

/**
 * Aggressive performance settings for very large graphs (1000+ nodes)
 */
export const AGGRESSIVE_PERFORMANCE_SETTINGS: PerformanceModeSettings = {
  enabled: true,
  nodeThreshold: 1000,
  settings: {
    hideLabels: true,
    hideEdgeLabels: true,
    simplifyEdges: true,
    reduceNodeDetail: true,
    lowerPixelRatio: true,
    hideEdgesOnPan: true,
  },
};

/**
 * Hook for managing performance mode in Cytoscape graphs.
 *
 * @param cy - Cytoscape Core instance (can be null during initialization)
 * @param nodeCount - Current number of nodes in the graph
 * @returns Performance mode state and control functions
 *
 * @example
 * ```tsx
 * const { performanceMode, setPerformanceMode, autoDetectedMode } = usePerformanceMode(
 *   cyRef.current,
 *   nodes.length
 * );
 *
 * // Show suggestion to user
 * if (autoDetectedMode && !performanceMode.enabled) {
 *   showToast('Large graph detected. Enable performance mode?');
 * }
 * ```
 */
export function usePerformanceMode(
  cy: Core | null,
  nodeCount: number
): UsePerformanceModeReturn {
  const [performanceMode, setPerformanceModeState] = useState<PerformanceModeSettings>(
    DEFAULT_PERFORMANCE_SETTINGS
  );

  // Track event handlers for cleanup
  const panZoomHandlerRef = useRef<(() => void) | null>(null);
  const panZoomEndHandlerRef = useRef<(() => void) | null>(null);

  // Auto-detect when performance mode should be suggested
  const autoDetectedMode = nodeCount > performanceMode.nodeThreshold;

  /**
   * Apply performance optimizations to the Cytoscape instance
   */
  useEffect(() => {
    if (!cy) return;

    // Clean up previous event handlers
    if (panZoomHandlerRef.current) {
      cy.off('pan zoom', panZoomHandlerRef.current);
      panZoomHandlerRef.current = null;
    }
    if (panZoomEndHandlerRef.current) {
      cy.off('panend zoomend', panZoomEndHandlerRef.current);
      panZoomEndHandlerRef.current = null;
    }

    if (performanceMode.enabled) {
      const { settings } = performanceMode;

      cy.batch(() => {
        // Simplify edges to haystack for faster rendering
        if (settings.simplifyEdges) {
          cy.edges().addClass('performance-mode');
        }

        // Hide node labels
        if (settings.hideLabels) {
          cy.nodes().addClass('performance-no-label');
        }

        // Hide edge labels
        if (settings.hideEdgeLabels) {
          cy.edges().addClass('performance-no-label');
        }

        // Reduce node visual detail
        if (settings.reduceNodeDetail) {
          cy.nodes().addClass('performance-reduced-detail');
        }
      });

      // Enable viewport optimizations - hide edges during pan/zoom
      if (settings.hideEdgesOnPan) {
        const onPanZoom = () => {
          cy.edges().style('opacity', 0.15);
        };

        const onPanZoomEnd = () => {
          cy.edges().style('opacity', 1);
        };

        panZoomHandlerRef.current = onPanZoom;
        panZoomEndHandlerRef.current = onPanZoomEnd;

        cy.on('pan zoom', onPanZoom);
        cy.on('panend zoomend', onPanZoomEnd);
      }

      // Lower pixel ratio for faster canvas rendering
      if (settings.lowerPixelRatio) {
        // Note: pixelRatio is set at initialization, but we can force a resize
        // which may help with some rendering optimizations
        cy.resize();
      }
    } else {
      // Restore full quality rendering
      cy.batch(() => {
        cy.edges().removeClass('performance-mode performance-no-label');
        cy.nodes().removeClass('performance-no-label performance-reduced-detail');
        // Reset any inline styles
        cy.edges().removeStyle('opacity');
      });
    }

    // Cleanup function
    return () => {
      if (cy && panZoomHandlerRef.current) {
        cy.off('pan zoom', panZoomHandlerRef.current);
      }
      if (cy && panZoomEndHandlerRef.current) {
        cy.off('panend zoomend', panZoomEndHandlerRef.current);
      }
    };
  }, [cy, performanceMode]);

  /**
   * Update performance mode settings (supports partial updates)
   */
  const setPerformanceMode = useCallback((updates: Partial<PerformanceModeSettings>) => {
    setPerformanceModeState((prev) => ({
      ...prev,
      ...updates,
      settings: updates.settings
        ? { ...prev.settings, ...updates.settings }
        : prev.settings,
    }));
  }, []);

  /**
   * Update individual performance settings
   */
  const updateSettings = useCallback((settings: Partial<PerformanceSettings>) => {
    setPerformanceModeState((prev) => ({
      ...prev,
      settings: { ...prev.settings, ...settings },
    }));
  }, []);

  /**
   * Reset to default settings
   */
  const resetToDefaults = useCallback(() => {
    setPerformanceModeState(DEFAULT_PERFORMANCE_SETTINGS);
  }, []);

  return {
    performanceMode,
    setPerformanceMode,
    updateSettings,
    autoDetectedMode,
    resetToDefaults,
  };
}

/**
 * Generate stylesheet entries for performance mode.
 * These should be merged with the main Cytoscape stylesheet.
 */
export function getPerformanceModeStylesheet() {
  return [
    // Simplified edge rendering using haystack (straight lines)
    {
      selector: 'edge.performance-mode',
      style: {
        'curve-style': 'haystack' as const,
        'haystack-radius': 0.5,
        'line-opacity': 0.6,
        // Labels already hidden via class
      },
    },

    // Hide labels on nodes
    {
      selector: 'node.performance-no-label',
      style: {
        'label': '',
        'text-opacity': 0,
      },
    },

    // Hide labels on edges
    {
      selector: 'edge.performance-no-label',
      style: {
        'label': '',
        'text-opacity': 0,
      },
    },

    // Reduced visual detail for nodes
    {
      selector: 'node.performance-reduced-detail',
      style: {
        'overlay-opacity': 0,
        'border-width': 1,
        // Disable background image for maximum performance
        // 'background-image': 'none',
      },
    },
  ];
}

/**
 * Get recommended performance settings based on graph size
 */
export function getRecommendedSettings(nodeCount: number): PerformanceModeSettings {
  if (nodeCount > 2000) {
    // Very large graph - enable all optimizations
    return {
      ...AGGRESSIVE_PERFORMANCE_SETTINGS,
      enabled: true,
    };
  } else if (nodeCount > 1000) {
    // Large graph - enable most optimizations
    return {
      enabled: true,
      nodeThreshold: 500,
      settings: {
        hideLabels: true,
        hideEdgeLabels: true,
        simplifyEdges: true,
        reduceNodeDetail: true,
        lowerPixelRatio: true,
        hideEdgesOnPan: true,
      },
    };
  } else if (nodeCount > 500) {
    // Medium-large graph - enable some optimizations
    return {
      enabled: true,
      nodeThreshold: 500,
      settings: {
        hideLabels: false,
        hideEdgeLabels: true,
        simplifyEdges: true,
        reduceNodeDetail: false,
        lowerPixelRatio: true,
        hideEdgesOnPan: true,
      },
    };
  }

  // Small graph - no optimizations needed
  return DEFAULT_PERFORMANCE_SETTINGS;
}
