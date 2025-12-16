"""
Annotation System Service

Allow users to add notes, tags, and annotations to:
- Documents
- Entities
- Relationships
- Chunks/Evidence
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, desc
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)



Base = declarative_base()


class Annotation(Base):
    """Annotation model for storing user notes and tags."""

    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True)
    target_type = Column(String(50))  # document, entity, relationship, chunk
    target_id = Column(Integer)
    note = Column(Text)
    tags = Column(Text)  # JSON array of tags
    priority = Column(String(20))  # high, medium, low
    status = Column(String(20))  # open, in_progress, resolved, archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnnotationService:
    """Service for managing annotations."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        # Create table if not exists
        Base.metadata.create_all(self.engine)

    def add_annotation(
        self,
        target_type: str,
        target_id: int,
        note: str,
        tags: List[str] = None,
        priority: str = "medium",
        status: str = "open",
    ) -> Dict[str, Any]:
        """Add a new annotation."""
        session = self.Session()
        try:
            annotation = Annotation(
                target_type=target_type,
                target_id=target_id,
                note=note,
                tags=json.dumps(tags or []),
                priority=priority,
                status=status,
            )
            session.add(annotation)
            session.commit()

            return {
                "id": annotation.id,
                "target_type": annotation.target_type,
                "target_id": annotation.target_id,
                "note": annotation.note,
                "tags": tags or [],
                "priority": annotation.priority,
                "status": annotation.status,
                "created_at": annotation.created_at.isoformat(),
            }
        finally:
            session.close()

    def update_annotation(
        self,
        annotation_id: int,
        note: str = None,
        tags: List[str] = None,
        priority: str = None,
        status: str = None,
    ) -> Dict[str, Any]:
        """Update an existing annotation."""
        session = self.Session()
        try:
            annotation = session.query(Annotation).filter_by(id=annotation_id).first()
            if not annotation:
                return {"error": "Annotation not found"}

            if note is not None:
                annotation.note = note
            if tags is not None:
                annotation.tags = json.dumps(tags)
            if priority is not None:
                annotation.priority = priority
            if status is not None:
                annotation.status = status

            session.commit()

            return {
                "id": annotation.id,
                "note": annotation.note,
                "tags": json.loads(annotation.tags) if annotation.tags else [],
                "priority": annotation.priority,
                "status": annotation.status,
                "updated_at": annotation.updated_at.isoformat(),
            }
        finally:
            session.close()

    def delete_annotation(self, annotation_id: int) -> bool:
        """Delete an annotation."""
        session = self.Session()
        try:
            annotation = session.query(Annotation).filter_by(id=annotation_id).first()
            if annotation:
                session.delete(annotation)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_annotations(
        self,
        target_type: str = None,
        target_id: int = None,
        status: str = None,
        priority: str = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get annotations with optional filters."""
        session = self.Session()
        try:
            query = session.query(Annotation)

            if target_type:
                query = query.filter(Annotation.target_type == target_type)
            if target_id:
                query = query.filter(Annotation.target_id == target_id)
            if status:
                query = query.filter(Annotation.status == status)
            if priority:
                query = query.filter(Annotation.priority == priority)

            annotations = query.order_by(desc(Annotation.created_at)).limit(limit).all()

            return [
                {
                    "id": a.id,
                    "target_type": a.target_type,
                    "target_id": a.target_id,
                    "note": a.note,
                    "tags": json.loads(a.tags) if a.tags else [],
                    "priority": a.priority,
                    "status": a.status,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in annotations
            ]
        finally:
            session.close()

    def get_all_tags(self) -> List[str]:
        """Get all unique tags used in annotations."""
        session = self.Session()
        try:
            annotations = session.query(Annotation.tags).all()
            all_tags = set()

            for (tags_json,) in annotations:
                if tags_json:
                    try:
                        tags = json.loads(tags_json)
                        all_tags.update(tags)
                    except json.JSONDecodeError:
                        pass

            return sorted(list(all_tags))
        finally:
            session.close()

    def get_annotation_stats(self) -> Dict[str, Any]:
        """Get annotation statistics."""
        session = self.Session()
        try:
            total = session.query(Annotation).count()

            by_status = {}
            for status in ["open", "in_progress", "resolved", "archived"]:
                count = session.query(Annotation).filter_by(status=status).count()
                by_status[status] = count

            by_priority = {}
            for priority in ["high", "medium", "low"]:
                count = session.query(Annotation).filter_by(priority=priority).count()
                by_priority[priority] = count

            by_type = {}
            for target_type in ["document", "entity", "relationship", "chunk"]:
                count = (
                    session.query(Annotation).filter_by(target_type=target_type).count()
                )
                by_type[target_type] = count

            return {
                "total": total,
                "by_status": by_status,
                "by_priority": by_priority,
                "by_type": by_type,
            }
        finally:
            session.close()

    def search_annotations(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search annotations by note content."""
        session = self.Session()
        try:
            annotations = (
                session.query(Annotation)
                .filter(Annotation.note.ilike(f"%{query}%"))
                .order_by(desc(Annotation.created_at))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": a.id,
                    "target_type": a.target_type,
                    "target_id": a.target_id,
                    "note": a.note,
                    "tags": json.loads(a.tags) if a.tags else [],
                    "priority": a.priority,
                    "status": a.status,
                }
                for a in annotations
            ]
        finally:
            session.close()


# Singleton
_service_instance = None


def get_annotation_service() -> AnnotationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AnnotationService()
    return _service_instance
