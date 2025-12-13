"""
Advanced Filtering Service

Cross-page filtering capabilities:
- Entity type filters
- Date range filters
- Document filters
- Priority/status filters
- Tag filters
- Full-text search
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func, and_, or_, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    Document,
    Chunk,
    CanonicalEntity,
    Entity,
    EntityRelationship,
)

load_dotenv()
logger = logging.getLogger(__name__)




class FilterService:
    """Service for advanced filtering."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_filter_options(self) -> Dict[str, Any]:
        """Get all available filter options."""
        session = self.Session()
        try:
            # Entity types
            entity_types = session.query(CanonicalEntity.label).distinct().all()
            entity_types = [t[0] for t in entity_types if t[0]]

            # File types
            file_types = session.query(Document.doc_type).distinct().all()
            file_types = [t[0] for t in file_types if t[0]]

            # Date range
            earliest = session.query(func.min(Document.created_at)).scalar()
            latest = session.query(func.max(Document.created_at)).scalar()

            return {
                "entity_types": sorted(entity_types),
                "file_types": sorted(file_types),
                "date_range": {
                    "earliest": earliest.isoformat() if earliest else None,
                    "latest": latest.isoformat() if latest else None,
                },
            }
        finally:
            session.close()

    def filter_documents(
        self,
        file_types: List[str] = None,
        date_from: str = None,
        date_to: str = None,
        search_text: str = None,
        has_entities: bool = None,
        min_chunks: int = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Filter documents with multiple criteria."""
        session = self.Session()
        try:
            query = session.query(Document)

            if file_types:
                query = query.filter(Document.doc_type.in_(file_types))

            if date_from:
                try:
                    from_date = datetime.fromisoformat(date_from)
                    query = query.filter(Document.created_at >= from_date)
                except ValueError:
                    pass

            if date_to:
                try:
                    to_date = datetime.fromisoformat(date_to)
                    query = query.filter(Document.created_at <= to_date)
                except ValueError:
                    pass

            if search_text:
                query = query.filter(Document.filename.ilike(f"%{search_text}%"))

            documents = query.order_by(desc(Document.created_at)).limit(limit).all()

            results = []
            for doc in documents:
                # Count chunks
                chunk_count = (
                    session.query(func.count(Chunk.id))
                    .filter(Chunk.doc_id == doc.id)
                    .scalar()
                )

                if min_chunks and chunk_count < min_chunks:
                    continue

                # Count unique entities
                entity_count = (
                    session.query(
                        func.count(func.distinct(Entity.canonical_entity_id))
                    )
                    .filter(Entity.doc_id == doc.id)
                    .scalar()
                ) or 0

                if has_entities is True and entity_count == 0:
                    continue
                elif has_entities is False and entity_count > 0:
                    continue

                results.append(
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "file_type": doc.doc_type,
                        "chunk_count": chunk_count,
                        "entity_count": entity_count,
                        "created_at": doc.created_at.isoformat()
                        if doc.created_at
                        else None,
                    }
                )

            return results
        finally:
            session.close()

    def filter_entities(
        self,
        entity_types: List[str] = None,
        min_mentions: int = None,
        max_mentions: int = None,
        has_relationships: bool = None,
        search_text: str = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Filter entities with multiple criteria."""
        session = self.Session()
        try:
            query = session.query(CanonicalEntity)

            if entity_types:
                query = query.filter(CanonicalEntity.label.in_(entity_types))

            if min_mentions is not None:
                query = query.filter(CanonicalEntity.total_mentions >= min_mentions)

            if max_mentions is not None:
                query = query.filter(CanonicalEntity.total_mentions <= max_mentions)

            if search_text:
                query = query.filter(
                    or_(
                        CanonicalEntity.canonical_name.ilike(f"%{search_text}%"),
                        CanonicalEntity.aliases.ilike(f"%{search_text}%"),
                    )
                )

            entities = (
                query.order_by(desc(CanonicalEntity.total_mentions)).limit(limit).all()
            )

            results = []
            for entity in entities:
                # Count relationships
                rel_count = (
                    session.query(func.count(EntityRelationship.id))
                    .filter(
                        or_(
                            EntityRelationship.entity1_id == entity.id,
                            EntityRelationship.entity2_id == entity.id,
                        )
                    )
                    .scalar()
                ) or 0

                if has_relationships is True and rel_count == 0:
                    continue
                elif has_relationships is False and rel_count > 0:
                    continue

                results.append(
                    {
                        "id": entity.id,
                        "name": entity.canonical_name,
                        "type": entity.label,
                        "mentions": entity.total_mentions,
                        "relationship_count": rel_count,
                        "aliases": entity.aliases.split(",") if entity.aliases else [],
                    }
                )

            return results
        finally:
            session.close()

    def get_entity_stats(self) -> Dict[str, Any]:
        """Get entity statistics for filter UI."""
        session = self.Session()
        try:
            # By type
            by_type = (
                session.query(CanonicalEntity.label, func.count(CanonicalEntity.id))
                .group_by(CanonicalEntity.label)
                .all()
            )

            # Mention ranges
            min_mentions = (
                session.query(func.min(CanonicalEntity.total_mentions)).scalar() or 0
            )
            max_mentions = (
                session.query(func.max(CanonicalEntity.total_mentions)).scalar() or 0
            )
            avg_mentions = (
                session.query(func.avg(CanonicalEntity.total_mentions)).scalar() or 0
            )

            return {
                "by_type": {t: c for t, c in by_type if t},
                "mention_range": {
                    "min": min_mentions,
                    "max": max_mentions,
                    "avg": round(avg_mentions, 1),
                },
            }
        finally:
            session.close()

    def get_document_stats(self) -> Dict[str, Any]:
        """Get document statistics for filter UI."""
        session = self.Session()
        try:
            total = session.query(func.count(Document.id)).scalar() or 0

            # By file type
            by_type = (
                session.query(Document.doc_type, func.count(Document.id))
                .group_by(Document.doc_type)
                .all()
            )

            # By date (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_count = (
                session.query(func.count(Document.id))
                .filter(Document.created_at >= thirty_days_ago)
                .scalar()
            ) or 0

            return {
                "total": total,
                "by_type": {t or "unknown": c for t, c in by_type},
                "recent_30_days": recent_count,
            }
        finally:
            session.close()


# Singleton
_service_instance = None


def get_filter_service() -> FilterService:
    global _service_instance
    if _service_instance is None:
        _service_instance = FilterService()
    return _service_instance
