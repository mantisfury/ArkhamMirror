"""
Document Comparison Service

Side-by-side comparison of documents:
- Highlight shared entities
- Show common themes
- Identify differences
"""

import os
import logging
import difflib
from typing import Dict, Any, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    Document,
    Chunk,
    EntityMention,
    CanonicalEntity,
)
from app.arkham.services.utils.security_utils import get_display_filename

load_dotenv()
logger = logging.getLogger(__name__)




class ComparisonService:
    """Service for comparing documents."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_document_content(self, doc_id: int) -> Dict[str, Any]:
        """Get document content and metadata."""
        session = self.Session()
        try:
            doc = session.query(Document).filter_by(id=doc_id).first()
            if not doc:
                return {"error": "Document not found"}

            chunks = (
                session.query(Chunk)
                .filter_by(doc_id=doc_id)
                .order_by(Chunk.chunk_index)
                .all()
            )

            full_text = "\n\n".join([c.text for c in chunks])

            # Get entities
            entity_ids = set()
            for chunk in chunks:
                mentions = (
                    session.query(EntityMention.canonical_entity_id)
                    .filter(EntityMention.chunk_id == chunk.id)
                    .distinct()
                    .all()
                )
                entity_ids.update(m[0] for m in mentions if m[0])

            entities = (
                (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(list(entity_ids)))
                    .all()
                )
                if entity_ids
                else []
            )

            return {
                "id": doc.id,
                "filename": get_display_filename(doc),
                "file_type": doc.doc_type or "unknown",
                "text": full_text,
                "chunk_count": len(chunks),
                "entities": [
                    {"id": e.id, "name": e.canonical_name, "type": e.label}
                    for e in entities
                ],
            }
        finally:
            session.close()

    def get_available_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of available documents for comparison."""
        session = self.Session()
        try:
            documents = session.query(Document).limit(limit).all()
            return [
                {
                    "id": d.id,
                    "filename": get_display_filename(d),
                    "file_type": d.doc_type or "unknown",
                }
                for d in documents
            ]
        finally:
            session.close()

    def compare_entities(self, doc1_id: int, doc2_id: int) -> Dict[str, Any]:
        """Compare entities between two documents."""
        doc1 = self.get_document_content(doc1_id)
        doc2 = self.get_document_content(doc2_id)

        if "error" in doc1 or "error" in doc2:
            return {"error": "Could not load documents"}

        entities1 = {e["id"]: e for e in doc1["entities"]}
        entities2 = {e["id"]: e for e in doc2["entities"]}

        shared_ids = set(entities1.keys()) & set(entities2.keys())
        only_doc1_ids = set(entities1.keys()) - set(entities2.keys())
        only_doc2_ids = set(entities2.keys()) - set(entities1.keys())

        return {
            "shared": [entities1[eid] for eid in shared_ids],
            "only_doc1": [entities1[eid] for eid in only_doc1_ids],
            "only_doc2": [entities2[eid] for eid in only_doc2_ids],
            "shared_count": len(shared_ids),
            "similarity_score": (
                len(shared_ids) / max(len(entities1), len(entities2), 1) * 100
                if entities1 or entities2
                else 0
            ),
        }

    def compare_text(self, doc1_id: int, doc2_id: int) -> Dict[str, Any]:
        """Compare text content between documents."""
        doc1 = self.get_document_content(doc1_id)
        doc2 = self.get_document_content(doc2_id)

        if "error" in doc1 or "error" in doc2:
            return {"error": "Could not load documents"}

        # Split into lines for diff
        lines1 = doc1["text"].splitlines()
        lines2 = doc2["text"].splitlines()

        # Get diff
        differ = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=doc1["filename"],
            tofile=doc2["filename"],
            lineterm="",
        )
        diff_lines = list(differ)

        # Calculate similarity ratio
        matcher = difflib.SequenceMatcher(None, doc1["text"], doc2["text"])
        similarity = matcher.ratio() * 100

        # Find common sequences
        matching_blocks = matcher.get_matching_blocks()
        common_phrases = []
        for block in matching_blocks[:10]:
            if block.size > 30:
                phrase = doc1["text"][block.a : block.a + block.size]
                if phrase.strip():
                    common_phrases.append(phrase[:100])

        return {
            "diff": "\n".join(diff_lines[:200]),  # Limit diff size
            "similarity": round(similarity, 1),
            "doc1_lines": len(lines1),
            "doc2_lines": len(lines2),
            "common_phrases": common_phrases[:5],
        }

    def full_comparison(self, doc1_id: int, doc2_id: int) -> Dict[str, Any]:
        """Full comparison of two documents."""
        doc1 = self.get_document_content(doc1_id)
        doc2 = self.get_document_content(doc2_id)

        if "error" in doc1 or "error" in doc2:
            return {"error": "Could not load documents"}

        entity_comparison = self.compare_entities(doc1_id, doc2_id)
        text_comparison = self.compare_text(doc1_id, doc2_id)

        return {
            "doc1": {
                "id": doc1["id"],
                "filename": doc1["filename"],
                "chunk_count": doc1["chunk_count"],
                "entity_count": len(doc1["entities"]),
            },
            "doc2": {
                "id": doc2["id"],
                "filename": doc2["filename"],
                "chunk_count": doc2["chunk_count"],
                "entity_count": len(doc2["entities"]),
            },
            "entities": entity_comparison,
            "text": text_comparison,
        }


# Singleton
_service_instance = None


def get_comparison_service() -> ComparisonService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ComparisonService()
    return _service_instance
