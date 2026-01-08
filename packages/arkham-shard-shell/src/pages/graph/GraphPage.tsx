/**
 * GraphPage - Entity relationship graph visualization
 *
 * Provides interactive visualization of entity relationships and connections.
 * Uses react-force-graph-2d for physics-based graph rendering with advanced controls.
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import { Icon } from '../../components/common/Icon';
import { AIAnalystButton } from '../../components/AIAnalyst';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { useGraphSettings } from './hooks/useGraphSettings';
import { useUrlParams } from './hooks/useUrlParams';
import { GraphControls, DataSourcesPanel, LayoutModeControls, AssociationMatrix, MatrixControls, SankeyDiagram, SankeyControls } from './components';
import type { FlowData } from './components';
import { EgoMetricsPanel } from './components/EgoMetricsPanel';
import { fetchScores, type EntityScore } from './api';
import { getRelationshipStyle, extractRelationshipTypes } from './constants/relationshipStyles';
import './GraphPage.css';

// Types
interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  entity_type?: string;
  document_count?: number;
  metadata?: Record<string, unknown>;
  // Force graph properties
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  weight: number;
  type?: string;
  relationship_type?: string;
  co_occurrence_count?: number;
  metadata?: Record<string, unknown>;
}

interface GraphData {
  project_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

interface GraphStats {
  node_count: number;
  edge_count: number;
  avg_degree: number;
  density: number;
  diameter?: number;
  avg_clustering?: number;
}

interface PathResult {
  path_found: boolean;
  path_length: number;
  path: string[];
  edges: GraphEdge[];
  total_weight: number;
}

// Entity type colors
const ENTITY_TYPE_COLORS: Record<string, string> = {
  // Standard NER types
  person: '#4299e1',
  organization: '#48bb78',
  location: '#ed8936',
  event: '#9f7aea',
  document: '#f56565',
  date: '#38b2ac',
  cardinal: '#a0aec0',  // Numbers
  money: '#68d391',     // Currency
  percent: '#fc8181',   // Percentages
  time: '#63b3ed',      // Times
  quantity: '#b794f4',  // Quantities
  ordinal: '#f6ad55',   // Ordinal numbers
  gpe: '#ed8936',       // Geo-political entities (like location)
  norp: '#9f7aea',      // Nationalities, religious, political groups
  fac: '#f687b3',       // Facilities
  product: '#4fd1c5',   // Products
  law: '#fc8181',       // Laws
  work_of_art: '#fbb6ce', // Works of art
  language: '#90cdf4',  // Languages

  // Cross-shard node types
  claim: '#f59e0b',       // Claims shard - amber
  evidence: '#3b82f6',    // ACH evidence - blue
  hypothesis: '#8b5cf6',  // ACH hypothesis - purple
  artifact: '#10b981',    // Provenance artifact - emerald
  timeline_event: '#ec4899', // Timeline event - pink

  // Fallback
  other: '#718096',
  unknown: '#718096',
};

type TabId = 'graph' | 'matrix' | 'sankey' | 'controls' | 'sources';

export function GraphPage() {
  const { toast } = useToast();
  const graphRef = useRef<ForceGraphMethods | null>(null);
  const graphSettings = useGraphSettings();

  // State
  const [activeTab, setActiveTab] = useState<TabId>('graph');
  const [urlCopied, setUrlCopied] = useState(false);
  const [projectId, _setProjectId] = useState<string>('default');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(new Set());
  const [building, setBuilding] = useState(false);
  const [pathMode, setPathMode] = useState(false);
  const [pathStart, setPathStart] = useState<GraphNode | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [zoomLevel, setZoomLevel] = useState(1);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const hasInitialFit = useRef(false); // Track if initial zoomToFit has been done

  // Scoring state
  const [scores, setScores] = useState<Map<string, EntityScore>>(new Map());
  const [scoresLoading, setScoresLoading] = useState(false);
  const [scoresError, setScoresError] = useState<string | null>(null);

  // Layout calculation state
  const [layoutPositions, setLayoutPositions] = useState<Map<string, { x: number; y: number }>>(new Map());
  const [layoutCalculating, setLayoutCalculating] = useState(false);

  // Ego network focus mode state
  const [egoFocusEntity, setEgoFocusEntity] = useState<string | null>(null);
  const [showEgoPanel, setShowEgoPanel] = useState(false);

  // Matrix view state
  const [matrixSortBy, setMatrixSortBy] = useState<'alphabetical' | 'degree' | 'cluster' | 'type'>('degree');
  const [matrixColorScale, setMatrixColorScale] = useState<'linear' | 'log' | 'sqrt'>('sqrt');
  const [matrixCellSize, setMatrixCellSize] = useState(20);
  const [matrixShowLabels, setMatrixShowLabels] = useState(true);
  const [matrixRowType, setMatrixRowType] = useState('');
  const [matrixColType, setMatrixColType] = useState('');
  const [matrixBipartiteMode, setMatrixBipartiteMode] = useState(false);

  // Sankey view state
  const [sankeyFlowData, setSankeyFlowData] = useState<FlowData | null>(null);
  const [sankeyLoading, setSankeyLoading] = useState(false);
  const [sankeySourceTypes, setSankeySourceTypes] = useState<string[]>(['person']);
  const [sankeyTargetTypes, setSankeyTargetTypes] = useState<string[]>(['organization']);
  const [sankeyIntermediateTypes, setSankeyIntermediateTypes] = useState<string[]>([]);
  const [sankeyFlowType, setSankeyFlowType] = useState<'entity' | 'relationship'>('entity');
  const [sankeyAggregateByType, setSankeyAggregateByType] = useState(false);
  const [sankeyMinWeight, setSankeyMinWeight] = useState(0);
  const [sankeyMaxLinks, setSankeyMaxLinks] = useState(50);

  // Container ref for responsive sizing
  const containerRef = useRef<HTMLDivElement>(null);

  // Resize observer for responsive graph
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerSize({
          width: rect.width,
          height: rect.height,
        });
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Fetch graph data
  const { data: graphData, loading, error, refetch } = useFetch<GraphData>(
    `/api/graph/${projectId}`
  );

  // Fetch statistics
  const { data: stats, refetch: refetchStats } = useFetch<GraphStats>(
    `/api/graph/stats?project_id=${projectId}`
  );

  // Extract settings for easier access
  const { settings, normalizedWeights, updateFilters, updateScoring, updateLayout } = graphSettings;
  const { filters, labels, nodeSize, physics, layout, scoring } = settings;

  // URL params for shareable views
  const { copyShareableUrl } = useUrlParams(
    settings,
    updateFilters,
    updateScoring,
    activeTab,
    selectedNode?.id || undefined,
    (tab: string) => {
      if (tab === 'graph' || tab === 'matrix' || tab === 'sankey' || tab === 'controls' || tab === 'sources') {
        setActiveTab(tab as TabId);
      }
    },
    (nodeId) => {
      // Look up and select the node by ID
      if (nodeId && graphData) {
        const node = graphData.nodes.find(n => n.id === nodeId);
        if (node) setSelectedNode(node);
      } else {
        setSelectedNode(null);
      }
    }
  );

  // Handle share button click
  const handleShare = async () => {
    const success = await copyShareableUrl();
    if (success) {
      setUrlCopied(true);
      toast.success('Graph URL copied to clipboard');
      setTimeout(() => setUrlCopied(false), 2000);
    } else {
      toast.error('Failed to copy URL');
    }
  };

  // Fetch scores when scoring is enabled
  const loadScores = useCallback(async () => {
    if (!scoring.enabled || !graphData) return;

    setScoresLoading(true);
    setScoresError(null);

    try {
      const response = await fetchScores({
        project_id: projectId,
        centrality_type: scoring.centralityType,
        centrality_weight: normalizedWeights.centrality,
        frequency_weight: normalizedWeights.frequency,
        recency_weight: normalizedWeights.recency,
        credibility_weight: normalizedWeights.credibility,
        corroboration_weight: normalizedWeights.corroboration,
        recency_half_life_days: scoring.recencyHalfLifeDays,
        limit: 500,
      });

      // Build score map by entity_id
      const scoreMap = new Map<string, EntityScore>();
      response.scores.forEach(score => {
        scoreMap.set(score.entity_id, score);
      });
      setScores(scoreMap);
      toast.success(`Calculated scores for ${response.entity_count} entities`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to calculate scores';
      setScoresError(message);
      toast.error(message);
    } finally {
      setScoresLoading(false);
    }
  }, [scoring, projectId, normalizedWeights, graphData, toast]);

  // Auto-fetch scores when scoring is enabled or settings change
  useEffect(() => {
    if (scoring.enabled && graphData && graphData.nodes.length > 0) {
      loadScores();
    }
  }, [scoring.enabled, scoring.centralityType, graphData?.nodes.length]);

  // Transform data for force graph - properly memoized
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };

    // Map nodes with type normalization
    let nodes = graphData.nodes.map(node => ({
      ...node,
      type: node.entity_type || node.type || 'unknown',
    }));

    // Apply entity type filter
    if (filters.entityTypes.length > 0 && !filters.entityTypes.includes('__none__')) {
      nodes = nodes.filter(n => filters.entityTypes.includes(n.type));
    } else if (filters.entityTypes.includes('__none__')) {
      nodes = [];
    }

    // Apply degree filter
    nodes = nodes.filter(n => {
      const degree = n.degree || 0;
      return degree >= filters.minDegree && degree <= filters.maxDegree;
    });

    // Apply search filter
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      nodes = nodes.filter(n =>
        n.label?.toLowerCase().includes(query) ||
        n.id.toLowerCase().includes(query)
      );
    }

    // Apply document source filter
    if (filters.documentSources.length > 0) {
      nodes = nodes.filter(n => {
        // Check if node has any matching document source
        const nodeDocs = n.metadata?.document_ids as string[] | undefined;
        return nodeDocs?.some(doc => filters.documentSources.includes(doc));
      });
    }

    // Apply max nodes limit - sort by importance and take top N
    if (filters.maxNodes > 0 && nodes.length > filters.maxNodes) {
      // Sort by importance (degree + document count)
      nodes.sort((a, b) => {
        const scoreA = (a.degree || 0) * 2 + (a.document_count || 0);
        const scoreB = (b.degree || 0) * 2 + (b.document_count || 0);
        return scoreB - scoreA;
      });
      nodes = nodes.slice(0, filters.maxNodes);
    }

    const nodeIds = new Set(nodes.map(n => n.id));

    // Filter and transform edges to links
    const links = graphData.edges
      .filter(edge => {
        const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id;
        const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id;

        // Node and weight filter
        if (!nodeIds.has(sourceId) || !nodeIds.has(targetId)) return false;
        if (edge.weight < filters.minEdgeWeight) return false;

        // Relationship type filter
        if (filters.relationshipTypes.length > 0) {
          const edgeType = (edge.relationship_type || edge.type || 'related').toLowerCase().replace(/-/g, '_');
          if (!filters.relationshipTypes.includes(edgeType)) return false;
        }

        return true;
      })
      .map(edge => ({
        source: typeof edge.source === 'string' ? edge.source : edge.source.id,
        target: typeof edge.target === 'string' ? edge.target : edge.target.id,
        weight: edge.weight,
        type: edge.relationship_type || edge.type || 'related',
        relationship_type: edge.relationship_type || edge.type || 'related',
        co_occurrence_count: edge.co_occurrence_count || 0,
      }));

    return { nodes, links };
  }, [graphData, filters]);

  // Calculate node importance scores for label visibility
  const nodeImportance = useMemo(() => {
    const nodes = forceGraphData.nodes;
    if (nodes.length === 0) return new Map<string, number>();

    // Calculate max degree for normalization
    const maxDegree = Math.max(...nodes.map(n => n.degree || 1));

    // Create importance map
    const importance = new Map<string, number>();
    nodes.forEach(node => {
      const degree = node.degree || 0;
      const docCount = node.document_count || 1;
      // Simple importance: weighted combination of degree and document count
      const score = (degree / maxDegree) * 0.7 + (Math.min(docCount, 10) / 10) * 0.3;
      importance.set(node.id, score);
    });

    return importance;
  }, [forceGraphData.nodes]);

  // Get top N% of nodes by importance
  const topNodes = useMemo(() => {
    if (labels.mode !== 'top') return new Set<string>();

    const entries = Array.from(nodeImportance.entries());
    entries.sort((a, b) => b[1] - a[1]);

    const topCount = Math.max(1, Math.ceil(entries.length * (labels.topPercent / 100)));
    return new Set(entries.slice(0, topCount).map(([id]) => id));
  }, [nodeImportance, labels.mode, labels.topPercent]);

  // Level-of-detail settings based on node count for performance
  const lodSettings = useMemo(() => {
    const nodeCount = forceGraphData.nodes.length;
    return {
      // Disable directional particles for large graphs
      showDirectionalParticles: nodeCount < 200,
      // Reduce particle count for medium graphs
      particleCount: nodeCount < 100 ? 2 : nodeCount < 300 ? 1 : 0,
      // Simplify link rendering for very large graphs
      simplifyLinks: nodeCount >= 500,
      // Skip text backgrounds for large graphs
      showTextBackgrounds: nodeCount < 300,
      // Reduce cooldown ticks for large graphs
      cooldownTicks: nodeCount < 200 ? 100 : nodeCount < 500 ? 50 : 30,
      // Reduce physics precision for very large graphs
      warmupTicks: nodeCount < 200 ? 0 : nodeCount < 500 ? 100 : 200,
    };
  }, [forceGraphData.nodes.length]);

  // Build graph with data sources
  const buildGraph = async () => {
    setBuilding(true);
    try {
      const { dataSources } = settings;
      // Determine if any documents are selected
      const hasDocuments = (dataSources.selectedDocumentIds === null || (dataSources.selectedDocumentIds && dataSources.selectedDocumentIds.length > 0)) || dataSources.documentEntities;

      const response = await fetch('/api/graph/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          min_co_occurrence: 1,
          // Primary data sources
          include_document_entities: hasDocuments,
          include_cooccurrences: dataSources.entityCooccurrences,
          // Specific documents to include (empty = all)
          document_ids: dataSources.selectedDocumentIds,  // null = all, [] = none, [...] = specific
          // Cross-shard node sources
          include_temporal: dataSources.timelineEvents,
          include_claims: dataSources.claims,
          include_ach_evidence: dataSources.achEvidence,
          include_ach_hypotheses: dataSources.achHypotheses,
          include_provenance_artifacts: dataSources.provenanceArtifacts,
          // Cross-shard edge sources
          include_contradictions: dataSources.contradictions,
          include_patterns: dataSources.patterns,
          // Weight modifiers
          apply_credibility_weights: dataSources.credibilityRatings,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to build graph');
      }

      const result = await response.json();

      // Build detailed success message
      let message = `Graph built: ${result.node_count} nodes, ${result.edge_count} edges`;
      if (result.cross_shard_nodes_added > 0 || result.cross_shard_edges_added > 0) {
        message += ` (+${result.cross_shard_nodes_added} cross-shard nodes, +${result.cross_shard_edges_added} edges)`;
      }
      toast.success(message);

      refetch();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build graph');
    } finally {
      setBuilding(false);
    }
  };

  // Calculate layout positions from server
  const calculateLayout = async () => {
    if (layout.layoutType === 'force') {
      // Force layout is handled by frontend
      setLayoutPositions(new Map());
      return;
    }

    setLayoutCalculating(true);
    try {
      const response = await fetch('/api/graph/layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          layout_type: layout.layoutType,
          root_node_id: layout.rootNodeId,
          direction: layout.direction,
          layer_spacing: layout.layerSpacing,
          node_spacing: layout.nodeSpacing,
          radius: layout.radius,
          radius_step: layout.radiusStep,
          left_types: layout.leftTypes,
          right_types: layout.rightTypes,
          columns: layout.gridColumns,
          cell_width: layout.cellWidth,
          cell_height: layout.cellHeight,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to calculate layout');
      }

      const result = await response.json();

      // Convert positions to Map
      const positions = new Map<string, { x: number; y: number }>();
      for (const [nodeId, pos] of Object.entries(result.positions)) {
        const { x, y } = pos as { x: number; y: number };
        positions.set(nodeId, { x, y });
      }

      setLayoutPositions(positions);
      toast.success(`${layout.layoutType} layout applied (${result.calculation_time_ms.toFixed(0)}ms)`);

      // Apply positions to graph nodes
      if (graphRef.current && positions.size > 0) {
        // Get the current graph data
        const fg = graphRef.current;

        // Center offset to place graph in middle of viewport
        const centerX = containerSize.width / 2;
        const centerY = containerSize.height / 2;

        // Apply fixed positions
        forceGraphData.nodes.forEach((node) => {
          const pos = positions.get(node.id);
          if (pos) {
            node.fx = pos.x + centerX;
            node.fy = pos.y + centerY;
          }
        });

        // Reheat to apply positions
        fg.d3ReheatSimulation?.();

        // Zoom to fit after applying
        setTimeout(() => {
          fg.zoomToFit?.(400, 50);
        }, 100);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to calculate layout');
    } finally {
      setLayoutCalculating(false);
    }
  };

  // Clear fixed positions (return to force layout)
  const clearLayoutPositions = useCallback(() => {
    setLayoutPositions(new Map());
    forceGraphData.nodes.forEach((node) => {
      node.fx = null;
      node.fy = null;
    });
    if (graphRef.current) {
      graphRef.current.d3ReheatSimulation?.();
    }
  }, [forceGraphData.nodes]);

  // Reset positions when switching to force layout
  useEffect(() => {
    if (layout.layoutType === 'force' && layoutPositions.size > 0) {
      clearLayoutPositions();
    }
  }, [layout.layoutType, layoutPositions.size, clearLayoutPositions]);

  // Find path between two nodes
  const findPath = async (sourceId: string, targetId: string) => {
    try {
      const response = await fetch('/api/graph/path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          source_entity_id: sourceId,
          target_entity_id: targetId,
          max_depth: 6,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to find path');
      }

      const result: PathResult = await response.json();
      if (result.path_found) {
        toast.success(`Path found: ${result.path_length} hops`);
        // Highlight the path
        setHighlightedPath(new Set(result.path));
      } else {
        toast.info('No path found between entities');
        setHighlightedPath(new Set());
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to find path');
    }
  };

  // Export graph
  const exportGraph = async (format: string) => {
    try {
      const response = await fetch('/api/graph/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          format: format,
          include_metadata: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to export graph');
      }

      const result = await response.json();

      // Create download
      const blob = new Blob([result.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `graph_${projectId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast.success(`Graph exported as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export graph');
    }
  };

  // Handle node click
  const handleNodeClick = useCallback((node: GraphNode) => {
    if (pathMode) {
      if (!pathStart) {
        setPathStart(node);
        toast.info(`Start: ${node.label}. Click another node to find path.`);
      } else {
        findPath(pathStart.id, node.id);
        setPathStart(null);
        setPathMode(false);
      }
    } else {
      setSelectedNode(node);
      // Zoom to node
      graphRef.current?.centerAt(node.x, node.y, 500);
      graphRef.current?.zoom(2, 500);
    }
  }, [pathMode, pathStart, projectId]);

  // Handle node right-click (context menu)
  const handleNodeRightClick = useCallback((node: GraphNode) => {
    // Could show context menu here
    setSelectedNode(node);
  }, []);

  // Get connected nodes
  const getConnectedNodes = useCallback((nodeId: string): GraphNode[] => {
    if (!graphData) return [];

    const connectedIds = new Set<string>();
    graphData.edges.forEach(edge => {
      const sourceId = typeof edge.source === 'string' ? edge.source : edge.source.id;
      const targetId = typeof edge.target === 'string' ? edge.target : edge.target.id;
      if (sourceId === nodeId) connectedIds.add(targetId);
      if (targetId === nodeId) connectedIds.add(sourceId);
    });

    return graphData.nodes.filter(node => connectedIds.has(node.id));
  }, [graphData]);

  // Get unique entity types for filter
  const entityTypes = useMemo(() => {
    if (!graphData) return [];
    return Array.from(new Set(graphData.nodes.map(n => n.entity_type || n.type || 'unknown')));
  }, [graphData]);

  // Get unique relationship types for filter
  const relationshipTypes = useMemo(() => {
    if (!graphData) return [];
    return extractRelationshipTypes(graphData.edges);
  }, [graphData]);

  // Calculate node radius based on settings
  const getNodeRadius = useCallback((node: GraphNode): number => {
    const { minRadius, maxRadius, sizeBy } = nodeSize;

    if (sizeBy === 'uniform') {
      return (minRadius + maxRadius) / 2;
    }

    let value = 0;
    let maxValue = 1;

    switch (sizeBy) {
      case 'degree':
        value = node.degree || 0;
        maxValue = Math.max(...forceGraphData.nodes.map(n => n.degree || 1));
        break;
      case 'document_count':
        value = node.document_count || 0;
        maxValue = Math.max(...forceGraphData.nodes.map(n => n.document_count || 1));
        break;
      case 'composite':
        // Use composite score if available
        if (scoring.enabled && scores.size > 0) {
          const entityScore = scores.get(node.id);
          value = entityScore?.composite_score || 0;
          maxValue = Math.max(...Array.from(scores.values()).map(s => s.composite_score || 1));
        } else {
          // Fall back to degree if scores not available
          value = node.degree || 0;
          maxValue = Math.max(...forceGraphData.nodes.map(n => n.degree || 1));
        }
        break;
      case 'pagerank':
        // Use centrality score if available
        if (scoring.enabled && scores.size > 0) {
          const entityScore = scores.get(node.id);
          value = entityScore?.centrality_score || 0;
          maxValue = 1; // Already normalized
        } else {
          value = node.degree || 0;
          maxValue = Math.max(...forceGraphData.nodes.map(n => n.degree || 1));
        }
        break;
      case 'betweenness':
        // Use centrality score if available (with betweenness type)
        if (scoring.enabled && scores.size > 0 && scoring.centralityType === 'betweenness') {
          const entityScore = scores.get(node.id);
          value = entityScore?.centrality_score || 0;
          maxValue = 1;
        } else {
          value = node.degree || 0;
          maxValue = Math.max(...forceGraphData.nodes.map(n => n.degree || 1));
        }
        break;
      default:
        // Default to degree
        value = node.degree || 0;
        maxValue = Math.max(...forceGraphData.nodes.map(n => n.degree || 1));
    }

    const normalized = maxValue > 0 ? value / maxValue : 0;
    return minRadius + normalized * (maxRadius - minRadius);
  }, [nodeSize, forceGraphData.nodes, scoring.enabled, scores]);

  // Determine if label should be shown for a node
  const shouldShowLabel = useCallback((node: GraphNode, globalScale: number): boolean => {
    const isSelected = selectedNode?.id === node.id;
    const isInPath = highlightedPath.has(node.id);
    const isPathStart = pathStart?.id === node.id;

    // Always show for selected/highlighted nodes
    if (isSelected || isInPath || isPathStart) return true;

    switch (labels.mode) {
      case 'all':
        return true;
      case 'top':
        return topNodes.has(node.id);
      case 'zoom':
        return globalScale >= labels.zoomThreshold;
      case 'selected':
        // Show for selected node and its neighbors
        if (!selectedNode) return false;
        if (node.id === selectedNode.id) return true;
        // Check if node is a neighbor of selected
        return forceGraphData.links.some(link => {
          const sourceId = typeof link.source === 'string' ? link.source : (link.source as GraphNode).id;
          const targetId = typeof link.target === 'string' ? link.target : (link.target as GraphNode).id;
          return (sourceId === selectedNode.id && targetId === node.id) ||
                 (targetId === selectedNode.id && sourceId === node.id);
        });
      default:
        return false;
    }
  }, [labels, selectedNode, highlightedPath, pathStart, topNodes, forceGraphData.links]);

  // Node canvas rendering
  const nodeCanvasObject = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.label || node.id;
    const fontSize = Math.max(labels.fontSize / globalScale, 4);
    const nodeColor = ENTITY_TYPE_COLORS[node.type?.toLowerCase() || 'unknown'] || ENTITY_TYPE_COLORS.unknown;

    // Node size from settings
    const radius = getNodeRadius(node);

    // Highlight if selected or in path
    const isSelected = selectedNode?.id === node.id;
    const isInPath = highlightedPath.has(node.id);
    const isPathStart = pathStart?.id === node.id;

    // Draw node circle
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);

    // Fill
    ctx.fillStyle = isPathStart ? '#f6e05e' : isInPath ? '#68d391' : isSelected ? '#f56565' : nodeColor;
    ctx.fill();

    // Border
    if (isSelected || isInPath || isPathStart) {
      ctx.strokeStyle = isPathStart ? '#d69e2e' : isInPath ? '#38a169' : '#c53030';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Draw label based on visibility settings
    if (shouldShowLabel(node, globalScale)) {
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      // Background for text (skip for large graphs for performance)
      if (lodSettings.showTextBackgrounds) {
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.fillRect(
          node.x! - textWidth / 2 - 2,
          node.y! + radius + 2,
          textWidth + 4,
          fontSize + 2
        );
      }

      ctx.fillStyle = '#1a202c';
      ctx.fillText(label, node.x!, node.y! + radius + 3);
    }
  }, [selectedNode, highlightedPath, pathStart, labels.fontSize, getNodeRadius, shouldShowLabel, lodSettings.showTextBackgrounds]);

  // Calculate max edge weight for opacity normalization
  const maxEdgeWeight = useMemo(() => {
    if (!forceGraphData.links.length) return 1;
    return Math.max(...forceGraphData.links.map(l => l.weight || 0), 1);
  }, [forceGraphData.links]);

  // Link rendering - color based on relationship type with weight-based opacity
  const linkColor = useCallback((link: GraphEdge): string => {
    const sourceId = typeof link.source === 'string' ? link.source : (link.source as GraphNode).id;
    const targetId = typeof link.target === 'string' ? link.target : (link.target as GraphNode).id;

    // Highlighted path takes precedence
    if (highlightedPath.has(sourceId) && highlightedPath.has(targetId)) {
      return '#68d391'; // Green for path
    }

    // Get relationship type style
    const relType = link.relationship_type || link.type;
    const style = getRelationshipStyle(relType);

    // Calculate opacity based on weight (stronger = more opaque)
    // Range from 30% (weak) to 100% (strong)
    const normalizedWeight = Math.min((link.weight || 0) / maxEdgeWeight, 1);
    const opacity = Math.round(0.3 + normalizedWeight * 0.7); // 0.3 to 1.0
    const opacityHex = Math.round(opacity * 255).toString(16).padStart(2, '0');

    return style.color + opacityHex;
  }, [highlightedPath, maxEdgeWeight]);

  const linkWidth = useCallback((link: GraphEdge): number => {
    const sourceId = typeof link.source === 'string' ? link.source : (link.source as GraphNode).id;
    const targetId = typeof link.target === 'string' ? link.target : (link.target as GraphNode).id;

    if (highlightedPath.has(sourceId) && highlightedPath.has(targetId)) {
      return 3;
    }

    // Get relationship type style for width multiplier
    const relType = link.relationship_type || link.type;
    const style = getRelationshipStyle(relType);
    const widthMultiplier = style.width || 1;

    return Math.max(0.5, link.weight * 2 * widthMultiplier);
  }, [highlightedPath]);

  // Reset view
  const resetView = () => {
    graphRef.current?.zoomToFit(400, 50);
    setSelectedNode(null);
    setHighlightedPath(new Set());
    setPathStart(null);
    setPathMode(false);
  };

  // Toggle path mode
  const togglePathMode = () => {
    if (pathMode) {
      setPathMode(false);
      setPathStart(null);
      setHighlightedPath(new Set());
    } else {
      setPathMode(true);
      setSelectedNode(null);
      toast.info('Click on a starting node');
    }
  };

  // Handle ego focus mode
  const handleEgoFocus = useCallback((entityId: string) => {
    setEgoFocusEntity(entityId);
    setShowEgoPanel(true);
    toast.info(`Focused on ${selectedNode?.label || entityId}`);
  }, [selectedNode?.label]);

  // Clear ego focus
  const clearEgoFocus = useCallback(() => {
    setEgoFocusEntity(null);
    setShowEgoPanel(false);
  }, []);

  // Load Sankey flow data
  const loadSankeyFlows = useCallback(async () => {
    setSankeyLoading(true);
    try {
      const response = await fetch('/api/graph/flows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          flow_type: sankeyFlowType,
          source_types: sankeySourceTypes,
          target_types: sankeyTargetTypes,
          intermediate_types: sankeyIntermediateTypes,
          min_weight: sankeyMinWeight,
          aggregate_by_type: sankeyAggregateByType,
          max_links: sankeyMaxLinks,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to load flow data');
      }

      const flowData = await response.json();
      setSankeyFlowData(flowData);
      toast.success(`Loaded ${flowData.node_count} nodes, ${flowData.link_count} flows`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load flows');
      setSankeyFlowData(null);
    } finally {
      setSankeyLoading(false);
    }
  }, [projectId, sankeyFlowType, sankeySourceTypes, sankeyTargetTypes, sankeyIntermediateTypes, sankeyMinWeight, sankeyAggregateByType, sankeyMaxLinks, toast]);

  // Handle clicking an alter in the ego panel
  const handleAlterClick = useCallback((alterId: string) => {
    // Find the node and select it
    const alterNode = forceGraphData.nodes.find(n => n.id === alterId);
    if (alterNode) {
      setSelectedNode(alterNode);
      // Center on the alter
      graphRef.current?.centerAt(alterNode.x, alterNode.y, 500);
      graphRef.current?.zoom(2, 500);
    }
  }, [forceGraphData.nodes]);

  return (
    <div className="graph-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Network" size={28} />
          <div>
            <h1>Graph</h1>
            <p className="page-description">Visualize entity relationships and connections</p>
          </div>
        </div>

        <div className="graph-actions">
          <button
            className="btn btn-secondary"
            onClick={buildGraph}
            disabled={building}
          >
            {building ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Building...
              </>
            ) : (
              <>
                <Icon name="GitBranch" size={16} />
                Build Graph
              </>
            )}
          </button>
          <button
            className={`btn ${pathMode ? 'btn-primary' : 'btn-secondary'}`}
            onClick={togglePathMode}
            disabled={!graphData}
          >
            <Icon name="Route" size={16} />
            {pathMode ? 'Cancel Path' : 'Find Path'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={resetView}
            disabled={!graphData}
          >
            <Icon name="Maximize" size={16} />
            Reset View
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => exportGraph('json')}
            disabled={!graphData}
          >
            <Icon name="Download" size={16} />
            Export
          </button>
          <button
            className={`btn ${urlCopied ? 'btn-primary' : 'btn-secondary'}`}
            onClick={handleShare}
            disabled={!graphData}
            title="Copy shareable URL to clipboard"
          >
            <Icon name={urlCopied ? 'Check' : 'Share2'} size={16} />
            {urlCopied ? 'Copied!' : 'Share'}
          </button>
          <AIAnalystButton
            shard="graph"
            targetId={selectedNode?.id || 'overview'}
            context={{
              stats: stats ? {
                node_count: stats.node_count,
                edge_count: stats.edge_count,
                avg_degree: stats.avg_degree,
                density: stats.density,
              } : null,
              visible_nodes: forceGraphData.nodes.length,
              visible_edges: forceGraphData.links.length,
              selected_node: selectedNode ? {
                id: selectedNode.id,
                label: selectedNode.label,
                type: selectedNode.type || selectedNode.entity_type,
                degree: selectedNode.degree,
              } : null,
              relationship_types: Array.from(relationshipTypes),
              entity_types: Array.from(entityTypes),
              project_id: projectId,
            }}
            disabled={!graphData}
          />
        </div>
      </header>

      {/* Statistics Bar */}
      {stats && (
        <div className="graph-stats">
          <div className="stat-item">
            <Icon name="Circle" size={16} />
            <span className="stat-label">Nodes:</span>
            <span className="stat-value">{forceGraphData.nodes.length} / {stats.node_count}</span>
          </div>
          <div className="stat-item">
            <Icon name="Minus" size={16} />
            <span className="stat-label">Edges:</span>
            <span className="stat-value">{forceGraphData.links.length} / {stats.edge_count}</span>
          </div>
          <div className="stat-item">
            <Icon name="GitBranch" size={16} />
            <span className="stat-label">Avg Degree:</span>
            <span className="stat-value">{stats.avg_degree.toFixed(2)}</span>
          </div>
          <div className="stat-item">
            <Icon name="Percent" size={16} />
            <span className="stat-label">Density:</span>
            <span className="stat-value">{(stats.density * 100).toFixed(2)}%</span>
          </div>
          <div className="stat-item">
            <Icon name="ZoomIn" size={16} />
            <span className="stat-label">Zoom:</span>
            <span className="stat-value">{zoomLevel.toFixed(1)}x</span>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="graph-tabs">
        <button
          className={`graph-tab ${activeTab === 'graph' ? 'active' : ''}`}
          onClick={() => setActiveTab('graph')}
        >
          <Icon name="Network" size={16} />
          Graph View
        </button>
        <button
          className={`graph-tab ${activeTab === 'matrix' ? 'active' : ''}`}
          onClick={() => setActiveTab('matrix')}
        >
          <Icon name="Grid3X3" size={16} />
          Matrix View
        </button>
        <button
          className={`graph-tab ${activeTab === 'sankey' ? 'active' : ''}`}
          onClick={() => setActiveTab('sankey')}
        >
          <Icon name="GitBranch" size={16} />
          Sankey View
        </button>
        <button
          className={`graph-tab ${activeTab === 'controls' ? 'active' : ''}`}
          onClick={() => setActiveTab('controls')}
        >
          <Icon name="Sliders" size={16} />
          Controls
        </button>
        <button
          className={`graph-tab ${activeTab === 'sources' ? 'active' : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          <Icon name="Database" size={16} />
          Data Sources
        </button>
      </div>

      <div className="graph-layout">
        {/* Sidebar - content changes based on tab */}
        <aside className={`graph-sidebar ${(activeTab !== 'graph' && activeTab !== 'matrix' && activeTab !== 'sankey') ? 'wide' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
          {/* Collapse toggle button */}
          <button
            className="sidebar-collapse-toggle"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <Icon name={sidebarCollapsed ? 'ChevronRight' : 'ChevronLeft'} size={16} />
          </button>

          {/* Sidebar content - hidden when collapsed */}
          <div className="sidebar-content">
          {activeTab === 'sankey' ? (
            <SankeyControls
              entityTypes={entityTypes}
              sourceTypes={sankeySourceTypes}
              onSourceTypesChange={setSankeySourceTypes}
              targetTypes={sankeyTargetTypes}
              onTargetTypesChange={setSankeyTargetTypes}
              intermediateTypes={sankeyIntermediateTypes}
              onIntermediateTypesChange={setSankeyIntermediateTypes}
              flowType={sankeyFlowType}
              onFlowTypeChange={setSankeyFlowType}
              aggregateByType={sankeyAggregateByType}
              onAggregateByTypeChange={setSankeyAggregateByType}
              minWeight={sankeyMinWeight}
              onMinWeightChange={setSankeyMinWeight}
              maxLinks={sankeyMaxLinks}
              onMaxLinksChange={setSankeyMaxLinks}
              onRefresh={loadSankeyFlows}
              isLoading={sankeyLoading}
            />
          ) : activeTab === 'matrix' ? (
            <MatrixControls
              sortBy={matrixSortBy}
              onSortByChange={setMatrixSortBy}
              colorScale={matrixColorScale}
              onColorScaleChange={setMatrixColorScale}
              cellSize={matrixCellSize}
              onCellSizeChange={setMatrixCellSize}
              showLabels={matrixShowLabels}
              onShowLabelsChange={setMatrixShowLabels}
              entityTypes={entityTypes}
              rowEntityType={matrixRowType}
              onRowEntityTypeChange={setMatrixRowType}
              colEntityType={matrixColType}
              onColEntityTypeChange={setMatrixColType}
              bipartiteMode={matrixBipartiteMode}
              onBipartiteModeChange={setMatrixBipartiteMode}
            />
          ) : activeTab === 'controls' ? (
            <>
              <LayoutModeControls
                settings={layout}
                onChange={updateLayout}
                selectedNodeId={selectedNode?.id}
                entityTypes={entityTypes}
                onApplyLayout={calculateLayout}
                isCalculating={layoutCalculating}
              />
              <GraphControls
                graphSettings={graphSettings}
                availableEntityTypes={entityTypes}
                availableRelationshipTypes={relationshipTypes}
                onRecalculateScores={loadScores}
                scoresLoading={scoresLoading}
                scoresError={scoresError}
                isForceLayout={layout.layoutType === 'force'}
              />
            </>
          ) : activeTab === 'sources' ? (
            <DataSourcesPanel
              settings={graphSettings.settings.dataSources}
              onChange={graphSettings.updateDataSources}
              onRefresh={() => {
                // Rebuild graph with new data sources
                buildGraph();
              }}
              isLoading={building}
            />
          ) : (
            <>
              {/* Entity Legend */}
              <div className="sidebar-section">
                <h3>Entity Types</h3>
                <div className="legend-items">
                  {entityTypes.filter(t => !['claim', 'evidence', 'hypothesis', 'artifact', 'timeline_event'].includes(t?.toLowerCase())).map(type => (
                    <div key={type} className="legend-item">
                      <div
                        className="legend-color"
                        style={{ backgroundColor: ENTITY_TYPE_COLORS[type?.toLowerCase() || 'unknown'] || ENTITY_TYPE_COLORS.unknown }}
                      />
                      <span className="legend-label">{type}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Cross-Shard Legend - only show if any cross-shard types are present */}
              {entityTypes.some(t => ['claim', 'evidence', 'hypothesis', 'artifact', 'timeline_event'].includes(t?.toLowerCase())) && (
                <div className="sidebar-section">
                  <h3>Cross-Shard Data</h3>
                  <div className="legend-items">
                    {[
                      { type: 'claim', label: 'Claims', shard: 'Claims' },
                      { type: 'evidence', label: 'Evidence', shard: 'ACH' },
                      { type: 'hypothesis', label: 'Hypotheses', shard: 'ACH' },
                      { type: 'artifact', label: 'Artifacts', shard: 'Provenance' },
                      { type: 'timeline_event', label: 'Events', shard: 'Timeline' },
                    ]
                      .filter(({ type }) => entityTypes.some(t => t?.toLowerCase() === type))
                      .map(({ type, label, shard }) => (
                        <div key={type} className="legend-item">
                          <div
                            className="legend-color"
                            style={{ backgroundColor: ENTITY_TYPE_COLORS[type] }}
                          />
                          <span className="legend-label">{label}</span>
                          <span className="legend-hint" style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>{shard}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {pathMode && (
                <div className="sidebar-section path-mode-info">
                  <h3>Path Finding</h3>
                  <p>{pathStart ? `Start: ${pathStart.label}` : 'Click a start node'}</p>
                  <p>Then click a destination node</p>
                </div>
              )}

              {selectedNode && (
                <div className="sidebar-section">
                  <h3>Node Details</h3>
                  <div className="node-details">
                    <div className="detail-item">
                      <span className="detail-label">ID:</span>
                      <span className="detail-value">{selectedNode.id}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Label:</span>
                      <span className="detail-value">{selectedNode.label}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Type:</span>
                      <span className="detail-value">{selectedNode.type}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Degree:</span>
                      <span className="detail-value">{selectedNode.degree}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Documents:</span>
                      <span className="detail-value">{selectedNode.document_count || 0}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Connections:</span>
                      <span className="detail-value">
                        {getConnectedNodes(selectedNode.id).length}
                      </span>
                    </div>
                  </div>
                  <button
                    className={`btn btn-sm ${egoFocusEntity === selectedNode.id ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleEgoFocus(selectedNode.id)}
                    style={{ marginTop: '0.75rem', width: '100%' }}
                  >
                    <Icon name="Target" size={14} />
                    {egoFocusEntity === selectedNode.id ? 'Focused' : 'Focus (Ego Network)'}
                  </button>
                  <div style={{ marginTop: '0.5rem', width: '100%' }}>
                    <AIAnalystButton
                      shard="graph"
                      targetId={selectedNode.id}
                      context={{
                        selected_item: {
                          id: selectedNode.id,
                          label: selectedNode.label,
                          type: selectedNode.type,
                          degree: selectedNode.degree,
                          document_count: selectedNode.document_count,
                        },
                        related_items: getConnectedNodes(selectedNode.id).map(n => ({
                          id: n.id,
                          label: n.label,
                          type: n.type,
                          degree: n.degree,
                        })),
                        statistics: stats ? {
                          total_nodes: stats.node_count,
                          total_edges: stats.edge_count,
                          avg_degree: stats.avg_degree,
                          density: stats.density,
                        } : {},
                        filters_applied: filters,
                      }}
                      label="AI Analysis"
                      variant="secondary"
                      size="sm"
                    />
                  </div>
                </div>
              )}

              {/* Quick tip */}
              <div className="sidebar-section">
                <h3>Tips</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
                  Click the <strong>Controls</strong> tab to adjust label visibility, node sizing, physics, and filtering.
                </p>
              </div>
            </>
          )}
          </div>
        </aside>

        {/* Graph Visualization Area */}
        <main className="graph-content" ref={containerRef}>
          {/* Ego Network Panel */}
          {showEgoPanel && (
            <div className="ego-panel-container">
              <EgoMetricsPanel
                entityId={egoFocusEntity}
                entityName={selectedNode?.label}
                projectId={projectId}
                onClose={clearEgoFocus}
                onAlterClick={handleAlterClick}
              />
            </div>
          )}

          {/* Matrix View */}
          {activeTab === 'matrix' && (
            <div className="matrix-view-container">
              {loading ? (
                <div className="graph-loading">
                  <Icon name="Loader2" size={48} className="spin" />
                  <span>Loading data...</span>
                </div>
              ) : error ? (
                <div className="graph-error">
                  <Icon name="AlertCircle" size={48} />
                  <span>Failed to load data</span>
                  <button className="btn btn-secondary" onClick={() => refetch()}>
                    Retry
                  </button>
                </div>
              ) : forceGraphData.nodes.length > 0 ? (
                <AssociationMatrix
                  nodes={forceGraphData.nodes}
                  edges={forceGraphData.links}
                  sortBy={matrixSortBy}
                  colorScale={matrixColorScale}
                  cellSize={matrixCellSize}
                  showLabels={matrixShowLabels}
                  rowEntityType={matrixRowType}
                  colEntityType={matrixColType}
                  bipartiteMode={matrixBipartiteMode}
                  bipartiteRowType={matrixRowType}
                  bipartiteColType={matrixColType}
                  onCellClick={(rowId, colId) => {
                    // Highlight both nodes in graph view
                    setHighlightedPath(new Set([rowId, colId]));
                    toast.info(`Connection: ${rowId} - ${colId}`);
                  }}
                  onNodeClick={(nodeId) => {
                    const node = forceGraphData.nodes.find(n => n.id === nodeId);
                    if (node) {
                      setSelectedNode(node);
                      setActiveTab('graph');
                    }
                  }}
                  highlightedNodes={highlightedPath}
                />
              ) : (
                <div className="matrix-empty">
                  <Icon name="Grid3X3" size={64} />
                  <h3>No Data</h3>
                  <p>Build a graph to view the association matrix</p>
                  <button className="btn btn-primary" onClick={buildGraph}>
                    <Icon name="GitBranch" size={16} />
                    Build Graph
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Sankey View */}
          {activeTab === 'sankey' && (
            <div className="sankey-view-container">
              <SankeyDiagram
                flowData={sankeyFlowData}
                width={containerSize.width - 40}
                height={containerSize.height - 40}
                onNodeClick={(nodeId) => {
                  const node = forceGraphData.nodes.find(n => n.id === nodeId);
                  if (node) {
                    setSelectedNode(node);
                    setActiveTab('graph');
                    graphRef.current?.centerAt(node.x, node.y, 500);
                  }
                }}
                onLinkClick={(source, target) => {
                  setHighlightedPath(new Set([source, target]));
                  toast.info(`Flow: ${source} → ${target}`);
                }}
                highlightedNodes={highlightedPath}
                isLoading={sankeyLoading}
              />
            </div>
          )}

          {/* Graph View */}
          {activeTab !== 'matrix' && activeTab !== 'sankey' && loading ? (
            <div className="graph-loading">
              <Icon name="Loader2" size={48} className="spin" />
              <span>Loading graph...</span>
            </div>
          ) : activeTab !== 'matrix' && activeTab !== 'sankey' && error ? (
            <div className="graph-error">
              <Icon name="AlertCircle" size={48} />
              <span>Failed to load graph</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : activeTab !== 'matrix' && activeTab !== 'sankey' && forceGraphData.nodes.length > 0 ? (
            <div className="graph-visualization">
              <ForceGraph2D
                graphData={forceGraphData}
                width={containerSize.width}
                height={containerSize.height}
                nodeId="id"
                nodeLabel={node => `${node.label} (${node.type})`}
                nodeCanvasObject={nodeCanvasObject}
                nodePointerAreaPaint={(node, color, ctx) => {
                  ctx.fillStyle = color;
                  ctx.beginPath();
                  const radius = getNodeRadius(node as GraphNode);
                  ctx.arc(node.x!, node.y!, radius + 4, 0, 2 * Math.PI);
                  ctx.fill();
                }}
                // Physics settings from controls (only apply for force layout)
                d3AlphaDecay={layout.layoutType === 'force' ? physics.alphaDecay : 0.1}
                d3VelocityDecay={0.4}
                onZoom={({ k }) => setZoomLevel(k)}
                // Apply physics simulation settings
                ref={(fg: ForceGraphMethods | null) => {
                  if (fg) {
                    // Store ref for other operations
                    (graphRef as any).current = fg;
                    // Apply force simulation settings (only for force layout)
                    if (layout.layoutType === 'force') {
                      fg.d3Force('charge')?.strength(physics.chargeStrength);
                      fg.d3Force('link')
                        ?.distance(physics.linkDistance)
                        ?.strength(physics.linkStrength);
                      fg.d3Force('center')?.strength(physics.centerStrength);
                      // Add collision force for minimum separation
                      const d3 = (fg as any).d3Force;
                      if (d3 && physics.collisionPadding > 0) {
                        // Create collision force if needed
                        const collision = d3('collision');
                        if (collision) {
                          collision.radius((node: GraphNode) => getNodeRadius(node) + physics.collisionPadding);
                        }
                      }
                    } else {
                      // For calculated layouts, minimize physics forces
                      fg.d3Force('charge')?.strength(-10);
                      fg.d3Force('link')?.strength(0);
                      fg.d3Force('center')?.strength(0);
                    }
                  }
                }}
                linkColor={linkColor}
                linkWidth={lodSettings.simplifyLinks ? 1 : linkWidth}
                // Performance: reduce/disable particles for large graphs
                linkDirectionalParticles={lodSettings.particleCount}
                linkDirectionalParticleWidth={1.5}
                onNodeClick={handleNodeClick}
                onNodeRightClick={handleNodeRightClick}
                onBackgroundClick={() => {
                  if (!pathMode) {
                    setSelectedNode(null);
                    setHighlightedPath(new Set());
                  }
                }}
                enableNodeDrag={true}
                enableZoomInteraction={true}
                enablePanInteraction={true}
                // Performance: reduce simulation time for large graphs
                cooldownTicks={lodSettings.cooldownTicks}
                warmupTicks={lodSettings.warmupTicks}
                onEngineStop={() => {
                  // Only fit to view on initial load, not on every engine stop
                  if (!hasInitialFit.current) {
                    hasInitialFit.current = true;
                    graphRef.current?.zoomToFit(400, 50);
                  }
                }}
              />
            </div>
          ) : activeTab !== 'matrix' && activeTab !== 'sankey' ? (
            <div className="graph-empty">
              <Icon name="Network" size={64} />
              <h3>No Graph Data</h3>
              <p>Build a graph to visualize entity relationships</p>
              <button className="btn btn-primary" onClick={buildGraph}>
                <Icon name="GitBranch" size={16} />
                Build Graph
              </button>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
