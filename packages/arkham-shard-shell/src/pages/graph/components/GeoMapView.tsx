/**
 * GeoMapView - Interactive geographic visualization
 *
 * Uses MapLibre GL for full zoom/pan capabilities with OpenStreetMap tiles.
 * Falls back to SVG-based view if MapLibre fails to load (air-gapped mode).
 */

import { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import Map, { Marker, Source, Layer, NavigationControl, Popup } from 'react-map-gl/maplibre';
import type { MapRef } from 'react-map-gl/maplibre';
import type { GeoGraphData, GeoNode } from './GeoGraphView';
import 'maplibre-gl/dist/maplibre-gl.css';

interface GeoMapViewProps {
  data: GeoGraphData;
  showEdges: boolean;
  showClusters: boolean;
  selectedNodeId: string | null;
  onNodeClick: (nodeId: string) => void;
  onEdgeClick?: (source: string, target: string) => void;
  entityColors: Record<string, string>;
}

// Dark mode style using CartoDB dark tiles (free, no API key required)
const MAP_STYLE = {
  version: 8 as const,
  sources: {
    carto: {
      type: 'raster' as const,
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    {
      id: 'carto-dark',
      type: 'raster' as const,
      source: 'carto',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

// ============================================================================
// SVG Fallback for Air-Gapped Mode
//
// NOTE: We intentionally avoid fetching any third-party map assets here to
// prevent leaking auth tokens to external origins and to keep air-gapped mode
// truly offline.
// ============================================================================

const MAP_BOUNDS = {
  minLat: -60,
  maxLat: 85,
  minLng: -180,
  maxLng: 180,
};

function latLngToSvg(
  lat: number,
  lng: number,
  width: number,
  height: number
): { x: number; y: number } {
  const { minLat, maxLat, minLng, maxLng } = MAP_BOUNDS;
  const x = ((lng - minLng) / (maxLng - minLng)) * width;
  const y = ((maxLat - lat) / (maxLat - minLat)) * height;
  return { x, y };
}

function geoJsonToPath(geometry: any, width: number, height: number): string {
  const toPoint = (coord: number[]) => {
    const { x, y } = latLngToSvg(coord[1], coord[0], width, height);
    return `${x},${y}`;
  };

  const ringToPath = (ring: number[][]) => {
    if (ring.length === 0) return '';
    return `M${toPoint(ring[0])} ${ring
      .slice(1)
      .map((c) => `L${toPoint(c)}`)
      .join(' ')} Z`;
  };

  if (geometry.type === 'Polygon') {
    return geometry.coordinates.map(ringToPath).join(' ');
  } else if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates
      .map((polygon: number[][][]) => polygon.map(ringToPath).join(' '))
      .join(' ');
  }
  return '';
}

function SvgFallbackMap({
  data,
  showEdges,
  selectedNodeId,
  onNodeClick,
  onEdgeClick,
  entityColors,
}: Omit<GeoMapViewProps, 'showClusters'>) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    node: GeoNode;
  } | null>(null);

  const width = 960;
  const height = 500;

  void geoJsonToPath; // kept for potential future offline world map rendering

  const nodeCoords = useMemo(() => {
    const coords: Record<string, { x: number; y: number; lat: number; lng: number }> = {};
    if (data?.nodes) {
      for (const node of data.nodes) {
        if (typeof node.latitude === 'number' && typeof node.longitude === 'number') {
          const { x, y } = latLngToSvg(node.latitude, node.longitude, width, height);
          coords[node.id] = { x, y, lat: node.latitude, lng: node.longitude };
        }
      }
    }
    return coords;
  }, [data?.nodes]);

  const validNodes = useMemo(() => {
    return (data?.nodes || []).filter(
      (node) =>
        typeof node.latitude === 'number' &&
        typeof node.longitude === 'number' &&
        !isNaN(node.latitude) &&
        !isNaN(node.longitude) &&
        node.latitude >= -90 &&
        node.latitude <= 90 &&
        node.longitude >= -180 &&
        node.longitude <= 180
    );
  }, [data?.nodes]);

  const validEdges = useMemo(() => {
    return (data?.edges || []).filter(
      (edge) => nodeCoords[edge.source] && nodeCoords[edge.target]
    );
  }, [data?.edges, nodeCoords]);

  const handleNodeHover = (node: GeoNode, event: React.MouseEvent) => {
    setHoveredNode(node.id);
    const rect = event.currentTarget.getBoundingClientRect();
    const containerRect = event.currentTarget
      .closest('.geo-svg-container')
      ?.getBoundingClientRect();
    if (containerRect) {
      setTooltip({
        x: rect.left - containerRect.left + rect.width / 2,
        y: rect.top - containerRect.top - 10,
        node,
      });
    }
  };

  const handleNodeLeave = () => {
    setHoveredNode(null);
    setTooltip(null);
  };

  return (
    <div
      className="geo-svg-container"
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'auto' }}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{
          width: '100%',
          height: '100%',
          minHeight: '400px',
          background: 'linear-gradient(180deg, #1a365d 0%, #2d3748 100%)',
          borderRadius: '8px',
        }}
      >
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path
              d="M 50 0 L 0 0 0 50"
              fill="none"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#grid)" />

        {/* World map background intentionally omitted in offline mode */}

        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
          strokeDasharray="5,5"
        />
        <line
          x1={width / 2}
          y1={0}
          x2={width / 2}
          y2={height}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
          strokeDasharray="5,5"
        />

        {showEdges &&
          validEdges.map((edge, idx) => {
            const source = nodeCoords[edge.source];
            const target = nodeCoords[edge.target];
            const isSelected =
              selectedNodeId === edge.source || selectedNodeId === edge.target;

            return (
              <line
                key={`edge-${idx}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={isSelected ? '#3b82f6' : 'rgba(148, 163, 184, 0.4)'}
                strokeWidth={isSelected ? 2 : 1}
                style={{ cursor: 'pointer' }}
                onClick={() => onEdgeClick?.(edge.source, edge.target)}
              />
            );
          })}

        {validNodes.map((node) => {
          const coords = nodeCoords[node.id];
          if (!coords) return null;

          const color =
            entityColors[node.entity_type?.toLowerCase()] ||
            entityColors.default ||
            '#64748b';
          const isSelected = selectedNodeId === node.id;
          const isHovered = hoveredNode === node.id;
          const radius = isSelected ? 8 : isHovered ? 7 : 5;

          return (
            <g key={node.id}>
              {(isSelected || isHovered) && (
                <circle cx={coords.x} cy={coords.y} r={radius + 4} fill={color} opacity={0.3} />
              )}
              <circle
                cx={coords.x}
                cy={coords.y}
                r={radius}
                fill={color}
                stroke={isSelected ? '#ffffff' : 'rgba(255,255,255,0.5)'}
                strokeWidth={isSelected ? 2 : 1}
                style={{ cursor: 'pointer', transition: 'r 0.2s ease' }}
                onClick={() => onNodeClick(node.id)}
                onMouseEnter={(e) => handleNodeHover(node, e)}
                onMouseLeave={handleNodeLeave}
              />
              {isSelected && (
                <text
                  x={coords.x}
                  y={coords.y - radius - 5}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="11"
                  fontWeight="500"
                  style={{ pointerEvents: 'none' }}
                >
                  {node.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(71, 85, 105, 0.5)',
            borderRadius: '6px',
            padding: '8px 12px',
            color: '#f1f5f9',
            fontSize: '12px',
            pointerEvents: 'none',
            zIndex: 1000,
            minWidth: '120px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>{tooltip.node.label}</div>
          <div style={{ color: '#94a3b8', fontSize: '11px' }}>{tooltip.node.entity_type}</div>
          <div style={{ color: '#64748b', fontSize: '10px', marginTop: '4px' }}>
            {tooltip.node.latitude?.toFixed(4)}, {tooltip.node.longitude?.toFixed(4)}
          </div>
        </div>
      )}

      <div
        style={{
          position: 'absolute',
          bottom: '10px',
          left: '10px',
          background: 'rgba(15, 23, 42, 0.8)',
          borderRadius: '4px',
          padding: '6px 10px',
          color: '#94a3b8',
          fontSize: '11px',
        }}
      >
        Air-gapped mode (no zoom). {validNodes.length} locations shown.
      </div>
    </div>
  );
}

// ============================================================================
// MapLibre Interactive Map (Online Mode)
// ============================================================================

export default function GeoMapView({
  data,
  showEdges,
  showClusters: _showClusters,
  selectedNodeId,
  onNodeClick,
  onEdgeClick,
  entityColors,
}: GeoMapViewProps) {
  void _showClusters; // Not yet implemented

  const [mapRef, setMapRef] = useState<MapRef | null>(null);
  const [popupInfo, setPopupInfo] = useState<GeoNode | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter valid nodes with coordinates
  const validNodes = useMemo(() => {
    return (data?.nodes || []).filter(
      (node) =>
        typeof node.latitude === 'number' &&
        typeof node.longitude === 'number' &&
        !isNaN(node.latitude) &&
        !isNaN(node.longitude)
    );
  }, [data?.nodes]);

  // Calculate initial view state to fit all points
  const initialViewState = useMemo(() => {
    if (validNodes.length === 0) {
      return { longitude: 0, latitude: 20, zoom: 1.5 };
    }

    const lngs = validNodes.map((n) => n.longitude!);
    const lats = validNodes.map((n) => n.latitude!);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);

    const centerLng = (minLng + maxLng) / 2;
    const centerLat = (minLat + maxLat) / 2;

    const lngSpan = maxLng - minLng;
    const latSpan = maxLat - minLat;
    const maxSpan = Math.max(lngSpan, latSpan);

    let zoom = 1.5;
    if (maxSpan < 0.1) zoom = 14;
    else if (maxSpan < 0.5) zoom = 12;
    else if (maxSpan < 1) zoom = 10;
    else if (maxSpan < 5) zoom = 7;
    else if (maxSpan < 20) zoom = 5;
    else if (maxSpan < 60) zoom = 3;
    else if (maxSpan < 120) zoom = 2;

    return { longitude: centerLng, latitude: centerLat, zoom };
  }, [validNodes]);

  // Build GeoJSON for edges
  const edgesGeoJson = useMemo(() => {
    if (!showEdges || !data?.edges || validNodes.length === 0) {
      return { type: 'FeatureCollection' as const, features: [] as any[] };
    }

    const nodeMap = new globalThis.Map(validNodes.map((n) => [n.id, n]));
    const features: any[] = [];

    for (const edge of data.edges) {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) continue;

      const isSelected =
        selectedNodeId === edge.source || selectedNodeId === edge.target;

      features.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: [
            [source.longitude!, source.latitude!],
            [target.longitude!, target.latitude!],
          ],
        },
        properties: {
          source: edge.source,
          target: edge.target,
          weight: edge.weight || 1,
          selected: isSelected,
        },
      });
    }

    return { type: 'FeatureCollection' as const, features };
  }, [data?.edges, validNodes, showEdges, selectedNodeId]);

  // Handle marker click
  const handleMarkerClick = useCallback(
    (node: GeoNode, e: MouseEvent) => {
      e.stopPropagation();
      setPopupInfo(node);
      onNodeClick(node.id);
    },
    [onNodeClick]
  );

  // Fit bounds when data changes
  useEffect(() => {
    if (mapRef && validNodes.length > 1) {
      const lngs = validNodes.map((n) => n.longitude!);
      const lats = validNodes.map((n) => n.latitude!);

      mapRef.fitBounds(
        [
          [Math.min(...lngs) - 1, Math.min(...lats) - 1],
          [Math.max(...lngs) + 1, Math.max(...lats) + 1],
        ],
        { padding: 50, duration: 1000 }
      );
    }
  }, [mapRef, validNodes]);

  // If map fails to load (air-gapped), show SVG fallback
  if (mapError) {
    return (
      <SvgFallbackMap
        data={data}
        showEdges={showEdges}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        entityColors={entityColors}
      />
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Map
        ref={(ref) => setMapRef(ref)}
        initialViewState={initialViewState}
        style={{ width: '100%', height: '100%', minHeight: '400px' }}
        mapStyle={MAP_STYLE}
        onError={(e) => {
          console.warn('MapLibre error:', e);
          setMapError(e.error?.message || 'Map load failed');
        }}
        attributionControl={false}
      >
        <NavigationControl position="top-right" />

        {/* Edge lines */}
        <Source id="edges" type="geojson" data={edgesGeoJson}>
          <Layer
            id="edge-lines"
            type="line"
            paint={{
              'line-color': [
                'case',
                ['get', 'selected'],
                '#3b82f6',
                'rgba(148, 163, 184, 0.5)',
              ],
              'line-width': ['case', ['get', 'selected'], 2, 1],
            }}
          />
        </Source>

        {/* Node markers */}
        {validNodes.map((node) => {
          const color =
            entityColors[node.entity_type?.toLowerCase()] ||
            entityColors.default ||
            '#ef4444';
          const isSelected = selectedNodeId === node.id;

          return (
            <Marker
              key={node.id}
              longitude={node.longitude!}
              latitude={node.latitude!}
              anchor="center"
              onClick={(e) =>
                handleMarkerClick(node, e.originalEvent)
              }
            >
              <div
                style={{
                  width: isSelected ? 18 : 14,
                  height: isSelected ? 18 : 14,
                  borderRadius: '50%',
                  backgroundColor: color,
                  border: isSelected ? '3px solid white' : '2px solid rgba(255,255,255,0.7)',
                  boxShadow: isSelected
                    ? '0 0 10px rgba(59, 130, 246, 0.8)'
                    : '0 2px 4px rgba(0,0,0,0.3)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
                title={node.label}
              />
            </Marker>
          );
        })}

        {/* Popup for selected node */}
        {popupInfo && (
          <Popup
            longitude={popupInfo.longitude!}
            latitude={popupInfo.latitude!}
            anchor="bottom"
            onClose={() => setPopupInfo(null)}
            closeButton={true}
            closeOnClick={false}
            offset={15}
          >
            <div style={{ padding: '0.5rem', maxWidth: '220px', color: '#1f2937' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                {popupInfo.label}
              </div>
              {popupInfo.entity_type && (
                <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Type: {popupInfo.entity_type}
                </div>
              )}
              <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                {popupInfo.latitude?.toFixed(4)}, {popupInfo.longitude?.toFixed(4)}
              </div>
              {popupInfo.city && (
                <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                  {popupInfo.city}{popupInfo.country ? `, ${popupInfo.country}` : ''}
                </div>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {/* Stats overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: '2rem',
          left: '0.5rem',
          background: 'rgba(15, 23, 42, 0.85)',
          color: 'white',
          padding: '0.5rem 0.75rem',
          borderRadius: '0.375rem',
          fontSize: '0.75rem',
          backdropFilter: 'blur(4px)',
        }}
      >
        {validNodes.length} locations • {data?.edges?.length || 0} connections
        <div style={{ fontSize: '0.625rem', color: '#94a3b8', marginTop: '2px' }}>
          Scroll to zoom • Drag to pan
        </div>
      </div>
    </div>
  );
}
