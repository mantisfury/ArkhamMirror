import base64
import io
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np

# Third-party imports
from qdrant_client import QdrantClient
import umap.umap_ as umap
from wordcloud import WordCloud
from spacy.lang.en.stop_words import STOP_WORDS
import string

# Local imports
from config.settings import DATABASE_URL, QDRANT_URL
from app.arkham.services.db.models import (
    Document,
    Chunk,
    Cluster,
    CanonicalEntity,
    EntityRelationship,
)

logger = logging.getLogger(__name__)

# Initialize Qdrant client from central config
qdrant_client = QdrantClient(url=QDRANT_URL)
COLLECTION_NAME = "arkham_mirror_hybrid"

# Database setup from central config
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Default blocklist for wordcloud - common chunking/OCR artifacts
WORDCLOUD_BLOCKLIST = {
    "page",
    "start",
    "end",
    "figure",
    "table",
    "document",
    "paragraph",
    "section",
    "chapter",
    "appendix",
    "index",
    "note",
    "notes",
    "reference",
    "references",
    "continued",
    "see",
    "page\\d+",
    "fig",
    "tab",
    "doc",
    "ref",
}


def get_cluster_map_data() -> List[Dict[str, Any]]:
    """
    Fetches document centroids and computes UMAP projection for visualization.
    Returns a list of dictionaries containing x, y coordinates and document metadata.
    """
    session = SessionLocal()
    try:
        docs = session.query(Document).all()
        if len(docs) < 3:
            return []

        doc_data = []
        vectors = []

        # Limit to avoid performance issues on large datasets
        # In a real prod env, these centroids should be pre-calculated
        docs = docs[:1000]

        # Optimize: Fetch all chunks for these docs in one go
        doc_ids = [d.id for d in docs]
        all_chunks = session.query(Chunk).filter(Chunk.doc_id.in_(doc_ids)).all()

        chunks_by_doc = defaultdict(list)
        for chunk in all_chunks:
            chunks_by_doc[chunk.doc_id].append(chunk)

        for doc in docs:
            # Get chunks from pre-fetched map
            chunks = chunks_by_doc.get(doc.id, [])
            if not chunks:
                continue

            chunk_ids = [c.id for c in chunks]
            try:
                points = qdrant_client.retrieve(
                    collection_name=COLLECTION_NAME, ids=chunk_ids, with_vectors=True
                )
                chunk_vecs = [
                    p.vector["dense"]
                    for p in points
                    if p.vector and "dense" in p.vector
                ]

                # Handle case where vector might be just a list if not named vectors
                if not chunk_vecs:
                    chunk_vecs = [
                        p.vector
                        for p in points
                        if p.vector and isinstance(p.vector, list)
                    ]

                if chunk_vecs:
                    centroid = np.mean(chunk_vecs, axis=0)

                    cluster_name = "Unclustered"
                    if doc.cluster_id:
                        cluster = session.query(Cluster).get(doc.cluster_id)
                        if cluster:
                            cluster_name = cluster.name

                    doc_data.append(
                        {
                            "id": doc.id,
                            "title": doc.title,
                            "cluster": cluster_name,
                            "type": doc.doc_type,
                            "date": str(doc.created_at),
                        }
                    )
                    vectors.append(centroid)
            except Exception as e:
                logger.error(f"Error fetching vectors for doc {doc.id}: {e}")
                continue

        if len(vectors) < 3:
            return []

        # Reduce to 2D with UMAP
        # Default n_neighbors is 15. We must ensure n_neighbors < n_samples to avoid warnings.
        n_neighbors = min(15, len(vectors) - 1)
        if n_neighbors < 2:
            n_neighbors = 2

        # n_jobs=1 explicitly set to avoid warning when using random_state
        reducer = umap.UMAP(
            n_components=2, n_neighbors=n_neighbors, random_state=42, n_jobs=1
        )
        embedding = reducer.fit_transform(np.array(vectors))

        # Combine metadata with coordinates
        result = []
        for i, data in enumerate(doc_data):
            result.append(
                {**data, "x": float(embedding[i, 0]), "y": float(embedding[i, 1])}
            )

        return result
    finally:
        session.close()


