import networkx as nx
import logging
import community.community_louvain as community_louvain
from sqlalchemy.orm import Session
from sqlalchemy import func
from .db.models import CanonicalEntity, EntityRelationship

logger = logging.getLogger(__name__)


def build_networkx_graph(
    session: Session,
    min_strength: float = 0.1,
    min_degree: int = 1,
    max_doc_ratio: float = 0.8,
    exclude_types: list = None,
    hide_singletons: bool = True,
) -> nx.Graph:
    """
    Builds a NetworkX graph from the database with configurable filtering.

    Args:
        session: SQLAlchemy session
        min_strength: Minimum relationship strength to include edges
        min_degree: Minimum node degree required (after edge filtering)
        max_doc_ratio: Maximum document ratio - hide nodes appearing in > X% of docs
        exclude_types: List of entity types to exclude (e.g., ["DATE"])
        hide_singletons: Whether to remove nodes with no edges after filtering

    Returns:
        Filtered NetworkX Graph
    """
    if exclude_types is None:
        exclude_types = []

    G = nx.Graph()

    # Get total document count for ratio calculation
    from .db.models import Document

    total_docs = session.query(func.count(Document.id)).scalar() or 1

    # Fetch nodes
    entities = session.query(CanonicalEntity).all()
    for entity in entities:
        # Skip excluded entity types
        if entity.label in exclude_types:
            continue

        # Calculate document ratio for super-node filtering
        doc_count = entity.document_count if hasattr(entity, "document_count") else 1
        doc_ratio = doc_count / total_docs if total_docs > 0 else 0

        # Skip super-nodes that appear in too many documents
        if doc_ratio > max_doc_ratio:
            continue

        G.add_node(
            entity.id,
            label=entity.canonical_name,
            type=entity.label,
            size=entity.total_mentions,
            doc_ratio=doc_ratio,
        )

    # Fetch edges and aggregate strength
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
        # Ensure both nodes exist (weren't filtered out)
        if G.has_node(r.entity1_id) and G.has_node(r.entity2_id):
            G.add_edge(r.entity1_id, r.entity2_id, weight=r.total_strength)

    # Apply degree filtering
    if min_degree > 0:
        nodes_to_remove = [
            node for node, degree in dict(G.degree()).items() if degree < min_degree
        ]
        G.remove_nodes_from(nodes_to_remove)

    # Remove singletons (nodes with no edges) if requested
    if hide_singletons:
        singletons = [node for node, degree in dict(G.degree()).items() if degree == 0]
        G.remove_nodes_from(singletons)

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
        logger.error(f"Error in community detection: {e}")
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
