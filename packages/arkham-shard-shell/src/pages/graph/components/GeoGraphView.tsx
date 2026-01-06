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

import { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Icon } from '../../../components/common/Icon';

// Fix Leaflet default icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

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
  default: '#64748b',
};

// Create custom icon for entity type
function createMarkerIcon(entityType: string, isSelected: boolean = false): L.DivIcon {
  const color = ENTITY_COLORS[entityType.toLowerCase()] || ENTITY_COLORS.default;
  const size = isSelected ? 16 : 12;

  return L.divIcon({
    className: 'geo-marker-icon',
    html: `<div style="
      width: ${size}px;
      height: ${size}px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      ${isSelected ? 'transform: scale(1.3);' : ''}
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// Map bounds fitter component
function MapBoundsFitter({ bounds }: { bounds: GeoBounds | null }) {
  const map = useMap();

  useEffect(() => {
    if (bounds) {
      const leafletBounds = L.latLngBounds(
        [bounds.min_lat, bounds.min_lng],
        [bounds.max_lat, bounds.max_lng]
      );
      map.fitBounds(leafletBounds, { padding: [50, 50] });
    }
  }, [bounds, map]);

  return null;
}

export function GeoGraphView({
  projectId,
  onNodeClick,
  onEdgeClick,
  height = 600,
}: GeoGraphViewProps) {
  const [data, setData] = useState<GeoGraphData | null>(null);
  const [loading, setLoading] = useState(false);
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

  // Build coordinate lookup for edges
  const nodeCoords = data?.nodes.reduce((acc, node) => {
    acc[node.id] = [node.latitude, node.longitude] as [number, number];
    return acc;
  }, {} as Record<string, [number, number]>) || {};

  // Handle node click
  const handleNodeClick = (nodeId: string) => {
    setSelectedNodeId(prev => prev === nodeId ? null : nodeId);
    onNodeClick?.(nodeId);
  };

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

  const defaultCenter: [number, number] = data.bounds?.center || [0, 0];
  const defaultZoom = data.bounds ? 4 : 2;

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

      {/* Map */}
      <div className="geo-map-container" style={{ height: height - 60 }}>
        <MapContainer
          center={defaultCenter}
          zoom={defaultZoom}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapBoundsFitter bounds={data.bounds} />

          {/* Edges */}
          {showEdges && data.edges.map((edge, idx) => {
            const sourceCoords = nodeCoords[edge.source];
            const targetCoords = nodeCoords[edge.target];

            if (!sourceCoords || !targetCoords) return null;

            const isSelected = selectedNodeId === edge.source || selectedNodeId === edge.target;

            return (
              <Polyline
                key={`edge-${idx}`}
                positions={[sourceCoords, targetCoords]}
                pathOptions={{
                  color: isSelected ? '#3b82f6' : '#64748b',
                  weight: isSelected ? 3 : Math.max(1, Math.min(4, edge.weight * 2)),
                  opacity: isSelected ? 0.9 : 0.5,
                  dashArray: edge.relationship_type === 'related' ? '5,5' : undefined,
                }}
                eventHandlers={{
                  click: () => onEdgeClick?.(edge.source, edge.target),
                }}
              >
                <Popup>
                  <div className="geo-popup">
                    <strong>{edge.relationship_type}</strong>
                    <div>Distance: {edge.distance_km.toFixed(1)} km</div>
                  </div>
                </Popup>
              </Polyline>
            );
          })}

          {/* Cluster circles */}
          {showClusters && data.clusters.map((cluster) => (
            <CircleMarker
              key={cluster.id}
              center={cluster.center}
              radius={Math.max(20, Math.min(50, cluster.node_count * 5))}
              pathOptions={{
                color: '#8b5cf6',
                fillColor: '#8b5cf6',
                fillOpacity: 0.3,
                weight: 2,
              }}
            >
              <Popup>
                <div className="geo-popup">
                  <strong>Cluster</strong>
                  <div>{cluster.node_count} locations</div>
                  <div>Radius: {cluster.radius_km.toFixed(1)} km</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}

          {/* Node markers */}
          {data.nodes.map((node) => (
            <Marker
              key={node.id}
              position={[node.latitude, node.longitude]}
              icon={createMarkerIcon(node.entity_type, selectedNodeId === node.id)}
              eventHandlers={{
                click: () => handleNodeClick(node.id),
              }}
            >
              <Popup>
                <div className="geo-popup">
                  <strong>{node.label}</strong>
                  <div className="entity-type">{node.entity_type}</div>
                  {node.address && <div>{node.address}</div>}
                  {node.city && <div>{node.city}</div>}
                  {node.country && <div>{node.country}</div>}
                  <div className="coords">
                    {node.latitude.toFixed(4)}, {node.longitude.toFixed(4)}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
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
