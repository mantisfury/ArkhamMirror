"""
Entity Relationship Graph

Visualizes connections between entities across documents.
Shows which people, organizations, and locations appear together.
"""

import os
import streamlit as st
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from streamlit_agraph import agraph, Node, Edge, Config
import networkx as nx
import matplotlib.colors as mcolors

from backend.db.models import CanonicalEntity, EntityRelationship, Entity, Document
from backend.utils.auth import check_authentication
from backend.graph_utils import (
    build_networkx_graph,
    detect_communities,
    get_shortest_path,
)

# Authentication check
check_authentication()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

st.set_page_config(page_title="Entity Graph", page_icon="🕸️", layout="wide")

st.title("🕸️ Interactive Entity Graph")
st.markdown(
    """
    Explore relationships between entities. 
    **Click on a node** to see which documents mention that entity.
    """
)


@st.cache_data(ttl=300)
def get_full_graph(min_strength=1):
    """
    Builds the full NetworkX graph from the database.
    """
    session = Session()
    try:
        return build_networkx_graph(session, min_strength)
    finally:
        session.close()


def nx_to_agraph(G, limit=100, partition=None, entity_type="All"):
    """
    Convert NetworkX graph to agraph Nodes and Edges with filtering.
    """
    # Filter by entity type if needed
    if entity_type != "All":
        # Create a subgraph view
        nodes_to_keep = [
            n for n, d in G.nodes(data=True) if d.get("type") == entity_type
        ]
        # Note: This is strict filtering (only shows nodes of that type).
        # Usually we want to see connections TO that type too, but let's stick to simple filtering for now.
        # Or maybe we filter the *top* list but keep neighbors?
        # Let's just filter the candidate list for top nodes.
        candidates = [n for n in G.nodes(data=True) if n[1].get("type") == entity_type]
    else:
        candidates = list(G.nodes(data=True))

    # Sort by size (mentions) and take top N
    sorted_nodes = sorted(candidates, key=lambda x: x[1].get("size", 0), reverse=True)[
        :limit
    ]
    top_node_ids = {n[0] for n in sorted_nodes}

    nodes = []
    palette = list(mcolors.TABLEAU_COLORS.values())

    for node_id, data in sorted_nodes:
        color = "#999999"  # Default gray

        if partition:
            # Color by community
            comm_id = partition.get(node_id, 0)
            color = palette[comm_id % len(palette)]
        else:
            # Color by type
            lbl = data.get("type")
            if lbl == "PERSON":
                color = "#FF6B6B"  # Red
            elif lbl == "ORG":
                color = "#4ECDC4"  # Teal
            elif lbl == "GPE":
                color = "#95E1D3"  # Green

        # Size normalization
        size = 15 + (data.get("size", 1) * 2)
        if size > 50:
            size = 50

        nodes.append(
            Node(
                id=node_id,
                label=data.get("label", "Unknown"),
                size=size,
                color=color,
                title=f"{data.get('type')}\nMentions: {data.get('size')}",
            )
        )

    edges = []
    for u, v, data in G.edges(data=True):
        if u in top_node_ids and v in top_node_ids:
            weight = data.get("weight", 1)
            edges.append(
                Edge(
                    source=u,
                    target=v,
                    label=str(int(weight)) if weight > 1 else "",
                    color="#cccccc",
                )
            )

    return nodes, edges


def get_related_documents(canonical_id):
    """Fetch documents that mention this canonical entity."""
    session = Session()
    try:
        results = (
            session.query(Document, Entity.count)
            .join(Entity, Entity.doc_id == Document.id)
            .filter(Entity.canonical_entity_id == canonical_id)
            .order_by(Entity.count.desc())
            .all()
        )
        return results
    finally:
        session.close()


# --- Sidebar Controls ---
st.sidebar.header("Graph Controls")

# 1. Filters
entity_type = st.sidebar.selectbox(
    "Entity Type", ["All", "PERSON", "ORG", "GPE", "DATE", "EVENT"]
)

min_strength = st.sidebar.slider(
    "Minimum Relationship Strength", 1, 10, 1, help="Filter out weak connections"
)

