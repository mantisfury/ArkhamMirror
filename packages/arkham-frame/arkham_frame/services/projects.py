"""
ProjectService - Full project management service.

Provides CRUD operations, settings management, and statistics for projects.
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
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

    # Frame schema for core tables
    SCHEMA = "arkham_frame"

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
        """Ensure project tables exist."""
        if not self.db or not self.db._engine:
            return

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                # Create schema if not exists
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.SCHEMA}"))

                # Projects table
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.SCHEMA}.projects (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        description TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        settings JSONB DEFAULT '{{}}',
                        metadata JSONB DEFAULT '{{}}'
                    )
                """))

                # Indexes
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_projects_name ON {self.SCHEMA}.projects(name)
                """))
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_projects_updated ON {self.SCHEMA}.projects(updated_at)
                """))

                conn.commit()
                logger.debug("Project tables created/verified")

        except Exception as e:
            logger.error(f"Failed to create project tables: {e}")
            raise ProjectError(f"Table creation failed: {e}")

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
        now = datetime.utcnow()

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                conn.execute(
                    text(f"""
                        INSERT INTO {self.SCHEMA}.projects
                        (id, name, description, created_at, updated_at, settings, metadata)
                        VALUES (:id, :name, :description, :created_at, :updated_at, :settings, :metadata)
                    """),
                    {
                        "id": project_id,
                        "name": name,
                        "description": description,
                        "created_at": now,
                        "updated_at": now,
                        "settings": json.dumps(settings or {}),
                        "metadata": json.dumps({}),
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

        Args:
            project_id: Project ID

        Returns:
            Project or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM {self.SCHEMA}.projects WHERE id = :id"),
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

        Args:
            name: Project name

        Returns:
            Project or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM {self.SCHEMA}.projects WHERE name = :name"),
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

        Args:
            offset: Number of records to skip
            limit: Maximum records to return
            sort: Column to sort by (name, created_at, updated_at)
            order: Sort order (asc/desc)

        Returns:
            Tuple of (projects list, total count)
        """
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
                    text(f"SELECT COUNT(*) FROM {self.SCHEMA}.projects"),
                )
                total = count_result.scalar()

                # Get projects
                result = conn.execute(
                    text(f"""
                        SELECT * FROM {self.SCHEMA}.projects
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
        params = {"id": project_id, "updated_at": datetime.utcnow()}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if settings is not None:
            updates.append("settings = settings || :settings")
            params["settings"] = json.dumps(settings)

        if not updates:
            return await self.get_project(project_id)

        updates.append("updated_at = :updated_at")

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        UPDATE {self.SCHEMA}.projects
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
                    # Delete associated documents
                    conn.execute(
                        text(f"DELETE FROM {self.SCHEMA}.documents WHERE project_id = :project_id"),
                        {"project_id": project_id},
                    )

                # Delete project
                result = conn.execute(
                    text(f"DELETE FROM {self.SCHEMA}.projects WHERE id = :id"),
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
            "exported_at": datetime.utcnow().isoformat(),
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
        """Convert database row to Project object."""
        settings = row.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)

        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return Project(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
            settings=settings,
            metadata=metadata,
        )
