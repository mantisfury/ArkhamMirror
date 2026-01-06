/**
 * useUrlParams - URL parameter synchronization for shareable graph views
 *
 * Syncs key graph settings to URL params so views can be shared via link.
 */

import { useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { GraphSettings, FilterSettings, ScoringSettings } from './useGraphSettings';

// Subset of settings that make sense to share via URL
interface UrlGraphSettings {
  // Filters
  entityTypes?: string[];
  minDegree?: number;
  maxDegree?: number;
  minEdgeWeight?: number;
  maxNodes?: number;
  searchQuery?: string;

  // Scoring
  scoringEnabled?: boolean;
  centralityType?: string;

  // View
  tab?: string;
  selectedNode?: string;
}

/**
 * Parse URL params into graph settings
 */
function parseUrlParams(searchParams: URLSearchParams): Partial<UrlGraphSettings> {
  const settings: Partial<UrlGraphSettings> = {};

  // Entity types (comma-separated)
  const entityTypes = searchParams.get('types');
  if (entityTypes) {
    settings.entityTypes = entityTypes.split(',').filter(Boolean);
  }

  // Numeric filters
  const minDegree = searchParams.get('minDegree');
  if (minDegree) settings.minDegree = parseInt(minDegree, 10);

  const maxDegree = searchParams.get('maxDegree');
  if (maxDegree) settings.maxDegree = parseInt(maxDegree, 10);

  const minWeight = searchParams.get('minWeight');
  if (minWeight) settings.minEdgeWeight = parseFloat(minWeight);

  const maxNodes = searchParams.get('maxNodes');
  if (maxNodes) settings.maxNodes = parseInt(maxNodes, 10);

  // Search query
  const search = searchParams.get('search');
  if (search) settings.searchQuery = search;

  // Scoring
  const scoring = searchParams.get('scoring');
  if (scoring === 'true') settings.scoringEnabled = true;

  const centrality = searchParams.get('centrality');
  if (centrality) settings.centralityType = centrality;

  // View state
  const tab = searchParams.get('tab');
  if (tab) settings.tab = tab;

  const node = searchParams.get('node');
  if (node) settings.selectedNode = node;

  return settings;
}

/**
 * Build URL params from graph settings
 */
function buildUrlParams(settings: GraphSettings, tab?: string, selectedNode?: string): URLSearchParams {
  const params = new URLSearchParams();

  const { filters, scoring } = settings;

  // Entity types (only if filtered)
  if (filters.entityTypes.length > 0) {
    params.set('types', filters.entityTypes.join(','));
  }

  // Numeric filters (only if non-default)
  if (filters.minDegree > 0) {
    params.set('minDegree', filters.minDegree.toString());
  }
  if (filters.maxDegree < 1000) {
    params.set('maxDegree', filters.maxDegree.toString());
  }
  if (filters.minEdgeWeight > 0) {
    params.set('minWeight', filters.minEdgeWeight.toString());
  }
  if (filters.maxNodes > 0) {
    params.set('maxNodes', filters.maxNodes.toString());
  }

  // Search
  if (filters.searchQuery) {
    params.set('search', filters.searchQuery);
  }

  // Scoring (only if enabled)
  if (scoring.enabled) {
    params.set('scoring', 'true');
    params.set('centrality', scoring.centralityType);
  }

  // Tab (only if not default)
  if (tab && tab !== 'graph') {
    params.set('tab', tab);
  }

  // Selected node
  if (selectedNode) {
    params.set('node', selectedNode);
  }

  return params;
}

/**
 * Hook to sync graph settings with URL params
 */
export function useUrlParams(
  settings: GraphSettings,
  updateFilters: (updates: Partial<FilterSettings>) => void,
  updateScoring: (updates: Partial<ScoringSettings>) => void,
  tab?: string,
  selectedNode?: string,
  setTab?: (tab: string) => void,
  setSelectedNode?: (node: string | null) => void
) {
  const [searchParams, setSearchParams] = useSearchParams();

  // On mount, apply URL params to settings
  useEffect(() => {
    const urlSettings = parseUrlParams(searchParams);

    // Apply filters
    const filterUpdates: Partial<FilterSettings> = {};
    if (urlSettings.entityTypes !== undefined) filterUpdates.entityTypes = urlSettings.entityTypes;
    if (urlSettings.minDegree !== undefined) filterUpdates.minDegree = urlSettings.minDegree;
    if (urlSettings.maxDegree !== undefined) filterUpdates.maxDegree = urlSettings.maxDegree;
    if (urlSettings.minEdgeWeight !== undefined) filterUpdates.minEdgeWeight = urlSettings.minEdgeWeight;
    if (urlSettings.maxNodes !== undefined) filterUpdates.maxNodes = urlSettings.maxNodes;
    if (urlSettings.searchQuery !== undefined) filterUpdates.searchQuery = urlSettings.searchQuery;

    if (Object.keys(filterUpdates).length > 0) {
      updateFilters(filterUpdates);
    }

    // Apply scoring
    if (urlSettings.scoringEnabled !== undefined || urlSettings.centralityType !== undefined) {
      const scoringUpdates: Partial<ScoringSettings> = {};
      if (urlSettings.scoringEnabled) scoringUpdates.enabled = true;
      if (urlSettings.centralityType) {
        scoringUpdates.centralityType = urlSettings.centralityType as ScoringSettings['centralityType'];
      }
      updateScoring(scoringUpdates);
    }

    // Apply view state
    if (urlSettings.tab && setTab) {
      setTab(urlSettings.tab);
    }
    if (urlSettings.selectedNode && setSelectedNode) {
      // Note: This would need the actual node object, so we just store the ID
      // The GraphPage would need to look up the node
    }
  }, []); // Only run on mount

  // Update URL when settings change
  const updateUrl = useCallback(() => {
    const newParams = buildUrlParams(settings, tab, selectedNode || undefined);
    const currentString = searchParams.toString();
    const newString = newParams.toString();

    // Only update if different to prevent loops
    if (currentString !== newString) {
      setSearchParams(newParams, { replace: true });
    }
  }, [settings, tab, selectedNode, searchParams, setSearchParams]);

  // Generate shareable URL
  const getShareableUrl = useCallback((): string => {
    const params = buildUrlParams(settings, tab, selectedNode || undefined);
    const base = window.location.origin + window.location.pathname;
    const paramString = params.toString();
    return paramString ? `${base}?${paramString}` : base;
  }, [settings, tab, selectedNode]);

  // Copy URL to clipboard
  const copyShareableUrl = useCallback(async (): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(getShareableUrl());
      return true;
    } catch {
      return false;
    }
  }, [getShareableUrl]);

  return {
    updateUrl,
    getShareableUrl,
    copyShareableUrl,
  };
}
