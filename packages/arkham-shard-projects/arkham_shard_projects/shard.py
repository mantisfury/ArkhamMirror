"""
Projects Shard - Main Shard Implementation

Project workspace management for ArkhamFrame - organize documents,
entities, and analyses into collaborative workspaces.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    Project,
    ProjectActivity,
    ProjectDocument,
    ProjectFilter,
    ProjectMember,
    ProjectRole,
    ProjectStatistics,
    ProjectStatus,
)

logger = logging.getLogger(__name__)


class ProjectsShard(ArkhamShard):
    """
    Projects Shard - Manages project workspaces.

    This shard provides:
    - Project creation and management
    - Document grouping and association
    - Member management with role-based access
    - Activity tracking and logging
    - Project templates and statistics
    """

    name = "projects"
    version = "0.1.0"
    description = "Project workspace management for organizing documents, entities, and analyses"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._storage = None
        self._initialized = False

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._storage = getattr(frame, "storage", None)

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        await self._subscribe_to_events()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.projects_shard = self

        self._initialized = True
        logger.info(f"ProjectsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        if self._events:
            await self._events.unsubscribe("document.created", self._on_document_created)
            await self._events.unsubscribe("entity.created", self._on_entity_created)

        self._initialized = False
        logger.info("ProjectsShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for projects shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                owner_id TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                settings TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                member_count INTEGER DEFAULT 0,
                document_count INTEGER DEFAULT 0
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_project_members (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                added_at TEXT,
                added_by TEXT DEFAULT 'system',
                FOREIGN KEY (project_id) REFERENCES arkham_projects(id),
                UNIQUE(project_id, user_id)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_project_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                added_at TEXT,
                added_by TEXT DEFAULT 'system',
                FOREIGN KEY (project_id) REFERENCES arkham_projects(id),
                UNIQUE(project_id, document_id)
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_project_activity (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT,
                target_type TEXT DEFAULT 'project',
                target_id TEXT,
                timestamp TEXT,
                details TEXT DEFAULT '{}',
                FOREIGN KEY (project_id) REFERENCES arkham_projects(id)
            )
        """)

        # Create indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_status ON arkham_projects(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_owner ON arkham_projects(owner_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_members_project ON arkham_project_members(project_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_members_user ON arkham_project_members(user_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_project ON arkham_project_documents(project_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_project ON arkham_project_activity(project_id)
        """)

        logger.debug("Projects schema created/verified")

    # === Event Subscriptions ===

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events from other shards."""
        if not self._events:
            logger.warning("Events service not available")
            return

        await self._events.subscribe("document.created", self._on_document_created)
        await self._events.subscribe("entity.created", self._on_entity_created)

    async def _on_document_created(self, event: Dict[str, Any]) -> None:
        """Handle document.created event - auto-associate with active project."""
        document_id = event.get("payload", {}).get("document_id")
        if not document_id:
            return

        # Check for active project context in event metadata
        project_id = event.get("metadata", {}).get("project_id")
        if project_id:
            logger.info(f"Auto-associating document {document_id} with project {project_id}")
            # Would add document to project here in real implementation

    async def _on_entity_created(self, event: Dict[str, Any]) -> None:
        """Handle entity.created event - track in project context."""
        entity_id = event.get("payload", {}).get("entity_id")
        project_id = event.get("metadata", {}).get("project_id")
        if entity_id and project_id:
            logger.debug(f"Entity {entity_id} created in project {project_id} context")

    # === Public API Methods ===

    async def create_project(
        self,
        name: str,
        description: str = "",
        owner_id: str = "system",
        status: ProjectStatus = ProjectStatus.ACTIVE,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Project:
        """Create a new project."""
        project_id = str(uuid4())
        now = datetime.utcnow()

        project = Project(
            id=project_id,
            name=name,
            description=description,
            status=status,
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
            settings=settings or {},
            metadata=metadata or {},
        )

        await self._save_project(project)

        # Log activity
        await self._log_activity(
            project_id=project_id,
            action="created",
            actor_id=owner_id,
            target_type="project",
            target_id=project_id,
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.project.created",
                {
                    "project_id": project_id,
                    "name": name,
                    "owner_id": owner_id,
                },
                source=self.name,
            )

        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_projects WHERE id = ?",
            [project_id],
        )
        return self._row_to_project(row) if row else None

    async def list_projects(
        self,
        filter: Optional[ProjectFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Project]:
        """List projects with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_projects WHERE 1=1"
        params = []

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.owner_id:
                query += " AND owner_id = ?"
                params.append(filter.owner_id)
            if filter.search_text:
                query += " AND (name LIKE ? OR description LIKE ?)"
                search_term = f"%{filter.search_text}%"
                params.extend([search_term, search_term])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_project(row) for row in rows]

    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[ProjectStatus] = None,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Project]:
        """Update a project."""
        project = await self.get_project(project_id)
        if not project:
            return None

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            old_status = project.status
            project.status = status
            if old_status != status:
                await self._log_activity(
                    project_id=project_id,
                    action=f"status_changed_{status.value}",
                    actor_id="system",
                    details={"old_status": old_status.value, "new_status": status.value},
                )
        if settings is not None:
            project.settings = settings
        if metadata is not None:
            project.metadata = metadata

        project.updated_at = datetime.utcnow()
        await self._save_project(project, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.project.updated",
                {"project_id": project_id, "name": project.name},
                source=self.name,
            )

        return project

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        if not self._db:
            return False

        await self._db.execute("DELETE FROM arkham_projects WHERE id = ?", [project_id])

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.project.deleted",
                {"project_id": project_id},
                source=self.name,
            )

        return True

    async def add_document(
        self,
        project_id: str,
        document_id: str,
        added_by: str = "system",
    ) -> ProjectDocument:
        """Add a document to a project."""
        doc_id = str(uuid4())
        now = datetime.utcnow()

        project_doc = ProjectDocument(
            id=doc_id,
            project_id=project_id,
            document_id=document_id,
            added_at=now,
            added_by=added_by,
        )

        await self._save_project_document(project_doc)
        await self._update_project_counts(project_id)

        # Log activity
        await self._log_activity(
            project_id=project_id,
            action="document_added",
            actor_id=added_by,
            target_type="document",
            target_id=document_id,
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.document.added",
                {"project_id": project_id, "document_id": document_id},
                source=self.name,
            )

        return project_doc

    async def remove_document(
        self,
        project_id: str,
        document_id: str,
    ) -> bool:
        """Remove a document from a project."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_project_documents WHERE project_id = ? AND document_id = ?",
            [project_id, document_id],
        )

        await self._update_project_counts(project_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.document.removed",
                {"project_id": project_id, "document_id": document_id},
                source=self.name,
            )

        return True

    async def add_member(
        self,
        project_id: str,
        user_id: str,
        role: ProjectRole = ProjectRole.VIEWER,
        added_by: str = "system",
    ) -> ProjectMember:
        """Add a member to a project."""
        member_id = str(uuid4())
        now = datetime.utcnow()

        member = ProjectMember(
            id=member_id,
            project_id=project_id,
            user_id=user_id,
            role=role,
            added_at=now,
            added_by=added_by,
        )

        await self._save_project_member(member)
        await self._update_project_counts(project_id)

        # Log activity
        await self._log_activity(
            project_id=project_id,
            action="member_added",
            actor_id=added_by,
            target_type="member",
            target_id=user_id,
            details={"role": role.value},
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.member.added",
                {"project_id": project_id, "user_id": user_id, "role": role.value},
                source=self.name,
            )

        return member

    async def remove_member(
        self,
        project_id: str,
        user_id: str,
    ) -> bool:
        """Remove a member from a project."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_project_members WHERE project_id = ? AND user_id = ?",
            [project_id, user_id],
        )

        await self._update_project_counts(project_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.member.removed",
                {"project_id": project_id, "user_id": user_id},
                source=self.name,
            )

        return True

    async def get_activity(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProjectActivity]:
        """Get activity log for a project."""
        if not self._db:
            return []

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_project_activity WHERE project_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            [project_id, limit, offset],
        )
        return [self._row_to_activity(row) for row in rows]

    async def get_statistics(self) -> ProjectStatistics:
        """Get statistics about projects in the system."""
        if not self._db:
            return ProjectStatistics()

        # Stub implementation - returns empty stats
        return ProjectStatistics()

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of projects, optionally filtered by status."""
        if not self._db:
            return 0

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_projects WHERE status = ?",
                [status],
            )
        else:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_projects"
            )

        return result["count"] if result else 0

    # === Private Helper Methods ===

    async def _save_project(self, project: Project, update: bool = False) -> None:
        """Save a project to the database."""
        if not self._db:
            return

        import json
        data = (
            project.id,
            project.name,
            project.description,
            project.status.value,
            project.owner_id,
            project.created_at.isoformat(),
            project.updated_at.isoformat(),
            json.dumps(project.settings),
            json.dumps(project.metadata),
            project.member_count,
            project.document_count,
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_projects SET
                    name=?, description=?, status=?, owner_id=?,
                    created_at=?, updated_at=?, settings=?, metadata=?,
                    member_count=?, document_count=?
                WHERE id=?
            """, data[1:] + (project.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_projects (
                    id, name, description, status, owner_id,
                    created_at, updated_at, settings, metadata,
                    member_count, document_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_project_member(self, member: ProjectMember) -> None:
        """Save a project member to the database."""
        if not self._db:
            return

        await self._db.execute("""
            INSERT INTO arkham_project_members (
                id, project_id, user_id, role, added_at, added_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            member.id,
            member.project_id,
            member.user_id,
            member.role.value,
            member.added_at.isoformat(),
            member.added_by,
        ))

    async def _save_project_document(self, doc: ProjectDocument) -> None:
        """Save a project document to the database."""
        if not self._db:
            return

        await self._db.execute("""
            INSERT INTO arkham_project_documents (
                id, project_id, document_id, added_at, added_by
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            doc.id,
            doc.project_id,
            doc.document_id,
            doc.added_at.isoformat(),
            doc.added_by,
        ))

    async def _log_activity(
        self,
        project_id: str,
        action: str,
        actor_id: str,
        target_type: str = "project",
        target_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an activity entry for a project."""
        if not self._db:
            return

        import json
        activity_id = str(uuid4())

        await self._db.execute("""
            INSERT INTO arkham_project_activity (
                id, project_id, action, actor_id, target_type, target_id, timestamp, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            activity_id,
            project_id,
            action,
            actor_id,
            target_type,
            target_id,
            datetime.utcnow().isoformat(),
            json.dumps(details or {}),
        ))

    async def _update_project_counts(self, project_id: str) -> None:
        """Update member and document counts for a project."""
        if not self._db:
            return

        member_count = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_project_members WHERE project_id = ?",
            [project_id],
        )

        doc_count = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_project_documents WHERE project_id = ?",
            [project_id],
        )

        await self._db.execute("""
            UPDATE arkham_projects SET
                member_count = ?,
                document_count = ?,
                updated_at = ?
            WHERE id = ?
        """, [
            member_count["count"] if member_count else 0,
            doc_count["count"] if doc_count else 0,
            datetime.utcnow().isoformat(),
            project_id,
        ])

    def _row_to_project(self, row: Dict[str, Any]) -> Project:
        """Convert database row to Project object."""
        import json
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=ProjectStatus(row["status"]),
            owner_id=row["owner_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            settings=json.loads(row["settings"] or "{}"),
            metadata=json.loads(row["metadata"] or "{}"),
            member_count=row["member_count"],
            document_count=row["document_count"],
        )

    def _row_to_activity(self, row: Dict[str, Any]) -> ProjectActivity:
        """Convert database row to ProjectActivity object."""
        import json
        return ProjectActivity(
            id=row["id"],
            project_id=row["project_id"],
            action=row["action"],
            actor_id=row["actor_id"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.utcnow(),
            details=json.loads(row["details"] or "{}"),
        )
