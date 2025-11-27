import networkx as nx
import community.community_louvain as community_louvain
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.db.models import CanonicalEntity, EntityRelationship


def build_networkx_graph(session: Session, min_strength: int = 1):
    """
    Builds a NetworkX graph from the database.
    Aggregates multiple relationship records between the same entities into a single weighted edge.
    """
    G = nx.Graph()

    # Fetch nodes
    entities = session.query(CanonicalEntity).all()
    for entity in entities:
        G.add_node(
            entity.id,
            label=entity.canonical_name,
            type=entity.label,
            size=entity.total_mentions,
        )

    # Fetch edges and aggregate strength
    # We can do this aggregation in SQL for better performance
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

    for r in relationships:
        # Ensure nodes exist (they should, due to FKs, but good to be safe)
        if G.has_node(r.entity1_id) and G.has_node(r.entity2_id):
            G.add_edge(r.entity1_id, r.entity2_id, weight=r.total_strength)

    return G


def detect_communities(G: nx.Graph):
    """
    Runs Louvain community detection.
    Returns a dict {node_id: partition_id}.
    """
    if len(G.nodes) == 0:
        return {}

    # Louvain requires undirected graph, which we have.
    # It uses edge weights if present.
    try:
        partition = community_louvain.best_partition(G, weight="weight")
        return partition
    except Exception as e:
        print(f"Error in community detection: {e}")
        return {}


def get_shortest_path(G: nx.Graph, source_id: int, target_id: int):
    """
    Returns a list of node IDs representing the shortest path.
    """
    try:
        path = nx.shortest_path(G, source=source_id, target=target_id)
        return path
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None
