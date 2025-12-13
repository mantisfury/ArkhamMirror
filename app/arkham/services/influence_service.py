"""
Entity Influence Mapping Service

Analyzes entity relationships to identify power dynamics, central actors,
and hidden connections through network analysis metrics.
"""

import os
import logging
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import networkx as nx

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    EntityRelationship,
)

load_dotenv()
logger = logging.getLogger(__name__)




class InfluenceService:
    """Service for entity influence and power dynamics analysis."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def build_graph(self, min_strength: float = 0.1) -> nx.Graph:
        """Build NetworkX graph from entity relationships."""
        session = self.Session()
        try:
            G = nx.Graph()

            # Add nodes
            entities = session.query(CanonicalEntity).all()
            for entity in entities:
                G.add_node(
                    entity.id,
                    name=entity.canonical_name,
                    label=entity.label,
                    mentions=entity.total_mentions or 0,
                )

            # Add edges with aggregated weights
            relationships = (
                session.query(
                    EntityRelationship.entity1_id,
                    EntityRelationship.entity2_id,
                    func.sum(EntityRelationship.strength).label("total_strength"),
                )
                .group_by(EntityRelationship.entity1_id, EntityRelationship.entity2_id)
                .having(func.sum(EntityRelationship.strength) >= min_strength)
                .all()
            )

            for rel in relationships:
                if G.has_node(rel.entity1_id) and G.has_node(rel.entity2_id):
                    G.add_edge(
                        rel.entity1_id, rel.entity2_id, weight=rel.total_strength
                    )

            return G
        finally:
            session.close()

    def get_influence_metrics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive influence metrics for all entities.

        Returns centrality scores, community detection, and power rankings.
        """
        G = self.build_graph()

        if len(G.nodes) == 0:
            return {
                "entities": [],
                "communities": [],
                "summary": {
                    "total_entities": 0,
                    "total_connections": 0,
                    "density": 0,
                    "avg_degree": 0,
                },
            }

        # Calculate centrality metrics
        degree_centrality = nx.degree_centrality(G)

        # Betweenness (who controls information flow)
        try:
            betweenness = nx.betweenness_centrality(G, weight="weight")
        except Exception:
            betweenness = {n: 0 for n in G.nodes}

        # Closeness (who can reach others quickly)
        try:
            closeness = nx.closeness_centrality(G)
        except Exception:
            closeness = {n: 0 for n in G.nodes}

        # PageRank (overall importance)
        try:
            pagerank = nx.pagerank(G, weight="weight")
        except Exception:
            pagerank = {n: 1 / len(G.nodes) for n in G.nodes}

        # Eigenvector centrality (connected to important nodes)
        try:
            eigenvector = nx.eigenvector_centrality(G, max_iter=1000, weight="weight")
        except Exception:
            eigenvector = {n: 0 for n in G.nodes}

        # Community detection
        try:
            import community.community_louvain as community_louvain

            partition = community_louvain.best_partition(G, weight="weight")
        except Exception:
            partition = {n: 0 for n in G.nodes}

        # Build entity list with all metrics
        entities = []
        for node_id in G.nodes:
            node_data = G.nodes[node_id]

            # Calculate composite influence score (weighted average)
            influence_score = (
                degree_centrality.get(node_id, 0) * 0.2
                + betweenness.get(node_id, 0) * 0.3
                + pagerank.get(node_id, 0) * 0.3
                + eigenvector.get(node_id, 0) * 0.2
            ) * 100  # Scale to 0-100

            entities.append(
                {
                    "id": node_id,
                    "name": node_data.get("name", "Unknown"),
                    "type": node_data.get("label", "UNKNOWN"),
                    "mentions": node_data.get("mentions", 0),
                    "degree": G.degree(node_id),
                    "connections": list(G.neighbors(node_id)),
                    "community": partition.get(node_id, 0),
                    "metrics": {
                        "degree_centrality": round(
                            degree_centrality.get(node_id, 0), 4
                        ),
                        "betweenness": round(betweenness.get(node_id, 0), 4),
                        "closeness": round(closeness.get(node_id, 0), 4),
                        "pagerank": round(pagerank.get(node_id, 0), 4),
                        "eigenvector": round(eigenvector.get(node_id, 0), 4),
                    },
                    "influence_score": round(influence_score, 2),
                }
            )

        # Sort by influence score
        entities.sort(key=lambda x: x["influence_score"], reverse=True)

        # Build community summary
        community_counts = {}
        for entity in entities:
            comm = entity["community"]
            if comm not in community_counts:
                community_counts[comm] = {
                    "id": comm,
                    "members": [],
                    "size": 0,
                    "key_member": None,
                }
            community_counts[comm]["members"].append(entity["name"])
            community_counts[comm]["size"] += 1
            # First entity added is most influential (entities are sorted by influence_score)
            if community_counts[comm]["key_member"] is None:
                community_counts[comm]["key_member"] = entity["name"]

        communities = list(community_counts.values())
        communities.sort(key=lambda x: x["size"], reverse=True)

        # Network summary
        summary = {
            "total_entities": len(G.nodes),
            "total_connections": len(G.edges),
            "density": round(nx.density(G), 4) if len(G.nodes) > 1 else 0,
            "avg_degree": round(sum(dict(G.degree()).values()) / len(G.nodes), 2)
            if len(G.nodes) > 0
            else 0,
            "num_communities": len(communities),
            "largest_community_size": communities[0]["size"] if communities else 0,
            "most_influential": entities[0]["name"] if entities else "N/A",
        }

        return {"entities": entities, "communities": communities, "summary": summary}

    def get_entity_influence_detail(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed influence analysis for a specific entity."""
        G = self.build_graph()

        if entity_id not in G.nodes:
            return None

        node_data = G.nodes[entity_id]

        # Get neighbors with their details
        neighbors = []
        for neighbor_id in G.neighbors(entity_id):
            neighbor_data = G.nodes[neighbor_id]
            edge_data = G.edges[entity_id, neighbor_id]
            neighbors.append(
                {
                    "id": neighbor_id,
                    "name": neighbor_data.get("name", "Unknown"),
                    "type": neighbor_data.get("label", "UNKNOWN"),
                    "connection_strength": edge_data.get("weight", 1),
                }
            )

        neighbors.sort(key=lambda x: x["connection_strength"], reverse=True)

        # Calculate ego network metrics
        ego = nx.ego_graph(G, entity_id)

        # Find shortest paths to other influential nodes
        try:
            pagerank = nx.pagerank(G, weight="weight")
            top_entities = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

            paths_to_top = []
            for target_id, pr in top_entities:
                if target_id != entity_id:
                    try:
                        path = nx.shortest_path(G, entity_id, target_id)
                        paths_to_top.append(
                            {
                                "target_id": target_id,
                                "target_name": G.nodes[target_id].get(
                                    "name", "Unknown"
                                ),
                                "distance": len(path) - 1,
                                "path": [G.nodes[n].get("name", str(n)) for n in path],
                            }
                        )
                    except nx.NetworkXNoPath:
                        pass
        except Exception:
            paths_to_top = []

        return {
            "id": entity_id,
            "name": node_data.get("name", "Unknown"),
            "type": node_data.get("label", "UNKNOWN"),
            "mentions": node_data.get("mentions", 0),
            "direct_connections": len(neighbors),
            "neighbors": neighbors[:20],  # Top 20
            "ego_network_size": len(ego.nodes),
            "ego_network_edges": len(ego.edges),
            "paths_to_influential": paths_to_top,
        }

    def get_power_dynamics(self) -> Dict[str, Any]:
        """
        Identify power dynamics and hidden relationships.
        """
        G = self.build_graph()

        if len(G.nodes) < 2:
            return {"brokers": [], "bridges": [], "clusters": []}

        # Find brokers (high betweenness, connect different communities)
        try:
            betweenness = nx.betweenness_centrality(G, weight="weight")
            import community.community_louvain as community_louvain

            partition = community_louvain.best_partition(G, weight="weight")
        except Exception:
            return {"brokers": [], "bridges": [], "clusters": []}

        # Identify bridges (edges connecting different communities)
        bridges = []
        for u, v in G.edges:
            if partition.get(u) != partition.get(v):
                bridges.append(
                    {
                        "entity1_id": u,
                        "entity1_name": G.nodes[u].get("name", "Unknown"),
                        "entity2_id": v,
                        "entity2_name": G.nodes[v].get("name", "Unknown"),
                        "community1": partition.get(u),
                        "community2": partition.get(v),
                        "strength": G.edges[u, v].get("weight", 1),
                    }
                )

        bridges.sort(key=lambda x: x["strength"], reverse=True)

        # Find brokers (high betweenness score)
        if betweenness:
            max_betweenness = max(betweenness.values())
            threshold = max_betweenness * 0.5  # Top half

            brokers = []
            for node_id, score in betweenness.items():
                if score >= threshold and score > 0:
                    brokers.append(
                        {
                            "id": node_id,
                            "name": G.nodes[node_id].get("name", "Unknown"),
                            "betweenness": round(score, 4),
                            "community": partition.get(node_id),
                            "degree": G.degree(node_id),
                        }
                    )

            brokers.sort(key=lambda x: x["betweenness"], reverse=True)
        else:
            brokers = []

        # Cluster summary with key members
        clusters = {}
        for node_id, comm in partition.items():
            if comm not in clusters:
                clusters[comm] = {
                    "id": comm,
                    "members": [],
                    "key_member": None,
                    "size": 0,
                }

            clusters[comm]["members"].append(
                {
                    "id": node_id,
                    "name": G.nodes[node_id].get("name", "Unknown"),
                    "degree": G.degree(node_id),
                }
            )
            clusters[comm]["size"] += 1

        # Find key member (highest degree) in each cluster
        for comm_id, cluster in clusters.items():
            if cluster["members"]:
                cluster["members"].sort(key=lambda x: x["degree"], reverse=True)
                cluster["key_member"] = cluster["members"][0]["name"]

        cluster_list = list(clusters.values())
        cluster_list.sort(key=lambda x: x["size"], reverse=True)

        return {
            "brokers": brokers[:10],
            "bridges": bridges[:20],
            "clusters": cluster_list,
        }

    def get_entity_mention_sources(self, entity_id: int) -> Dict[str, Any]:
        """
        Get the source documents and chunks where an entity was mentioned.

        Returns list of mentions with document info for drill-down.
        """
        session = self.Session()
        try:
            from app.arkham.services.db.models import Entity, Document

            # Get all entity mentions linked to this canonical entity
            mentions = (
                session.query(Entity)
                .filter(Entity.canonical_entity_id == entity_id)
                .all()
            )

            sources = []
            doc_ids_seen = set()

            for mention in mentions:
                doc = session.get(Document, mention.doc_id)
                if doc:
                    sources.append(
                        {
                            "mention_text": mention.text,
                            "mention_label": mention.label,
                            "mention_count": mention.count,
                            "doc_id": doc.id,
                            "doc_title": doc.title or f"Document {doc.id}",
                            "doc_type": doc.doc_type or "unknown",
                            "chunk_id": mention.chunk_id,
                        }
                    )
                    doc_ids_seen.add(doc.id)

            # Get canonical entity info
            canonical = session.get(CanonicalEntity, entity_id)

            return {
                "entity_id": entity_id,
                "entity_name": canonical.canonical_name if canonical else "Unknown",
                "total_mentions": canonical.total_mentions if canonical else 0,
                "unique_documents": len(doc_ids_seen),
                "sources": sources,
            }
        finally:
            session.close()

    def get_entity_connections(self, entity_id: int) -> Dict[str, Any]:
        """
        Get detailed connection information for an entity.

        Returns connected entities with relationship strength and shared document info.
        """
        session = self.Session()
        try:
            from app.arkham.services.db.models import Entity, Document

            # Get canonical entity info
            canonical = session.get(CanonicalEntity, entity_id)
            if not canonical:
                return {
                    "entity_id": entity_id,
                    "entity_name": "Unknown",
                    "connections": [],
                }

            # Get relationships where this entity is involved
            relationships = (
                session.query(EntityRelationship)
                .filter(
                    (EntityRelationship.entity1_id == entity_id)
                    | (EntityRelationship.entity2_id == entity_id)
                )
                .all()
            )

            connections = []
            for rel in relationships:
                # Determine the connected entity
                connected_id = (
                    rel.entity2_id if rel.entity1_id == entity_id else rel.entity1_id
                )
                connected = session.get(CanonicalEntity, connected_id)

                if connected:
                    # Get shared documents (where both entities appear)
                    entity1_docs = set(
                        e.doc_id
                        for e in session.query(Entity.doc_id)
                        .filter(Entity.canonical_entity_id == entity_id)
                        .all()
                    )
                    entity2_docs = set(
                        e.doc_id
                        for e in session.query(Entity.doc_id)
                        .filter(Entity.canonical_entity_id == connected_id)
                        .all()
                    )
                    shared_doc_ids = entity1_docs & entity2_docs

                    # Get document titles for shared docs (limit to 5)
                    shared_docs = []
                    for doc_id in list(shared_doc_ids)[:5]:
                        doc = session.get(Document, doc_id)
                        if doc:
                            shared_docs.append(
                                {
                                    "doc_id": doc.id,
                                    "doc_title": doc.title or f"Document {doc.id}",
                                    "doc_type": doc.doc_type or "unknown",
                                }
                            )

                    connections.append(
                        {
                            "connected_entity_id": connected.id,
                            "connected_entity_name": connected.canonical_name,
                            "connected_entity_type": connected.label,
                            "relationship_type": rel.relationship_type,
                            "strength": rel.strength,
                            "co_occurrence_count": rel.co_occurrence_count or 0,
                            "shared_document_count": len(shared_doc_ids),
                            "shared_documents": shared_docs,
                        }
                    )

            # Sort by strength (descending)
            connections.sort(key=lambda x: x["strength"], reverse=True)

            return {
                "entity_id": entity_id,
                "entity_name": canonical.canonical_name,
                "total_connections": len(connections),
                "connections": connections[:30],  # Limit to top 30
            }
        finally:
            session.close()


# Singleton
_service_instance = None


def get_influence_service() -> InfluenceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = InfluenceService()
    return _service_instance
