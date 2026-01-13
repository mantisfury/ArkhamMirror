/**
 * GeoMapView - Simple SVG-based geographic visualization
 *
 * Uses a simple equirectangular projection to display points on a world map.
 * No external mapping libraries required.
 */

import { useMemo, useState } from 'react';
import type { GeoGraphData } from './GeoGraphView';

interface GeoMapViewProps {
  data: GeoGraphData;
  showEdges: boolean;
  showClusters: boolean;
  selectedNodeId: string | null;
  onNodeClick: (nodeId: string) => void;
  onEdgeClick?: (source: string, target: string) => void;
  entityColors: Record<string, string>;
}

// Convert lat/lng to SVG coordinates using equirectangular projection
function latLngToSvg(
  lat: number,
  lng: number,
  width: number,
  height: number,
  bounds?: { minLat: number; maxLat: number; minLng: number; maxLng: number }
): { x: number; y: number } {
  // Use provided bounds or default to world view
  const minLat = bounds?.minLat ?? -60;
  const maxLat = bounds?.maxLat ?? 80;
  const minLng = bounds?.minLng ?? -180;
  const maxLng = bounds?.maxLng ?? 180;

  // Add padding
  const latRange = maxLat - minLat;
  const lngRange = maxLng - minLng;
  const padding = 0.1;

  const adjMinLat = minLat - latRange * padding;
  const adjMaxLat = maxLat + latRange * padding;
  const adjMinLng = minLng - lngRange * padding;
  const adjMaxLng = maxLng + lngRange * padding;

  const x = ((lng - adjMinLng) / (adjMaxLng - adjMinLng)) * width;
  const y = ((adjMaxLat - lat) / (adjMaxLat - adjMinLat)) * height; // Flip Y axis

  return { x, y };
}

export default function GeoMapView({
  data,
  showEdges,
  showClusters: _showClusters,
  selectedNodeId,
  onNodeClick,
  onEdgeClick,
  entityColors,
}: GeoMapViewProps) {
  // Note: showClusters is available but not yet implemented in SVG view
  void _showClusters;
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: typeof data.nodes[0] } | null>(null);

  const width = 900;
  const height = 500;

  // Calculate bounds from data
  const bounds = useMemo(() => {
    if (data?.bounds) {
      return {
        minLat: data.bounds.min_lat,
        maxLat: data.bounds.max_lat,
        minLng: data.bounds.min_lng,
        maxLng: data.bounds.max_lng,
      };
    }
    return undefined;
  }, [data?.bounds]);

  // Build coordinate lookup for edges
  const nodeCoords = useMemo(() => {
    const coords: Record<string, { x: number; y: number; lat: number; lng: number }> = {};
    if (data?.nodes) {
      for (const node of data.nodes) {
        if (typeof node.latitude === 'number' && typeof node.longitude === 'number') {
          const { x, y } = latLngToSvg(node.latitude, node.longitude, width, height, bounds);
          coords[node.id] = { x, y, lat: node.latitude, lng: node.longitude };
        }
      }
    }
    return coords;
  }, [data?.nodes, bounds]);

  // Filter valid nodes
  const validNodes = useMemo(() => {
    return (data?.nodes || []).filter(node =>
      typeof node.latitude === 'number' &&
      typeof node.longitude === 'number' &&
      !isNaN(node.latitude) &&
      !isNaN(node.longitude) &&
      node.latitude >= -90 && node.latitude <= 90 &&
      node.longitude >= -180 && node.longitude <= 180
    );
  }, [data?.nodes]);

  // Filter valid edges
  const validEdges = useMemo(() => {
    return (data?.edges || []).filter(edge =>
      nodeCoords[edge.source] && nodeCoords[edge.target]
    );
  }, [data?.edges, nodeCoords]);

  const handleNodeHover = (node: typeof data.nodes[0], event: React.MouseEvent) => {
    setHoveredNode(node.id);
    const rect = event.currentTarget.getBoundingClientRect();
    const containerRect = event.currentTarget.closest('.geo-svg-container')?.getBoundingClientRect();
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
    <div className="geo-svg-container" style={{ position: 'relative', width: '100%', height: '100%', overflow: 'auto' }}>
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
        {/* Simple world outline */}
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#grid)" />

        {/* Equator and prime meridian */}
        <line
          x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
          strokeDasharray="5,5"
        />
        <line
          x1={width / 2} y1={0} x2={width / 2} y2={height}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
          strokeDasharray="5,5"
        />

        {/* Edges */}
        {showEdges && validEdges.map((edge, idx) => {
          const source = nodeCoords[edge.source];
          const target = nodeCoords[edge.target];
          const isSelected = selectedNodeId === edge.source || selectedNodeId === edge.target;

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

        {/* Nodes */}
        {validNodes.map((node) => {
          const coords = nodeCoords[node.id];
          if (!coords) return null;

          const color = entityColors[node.entity_type?.toLowerCase()] || entityColors.default || '#64748b';
          const isSelected = selectedNodeId === node.id;
          const isHovered = hoveredNode === node.id;
          const radius = isSelected ? 8 : isHovered ? 7 : 5;

          return (
            <g key={node.id}>
              {/* Glow effect for selected/hovered */}
              {(isSelected || isHovered) && (
                <circle
                  cx={coords.x}
                  cy={coords.y}
                  r={radius + 4}
                  fill={color}
                  opacity={0.3}
                />
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
              {/* Label for selected node */}
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

      {/* Tooltip */}
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
            {tooltip.node.latitude.toFixed(4)}, {tooltip.node.longitude.toFixed(4)}
          </div>
        </div>
      )}

      {/* Info overlay */}
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
        Click on a point to select it. {validNodes.length} locations shown.
      </div>
    </div>
  );
}
