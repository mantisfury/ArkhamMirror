/**
 * Cytoscape.js Stylesheet Configuration
 *
 * Defines all visual styles for nodes, edges, and interactive states.
 * Uses CSS-like selectors and properties specific to Cytoscape.js.
 *
 * Style priorities (highest to lowest):
 * 1. Interactive states (.selected, .highlighted, .hidden)
 * 2. Progressive disclosure states (.seed-node, .expandable, .expanded)
 * 3. Dynamic sizing (degree-based)
 * 4. Entity type colors
 * 5. Base styles
 */

import type { StylesheetStyle } from 'cytoscape';
import { ENTITY_COLORS, getEntityIcon, getEntityColor } from './entityIcons';
import { RELATIONSHIP_STYLES } from '../../constants/relationshipStyles';

/**
 * Creates the complete Cytoscape stylesheet
 * @param showLabels - Whether to display node labels
 * @param showEdgeLabels - Whether to display edge labels
 */
export function createStylesheet(
  showLabels: boolean = true,
  showEdgeLabels: boolean = true
): StylesheetStyle[] {
  return [
    // ============================================
    // BASE NODE STYLES
    // ============================================
    {
      selector: 'node',
      style: {
        // Shape and size
        'shape': 'ellipse',
        'width': 50,
        'height': 50,

        // Background color (will be overridden by entity type)
        'background-color': '#718096',
        'background-opacity': 1,

        // Icon rendering - use data URI
        'background-image': (ele: any) => {
          const type = ele.data('type')?.toLowerCase() || 'unknown';
          return getEntityIcon(type);
        },
        'background-fit': 'none',
        'background-width': 24,
        'background-height': 24,
        'background-position-x': '50%',
        'background-position-y': '50%',
        'background-clip': 'none',

        // Border (color matches entity type)
        'border-width': 2,
        'border-color': (ele: any) => {
          const type = ele.data('type')?.toLowerCase() || 'unknown';
          const color = getEntityColor(type);
          // Darken the color slightly for border
          return color;
        },
        'border-style': 'solid',
        'border-opacity': 1,

        // Label styling
        'label': showLabels ? 'data(label)' : '',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 5,
        'font-size': 11,
        'font-family': 'Inter, system-ui, -apple-system, sans-serif',
        'color': '#1a202c',
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.85,
        'text-background-padding': '3px',
        'text-background-shape': 'roundrectangle',
        'text-wrap': 'ellipsis',
        'text-max-width': '100px',

        // Performance: hide labels when zoomed out
        'min-zoomed-font-size': 8,

        // Transition for smooth state changes
        'transition-property': 'background-color, border-color, border-width, width, height, opacity',
        'transition-duration': '0.2s',
        'transition-timing-function': 'ease-out',
      } as any,
    },

    // ============================================
    // DYNAMIC NODE SIZING BY DEGREE
    // ============================================
    {
      selector: 'node[degree > 5]',
      style: {
        'width': 60,
        'height': 60,
        'background-width': 28,
        'background-height': 28,
      },
    },
    {
      selector: 'node[degree > 10]',
      style: {
        'width': 70,
        'height': 70,
        'background-width': 32,
        'background-height': 32,
      },
    },
    {
      selector: 'node[degree > 20]',
      style: {
        'width': 80,
        'height': 80,
        'background-width': 36,
        'background-height': 36,
      },
    },

    // ============================================
    // ENTITY TYPE COLORS
    // ============================================
    ...Object.entries(ENTITY_COLORS).map(([type, color]) => ({
      selector: `node[type = "${type}"]`,
      style: {
        'background-color': color,
      },
    })),

    // ============================================
    // SELECTED NODE STATE
    // ============================================
    {
      selector: 'node.selected',
      style: {
        'border-width': 4,
        'border-color': '#f56565',
        'overlay-color': '#f56565',
        'overlay-opacity': 0.2,
        'overlay-padding': 8,
        'z-index': 999,
      },
    },

    // ============================================
    // HIGHLIGHTED PATH NODES
    // ============================================
    {
      selector: 'node.in-path',
      style: {
        'border-width': 4,
        'border-color': '#68d391',
        'overlay-color': '#68d391',
        'overlay-opacity': 0.2,
        'overlay-padding': 6,
        'z-index': 998,
      },
    },

    // ============================================
    // HIDDEN NODES
    // ============================================
    {
      selector: 'node.hidden',
      style: {
        'display': 'none',
      },
    },

    // ============================================
    // COMPOUND PARENT NODES (CLUSTERS)
    // ============================================
    {
      selector: ':parent',
      style: {
        'background-opacity': 0.15,
        'background-color': '#4299e1',
        'border-width': 2,
        'border-style': 'dashed',
        'border-color': '#2b6cb0',
        'padding': 30,
        'text-valign': 'top',
        'text-halign': 'center',
        'font-weight': 'bold',
        'font-size': 14,
        'label': 'data(label)',
        'shape': 'roundrectangle',
      },
    },

    // ============================================
    // BASE EDGE STYLES
    // ============================================
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#a0aec0',
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#a0aec0',
        'arrow-scale': 0.8,

        // Edge label
        'label': showEdgeLabels ? 'data(label)' : '',
        'font-size': 9,
        'text-rotation': 'autorotate',
        'text-margin-y': -8,
        'color': '#4a5568',
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.8,
        'text-background-padding': '2px',
        'text-background-shape': 'roundrectangle',

        // Performance
        'min-zoomed-font-size': 10,

        // Transitions
        'transition-property': 'line-color, width, opacity',
        'transition-duration': '0.2s',
      } as any,
    },

    // ============================================
    // EDGE WEIGHT STYLING (THICKER = STRONGER)
    // ============================================
    {
      selector: 'edge[weight > 3]',
      style: {
        'width': 3,
      },
    },
    {
      selector: 'edge[weight > 5]',
      style: {
        'width': 4,
      },
    },
    {
      selector: 'edge[weight > 10]',
      style: {
        'width': 5,
      },
    },

    // ============================================
    // RELATIONSHIP TYPE COLORS
    // ============================================
    ...Object.entries(RELATIONSHIP_STYLES).map(([type, style]) => ({
      selector: `edge[type = "${type}"]`,
      style: {
        'line-color': style.color,
        'target-arrow-color': style.color,
        'target-arrow-shape': style.directed ? 'triangle' : 'none',
        'line-style': style.dash ? 'dashed' : 'solid',
        ...(style.width ? { 'width': style.width } : {}),
      },
    })),

    // ============================================
    // HIGHLIGHTED PATH EDGES
    // ============================================
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#68d391',
        'target-arrow-color': '#68d391',
        'width': 4,
        'z-index': 999,
        'opacity': 1,
      },
    },

    // ============================================
    // EDGE BUNDLING & CURVATURE STYLES
    // ============================================

    // Multi-edge handling (multiple edges between same node pair)
    // Use unbundled-bezier to curve parallel edges away from each other
    {
      selector: 'edge.multi-edge',
      style: {
        'curve-style': 'unbundled-bezier',
        'control-point-distances': [40] as any,
        'control-point-weights': [0.5] as any,
      },
    },

    // Second parallel edge curves opposite direction
    {
      selector: 'edge.multi-edge-2',
      style: {
        'curve-style': 'unbundled-bezier',
        'control-point-distances': [-40] as any,
        'control-point-weights': [0.5] as any,
      },
    },

    // Third parallel edge (if present)
    {
      selector: 'edge.multi-edge-3',
      style: {
        'curve-style': 'unbundled-bezier',
        'control-point-distances': [80] as any,
        'control-point-weights': [0.5] as any,
      },
    },

    // ============================================
    // SELF-LOOP STYLES
    // ============================================
    {
      selector: 'edge[?selfLoop]',
      style: {
        'curve-style': 'bezier',
        'loop-direction': '45deg' as any,
        'loop-sweep': '-90deg' as any,
        'control-point-step-size': 50,
      },
    },

    // ============================================
    // PERFORMANCE MODE EDGE STYLES
    // ============================================
    // Haystack edges are straight lines that don't route around nodes
    {
      selector: 'edge.performance-mode',
      style: {
        'curve-style': 'haystack',
        'haystack-radius': 0.5,
        'line-opacity': 0.6,
        // Hide labels in performance mode
        'label': '',
        'target-arrow-shape': 'none',
      },
    },

    // ============================================
    // PROGRESSIVE DISCLOSURE STYLES
    // ============================================

    // Seed nodes (original query results) - distinctive double border
    {
      selector: 'node.seed-node',
      style: {
        'border-width': 4,
        'border-color': '#f59e0b',  // Amber
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
        'opacity': 0.8,
        'border-style': 'dotted',
      },
    },

    // Newly expanded nodes (animation state)
    {
      selector: 'node.newly-expanded',
      style: {
        'opacity': 0.3,
      },
    },

    // Collapsed neighbors (hidden but not removed)
    {
      selector: 'node.collapsed-neighbor',
      style: {
        'display': 'none',
      },
    },
    {
      selector: 'edge.collapsed-neighbor',
      style: {
        'display': 'none',
      },
    },

    // Depth indicator via opacity (farther = more faded)
    {
      selector: 'node[depth > 1]',
      style: {
        'opacity': 0.85,
      },
    },
    {
      selector: 'node[depth > 2]',
      style: {
        'opacity': 0.7,
      },
    },

    // ============================================
    // HOVER EFFECTS
    // ============================================
    {
      selector: 'node:active',
      style: {
        'overlay-opacity': 0.3,
      },
    },
    {
      selector: 'edge:active',
      style: {
        'overlay-opacity': 0.2,
        'width': 4,
      },
    },

    // ============================================
    // DIMMED STATE (for focusing on subset)
    // ============================================
    {
      selector: 'node.dimmed',
      style: {
        'opacity': 0.3,
      },
    },
    {
      selector: 'edge.dimmed',
      style: {
        'opacity': 0.15,
      },
    },

    // ============================================
    // FADED EDGES DURING PAN/ZOOM
    // ============================================
    {
      selector: 'edge.viewport-hidden',
      style: {
        'opacity': 0.2,
      },
    },
  ];
}

/**
 * Creates a minimal stylesheet for performance mode
 * Strips unnecessary styling for maximum render speed
 */
export function createPerformanceStylesheet(): StylesheetStyle[] {
  return [
    {
      selector: 'node',
      style: {
        'shape': 'ellipse',
        'width': 30,
        'height': 30,
        'background-color': (ele: any) => {
          const type = ele.data('type')?.toLowerCase() || 'unknown';
          return getEntityColor(type);
        },
        'border-width': 1,
        'border-color': '#2d3748',
        'label': '',
      } as any,
    },
    {
      selector: 'edge',
      style: {
        'width': 1,
        'line-color': '#a0aec0',
        'curve-style': 'haystack',
        'haystack-radius': 0.5,
        'line-opacity': 0.5,
        'target-arrow-shape': 'none',
      } as any,
    },
    {
      selector: 'node.selected',
      style: {
        'border-width': 3,
        'border-color': '#f56565',
        'width': 40,
        'height': 40,
      },
    },
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#68d391',
        'width': 2,
        'line-opacity': 1,
      },
    },
    {
      selector: '.hidden',
      style: {
        'display': 'none',
      },
    },
  ];
}

/**
 * Export default stylesheet
 */
export const defaultStylesheet = createStylesheet(true, true);
