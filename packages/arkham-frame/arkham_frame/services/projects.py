"""
ProjectService - Full project management service.

Provides CRUD operations, settings management, and statistics for projects.
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import uuid
import json

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Project not found."""
    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project not found: {project_id}")


class ProjectExistsError(Exception):
    """Project already exists."""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Project already exists: {name}")


class ProjectError(Exception):
    """General project operation error."""
    pass


@dataclass
class Project:
    """Project data model."""
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectStats:
    """Project statistics."""
    document_count: int = 0
    entity_count: int = 0
    total_pages: int = 0
    total_chunks: int = 0
    storage_bytes: int = 0
    pending_documents: int = 0
    completed_documents: int = 0
    failed_documents: int = 0


class ProjectService:
    """
    Full project management service.

    Provides:
    - CRUD operations for projects
    - Project settings management
    - Project statistics
    - Export/Import capabilities
    """

    # Use projects shard's table (public.arkham_projects) for consistency
    # This service now acts as a compatibility layer that delegates to the projects shard when available
    PROJECTS_TABLE = "public.arkham_projects"

    def __init__(self, db=None, storage=None, config=None):
        """
        Initialize ProjectService.

        Args:
            db: DatabaseService instance
            storage: StorageService instance
            config: ConfigService instance
        """
        self.db = db
        self.storage = storage
        self.config = config
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize project service and create tables."""
        logger.info("Initializing ProjectService...")

        if self.db and await self.db.is_connected():
            await self._ensure_tables()
            self._initialized = True
            logger.info("ProjectService initialized")
        else:
            logger.warning("ProjectService: Database not available")

    async def _ensure_tables(self) -> None:
        """Ensure project tables exist.
        
        Note: Projects shard creates public.arkham_projects. This method is kept
        for backward compatibility but should not be needed if projects shard is loaded.
        """
        if not self.db or not self.db._engine:
            return

        # Projects shard should create the table, but we ensure it exists as fallback
        # Table structure matches projects shard's arkham_projects table
        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                # Projects table (matches projects shard structure)
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.PROJECTS_TABLE} (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        status TEXT DEFAULT 'active',
                        tenant_id TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        settings TEXT DEFAULT '{{}}',
                        metadata TEXT DEFAULT '{{}}',
                        member_count INTEGER DEFAULT 0,
                        document_count INTEGER DEFAULT 0
                    )
                """))

                # Indexes
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_projects_name ON {self.PROJECTS_TABLE}(name)
                """))
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_projects_updated ON {self.PROJECTS_TABLE}(updated_at)
                """))

                conn.commit()
                logger.debug("Project tables created/verified (fallback)")

        except Exception as e:
            logger.warning(f"Failed to create project tables (projects shard should handle this): {e}")
            # Don't raise - projects shard will create the table

    # =========================================================================
    # Project CRUD
    # =========================================================================

    async def create_project(
        self,
        name: str,
        description: str = "",
        settings: Optional[Dict[str, Any]] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            name: Project name (must be unique)
            description: Project description
            settings: Initial project settings

        Returns:
            Created Project

        Raises:
            ProjectExistsError: If project with same name exists
        """
        if not self.db or not self.db._engine:
            raise ProjectError("Database not available")

        # Check for existing project
        existing = await self.get_project_by_name(name)
        if existing:
            raise ProjectExistsError(name)

        project_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                # Convert datetimes to ISO strings for TEXT fields, set defaults for shard table
                conn.execute(
                    text(f"""
                        INSERT INTO {self.PROJECTS_TABLE}
                        (id, name, description, status, owner_id, created_at, updated_at, settings, metadata, member_count, document_count)
                        VALUES (:id, :name, :description, :status, :owner_id, :created_at, :updated_at, :settings, :metadata, :member_count, :document_count)
                    """),
                    {
                        "id": project_id,
                        "name": name,
                        "description": description,
                        "status": "active",
                        "owner_id": "system",
                        "created_at": now.isoformat() if hasattr(now, "isoformat") else str(now),
                        "updated_at": now.isoformat() if hasattr(now, "isoformat") else str(now),
                        "settings": json.dumps(settings or {}),
                        "metadata": json.dumps({}),
                        "member_count": 0,
                        "document_count": 0,
                    },
                )
                conn.commit()

            # Create project storage directory
            if self.storage:
                await self.storage.get_project_path(project_id)

            logger.info(f"Created project: {name} ({project_id})")

            return Project(
                id=project_id,
                name=name,
                description=description,
                created_at=now,
                updated_at=now,
                settings=settings or {},
                metadata={},
            )

        except Exception as e:
            if "unique" in str(e).lower():
                raise ProjectExistsError(name)
            logger.error(f"Failed to create project: {e}")
            raise ProjectError(f"Project creation failed: {e}")

    async def get_project(self, project_id: str) -> Optional[Project]:
        """
        Get a project by ID.
        
        Delegates to projects shard if available, otherwise reads from public.arkham_projects.

        Args:
            project_id: Project ID

        Returns:
            Project or None if not found
        """
        # Try projects shard first
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
            if projects_shard:
                proj = await projects_shard.get_project(project_id)
                if proj:
                    # Convert shard's Project to this service's Project format
                    return Project(
                        id=proj.id,
                        name=proj.name,
                        description=proj.description,
                        created_at=proj.created_at if isinstance(proj.created_at, datetime) else datetime.fromisoformat(str(proj.created_at)),
                        updated_at=proj.updated_at if isinstance(proj.updated_at, datetime) else datetime.fromisoformat(str(proj.updated_at)),
                        settings=proj.settings,
                        metadata=proj.metadata,
                    )
        except Exception as e:
            logger.debug(f"Projects shard not available or project not found: {e}")

        # Fall back to direct database query
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text
        import json

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM {self.PROJECTS_TABLE} WHERE id = :id"),
                    {"id": project_id},
                )
                row = result.fetchone()

                if row:
                    return self._row_to_project(row._mapping)
                return None

        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None

    async def get_project_by_name(self, name: str) -> Optional[Project]:
        """
        Get a project by name.
        
        Delegates to projects shard if available, otherwise reads from public.arkham_projects.

        Args:
            name: Project name

        Returns:
            Project or None if not found
        """
        # Try projects shard first
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
            if projects_shard:
                # List projects and find by name
                projects = await projects_shard.list_projects(limit=1000, offset=0)
                for proj in projects:
                    if proj.name == name:
                        return Project(
                            id=proj.id,
                            name=proj.name,
                            description=proj.description,
                            created_at=proj.created_at if isinstance(proj.created_at, datetime) else datetime.fromisoformat(str(proj.created_at)),
                            updated_at=proj.updated_at if isinstance(proj.updated_at, datetime) else datetime.fromisoformat(str(proj.updated_at)),
                            settings=proj.settings,
                            metadata=proj.metadata,
                        )
        except Exception as e:
            logger.debug(f"Projects shard not available: {e}")

        # Fall back to direct database query
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM {self.PROJECTS_TABLE} WHERE name = :name"),
                    {"name": name},
                )
                row = result.fetchone()

                if row:
                    return self._row_to_project(row._mapping)
                return None

        except Exception as e:
            logger.error(f"Failed to get project by name {name}: {e}")
            return None

    async def list_projects(
        self,
        offset: int = 0,
        limit: int = 50,
        sort: str = "updated_at",
        order: str = "desc",
    ) -> Tuple[List[Project], int]:
        """
        List projects with pagination.
        
        Delegates to projects shard if available, otherwise reads from public.arkham_projects.

        Args:
            offset: Number of records to skip
            limit: Maximum records to return
            sort: Column to sort by (name, created_at, updated_at)
            order: Sort order (asc/desc)

        Returns:
            Tuple of (projects list, total count)
        """
        # Try projects shard first
        try:
            from ..main import get_frame
            frame = get_frame()
            projects_shard = frame.shards.get("projects")
            if projects_shard:
                projects = await projects_shard.list_projects(limit=limit, offset=offset)
                total = await projects_shard.get_count()
                # Convert shard's Project to this service's Project format
                converted = [
                    Project(
                        id=p.id,
                        name=p.name,
                        description=p.description,
                        created_at=p.created_at if isinstance(p.created_at, datetime) else datetime.fromisoformat(str(p.created_at)),
                        updated_at=p.updated_at if isinstance(p.updated_at, datetime) else datetime.fromisoformat(str(p.updated_at)),
                        settings=p.settings,
                        metadata=p.metadata,
                    )
                    for p in projects
                ]
                return converted, total
        except Exception as e:
            logger.debug(f"Projects shard not available: {e}")

        # Fall back to direct database query
        if not self.db or not self.db._engine:
            return [], 0

        from sqlalchemy import text

        # Validate sort column
        allowed_sorts = ["name", "created_at", "updated_at"]
        if sort not in allowed_sorts:
            sort = "updated_at"

        order = "DESC" if order.lower() == "desc" else "ASC"

        try:
            with self.db._engine.connect() as conn:
                # Get total count
                count_result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {self.PROJECTS_TABLE}"),
                )
                total = count_result.scalar()

                # Get projects
                result = conn.execute(
                    text(f"""
                        SELECT * FROM {self.PROJECTS_TABLE}
                        ORDER BY {sort} {order}
                        OFFSET :offset LIMIT :limit
                    """),
                    {"offset": offset, "limit": limit},
                )

                projects = [
                    self._row_to_project(row._mapping) for row in result.fetchall()
                ]

                return projects, total

        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return [], 0

    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Optional[Project]:
        """
        Update a project.

        Args:
            project_id: Project ID
            name: New name (optional)
            description: New description (optional)
            settings: New settings (merged with existing)

        Returns:
            Updated Project or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        # Check for name conflict
        if name:
            existing = await self.get_project_by_name(name)
            if existing and existing.id != project_id:
                raise ProjectExistsError(name)

        from sqlalchemy import text

        updates = []
        params = {"id": project_id, "updated_at": datetime.now(timezone.utc)}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if settings is not None:
            # For TEXT field, we need to merge JSON strings
            # Get current settings first
            current = await self.get_project(project_id)
            if current:
                merged_settings = {**(current.settings or {}), **(settings or {})}
                updates.append("settings = :settings")
                params["settings"] = json.dumps(merged_settings)
            else:
                updates.append("settings = :settings")
                params["settings"] = json.dumps(settings or {})

        if not updates:
            return await self.get_project(project_id)

        updates.append("updated_at = :updated_at")

        try:
            with self.db._engine.connect() as conn:
                # Convert updated_at to ISO string for TEXT field
                params["updated_at"] = params["updated_at"].isoformat() if hasattr(params["updated_at"], "isoformat") else str(params["updated_at"])
                result = conn.execute(
                    text(f"""
                        UPDATE {self.PROJECTS_TABLE}
                        SET {", ".join(updates)}
                        WHERE id = :id
                    """),
                    params,
                )
                conn.commit()

                if result.rowcount == 0:
                    return None

            return await self.get_project(project_id)

        except Exception as e:
            if "unique" in str(e).lower():
                raise ProjectExistsError(name)
            logger.error(f"Failed to update project {project_id}: {e}")
            return None

    async def delete_project(self, project_id: str, cascade: bool = False) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID
            cascade: If True, delete all associated documents

        Returns:
            True if deleted, False if not found
        """
        if not self.db or not self.db._engine:
            return False

        project = await self.get_project(project_id)
        if not project:
            return False

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                if cascade:
                    # Delete associated documents (in arkham_frame.documents)
                    conn.execute(
                        text("DELETE FROM arkham_frame.documents WHERE project_id = :project_id"),
                        {"project_id": project_id},
                    )

                # Delete project
                result = conn.execute(
                    text(f"DELETE FROM {self.PROJECTS_TABLE} WHERE id = :id"),
                    {"id": project_id},
                )
                conn.commit()

                if result.rowcount == 0:
                    return False

            logger.info(f"Deleted project: {project.name} ({project_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False

    # =========================================================================
    # Project Settings
    # =========================================================================

    async def get_setting(self, project_id: str, key: str) -> Any:
        """
        Get a project setting.

        Args:
            project_id: Project ID
            key: Setting key (supports dot notation: "category.key")

        Returns:
            Setting value or None if not found
        """
        project = await self.get_project(project_id)
        if not project:
            return None

        # Support dot notation
        keys = key.split(".")
        value = project.settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None

        return value

    async def set_setting(self, project_id: str, key: str, value: Any) -> bool:
        """
        Set a project setting.

        Args:
            project_id: Project ID
            key: Setting key (supports dot notation)
            value: Setting value

        Returns:
            True if successful
        """
        project = await self.get_project(project_id)
        if not project:
            return False

        # Build nested settings update
        keys = key.split(".")
        settings = project.settings.copy()

        # Navigate to nested location
        current = settings
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

        # Update project
        updated = await self.update_project(project_id, settings=settings)
        return updated is not None

    async def delete_setting(self, project_id: str, key: str) -> bool:
        """
        Delete a project setting.

        Args:
            project_id: Project ID
            key: Setting key to delete

        Returns:
            True if successful
        """
        project = await self.get_project(project_id)
        if not project:
            return False

        keys = key.split(".")
        settings = project.settings.copy()

        # Navigate to parent
        current = settings
        for k in keys[:-1]:
            if k not in current:
                return True  # Key doesn't exist
            current = current[k]

        # Delete key
        if keys[-1] in current:
            del current[keys[-1]]

        updated = await self.update_project(project_id, settings=settings)
        return updated is not None

    # =========================================================================
    # Project Statistics
    # =========================================================================

    async def get_stats(self, project_id: str) -> ProjectStats:
        """
        Get statistics for a project.

        Args:
            project_id: Project ID

        Returns:
            ProjectStats with counts and sizes
        """
        if not self.db or not self.db._engine:
            return ProjectStats()

        from sqlalchemy import text

        stats = ProjectStats()

        try:
            with self.db._engine.connect() as conn:
                # Document counts by status
                result = conn.execute(
                    text(f"""
                        SELECT status, COUNT(*) as count, SUM(file_size) as size, SUM(page_count) as pages
                        FROM {self.SCHEMA}.documents
                        WHERE project_id = :project_id
                        GROUP BY status
                    """),
                    {"project_id": project_id},
                )

                for row in result.fetchall():
                    status = row[0]
                    count = row[1] or 0
                    size = row[2] or 0
                    pages = row[3] or 0

                    stats.document_count += count
                    stats.storage_bytes += size
                    stats.total_pages += pages

                    if status == "completed":
                        stats.completed_documents = count
                    elif status == "pending":
                        stats.pending_documents = count
                    elif status == "failed":
                        stats.failed_documents = count

                # Chunk count
                result = conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM {self.SCHEMA}.chunks c
                        JOIN {self.SCHEMA}.documents d ON c.document_id = d.id
                        WHERE d.project_id = :project_id
                    """),
                    {"project_id": project_id},
                )
                stats.total_chunks = result.scalar() or 0

                # Entity count (if entities table exists)
                try:
                    result = conn.execute(
                        text(f"""
                            SELECT COUNT(*) FROM {self.SCHEMA}.entities e
                            JOIN {self.SCHEMA}.documents d ON e.document_id = d.id
                            WHERE d.project_id = :project_id
                        """),
                        {"project_id": project_id},
                    )
                    stats.entity_count = result.scalar() or 0
                except Exception:
                    pass  # Entities table might not exist yet

        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")

        return stats

    # =========================================================================
    # Project Count
    # =========================================================================

    async def get_project_count(self) -> int:
        """Get total number of projects."""
        if not self.db or not self.db._engine:
            return 0

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {self.SCHEMA}.projects"),
                )
                return result.scalar() or 0

        except Exception as e:
            logger.error(f"Failed to get project count: {e}")
            return 0

    # =========================================================================
    # Export/Import (Placeholder)
    # =========================================================================

    async def export_project(self, project_id: str, format: str = "zip") -> bytes:
        """
        Export a project and its data.

        Args:
            project_id: Project ID
            format: Export format (zip)

        Returns:
            Exported data as bytes
        """
        # TODO: Implement full export
        project = await self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(project_id)

        # Basic JSON export for now
        export_data = {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "settings": project.settings,
                "metadata": project.metadata,
            },
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

        return json.dumps(export_data, indent=2).encode()

    async def import_project(self, data: bytes, name: Optional[str] = None) -> Project:
        """
        Import a project from exported data.

        Args:
            data: Exported project data
            name: Override project name

        Returns:
            Imported Project
        """
        # TODO: Implement full import
        import_data = json.loads(data.decode())

        project_data = import_data.get("project", {})
        project_name = name or project_data.get("name", f"Imported-{uuid.uuid4().hex[:8]}")

        return await self.create_project(
            name=project_name,
            description=project_data.get("description", ""),
            settings=project_data.get("settings", {}),
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_project(self, row: Dict) -> Project:
        """Convert database row to Project object.
        
        Handles both arkham_frame.projects (JSONB, TIMESTAMP) and 
        public.arkham_projects (TEXT fields) formats.
        """
        settings = row.get("settings", {})
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except (json.JSONDecodeError, TypeError):
                settings = {}

        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        # Handle datetime - could be datetime object or ISO string
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                created_at = datetime.now(timezone.utc)
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                updated_at = datetime.now(timezone.utc)
        elif not isinstance(updated_at, datetime):
            updated_at = datetime.now(timezone.utc)

        return Project(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            created_at=created_at,
            updated_at=updated_at,
            settings=settings,
            metadata=metadata,
        )