limit = st.sidebar.slider(
    "Max Entities to Display", 10, 200, 50, 10, help="Limit nodes for performance"
)

use_communities = st.sidebar.checkbox(
    "🎨 Color by Community", help="Detect clusters using Louvain algorithm"
)

st.sidebar.markdown("---")

# 2. Pathfinding
st.sidebar.subheader("📍 Pathfinding")
session = Session()
all_entities = (
    session.query(CanonicalEntity).order_by(CanonicalEntity.canonical_name).all()
)
session.close()

entity_options = {e.canonical_name: e.id for e in all_entities}

source_name = st.sidebar.selectbox(
    "Source Entity", options=[""] + list(entity_options.keys())
)
target_name = st.sidebar.selectbox(
    "Target Entity", options=[""] + list(entity_options.keys())
)

path_nodes = []
if st.sidebar.button("Find Path") and source_name and target_name:
    source_id = entity_options[source_name]
    target_id = entity_options[target_name]

    # We need the full graph for pathfinding
    G_full = get_full_graph(
        1
    )  # Use min_strength 1 for pathfinding to find any connection
    path = get_shortest_path(G_full, source_id, target_id)

    if path:
        st.sidebar.success(f"Path found! ({len(path)} steps)")
        path_nodes = path
    else:
        st.sidebar.error("No path found between these entities.")

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Rebuild Graph Data"):
    with st.spinner("Rebuilding..."):
        import subprocess

        # Use absolute path
        script_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "build_entity_graph.py",
        )
        subprocess.run(["python", script_path], cwd=os.path.dirname(script_path))
        st.cache_data.clear()
        st.rerun()

# --- Main Logic ---

# Load Graph
G = get_full_graph(min_strength)

# Community Detection
partition = None
if use_communities:
    partition = detect_communities(G)

# Convert to Agraph
nodes, edges = nx_to_agraph(G, limit, partition, entity_type)

# Highlight Path if found
if path_nodes:
    # Add path nodes to the visualization if they aren't there
    existing_ids = {n.id for n in nodes}
    for pid in path_nodes:
        if pid not in existing_ids:
            # Fetch node data from G
            data = G.nodes[pid]
            nodes.append(
                Node(
                    id=pid,
                    label=data["label"],
                    size=20,
                    color="#FFFF00",
                    title="Path Node",
                )
            )
            existing_ids.add(pid)

    # Highlight edges in path
    path_edges = list(zip(path_nodes[:-1], path_nodes[1:]))
    for u, v in path_edges:
        # Check if edge exists in current visual edges
        found = False
        for e in edges:
            if (e.to == u and e.from_ == v) or (e.to == v and e.from_ == u):
                e.color = "#FF0000"  # Highlight red
                e.width = 3
                found = True
        if not found:
            # Add missing edge
            edges.append(Edge(source=u, target=v, color="#FF0000", width=3))

# Render
config = Config(
    width=900,
    height=600,
    directed=False,
    physics=True,
    hierarchical=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={"labelProperty": "label"},
    link={"labelProperty": "label", "renderLabel": True},
)

selected_node_id = agraph(nodes=nodes, edges=edges, config=config)

# Document Viewer
if selected_node_id:
    session = Session()
    entity = session.query(CanonicalEntity).get(selected_node_id)
    session.close()

    if entity:
        st.markdown("---")
        st.subheader(f"📄 Documents mentioning: **{entity.canonical_name}**")
        docs = get_related_documents(entity.id)
        if docs:
            for doc, count in docs:
                with st.expander(f"{doc.title} ({count} mentions)"):
                    st.markdown(f"**Type:** {doc.doc_type} | **Status:** {doc.status}")
                    if doc.summary:
                        st.markdown(f"**Summary:** {doc.summary}")
                    st.caption(f"Document ID: {doc.id}")
        else:
            st.info("No documents found.")

# Legend
st.sidebar.markdown("**Legend:**")
if use_communities:
    st.sidebar.info("Colors represent detected communities (clusters).")
else:
    st.sidebar.markdown("🔴 **Person**")
    st.sidebar.markdown("🔵 **Organization**")
    st.sidebar.markdown("🟢 **Location**")
