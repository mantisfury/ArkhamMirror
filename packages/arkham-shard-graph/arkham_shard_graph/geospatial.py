"""
Geospatial graph analysis.

Provides tools for extracting geographic coordinates from entities,
calculating distances, and preparing data for map-based visualization.
"""

from dataclasses import dataclass, field
from typing import Any
from math import radians, sin, cos, sqrt, atan2
import re
import logging

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


@dataclass
class GeoCoordinate:
    """Geographic coordinate."""
    latitude: float
    longitude: float

    def is_valid(self) -> bool:
        """Check if coordinates are valid."""
        return -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180


@dataclass
class GeoNode:
    """Node with geographic coordinates."""
    entity_id: str
    label: str
    latitude: float
    longitude: float
    location_type: str = "exact"  # exact, approximate, inferred, centroid
    entity_type: str = "location"
    address: str = ""
    city: str = ""
    country: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeoEdge:
    """Edge with geographic distance."""
    source_id: str
    target_id: str
    distance_km: float
    relationship_type: str = "related"
    weight: float = 1.0


@dataclass
class GeoBounds:
    """Geographic bounding box."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    @property
    def center(self) -> tuple[float, float]:
        """Get center point of bounds."""
        return (
            (self.min_lat + self.max_lat) / 2,
            (self.min_lng + self.max_lng) / 2,
        )

    def contains(self, lat: float, lng: float) -> bool:
        """Check if point is within bounds."""
        return (
            self.min_lat <= lat <= self.max_lat and
            self.min_lng <= lng <= self.max_lng
        )


@dataclass
class GeoCluster:
    """Cluster of nearby geographic nodes."""
    id: str
    center_lat: float
    center_lng: float
    node_ids: list[str] = field(default_factory=list)
    radius_km: float = 0.0


@dataclass
class GeoGraphData:
    """Geographic graph data for visualization."""
    nodes: list[GeoNode] = field(default_factory=list)
    edges: list[GeoEdge] = field(default_factory=list)
    bounds: GeoBounds | None = None
    clusters: list[GeoCluster] = field(default_factory=list)
    total_distance_km: float = 0.0


class GeoGraphEngine:
    """Geographic network analysis engine."""

    # Earth radius in kilometers
    EARTH_RADIUS_KM = 6371.0

    # Common coordinate patterns
    COORD_PATTERNS = [
        # Decimal degrees in parentheses: (40.7128, -74.0060) - most common format in our data
        r'\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)',
        # Decimal degrees without parentheses but with decimal points required
        r'(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})',
        # DMS: 40°42'46"N 74°0'22"W
        r"(\d+)°(\d+)'(\d+(?:\.\d+)?)[\"″]?\s*([NS])\s+(\d+)°(\d+)'(\d+(?:\.\d+)?)[\"″]?\s*([EW])",
    ]

    def extract_geo_nodes(
        self,
        graph: Graph,
        location_types: list[str] | None = None,
    ) -> list[GeoNode]:
        """
        Extract geographic coordinates from graph nodes.

        Looks for coordinates in node properties or attempts to
        parse from location-type entities.

        Args:
            graph: Source graph
            location_types: Entity types to treat as locations

        Returns:
            List of GeoNode with valid coordinates
        """
        location_types = location_types or ["location", "place", "address", "city", "country"]
        geo_nodes: list[GeoNode] = []

        for node in graph.nodes:
            lat, lng = None, None
            location_type = "exact"
            entity_type = (node.entity_type or node.type or "unknown").lower()

            # Check if node has explicit coordinates
            if node.properties:
                lat = node.properties.get("latitude") or node.properties.get("lat")
                lng = node.properties.get("longitude") or node.properties.get("lng") or node.properties.get("lon")

                if lat is not None and lng is not None:
                    try:
                        lat = float(lat)
                        lng = float(lng)
                    except (ValueError, TypeError):
                        lat, lng = None, None

            # Try to parse coordinates from label, description, or sentence
            if lat is None or lng is None:
                label = node.label or ""

                if node.properties:
                    # Try to find coordinates associated with THIS entity's label in the sentence
                    # This is the preferred method as it ensures we get the correct coordinates
                    sentence = str(node.properties.get("sentence", ""))
                    if sentence and label:
                        # Check if label appears followed by coordinates somewhere in the sentence
                        # Pattern: "Label, any words (lat, lng)" - e.g., "London, United Kingdom (51.5074, -0.1278)"
                        # Also handles: "Label (lat, lng)" directly
                        label_with_coords = re.search(
                            rf'{re.escape(label)}[^(]*\((-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\)',
                            sentence,
                            re.IGNORECASE
                        )
                        if label_with_coords:
                            try:
                                parsed_lat = float(label_with_coords.group(1))
                                parsed_lng = float(label_with_coords.group(2))
                                if -90 <= parsed_lat <= 90 and -180 <= parsed_lng <= 180:
                                    lat = parsed_lat
                                    lng = parsed_lng
                                    location_type = "parsed"
                            except ValueError:
                                pass

                # Only use fallback parsing from label/description if we still don't have coordinates
                # (Don't parse random coordinates from sentences not associated with this entity)
                if lat is None or lng is None:
                    text_to_parse = label
                    if node.properties:
                        text_to_parse += " " + str(node.properties.get("description", ""))
                        text_to_parse += " " + str(node.properties.get("address", ""))
                        # Note: We intentionally do NOT add sentence here to avoid
                        # extracting coordinates belonging to other entities

                    coords = self._parse_coordinates(text_to_parse)
                    if coords:
                        lat, lng = coords
                        location_type = "parsed"

            # Skip nodes without valid coordinates
            if lat is None or lng is None:
                continue

            # Validate coordinates
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                continue

            geo_nodes.append(GeoNode(
                entity_id=node.id,
                label=node.label or node.id,
                latitude=lat,
                longitude=lng,
                location_type=location_type,
                entity_type=entity_type,
                address=node.properties.get("address", "") if node.properties else "",
                city=node.properties.get("city", "") if node.properties else "",
                country=node.properties.get("country", "") if node.properties else "",
                properties=node.properties or {},
            ))

        return geo_nodes

    def _parse_coordinates(self, text: str) -> tuple[float, float] | None:
        """Try to parse coordinates from text."""
        if not text:
            return None

        # Try decimal degrees patterns (first two patterns)
        for i in range(2):
            decimal_match = re.search(self.COORD_PATTERNS[i], text)
            if decimal_match:
                try:
                    lat = float(decimal_match.group(1))
                    lng = float(decimal_match.group(2))
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        return (lat, lng)
                except ValueError:
                    pass

        # Try DMS pattern (third pattern)
        dms_match = re.search(self.COORD_PATTERNS[2], text, re.IGNORECASE)
        if dms_match:
            try:
                lat_deg = int(dms_match.group(1))
                lat_min = int(dms_match.group(2))
                lat_sec = float(dms_match.group(3))
                lat_dir = dms_match.group(4).upper()

                lng_deg = int(dms_match.group(5))
                lng_min = int(dms_match.group(6))
                lng_sec = float(dms_match.group(7))
                lng_dir = dms_match.group(8).upper()

                lat = lat_deg + lat_min / 60 + lat_sec / 3600
                if lat_dir == 'S':
                    lat = -lat

                lng = lng_deg + lng_min / 60 + lng_sec / 3600
                if lng_dir == 'W':
                    lng = -lng

                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return (lat, lng)
            except (ValueError, IndexError):
                pass

        return None

    def calculate_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lng = radians(lng2 - lng1)

        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return self.EARTH_RADIUS_KM * c

    def calculate_edge_distances(
        self,
        geo_nodes: list[GeoNode],
        edges: list[GraphEdge],
    ) -> list[GeoEdge]:
        """
        Calculate geographic distance for each edge.

        Args:
            geo_nodes: Nodes with coordinates
            edges: Graph edges

        Returns:
            List of GeoEdge with distances
        """
        # Build coordinate lookup
        coord_map = {
            node.entity_id: (node.latitude, node.longitude)
            for node in geo_nodes
        }

        geo_edges: list[GeoEdge] = []

        for edge in edges:
            source_coords = coord_map.get(edge.source)
            target_coords = coord_map.get(edge.target)

            if source_coords and target_coords:
                distance = self.calculate_distance(
                    source_coords[0], source_coords[1],
                    target_coords[0], target_coords[1],
                )

                geo_edges.append(GeoEdge(
                    source_id=edge.source,
                    target_id=edge.target,
                    distance_km=distance,
                    relationship_type=edge.relationship_type or edge.type or "related",
                    weight=edge.weight,
                ))

        return geo_edges

    def calculate_bounds(self, geo_nodes: list[GeoNode]) -> GeoBounds | None:
        """Calculate bounding box for all nodes."""
        if not geo_nodes:
            return None

        lats = [n.latitude for n in geo_nodes]
        lngs = [n.longitude for n in geo_nodes]

        return GeoBounds(
            min_lat=min(lats),
            max_lat=max(lats),
            min_lng=min(lngs),
            max_lng=max(lngs),
        )

    def cluster_nodes(
        self,
        geo_nodes: list[GeoNode],
        radius_km: float = 50.0,
    ) -> list[GeoCluster]:
        """
        Cluster nearby nodes for cleaner visualization.

        Uses simple distance-based clustering.

        Args:
            geo_nodes: Nodes to cluster
            radius_km: Maximum cluster radius

        Returns:
            List of GeoCluster
        """
        if not geo_nodes:
            return []

        clusters: list[GeoCluster] = []
        assigned = set()

        for node in geo_nodes:
            if node.entity_id in assigned:
                continue

            # Start new cluster
            cluster_nodes = [node]
            assigned.add(node.entity_id)

            # Find nearby nodes
            for other in geo_nodes:
                if other.entity_id in assigned:
                    continue

                distance = self.calculate_distance(
                    node.latitude, node.longitude,
                    other.latitude, other.longitude,
                )

                if distance <= radius_km:
                    cluster_nodes.append(other)
                    assigned.add(other.entity_id)

            # Calculate cluster center
            center_lat = sum(n.latitude for n in cluster_nodes) / len(cluster_nodes)
            center_lng = sum(n.longitude for n in cluster_nodes) / len(cluster_nodes)

            # Calculate cluster radius
            max_dist = 0.0
            for n in cluster_nodes:
                dist = self.calculate_distance(center_lat, center_lng, n.latitude, n.longitude)
                max_dist = max(max_dist, dist)

            clusters.append(GeoCluster(
                id=f"cluster_{len(clusters)}",
                center_lat=center_lat,
                center_lng=center_lng,
                node_ids=[n.entity_id for n in cluster_nodes],
                radius_km=max_dist,
            ))

        return clusters

    def build_geo_graph(
        self,
        graph: Graph,
        cluster_radius_km: float | None = None,
    ) -> GeoGraphData:
        """
        Build complete geographic graph data.

        Args:
            graph: Source graph
            cluster_radius_km: Optional clustering radius

        Returns:
            GeoGraphData ready for visualization
        """
        # Extract geo nodes
        geo_nodes = self.extract_geo_nodes(graph)

        if not geo_nodes:
            return GeoGraphData()

        # Calculate edge distances
        geo_edges = self.calculate_edge_distances(geo_nodes, graph.edges)

        # Calculate bounds
        bounds = self.calculate_bounds(geo_nodes)

        # Calculate total distance
        total_distance = sum(e.distance_km for e in geo_edges)

        # Optional clustering
        clusters = []
        if cluster_radius_km:
            clusters = self.cluster_nodes(geo_nodes, cluster_radius_km)

        return GeoGraphData(
            nodes=geo_nodes,
            edges=geo_edges,
            bounds=bounds,
            clusters=clusters,
            total_distance_km=total_distance,
        )

    def filter_by_bounds(
        self,
        geo_data: GeoGraphData,
        bounds: GeoBounds,
    ) -> GeoGraphData:
        """Filter geo data to only include nodes within bounds."""
        filtered_nodes = [
            n for n in geo_data.nodes
            if bounds.contains(n.latitude, n.longitude)
        ]

        node_ids = {n.entity_id for n in filtered_nodes}

        filtered_edges = [
            e for e in geo_data.edges
            if e.source_id in node_ids and e.target_id in node_ids
        ]

        return GeoGraphData(
            nodes=filtered_nodes,
            edges=filtered_edges,
            bounds=self.calculate_bounds(filtered_nodes),
            total_distance_km=sum(e.distance_km for e in filtered_edges),
        )

    def to_dict(self, geo_data: GeoGraphData) -> dict[str, Any]:
        """Convert GeoGraphData to dictionary for JSON serialization."""
        return {
            "nodes": [
                {
                    "id": n.entity_id,
                    "label": n.label,
                    "latitude": n.latitude,
                    "longitude": n.longitude,
                    "location_type": n.location_type,
                    "entity_type": n.entity_type,
                    "address": n.address,
                    "city": n.city,
                    "country": n.country,
                }
                for n in geo_data.nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "distance_km": e.distance_km,
                    "relationship_type": e.relationship_type,
                    "weight": e.weight,
                }
                for e in geo_data.edges
            ],
            "bounds": {
                "min_lat": geo_data.bounds.min_lat,
                "max_lat": geo_data.bounds.max_lat,
                "min_lng": geo_data.bounds.min_lng,
                "max_lng": geo_data.bounds.max_lng,
                "center": geo_data.bounds.center,
            } if geo_data.bounds else None,
            "clusters": [
                {
                    "id": c.id,
                    "center": [c.center_lat, c.center_lng],
                    "node_count": len(c.node_ids),
                    "node_ids": c.node_ids,
                    "radius_km": c.radius_km,
                }
                for c in geo_data.clusters
            ],
            "summary": {
                "node_count": len(geo_data.nodes),
                "edge_count": len(geo_data.edges),
                "total_distance_km": geo_data.total_distance_km,
                "cluster_count": len(geo_data.clusters),
            },
        }

    def to_geojson(self, geo_data: GeoGraphData) -> dict[str, Any]:
        """
        Convert to GeoJSON format for map libraries.

        Returns FeatureCollection with Point features for nodes
        and LineString features for edges.
        """
        features = []

        # Add node points
        for node in geo_data.nodes:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [node.longitude, node.latitude],
                },
                "properties": {
                    "id": node.entity_id,
                    "label": node.label,
                    "entity_type": node.entity_type,
                    "location_type": node.location_type,
                    "address": node.address,
                    "city": node.city,
                    "country": node.country,
                    "feature_type": "node",
                },
            })

        # Add edge lines
        node_coords = {
            n.entity_id: [n.longitude, n.latitude]
            for n in geo_data.nodes
        }

        for edge in geo_data.edges:
            source_coords = node_coords.get(edge.source_id)
            target_coords = node_coords.get(edge.target_id)

            if source_coords and target_coords:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [source_coords, target_coords],
                    },
                    "properties": {
                        "source": edge.source_id,
                        "target": edge.target_id,
                        "distance_km": edge.distance_km,
                        "relationship_type": edge.relationship_type,
                        "weight": edge.weight,
                        "feature_type": "edge",
                    },
                })

        return {
            "type": "FeatureCollection",
            "features": features,
        }
