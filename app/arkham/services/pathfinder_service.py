"""
Shortest Path Finder Service

Find shortest paths between entities in the entity graph.
Uses NetworkX for graph algorithms.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import networkx as nx
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    EntityRelationship,
)

load_dotenv()
logger = logging.getLogger(__name__)




class PathFinderService:
    """Service for finding paths between entities."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def build_graph(self, min_weight: float = 0.1) -> nx.Graph:
        """Build NetworkX graph from entity relationships."""
        session = self.Session()
        try:
            G = nx.Graph()

            # Add entities as nodes
            entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions > 0)
                .all()
            )

            for entity in entities:
                G.add_node(
                    entity.id,
                    name=entity.canonical_name,
                    type=entity.label,
                    mentions=entity.total_mentions,
                )

            # Add relationships as edges
            logger.info(f"Querying relationships with strength >= {min_weight}")
            relationships = (
                session.query(EntityRelationship)
                .filter(EntityRelationship.strength >= min_weight)
                .all()
            )
            logger.info(f"Found {len(relationships)} relationships")

            edge_count = 0
            for rel in relationships:
                if G.has_node(rel.entity1_id) and G.has_node(rel.entity2_id):
                    G.add_edge(
                        rel.entity1_id,
                        rel.entity2_id,
                        weight=rel.strength,
                        type=rel.relationship_type or "associated",
                    )
                    edge_count += 1

            logger.info(
                f"Added {edge_count} edges to graph (some rels may not have valid nodes)"
            )
            return G
        finally:
            session.close()

    def find_shortest_path(
        self, source_id: int, target_id: int, min_weight: float = 0.1
    ) -> Dict[str, Any]:
        """Find shortest path between two entities."""
        G = self.build_graph(min_weight)
        logger.info(
            f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges (min_weight={min_weight})"
        )

        if source_id not in G.nodes:
            return {"error": "Source entity not found in graph"}
        if target_id not in G.nodes:
            return {"error": "Target entity not found in graph"}

        try:
            # Find shortest path
            path = nx.shortest_path(G, source_id, target_id)

            # Build path details
            path_nodes = []
            for node_id in path:
                node_data = G.nodes[node_id]
                path_nodes.append(
                    {
                        "id": node_id,
                        "name": node_data.get("name", ""),
                        "type": node_data.get("type", ""),
                        "mentions": node_data.get("mentions", 0),
                    }
                )

            # Build edge details
            path_edges = []
            for i in range(len(path) - 1):
                edge_data = G.edges[path[i], path[i + 1]]
                path_edges.append(
                    {
                        "source": path[i],
                        "target": path[i + 1],
                        "weight": edge_data.get("weight", 1),
                        "type": edge_data.get("type", "associated"),
                    }
                )

            return {
                "found": True,
                "length": len(path) - 1,
                "path": path_nodes,
                "edges": path_edges,
            }

        except nx.NetworkXNoPath:
            return {
                "found": False,
                "error": "No path exists between these entities",
            }
        except Exception as e:
            return {"error": str(e)}

    def find_all_paths(
        self, source_id: int, target_id: int, max_length: int = 5, limit: int = 10
    ) -> Dict[str, Any]:
        """Find all simple paths up to a maximum length."""
        G = self.build_graph()

        if source_id not in G.nodes or target_id not in G.nodes:
            return {"error": "Entity not found in graph"}

        try:
            paths_gen = nx.all_simple_paths(G, source_id, target_id, cutoff=max_length)

            all_paths = []
            for i, path in enumerate(paths_gen):
                if i >= limit:
                    break

                path_nodes = []
                for node_id in path:
                    node_data = G.nodes[node_id]
                    path_nodes.append(
                        {
                            "id": node_id,
                            "name": node_data.get("name", ""),
                            "type": node_data.get("type", ""),
                        }
                    )

                all_paths.append(
                    {
                        "length": len(path) - 1,
                        "nodes": path_nodes,
                    }
                )

            return {
                "found": len(all_paths) > 0,
                "count": len(all_paths),
                "paths": all_paths,
            }

        except Exception as e:
            return {"error": str(e)}

    def get_entity_neighbors(self, entity_id: int, degree: int = 1) -> Dict[str, Any]:
        """Get entities within N degrees of separation."""
        G = self.build_graph()

        if entity_id not in G.nodes:
            return {"error": "Entity not found in graph"}

        try:
            # Use ego_graph for N-hop neighborhood
            ego = nx.ego_graph(G, entity_id, radius=degree)

            neighbors = []
            for node_id in ego.nodes:
                if node_id != entity_id:
                    node_data = G.nodes[node_id]
                    # Calculate distance from source
                    try:
                        distance = nx.shortest_path_length(G, entity_id, node_id)
                    except nx.NetworkXNoPath:
                        distance = -1

                    neighbors.append(
                        {
                            "id": node_id,
                            "name": node_data.get("name", ""),
                            "type": node_data.get("type", ""),
                            "mentions": node_data.get("mentions", 0),
                            "distance": distance,
                        }
                    )

            # Sort by distance, then mentions
            neighbors.sort(key=lambda x: (x["distance"], -x["mentions"]))

            return {
                "entity_id": entity_id,
                "degree": degree,
                "count": len(neighbors),
                "neighbors": neighbors,
            }

        except Exception as e:
            return {"error": str(e)}

    def get_searchable_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of entities for path finder UI."""
        session = self.Session()
        try:
            entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions > 0)
                .order_by(CanonicalEntity.total_mentions.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.canonical_name,
                    "type": e.label,
                    "mentions": e.total_mentions,
                }
                for e in entities
            ]
        finally:
            session.close()


# Singleton
_service_instance = None


def get_pathfinder_service() -> PathFinderService:
    global _service_instance
    if _service_instance is None:
        _service_instance = PathFinderService()
    return _service_instance
