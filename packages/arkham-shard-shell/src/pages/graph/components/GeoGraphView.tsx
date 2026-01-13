/**
 * GeoGraphView - Geographic network overlay on map
 *
 * Features:
 * - Leaflet map with OpenStreetMap tiles
 * - Nodes positioned at coordinates
 * - Edges as lines on map
 * - Clustering for dense areas
 * - Zoom-dependent detail levels
 */

import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { Icon } from '../../../components/common/Icon';

// Types
export interface GeoNode {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  location_type: string;
  entity_type: string;
  address: string;
  city: string;
  country: string;
}

export interface GeoEdge {
  source: string;
  target: string;
  distance_km: number;
  relationship_type: string;
  weight: number;
}

export interface GeoBounds {
  min_lat: number;
  max_lat: number;
  min_lng: number;
  max_lng: number;
  center: [number, number];
}

export interface GeoCluster {
  id: string;
  center: [number, number];
  node_count: number;
  node_ids: string[];
  radius_km: number;
}

export interface GeoGraphData {
  nodes: GeoNode[];
  edges: GeoEdge[];
  bounds: GeoBounds | null;
  clusters: GeoCluster[];
  summary: {
    node_count: number;
    edge_count: number;
    total_distance_km: number;
    cluster_count: number;
  };
}

export interface GeoGraphViewProps {
  projectId: string;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (source: string, target: string) => void;
  height?: number;
}

// Entity type colors
const ENTITY_COLORS: Record<string, string> = {
  location: '#3b82f6',
  place: '#3b82f6',
  city: '#8b5cf6',
  country: '#22c55e',
  address: '#f59e0b',
  person: '#ef4444',
  organization: '#06b6d4',
  other: '#64748b',
  default: '#64748b',
};

// Lazy load the map component to avoid SSR issues
const LazyMapView = lazy(() => import('./GeoMapView'));

export function GeoGraphView({
  projectId,
  onNodeClick,
  onEdgeClick,
  height = 600,
}: GeoGraphViewProps) {
  const [data, setData] = useState<GeoGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [showEdges, setShowEdges] = useState(true);
  const [showClusters, setShowClusters] = useState(false);
  const [clusterRadius, setClusterRadius] = useState(50);

  // Fetch geo data
  const fetchGeoData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = showClusters
        ? `/api/graph/geo/${projectId}?cluster_radius_km=${clusterRadius}`
        : `/api/graph/geo/${projectId}`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch geo data');
      const result = await response.json();

      if (result.success) {
        setData(result);
      } else {
        setError(result.error || result.message || 'No geographic data');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [projectId, showClusters, clusterRadius]);

  useEffect(() => {
    fetchGeoData();
  }, [fetchGeoData]);

  // Handle node click
  const handleNodeClick = useCallback((nodeId: string) => {
    setSelectedNodeId(prev => prev === nodeId ? null : nodeId);
    onNodeClick?.(nodeId);
  }, [onNodeClick]);

  // Empty/loading states
  if (loading) {
    return (
      <div className="geo-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading geographic data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="geo-error">
        <Icon name="MapPin" size={48} />
        <h3>No Geographic Data</h3>
        <p>{error}</p>
        <p className="hint">Add location entities with coordinates to see them on the map.</p>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="geo-empty">
        <Icon name="MapPin" size={48} />
        <h3>No Locations Found</h3>
        <p>No entities with geographic coordinates were found in this project.</p>
      </div>
    );
  }

  return (
    <div className="geo-view">
      {/* Controls */}
      <div className="geo-controls-bar">
        <div className="geo-stats">
          <span>{data.summary.node_count} locations</span>
          <span>{data.summary.edge_count} connections</span>
          <span>{data.summary.total_distance_km.toFixed(0)} km total</span>
        </div>
        <div className="geo-options">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showEdges}
              onChange={(e) => setShowEdges(e.target.checked)}
            />
            Show Edges
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showClusters}
              onChange={(e) => setShowClusters(e.target.checked)}
            />
            Cluster Nodes
          </label>
          {showClusters && (
            <div className="cluster-radius">
              <label>Radius:</label>
              <input
                type="range"
                min={10}
                max={200}
                value={clusterRadius}
                onChange={(e) => setClusterRadius(Number(e.target.value))}
              />
              <span>{clusterRadius}km</span>
            </div>
          )}
        </div>
      </div>

      {/* Map - Lazy loaded */}
      <div className="geo-map-container" style={{ height: height - 60 }}>
        <Suspense fallback={
          <div className="geo-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading map...</span>
          </div>
        }>
          <LazyMapView
            data={data}
            showEdges={showEdges}
            showClusters={showClusters}
            selectedNodeId={selectedNodeId}
            onNodeClick={handleNodeClick}
            onEdgeClick={onEdgeClick}
            entityColors={ENTITY_COLORS}
          />
        </Suspense>
      </div>

      {/* Legend */}
      <div className="geo-legend">
        {Object.entries(ENTITY_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
          <div key={type} className="legend-item">
            <span className="legend-dot" style={{ background: color }} />
            <span>{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Controls for GeoGraphView
 */
export interface GeoGraphControlsProps {
  showEdges: boolean;
  onShowEdgesChange: (show: boolean) => void;
  showLabels: boolean;
  onShowLabelsChange: (show: boolean) => void;
  clusterRadius: number;
  onClusterRadiusChange: (radius: number) => void;
}

export function GeoGraphControls({
  showEdges,
  onShowEdgesChange,
  showLabels,
  onShowLabelsChange,
  clusterRadius,
  onClusterRadiusChange,
}: GeoGraphControlsProps) {
  return (
    <div className="geo-controls">
      <div className="control-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showEdges}
            onChange={(e) => onShowEdgesChange(e.target.checked)}
          />
          Show Connections
        </label>
      </div>

      <div className="control-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={showLabels}
            onChange={(e) => onShowLabelsChange(e.target.checked)}
          />
          Show Labels
        </label>
      </div>

      <div className="control-group">
        <label>Cluster Radius (km)</label>
        <input
          type="range"
          min={10}
          max={200}
          value={clusterRadius}
          onChange={(e) => onClusterRadiusChange(Number(e.target.value))}
        />
        <span className="value">{clusterRadius}</span>
      </div>

      <div className="control-info">
        <Icon name="Info" size={14} />
        <p>Geographic view shows entities with location coordinates on a map. Edges represent relationships with distances.</p>
      </div>
    </div>
  );
}
