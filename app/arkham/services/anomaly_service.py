import logging
from config.settings import DATABASE_URL, QDRANT_URL, LM_STUDIO_URL
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.arkham.services.db.models import Anomaly, Chunk, Document
from app.arkham.services.embedding_services import embed_hybrid
from app.arkham.services.config import get_config
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from app.arkham.services.utils.security_utils import sanitize_for_llm

logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Qdrant setup
qdrant_client = QdrantClient(url=QDRANT_URL)
COLLECTION_NAME = "arkham_mirror_hybrid"


def get_anomaly_count() -> int:
    """
    Get total count of anomalies in the database.
    """
    session = Session()
    try:
        return session.query(Anomaly).count()
    except Exception as e:
        logger.error(f"Error counting anomalies: {e}")
        return 0
    finally:
        session.close()


def get_anomalies(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch anomalies from the database, sorted by score descending.

    Returns list of anomaly dictionaries with structure matching AnomalyItem TypedDict.
    """
    session = Session()
    try:
        anomalies = (
            session.query(Anomaly, Chunk, Document)
            .join(Chunk, Anomaly.chunk_id == Chunk.id)
            .join(Document, Chunk.doc_id == Document.id)
            .order_by(Anomaly.score.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results = []
        for anom, chunk, doc in anomalies:
            results.append(
                {
                    "id": anom.id,
                    "score": float(anom.score),
                    "reason": anom.reason or "",
                    "chunk_id": chunk.id,
                    "chunk_text": chunk.text[:200] + "..."
                    if len(chunk.text) > 200
                    else chunk.text,
                    "doc_id": doc.id,
                    "doc_title": doc.title or f"Document {doc.id}",
                }
            )

        return results
    except Exception as e:
        logger.error(f"Error fetching anomalies: {e}")
        return []
    finally:
        session.close()


def get_all_documents(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Fetch all documents for the document selector.

    Returns list of document dictionaries with id, title, and doc_type.
    """
    session = Session()
    try:
        documents = session.query(Document).order_by(Document.title).limit(limit).all()

        results = []
        for doc in documents:
            results.append(
                {
                    "id": doc.id,
                    "title": doc.title or f"Document {doc.id}",
                    "doc_type": doc.doc_type or "unknown",
                }
            )

        return results
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return []
    finally:
        session.close()


def get_document_text(doc_id: int) -> str:
    """
    Reconstruct full document text from chunks using chunk_index.
    """
    session = Session()
    try:
        chunks = (
            session.query(Chunk)
            .filter(Chunk.doc_id == doc_id)
            .order_by(Chunk.chunk_index)
            .all()
        )

        if not chunks:
            return "No text available for this document."

        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        full_text = ""
        current_pos = 0

        for c in sorted_chunks:
            start = c.chunk_index
            end = start + len(c.text)

            if start >= current_pos:
                # Gap or contiguous
                full_text += c.text
                current_pos = end
            else:
                # Overlap
                overlap_len = current_pos - start
                if overlap_len < len(c.text):
                    full_text += c.text[overlap_len:]
                    current_pos = end

        return full_text
    except Exception as e:
        logger.error(f"Error reconstructing document text: {e}")
        return f"Error loading document: {str(e)}"
    finally:
        session.close()


def get_rag_response(query: str, doc_ids: Optional[List[int]] = None) -> str:
    """
    Get RAG-based response to a query using vector search and LLM.

    Args:
        query: User's question
        doc_ids: Optional list of document IDs to restrict search to (None means all)

    Returns:
        LLM response string
    """
    try:
        # Get relevant context
        context = _get_relevant_context(query, doc_ids)

        # Use LM Studio for response (or fallback to simple context return)
        try:
            from openai import OpenAI

            llm_client = OpenAI(
                base_url=LM_STUDIO_URL,
                api_key="lm-studio",
            )

            system_msg = (
                "You are an expert forensic investigator analyzing a database of leaked documents. "
                "Your goal is to answer the user's questions accurately based ONLY on the provided context snippets. "
                "CRITICAL INSTRUCTION: When you cite information, you MUST include BOTH the Document Title and the Chunk ID in your citation. "
                "Format your citations exactly like this: [Source: Document Title | Chunk ID: 123]. "
                "\n\n"
                "If the answer is not in the context, say 'I cannot find that information in the provided documents.'"
            )

            messages = [
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": f"Context:\n{sanitize_for_llm(context)}\n\nQuestion: {sanitize_for_llm(query)}",
                },
            ]

            response = llm_client.chat.completions.create(
                model="local-model",
                messages=messages,
                temperature=get_config("ui.llm.temperature", 0.3),
                stream=False,
            )

            return response.choices[0].message.content

        except Exception as llm_error:
            # Fallback: return context directly if LLM not available
            logger.warning(f"LLM not available: {llm_error}")
            return f"LLM not available. Here's the relevant context:\n\n{context}"

    except Exception as e:
        return f"Error processing question: {str(e)}"


