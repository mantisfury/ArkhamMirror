import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    desc,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

from config.settings import DATABASE_URL

load_dotenv()
logger = logging.getLogger(__name__)


Base = declarative_base()


class Project(Base):
    """Project/Case model."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")  # active, archived, completed
    priority = Column(String(20), default="medium")  # high, medium, low
    tags = Column(Text)  # JSON array of tags
    color = Column(String(20), default="blue")  # For UI theming
    lead_investigator = Column(String(255))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectService:
    """Service for managing projects/cases."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        # Create tables if not exists (Project table)
        # Note: Document table is defined elsewhere, but we assume it exists
        Base.metadata.create_all(self.engine)

    def ensure_default_project(self) -> Dict[str, Any]:
        """
        Ensure the Default Project (ID=1) exists.

        Called on app startup to guarantee there's always a project
        for documents to be assigned to.

        Returns:
            Dict with default project info
        """
        session = self.Session()
        try:
            # Check if Default Project exists
            default = session.query(Project).filter_by(id=1).first()
            if default:
                return {"id": default.id, "name": default.name, "exists": True}

            # Create Default Project with ID=1
            # Use raw SQL to set specific ID
            from sqlalchemy import text

            session.execute(
                text("""
                INSERT INTO projects (id, name, description, status, priority, color)
                VALUES (1, 'Default Project', 'Default project for unassigned documents', 'active', 'medium', 'blue')
                ON CONFLICT (id) DO NOTHING
            """)
            )
            session.commit()

            logger.info("✓ Created Default Project (ID=1)")
            return {
                "id": 1,
                "name": "Default Project",
                "exists": False,
                "created": True,
            }
        except Exception as e:
            logger.error(f"Error ensuring default project: {e}")
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def create_project(
        self,
        name: str,
        description: str = "",
        priority: str = "medium",
        tags: List[str] = None,
        color: str = "blue",
        lead_investigator: str = "",
    ) -> Dict[str, Any]:
        """Create a new project."""
        session = self.Session()
        try:
            project = Project(
                name=name,
                description=description,
                priority=priority,
                tags=json.dumps(tags or []),
                color=color,
                lead_investigator=lead_investigator,
            )
            session.add(project)
            session.commit()

            return {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "priority": project.priority,
                "tags": tags or [],
                "color": project.color,
                "created_at": project.created_at.isoformat(),
            }
        finally:
            session.close()

    def update_project(
        self,
        project_id: int,
        name: str = None,
        description: str = None,
        status: str = None,
        priority: str = None,
        tags: List[str] = None,
        color: str = None,
        lead_investigator: str = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        """Update a project."""
        session = self.Session()
        try:
            project = session.query(Project).filter_by(id=project_id).first()
            if not project:
                return {"error": "Project not found"}

            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            if status is not None:
                project.status = status
            if priority is not None:
                project.priority = priority
            if tags is not None:
                project.tags = json.dumps(tags)
            if color is not None:
                project.color = color
            if lead_investigator is not None:
                project.lead_investigator = lead_investigator
            if notes is not None:
                project.notes = notes

            session.commit()

            return {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "updated_at": project.updated_at.isoformat()
                if project.updated_at
                else None,
            }
        finally:
            session.close()

    def delete_project(self, project_id: int) -> bool:
        """
        Delete a project.
        Moves all associated documents to the Default Project (ID=1).
        """
        if project_id == 1:
            logger.error("Cannot delete Default Project (ID=1)")
            return False

        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            # Move documents to Default Project
            session.query(DocModel).filter(DocModel.project_id == project_id).update(
                {"project_id": 1}
            )

            # Delete project
            project = session.query(Project).filter_by(id=project_id).first()
            if project:
                session.delete(project)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get a single project with details."""
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            project = session.query(Project).filter_by(id=project_id).first()
            if not project:
                return None

            # Count documents using Document.project_id
            doc_count = (
                session.query(DocModel)
                .filter(DocModel.project_id == project_id)
                .count()
            )

            return {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "priority": project.priority,
                "tags": json.loads(project.tags) if project.tags else [],
                "color": project.color,
                "lead_investigator": project.lead_investigator,
                "notes": project.notes,
                "document_count": doc_count,
                "created_at": project.created_at.isoformat()
                if project.created_at
                else None,
                "updated_at": project.updated_at.isoformat()
                if project.updated_at
                else None,
            }
        finally:
            session.close()

    def list_projects(
        self, status: str = None, priority: str = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List all projects with optional filters."""
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            query = session.query(Project)

            if status and status != "all":
                query = query.filter(Project.status == status)
            if priority and priority != "all":
                query = query.filter(Project.priority == priority)

            projects = query.order_by(desc(Project.updated_at)).limit(limit).all()

            result = []
            for p in projects:
                # Use Document.project_id directly
                doc_count = (
                    session.query(DocModel).filter(DocModel.project_id == p.id).count()
                )
                result.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description or "",
                        "status": p.status,
                        "priority": p.priority,
                        "tags": json.loads(p.tags) if p.tags else [],
                        "color": p.color,
                        "document_count": doc_count,
                        "updated_at": p.updated_at.isoformat()
                        if p.updated_at
                        else None,
                    }
                )

            return result
        finally:
            session.close()

    def add_document_to_project(
        self, project_id: int, document_id: int, notes: str = ""
    ) -> Dict[str, Any]:
        """Associate a document with a project by setting Document.project_id."""
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            doc = session.query(DocModel).filter_by(id=document_id).first()
            if not doc:
                return {"error": "Document not found"}

            if doc.project_id == project_id:
                return {"error": "Document already in project"}

            # Set project_id directly
            doc.project_id = project_id
            session.commit()

            return {
                "document_id": document_id,
                "project_id": project_id,
                "success": True,
            }
        finally:
            session.close()

    def remove_document_from_project(self, project_id: int, document_id: int) -> bool:
        """Remove a document from a project (moves to Default Project)."""
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            doc = (
                session.query(DocModel)
                .filter_by(id=document_id, project_id=project_id)
                .first()
            )
            if doc:
                # Move to Default Project (ID=1) instead of leaving orphaned
                doc.project_id = 1
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_project_documents(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all documents in a project using Document.project_id."""
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document as DocModel

            docs = (
                session.query(DocModel).filter(DocModel.project_id == project_id).all()
            )

            result = []
            for doc in docs:
                result.append(
                    {
                        "document_id": doc.id,
                        "filename": doc.title or doc.path.split("/")[-1]
                        if doc.path
                        else f"Document {doc.id}",
                        "file_type": doc.doc_type or "",
                        "added_at": doc.created_at.isoformat()
                        if doc.created_at
                        else None,
                        "notes": "",  # Notes stored at document level if needed
                    }
                )

            return result
        finally:
            session.close()

    def get_project_stats(self) -> Dict[str, Any]:
        """Get project statistics."""
        session = self.Session()
        try:
            total = session.query(Project).count()

            by_status = {}
            for status in ["active", "archived", "completed"]:
                count = session.query(Project).filter_by(status=status).count()
                by_status[status] = count

            by_priority = {}
            for priority in ["high", "medium", "low"]:
                count = session.query(Project).filter_by(priority=priority).count()
                by_priority[priority] = count

            return {
                "total": total,
                "by_status": by_status,
                "by_priority": by_priority,
            }
        finally:
            session.close()


# Singleton
_service_instance = None


def get_project_service() -> ProjectService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ProjectService()
    return _service_instance