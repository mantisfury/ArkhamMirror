/**
 * useGraphSettings - Hook for managing graph visualization settings
 *
 * Provides state management and localStorage persistence for all graph controls.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

// Types
export interface LabelSettings {
  mode: 'top' | 'zoom' | 'selected' | 'all';
  topPercent: number;  // 1-100, default 5
  fontSize: number;    // 8-20, default 12
  zoomThreshold: number; // 0.1-2, default 0.8
}

export interface LayoutSettings {
  chargeStrength: number;    // -1000 to -30, default -300
  linkDistance: number;      // 20 to 200, default 60
  linkStrength: number;      // 0.1 to 1.0, default 0.5
  centerStrength: number;    // 0 to 0.3, default 0.1
  collisionPadding: number;  // 0 to 20, default 5
  alphaDecay: number;        // 0.01 to 0.05, default 0.02
}

export interface NodeSizeSettings {
  sizeBy: 'uniform' | 'degree' | 'document_count' | 'composite' | 'betweenness' | 'pagerank';
  minRadius: number;  // 4-12, default 4
  maxRadius: number;  // 8-24, default 12
}

export interface FilterSettings {
  entityTypes: string[];      // Selected entity types (empty = all)
  minDegree: number;         // 0-50, default 0
  maxDegree: number;         // 1-1000, default 1000
  minEdgeWeight: number;     // 0-1, default 0
  documentSources: string[]; // Selected document IDs (empty = all)
  showGiantComponentOnly: boolean;
  searchQuery: string;
  maxNodes: number;          // 0 = unlimited, otherwise limit to top N by importance
}

export interface ScoringWeights {
  centrality: number;     // 0-1, default 0.25
  frequency: number;      // 0-1, default 0.20
  recency: number;        // 0-1, default 0.20
  credibility: number;    // 0-1, default 0.20
  corroboration: number;  // 0-1, default 0.15
}

export interface ScoringSettings {
  enabled: boolean;
  centralityType: 'pagerank' | 'betweenness' | 'eigenvector' | 'hits' | 'closeness';
  weights: ScoringWeights;
  recencyHalfLifeDays: number | null;  // null = disabled
}

export interface DataSourceSettings {
  // Primary sources - base data for graph building
  documentEntities: boolean;      // Include entities from documents
  selectedDocumentIds: string[];  // Specific documents to include (empty = all)
  entityCooccurrences: boolean;   // Include co-occurrence relationships

  // Node sources - add entities from other shards
  claims: boolean;           // Claims as nodes
  achEvidence: boolean;      // ACH evidence as nodes
  achHypotheses: boolean;    // ACH hypotheses as nodes
  provenanceArtifacts: boolean; // Provenance artifacts as nodes
  timelineEvents: boolean;   // Timeline events as nodes

  // Edge sources - add relationships from other shards
  contradictions: boolean;   // Contradiction pairs as edges
  patterns: boolean;         // Pattern matches as edges

  // Weighting sources - affect edge/node weights
  credibilityRatings: boolean; // Use source credibility for weights
}

export interface GraphSettings {
  labels: LabelSettings;
  layout: LayoutSettings;
  nodeSize: NodeSizeSettings;
  filters: FilterSettings;
  scoring: ScoringSettings;
  dataSources: DataSourceSettings;
}

// Default settings
export const DEFAULT_SETTINGS: GraphSettings = {
  labels: {
    mode: 'top',
    topPercent: 5,
    fontSize: 12,
    zoomThreshold: 0.8,
  },
  layout: {
    chargeStrength: -300,
    linkDistance: 60,
    linkStrength: 0.5,
    centerStrength: 0.1,
    collisionPadding: 5,
    alphaDecay: 0.02,
  },
  nodeSize: {
    sizeBy: 'degree',
    minRadius: 4,
    maxRadius: 12,
  },
  filters: {
    entityTypes: [],
    minDegree: 0,
    maxDegree: 1000,
    minEdgeWeight: 0,
    documentSources: [],
    showGiantComponentOnly: false,
    searchQuery: '',
    maxNodes: 0,  // 0 = unlimited
  },
  scoring: {
    enabled: false,
    centralityType: 'pagerank',
    weights: {
      centrality: 0.25,
      frequency: 0.20,
      recency: 0.20,
      credibility: 0.20,
      corroboration: 0.15,
    },
    recencyHalfLifeDays: 30,
  },
  dataSources: {
    // Primary sources - enabled by default
    documentEntities: true,
    selectedDocumentIds: [],  // Empty = all documents
    entityCooccurrences: true,
    // Cross-shard sources - disabled by default
    claims: false,
    achEvidence: false,
    achHypotheses: false,
    provenanceArtifacts: false,
    timelineEvents: false,
    contradictions: false,
    patterns: false,
    credibilityRatings: false,
  },
};

// Presets
export const PRESETS = {
  performance: {
    ...DEFAULT_SETTINGS,
    labels: { ...DEFAULT_SETTINGS.labels, mode: 'top' as const, topPercent: 3 },
    layout: { ...DEFAULT_SETTINGS.layout, alphaDecay: 0.05 },
  },
  detail: {
    ...DEFAULT_SETTINGS,
    labels: { ...DEFAULT_SETTINGS.labels, mode: 'all' as const },
    nodeSize: { ...DEFAULT_SETTINGS.nodeSize, minRadius: 6, maxRadius: 16 },
  },
  balanced: DEFAULT_SETTINGS,
};

const STORAGE_KEY = 'arkham-graph-settings';

export function useGraphSettings() {
  // Load settings from localStorage or use defaults
  const [settings, setSettings] = useState<GraphSettings>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Deep merge with defaults to handle new settings
        return {
          ...DEFAULT_SETTINGS,
          ...parsed,
          labels: { ...DEFAULT_SETTINGS.labels, ...parsed.labels },
          layout: { ...DEFAULT_SETTINGS.layout, ...parsed.layout },
          nodeSize: { ...DEFAULT_SETTINGS.nodeSize, ...parsed.nodeSize },
          filters: { ...DEFAULT_SETTINGS.filters, ...parsed.filters },
          scoring: {
            ...DEFAULT_SETTINGS.scoring,
            ...parsed.scoring,
            weights: { ...DEFAULT_SETTINGS.scoring.weights, ...parsed.scoring?.weights },
          },
          dataSources: { ...DEFAULT_SETTINGS.dataSources, ...parsed.dataSources },
        };
      }
    } catch {
      // Ignore parse errors
    }
    return DEFAULT_SETTINGS;
  });

  // Persist to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // Ignore storage errors
    }
  }, [settings]);

  // Update partial label settings
  const updateLabels = useCallback((updates: Partial<LabelSettings>) => {
    setSettings(prev => ({
      ...prev,
      labels: { ...prev.labels, ...updates },
    }));
  }, []);

  // Update partial layout settings
  const updateLayout = useCallback((updates: Partial<LayoutSettings>) => {
    setSettings(prev => ({
      ...prev,
      layout: { ...prev.layout, ...updates },
    }));
  }, []);

  // Update partial node size settings
  const updateNodeSize = useCallback((updates: Partial<NodeSizeSettings>) => {
    setSettings(prev => ({
      ...prev,
      nodeSize: { ...prev.nodeSize, ...updates },
    }));
  }, []);

  // Update partial filter settings
  const updateFilters = useCallback((updates: Partial<FilterSettings>) => {
    setSettings(prev => ({
      ...prev,
      filters: { ...prev.filters, ...updates },
    }));
  }, []);

  // Update partial scoring settings
  const updateScoring = useCallback((updates: Partial<ScoringSettings>) => {
    setSettings(prev => ({
      ...prev,
      scoring: { ...prev.scoring, ...updates },
    }));
  }, []);

  // Update scoring weights
  const updateScoringWeights = useCallback((updates: Partial<ScoringWeights>) => {
    setSettings(prev => ({
      ...prev,
      scoring: {
        ...prev.scoring,
        weights: { ...prev.scoring.weights, ...updates },
      },
    }));
  }, []);

  // Update data source settings
  const updateDataSources = useCallback((updates: Partial<DataSourceSettings>) => {
    setSettings(prev => ({
      ...prev,
      dataSources: { ...prev.dataSources, ...updates },
    }));
  }, []);

  // Apply preset
  const applyPreset = useCallback((preset: keyof typeof PRESETS) => {
    setSettings(PRESETS[preset]);
  }, []);

  // Reset to defaults
  const reset = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
  }, []);

  // Export settings as JSON
  const exportSettings = useCallback((): string => {
    return JSON.stringify(settings, null, 2);
  }, [settings]);

  // Import settings from JSON
  const importSettings = useCallback((json: string): boolean => {
    try {
      const parsed = JSON.parse(json);
      setSettings({
        ...DEFAULT_SETTINGS,
        ...parsed,
        labels: { ...DEFAULT_SETTINGS.labels, ...parsed.labels },
        layout: { ...DEFAULT_SETTINGS.layout, ...parsed.layout },
        nodeSize: { ...DEFAULT_SETTINGS.nodeSize, ...parsed.nodeSize },
        filters: { ...DEFAULT_SETTINGS.filters, ...parsed.filters },
        scoring: {
          ...DEFAULT_SETTINGS.scoring,
          ...parsed.scoring,
          weights: { ...DEFAULT_SETTINGS.scoring.weights, ...parsed.scoring?.weights },
        },
        dataSources: { ...DEFAULT_SETTINGS.dataSources, ...parsed.dataSources },
      });
      return true;
    } catch {
      return false;
    }
  }, []);

  // Normalize scoring weights to sum to 1
  const normalizedWeights = useMemo(() => {
    const w = settings.scoring.weights;
    const total = w.centrality + w.frequency + w.recency + w.credibility + w.corroboration;
    if (total === 0) return w;
    return {
      centrality: w.centrality / total,
      frequency: w.frequency / total,
      recency: w.recency / total,
      credibility: w.credibility / total,
      corroboration: w.corroboration / total,
    };
  }, [settings.scoring.weights]);

  return {
    settings,
    setSettings,
    updateLabels,
    updateLayout,
    updateNodeSize,
    updateFilters,
    updateScoring,
    updateScoringWeights,
    updateDataSources,
    normalizedWeights,
    applyPreset,
    reset,
    exportSettings,
    importSettings,
  };
}

export type UseGraphSettingsReturn = ReturnType<typeof useGraphSettings>;