def generate_wordcloud_base64(text: str, width: int = 800, height: int = 400) -> str:
    """Generates a wordcloud image and returns it as a base64 string."""
    if not text:
        return ""

    wordcloud = WordCloud(
        width=width,
        height=height,
        background_color="#1a1a2e",  # Dark background matching app theme
        colormap="plasma",  # Bright colors visible on dark background
        max_words=100,
    ).generate(text)

    img = wordcloud.to_image()
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def get_wordcloud_data(
    scope: str,
    filter_id: Optional[str] = None,
    custom_exclusions: Optional[List[str]] = None,
) -> str:
    """
    Generates a wordcloud base64 image based on the scope.
    scope: "all", "cluster", "doctype"
    filter_id: ID of the cluster or name of the doctype
    custom_exclusions: Additional words to exclude from the wordcloud
    """
    session = SessionLocal()
    try:
        chunks_query = session.query(Chunk)

        if scope == "cluster" and filter_id:
            # Get docs in cluster (convert filter_id to int since cluster_id is Integer)
            try:
                cluster_id_int = int(filter_id)
            except ValueError:
                return ""  # Invalid cluster ID
            docs = (
                session.query(Document)
                .filter(Document.cluster_id == cluster_id_int)
                .all()
            )
            doc_ids = [d.id for d in docs]
            if not doc_ids:
                return ""
            chunks = chunks_query.filter(Chunk.doc_id.in_(doc_ids)).limit(500).all()

        elif scope == "doctype" and filter_id:
            docs = session.query(Document).filter(Document.doc_type == filter_id).all()
            doc_ids = [d.id for d in docs]
            if not doc_ids:
                return ""
            chunks = chunks_query.filter(Chunk.doc_id.in_(doc_ids)).limit(500).all()

        else:  # scope == "all"
            chunks = chunks_query.limit(1000).all()

        if not chunks:
            return ""

        # Build combined blocklist: defaults + custom exclusions
        blocklist = WORDCLOUD_BLOCKLIST.copy()
        if custom_exclusions:
            blocklist.update(word.lower().strip() for word in custom_exclusions)

        # Generate text with blocklist filtering
        text_parts = []
        for c in chunks:
            # Remove stopwords, blocklist items, and short words
            words = [
                word
                for word in c.text.lower().split()
                if word not in STOP_WORDS
                and word not in string.punctuation
                and word not in blocklist
                and len(word) > 2
            ]
            text_parts.append(" ".join(words))

        full_text = " ".join(text_parts)
        return generate_wordcloud_base64(full_text)
    finally:
        session.close()


def get_entity_heatmap_data(top_n: int = 15) -> Dict[str, Any]:
    """
    Returns data for an entity co-occurrence heatmap.
    """
    session = SessionLocal()
    try:
        # Get top entities by total mentions
        top_entities = (
            session.query(CanonicalEntity)
            .order_by(CanonicalEntity.total_mentions.desc())
            .limit(top_n)
            .all()
        )

        if not top_entities:
            return {"labels": [], "z": []}

        entity_ids = [e.id for e in top_entities]
        entity_names = {e.id: e.canonical_name for e in top_entities}
        labels = [entity_names[eid][:20] for eid in entity_ids]

        # Build co-occurrence matrix
        matrix = np.zeros((len(entity_ids), len(entity_ids)))

        relationships = (
            session.query(EntityRelationship)
            .filter(
                EntityRelationship.entity1_id.in_(entity_ids),
                EntityRelationship.entity2_id.in_(entity_ids),
            )
            .all()
        )

        for rel in relationships:
            if rel.entity1_id in entity_names and rel.entity2_id in entity_names:
                idx1 = entity_ids.index(rel.entity1_id)
                idx2 = entity_ids.index(rel.entity2_id)
                # Use co_occurrence_count as primary metric, fall back to strength
                value = (
                    rel.co_occurrence_count
                    if rel.co_occurrence_count
                    else (rel.strength or 1.0)
                )
                matrix[idx1, idx2] = value
                matrix[idx2, idx1] = value  # Symmetric

        return {
            "labels": labels,
            "z": matrix.tolist(),  # Convert numpy array to list for JSON serialization
        }
    finally:
        session.close()


def get_clusters() -> List[Dict[str, Any]]:
    """Returns list of available clusters."""
    session = SessionLocal()
    try:
        clusters = session.query(Cluster).all()
        return [{"id": c.id, "name": c.name} for c in clusters]
    finally:
        session.close()


def get_doctypes() -> List[str]:
    """Returns list of available document types."""
    session = SessionLocal()
    try:
        doc_types = session.query(Document.doc_type).distinct().all()
        return [dt[0] for dt in doc_types if dt[0]]
    finally:
        session.close()
