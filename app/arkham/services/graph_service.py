# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import networkx as nx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from .graph_utils import build_networkx_graph, detect_communities
from .db.models import CanonicalEntity

# Load environment variables
load_dotenv()

# Database setup
# In a real app, use a shared database connection manager
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_entity_graph(
    entity_id: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get graph data (nodes and edges) for visualization.

    Args:
        entity_id: Optional ID to filter/focus the graph (not fully implemented in utils yet)

    Returns:
        Dict with 'nodes' and 'edges' lists suitable for frontend visualization
    """
    session = Session()
    try:
        # Build graph using existing utility
        G = build_networkx_graph(session, min_strength=0.1)

        # Detect communities
        partition = detect_communities(G)

        # Convert to frontend format
        nodes = []
        for node_id, data in G.nodes(data=True):
            nodes.append(
                {
                    "id": str(node_id),
                    "label": data.get("label", str(node_id)),
                    "type": data.get("type", "unknown"),
                    "size": data.get("size", 10),
                    "group": partition.get(node_id, 0),  # Community ID
                }
            )

        edges = []
        for u, v, data in G.edges(data=True):
            edges.append(
                {"source": str(u), "target": str(v), "weight": data.get("weight", 1)}
            )

        return {"nodes": nodes, "edges": edges}

    finally:
        session.close()


def get_available_entity_types() -> List[str]:
    """
    Get list of unique entity types in the database.

    Returns:
        List of entity type strings (e.g., ["PERSON", "ORG", "GPE", ...])
    """
    session = Session()
    try:
        from sqlalchemy import distinct

        types = session.query(distinct(CanonicalEntity.label)).all()
        return sorted([t[0] for t in types if t[0]])
    finally:
        session.close()


def get_filtered_entity_graph(
    min_strength: float = 0.1,
    min_degree: int = 1,
    max_doc_ratio: float = 0.8,
    exclude_types: Optional[List[str]] = None,
    hide_singletons: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get graph data with filtering applied.

    Args:
        min_strength: Minimum edge strength to include
        min_degree: Minimum node degree to include
        max_doc_ratio: Maximum document ratio (hide super-nodes)
        exclude_types: Entity types to exclude
        hide_singletons: Whether to hide nodes with no edges

    Returns:
        Dict with 'nodes' and 'edges' lists suitable for frontend visualization
    """
    session = Session()
    try:
        # Build graph with filtering
        G = build_networkx_graph(
            session,
            min_strength=min_strength,
            min_degree=min_degree,
            max_doc_ratio=max_doc_ratio,
            exclude_types=exclude_types or [],
            hide_singletons=hide_singletons,
        )

        # Detect communities
        partition = detect_communities(G)

        # Convert to frontend format
        nodes = []
        for node_id, data in G.nodes(data=True):
            nodes.append(
                {
                    "id": str(node_id),
                    "label": data.get("label", str(node_id)),
                    "type": data.get("type", "unknown"),
                    "size": data.get("size", 10),
                    "group": partition.get(node_id, 0),
                    "total_mentions": data.get("size", 1),  # For sizing calculations
                }
            )

        edges = []
        for u, v, data in G.edges(data=True):
            edges.append(
                {"source": str(u), "target": str(v), "weight": data.get("weight", 1)}
            )

        return {"nodes": nodes, "edges": edges}

    finally:
        session.close()
