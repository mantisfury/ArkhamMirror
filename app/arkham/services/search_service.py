import logging

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL, QDRANT_URL
import os
import sys
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from .embedding_services import embed_hybrid

from app.arkham.services.db.models import Document, TimelineEvent
from app.arkham.services.config import get_config

# Initialize Qdrant client
# Note: In a real production app, we might want to dependency inject this or use a singleton pattern
qdrant_client = QdrantClient(url=QDRANT_URL)
COLLECTION_NAME = "arkham_mirror_hybrid"


def hybrid_search(
    query: str,
    project_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    entity_type: Optional[str] = None,
    doc_type: Optional[str] = None,
    allowed_doc_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (dense + sparse) using Qdrant with optimized filtering.

    Args:
        query: Search query string
        project_id: Optional project ID to filter by (int)
        limit: Number of results to return
        offset: Offset for pagination (not fully supported by Qdrant search, used for slicing)
        date_from: Start date filter (ISO string)
        date_to: End date filter (ISO string)
        allowed_doc_ids: List of document IDs to restrict search to

    Returns:
        List of search results
    """
    try:
        # Generate embeddings (cached via LRU)
        q_vecs = embed_hybrid(query)

        # Build Filter with all conditions
        must_conditions = []

        # Project Filter - filter by project if specified and not ID 0 (all projects)
        if project_id and project_id > 0:
            must_conditions.append(
                FieldCondition(key="project_id", match=MatchValue(value=project_id))
            )

        # Document Filter
        if allowed_doc_ids:
            must_conditions.append(
                FieldCondition(
                    key="doc_id",
                    match=models.MatchAny(any=allowed_doc_ids),
                )
            )

        # Date range filter (if date fields exist in payload)
        if date_from:
            must_conditions.append(
                FieldCondition(
                    key="created_at", range=models.DatetimeRange(gte=date_from)
                )
            )
        if date_to:
            must_conditions.append(
                FieldCondition(
                    key="created_at", range=models.DatetimeRange(lte=date_to)
                )
            )

        search_filter = Filter(must=must_conditions) if must_conditions else None

        # Prepare sparse vector
        sparse_indices = list(map(int, q_vecs["sparse"].keys()))
        sparse_values = list(map(float, q_vecs["sparse"].values()))
        sparse_vector = models.SparseVector(
            indices=sparse_indices, values=sparse_values
        )

        # Optimize prefetch limit - fetch 2x more for dense/sparse individually for better fusion results
        # But overall limit stays constrained
        prefetch_limit = min(
            (limit + offset) * 2, 100
        )  # Cap at 100 to prevent over-fetching

        # Execute Hybrid Search with optimized parameters
        hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=q_vecs["dense"],
                    using="dense",
                    filter=search_filter,
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    filter=search_filter,
                    limit=prefetch_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit + offset,
            with_payload=True,  # Explicit payload fetching
        ).points

        # Apply offset manually since we fetched extra
        hits = hits[offset:]

        # Get unique doc_ids to fetch titles
        doc_ids = list(
            set(hit.payload.get("doc_id") for hit in hits if hit.payload.get("doc_id"))
        )

        # Fetch document titles from database
        doc_titles = {}
        if doc_ids:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            import os

            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
                doc_titles = {d.id: d.title or d.path for d in docs}
            finally:
                session.close()

        # Format results with optimized snippet generation
        results = []
        for hit in hits:
            text = hit.payload.get("text", "")
            doc_id = hit.payload.get("doc_id")
            # Only generate snippet if text exists and is long enough
            snippet = text[:200] + "..." if len(text) > 200 else text

            # Enrich metadata with title
            metadata = dict(hit.payload)
            metadata["title"] = doc_titles.get(doc_id, f"Document #{doc_id}")

            results.append(
                {
                    "id": hit.id,
                    "score": hit.score,
                    "doc_id": doc_id,
                    "text": text,
                    "snippet": snippet,
                    "metadata": metadata,
                }
            )

        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise e


def get_document_content(doc_id: int) -> str:
    """
    Reconstruct full document content by fetching all chunks in order.

    Args:
        doc_id: Document ID to fetch

    Returns:
        Full document text with all chunks concatenated
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    # Import Chunk model
    from app.arkham.services.db.models import Chunk

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Fetch all chunks for this document, ordered by chunk_index
        chunks = (
            session.query(Chunk)
            .filter(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
            .all()
        )

        if not chunks:
            return f"No content found for document #{doc_id}"

        # Concatenate all chunk texts with visual separators
        content_parts = []
        for i, chunk in enumerate(chunks):
            content_parts.append(f"--- Chunk {i + 1}/{len(chunks)} ---\n")
            content_parts.append(chunk.text or "")
            content_parts.append("\n\n")

        return "".join(content_parts)

    except Exception as e:
        logger.error(f"Error fetching document content: {e}")
        return f"Error loading document: {e}"
    finally:
        session.close()


def get_document_title(doc_id: int) -> str:
    """Get document title from database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if doc:
            return doc.title or doc.path
        return None
    except Exception as e:
        logger.error(f"Error fetching document title: {e}")
        return None
    finally:
        session.close()
