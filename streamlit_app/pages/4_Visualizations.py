import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import os
import numpy as np
import umap.umap_ as umap
from dotenv import load_dotenv
from backend.db.models import Document, Chunk
from qdrant_client import QdrantClient
import re
from datetime import datetime

load_dotenv()
st.set_page_config(layout="wide", page_title="Arkham Atlas")

# --- Setup ---
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
COLLECTION_NAME = "arkham_mirror_hybrid"

st.title("🗺️ Arkham Atlas: Visual Intelligence")

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Filters")

    # Project Filter (Placeholder for now as Project model isn't fully integrated in UI yet)
    # selected_project = st.selectbox("Select Project", ["All Projects"])

    view_mode = st.radio("View Mode", ["Cluster Map", "Timeline Analysis"])


# --- Helper Functions ---
def get_doc_vectors(session):
    """Fetches document centroids for visualization."""
    docs = session.query(Document).all()
    if not docs:
        return [], []

    doc_data = []
    vectors = []

    # This is heavy for large datasets, but okay for <10k docs locally
    # Ideally we cache these centroids in the DB
    for doc in docs:
        # Get chunks to compute centroid
        chunks = session.query(Chunk).filter(Chunk.doc_id == doc.id).all()
        if not chunks:
            continue

        chunk_ids = [c.id for c in chunks]
        points = qdrant_client.retrieve(
            collection_name=COLLECTION_NAME, ids=chunk_ids, with_vectors=True
        )
        chunk_vecs = [p.vector["dense"] for p in points if p.vector]
        if chunk_vecs:
            centroid = np.mean(chunk_vecs, axis=0)

            cluster_name = "Unclustered"
            if hasattr(doc, "cluster_id") and doc.cluster_id:
                from backend.db.models import Cluster

                cluster = session.query(Cluster).get(doc.cluster_id)
                if cluster:
                    cluster_name = cluster.name

            doc_data.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "cluster": cluster_name,
                    "date": doc.created_at,  # Fallback if no extracted date
                    "type": doc.doc_type,
                }
            )
            vectors.append(centroid)

    return doc_data, np.array(vectors)


def extract_dates_from_text(text):
    """Simple regex to find years/dates in text for timeline."""
    # Look for YYYY patterns between 1990 and 2030
    matches = re.findall(r"\b(199\d|20[0-2]\d)\b", text)
    return [int(m) for m in matches]


# --- Main Logic ---
session = Session()
try:
    if view_mode == "Cluster Map":
        st.subheader("🌌 Semantic Cluster Map")
        st.caption(
            "Each dot is a document. Closer dots are semantically similar. Colors represent discovered topics."
        )

        with st.spinner("Computing map projection..."):
            doc_data, X = get_doc_vectors(session)

            if len(doc_data) > 2:
                # Reduce to 2D with UMAP
                reducer = umap.UMAP(n_components=2, random_state=42)
                embedding = reducer.fit_transform(X)

                df = pd.DataFrame(doc_data)
                df["x"] = embedding[:, 0]

            else:
                st.warning("Not enough documents to visualize. Need at least 3.")

    elif view_mode == "Timeline Analysis":
        st.subheader("📅 Temporal Investigation")
        st.caption(
            "Distribution of documents based on extracted dates mentioned in the text."
        )

        # 1. Extract dates from chunks (Heavy operation - should be pre-computed in production)
        # For now, we'll sample
        timeline_data = []

        with st.spinner("Scanning documents for dates..."):
            docs = session.query(Document).all()
            for doc in docs:
                # Get first 5 chunks
                chunks = (
                    session.query(Chunk).filter(Chunk.doc_id == doc.id).limit(5).all()
                )
                full_text = " ".join([c.text for c in chunks])
                years = extract_dates_from_text(full_text)

                if years:
                    avg_year = int(np.mean(years))
                    timeline_data.append(
                        {
                            "doc_id": doc.id,
                            "title": doc.title,
                            "year": avg_year,
                            "count": len(years),
                        }
                    )

        if timeline_data:
            df_time = pd.DataFrame(timeline_data)

            # Histogram
            fig_hist = px.histogram(
                df_time,
                x="year",
                hover_data=["doc_id"],
                title="Document Timeline",
                template="plotly_dark",
                height=600,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        else:
            st.warning("No dates detected in documents.")

finally:
    session.close()