def _get_relevant_context(query: str, doc_ids: Optional[List[int]] = None) -> str:
    """
    Retrieve relevant chunks and anomaly info based on the query.

    Args:
        query: User's question
        doc_ids: Optional list of document IDs to filter by (None means all)
    """
    context_parts = []

    # 1. Vector Search (RAG)
    try:
        q_vecs = embed_hybrid(query)

        search_filter = None
        if doc_ids:
            # Use 'any' match for multiple doc IDs
            from qdrant_client.http.models import HasIdCondition

            search_filter = Filter(
                should=[
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
                    for doc_id in doc_ids
                ]
            )

        # Prepare sparse vector
        sparse_indices = list(map(int, q_vecs["sparse"].keys()))
        sparse_values = list(map(float, q_vecs["sparse"].values()))
        sparse_vector = models.SparseVector(
            indices=sparse_indices, values=sparse_values
        )

        limit = 10  # Limit for RAG context

        hits = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=q_vecs["dense"],
                    using="dense",
                    filter=search_filter,
                    limit=limit,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    filter=search_filter,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        ).points

        if hits:
            # Fetch document titles
            doc_ids = {
                hit.payload.get("doc_id") for hit in hits if "doc_id" in hit.payload
            }
            doc_titles = {}
            if doc_ids:
                session = Session()
                try:
                    docs = (
                        session.query(Document.id, Document.title)
                        .filter(Document.id.in_(doc_ids))
                        .all()
                    )
                    doc_titles = {doc_id: title for doc_id, title in docs}
                finally:
                    session.close()

            context_parts.append("### Relevant Text Segments:")
            for hit in hits:
                meta = hit.payload
                doc_title = doc_titles.get(meta.get("doc_id"), "Unknown Document")
                context_parts.append(
                    f"- [Source: {doc_title} | Chunk ID: {hit.id}] {meta.get('text', '')}"
                )
    except Exception as e:
        context_parts.append(f"Error searching vectors: {e}")

    # 2. Anomaly Context (if keyword detected)
    if (
        "anomal" in query.lower()
        or "outlier" in query.lower()
        or "suspicious" in query.lower()
    ):
        session = Session()
        try:
            count = session.query(Anomaly).count()
            context_parts.append(
                f"\n### Anomaly Data:\nTotal Anomalies Detected: {count}"
            )

            q = (
                session.query(Anomaly, Chunk)
                .join(Chunk, Anomaly.chunk_id == Chunk.id)
                .order_by(Anomaly.score.desc())
            )
            if doc_ids:
                q = q.filter(Chunk.doc_id.in_(doc_ids))

            top_anoms = q.limit(5).all()
            if top_anoms:
                context_parts.append("Top Severity Anomalies:")
                for a, c in top_anoms:
                    context_parts.append(
                        f"- Score {a.score:.2f}: {a.reason} (Chunk ID: {c.id})"
                    )
        finally:
            session.close()

    return "\n\n".join(context_parts)
