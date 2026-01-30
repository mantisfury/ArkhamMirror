"""
Projects Shard - Main Shard Implementation

Project workspace management for ArkhamFrame - organize documents,
entities, and analyses into collaborative workspaces.

Supports:
- Project-scoped vector collections for data isolation
- Per-project embedding model configuration
- Automatic collection creation/deletion on project lifecycle
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

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


# Known embedding models with their dimensions
# LOCAL models - run on your machine, no API required
LOCAL_EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": {
        "dimensions": 384,
        "description": "Fast, lightweight (384D)",
        "is_cloud": False,
    },
    "BAAI/bge-m3": {
        "dimensions": 1024,
        "description": "High quality, multilingual (1024D)",
        "is_cloud": False,
    },
    "all-mpnet-base-v2": {
        "dimensions": 768,
        "description": "Balanced quality (768D)",
        "is_cloud": False,
    },
    "paraphrase-MiniLM-L6-v2": {
        "dimensions": 384,
        "description": "Paraphrase optimized (384D)",
        "is_cloud": False,
    },
}

# CLOUD models - require API key, data sent to external service
CLOUD_EMBEDDING_MODELS = {
    "text-embedding-3-small": {
        "dimensions": 1536,
        "description": "[CLOUD API] OpenAI - High quality (1536D)",
        "is_cloud": True,
        "requires_api_key": True,
        "warning": "Data sent to OpenAI API. Requires OPENAI_API_KEY.",
    },
}

# Combined for backwards compatibility
KNOWN_EMBEDDING_MODELS = {**LOCAL_EMBEDDING_MODELS, **CLOUD_EMBEDDING_MODELS}

# Default embedding model for new projects (always local)
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


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
        self._vectors = None
        self._initialized = False

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._storage = getattr(frame, "storage", None)
        self._vectors = frame.get_service("vectors")

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        await self._subscribe_to_events()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.projects_shard = self

        self._initialized = True
        logger.info(f"ProjectsShard initialized (v{self.version})")
        if self._vectors:
            logger.info("Vector service available for project-scoped collections")

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
                tenant_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                settings TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                member_count INTEGER DEFAULT 0,
                document_count INTEGER DEFAULT 0
            )
        """)

        # Migration: Remove owner_id column if it exists (from older schema)
        # This handles the transition from owner-based to member-based access control
        try:
            # Check if owner_id column exists by attempting to query it
            result = await self._db.fetch_one("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'arkham_projects' AND column_name = 'owner_id'
            """)
            if result:
                logger.info("Migrating arkham_projects: removing owner_id column")
                # Drop the index first if it exists
                await self._db.execute("DROP INDEX IF EXISTS idx_projects_owner")
                # Drop the column
                await self._db.execute("ALTER TABLE arkham_projects DROP COLUMN IF EXISTS owner_id")
                logger.info("Migration complete: owner_id removed from arkham_projects")
        except Exception as e:
            # If information_schema query fails (e.g., SQLite), try direct DROP
            # This is safe because DROP COLUMN IF EXISTS won't error if column doesn't exist
            try:
                await self._db.execute("DROP INDEX IF EXISTS idx_projects_owner")
                await self._db.execute("ALTER TABLE arkham_projects DROP COLUMN IF EXISTS owner_id")
            except Exception as drop_error:
                # Some databases (like SQLite) don't support DROP COLUMN
                # In that case, we'll just log and continue - the column will be ignored
                logger.debug(f"Could not drop owner_id column (may not be supported): {drop_error}")

        # Ensure tenant_id column exists (for multi-tenancy support)
        try:
            await self._db.execute("ALTER TABLE arkham_projects ADD COLUMN IF NOT EXISTS tenant_id TEXT")
        except Exception as e:
            # Column might already exist, or ADD COLUMN IF NOT EXISTS not supported
            logger.debug(f"tenant_id column check: {e}")

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
            CREATE INDEX IF NOT EXISTS idx_projects_tenant ON arkham_projects(tenant_id)
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

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        # Add tenant_id columns to all tables
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY[
                    'arkham_projects',
                    'arkham_project_members',
                    'arkham_project_documents',
                    'arkham_project_activity'
                ];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        # Create tenant_id indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_projects_tenant ON arkham_projects(tenant_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_project_members_tenant ON arkham_project_members(tenant_id)
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

    # === Vector Collection Management ===

    def get_collection_names(self, project_id: str) -> Dict[str, str]:
        """
        Get the collection names for a project.

        Returns:
            Dict with 'documents', 'chunks', 'entities' keys mapping to collection names
        """
        return {
            "documents": f"project_{project_id}_documents",
            "chunks": f"project_{project_id}_chunks",
            "entities": f"project_{project_id}_entities",
        }

    async def create_project_collections(
        self,
        project_id: str,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> Dict[str, bool]:
        """
        Create vector collections for a project.

        Args:
            project_id: Project ID
            embedding_model: Embedding model to use (determines vector dimensions)

        Returns:
            Dict mapping collection type to creation success
        """
        if not self._vectors:
            logger.warning("Vector service not available, skipping collection creation")
            return {}

        # Get dimensions for the embedding model
        model_info = KNOWN_EMBEDDING_MODELS.get(embedding_model)
        if model_info:
            dimensions = model_info["dimensions"]
        else:
            # Unknown model - use default dimensions
            dimensions = 384
            logger.warning(f"Unknown embedding model '{embedding_model}', using default dimensions: {dimensions}")

        collection_names = self.get_collection_names(project_id)
        results = {}

        for coll_type, coll_name in collection_names.items():
            try:
                await self._vectors.create_collection(
                    name=coll_name,
                    vector_size=dimensions,
                )
                results[coll_type] = True
                logger.info(f"Created collection '{coll_name}' ({dimensions}D) for project {project_id}")
            except Exception as e:
                # Collection may already exist
                if "already exists" in str(e).lower():
                    results[coll_type] = True
                    logger.debug(f"Collection '{coll_name}' already exists")
                else:
                    results[coll_type] = False
                    logger.error(f"Failed to create collection '{coll_name}': {e}")

        return results

    async def delete_project_collections(self, project_id: str) -> Dict[str, bool]:
        """
        Delete all vector collections for a project.

        Args:
            project_id: Project ID

        Returns:
            Dict mapping collection type to deletion success
        """
        if not self._vectors:
            return {}

        collection_names = self.get_collection_names(project_id)
        results = {}

        for coll_type, coll_name in collection_names.items():
            try:
                await self._vectors.delete_collection(coll_name)
                results[coll_type] = True
                logger.info(f"Deleted collection '{coll_name}' for project {project_id}")
            except Exception as e:
                # Collection may not exist
                if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                    results[coll_type] = True
                else:
                    results[coll_type] = False
                    logger.error(f"Failed to delete collection '{coll_name}': {e}")

        return results

    async def get_project_collection_stats(self, project_id: str) -> Dict[str, Any]:
        """
        Get statistics for a project's vector collections.

        Returns:
            Dict with collection stats (vector counts, dimensions, etc.)
        """
        if not self._vectors:
            return {"available": False}

        collection_names = self.get_collection_names(project_id)
        stats = {"available": True, "collections": {}}

        for coll_type, coll_name in collection_names.items():
            try:
                info = await self._vectors.get_collection(coll_name)
                if info:
                    stats["collections"][coll_type] = {
                        "name": coll_name,
                        "vector_count": info.points_count,
                        "dimensions": info.vector_size,
                        "status": info.status,
                    }
                else:
                    stats["collections"][coll_type] = {"name": coll_name, "exists": False}
            except Exception as e:
                stats["collections"][coll_type] = {"name": coll_name, "error": str(e)}

        return stats

    async def update_project_embedding_model(
        self,
        project_id: str,
        new_model: str,
        wipe_collections: bool = False,
    ) -> Dict[str, Any]:
        """
        Update the embedding model for a project.

        If the new model has different dimensions, collections must be wiped.

        Args:
            project_id: Project ID
            new_model: New embedding model name
            wipe_collections: If True, wipe and recreate collections

        Returns:
            Result dict with success status and details
        """
        project = await self.get_project(project_id)
        if not project:
            return {"success": False, "error": "Project not found"}

        current_model = project.settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        current_dims = KNOWN_EMBEDDING_MODELS.get(current_model, {}).get("dimensions", 384)
        new_dims = KNOWN_EMBEDDING_MODELS.get(new_model, {}).get("dimensions", 384)

        # Check if dimensions differ
        requires_wipe = current_dims != new_dims

        if requires_wipe and not wipe_collections:
            return {
                "success": False,
                "requires_wipe": True,
                "message": f"Model change ({current_model} -> {new_model}) requires wiping collections ({current_dims}D -> {new_dims}D)",
                "current_model": current_model,
                "current_dimensions": current_dims,
                "new_model": new_model,
                "new_dimensions": new_dims,
            }

        # Update project settings
        project.settings["embedding_model"] = new_model
        project.settings["embedding_dimensions"] = new_dims
        await self._save_project(project, update=True)

        # If wiping, recreate collections
        wiped = False
        if requires_wipe and wipe_collections:
            await self.delete_project_collections(project_id)
            await self.create_project_collections(project_id, new_model)
            wiped = True

        # Log activity
        await self._log_activity(
            project_id=project_id,
            action="embedding_model_changed",
            actor_id="system",
            target_type="settings",
            target_id="embedding_model",
            details={
                "previous_model": current_model,
                "new_model": new_model,
                "wiped": wiped,
            },
        )

        return {
            "success": True,
            "previous_model": current_model,
            "new_model": new_model,
            "wiped": wiped,
        }

    # === Public API Methods ===

    async def create_project(
        self,
        name: str,
        description: str = "",
        creator_id: Optional[str] = None,
        status: ProjectStatus = ProjectStatus.ACTIVE,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding_model: Optional[str] = None,
        create_collections: bool = True,
        tenant_id: Optional[UUID] = None,
    ) -> Project:
        """
        Create a new project.

        Projects have no owner - all access is managed via member roles (VIEWER, EDITOR, ADMIN).
        The creator and all tenant admins are automatically added as ADMIN members.

        Args:
            name: Project name
            description: Project description
            creator_id: User ID of project creator (will be added as ADMIN member)
            status: Initial status
            settings: Custom settings dict
            metadata: Custom metadata dict
            embedding_model: Embedding model for this project (default: all-MiniLM-L6-v2)
            create_collections: Whether to create vector collections for this project
            tenant_id: Tenant ID for adding admins (from authenticated user; fallback to context)

        Returns:
            Created Project object

        Raises:
            ValueError: If project would be created without any members
        """
        project_id = str(uuid4())
        now = datetime.utcnow()

        # Set up settings with embedding model
        project_settings = settings or {}
        model = embedding_model or DEFAULT_EMBEDDING_MODEL
        project_settings["embedding_model"] = model
        project_settings["embedding_dimensions"] = KNOWN_EMBEDDING_MODELS.get(model, {}).get("dimensions", 384)

        project = Project(
            id=project_id,
            name=name,
            description=description,
            status=status,
            tenant_id=str(tenant_id) if tenant_id else None,
            created_at=now,
            updated_at=now,
            settings=project_settings,
            metadata=metadata or {},
        )

        await self._save_project(project)

        # Create vector collections for this project
        if create_collections and self._vectors:
            collection_results = await self.create_project_collections(project_id, model)
            logger.info(f"Created collections for project {project_id}: {collection_results}")

        # Log activity
        await self._log_activity(
            project_id=project_id,
            action="created",
            actor_id=creator_id or "system",
            target_type="project",
            target_id=project_id,
            details={"embedding_model": model},
        )

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.project.created",
                {
                    "project_id": project_id,
                    "name": name,
                    "creator_id": creator_id,
                    "embedding_model": model,
                },
                source=self.name,
            )

        # Add creator and all tenant admins as ADMIN members
        added_ids = set()
        creator_str = str(creator_id) if creator_id else None
        
        # Add creator as ADMIN
        if creator_str and creator_str != "system":
            try:
                await self.add_member(
                    project_id, creator_str, role=ProjectRole.ADMIN, added_by=creator_str
                )
                added_ids.add(creator_str)
                logger.debug("Added creator %s as ADMIN for project %s", creator_str, project_id)
            except Exception as e:
                logger.warning("Could not add creator as project member: %s", e, exc_info=True)

        # Add all tenant admins as ADMIN members
        effective_tenant_id = tenant_id or self.get_tenant_id_or_none()
        if effective_tenant_id is not None and not isinstance(effective_tenant_id, UUID):
            try:
                effective_tenant_id = UUID(str(effective_tenant_id))
            except (ValueError, TypeError):
                effective_tenant_id = None
        
        if effective_tenant_id:
            try:
                from arkham_frame.auth.tenant_users import get_tenant_admin_user_ids
                admin_ids = await get_tenant_admin_user_ids(effective_tenant_id)
                for uid in admin_ids:
                    uid_str = str(uid)
                    if uid_str not in added_ids:
                        try:
                            await self.add_member(
                                project_id, uid_str, role=ProjectRole.ADMIN, added_by=creator_str or "system"
                            )
                            added_ids.add(uid_str)
                            logger.debug("Added tenant admin %s as ADMIN for project %s", uid_str, project_id)
                        except Exception as e:
                            logger.warning("Could not add admin %s as member: %s", uid_str, e)
            except Exception as e:
                logger.warning("Could not fetch/add tenant admins as project members: %s", e, exc_info=True)

        # Validate that project has at least one member
        if len(added_ids) == 0:
            # Clean up: delete the project we just created
            await self._db.execute("DELETE FROM arkham_projects WHERE id = ?", [project_id])
            raise ValueError("Project must have at least one member")

        logger.info(f"Created project {project_id} with {len(added_ids)} members")
        return project

    async def get_project(
        self, project_id: str, tenant_id_override: Optional[UUID] = None
    ) -> Optional[Project]:
        """Get a project by ID.

        When tenant context (or tenant_id_override) is set, returns the project only
        if it belongs to that tenant or has tenant_id NULL (legacy). When no tenant
        context, returns by id only. Use tenant_id_override when the caller has
        the tenant from the request (e.g. member endpoints) to avoid relying on
        context var ordering.
        """
        if not self._db:
            return None

        tenant_id = tenant_id_override if tenant_id_override is not None else self.get_tenant_id_or_none()
        table = "public.arkham_projects"

        if tenant_id:
            # Try with tenant filter: (tenant_id::text = ? OR tenant_id IS NULL)
            query = f"SELECT * FROM {table} WHERE id = ? AND (tenant_id::text = ? OR tenant_id IS NULL)"
            params = [project_id, str(tenant_id)]
            row = await self._db.fetch_one(query, params)
            if row:
                return self._row_to_project(row)
            # Fallback: fetch by id only, then enforce tenant (handles type/coercion)
            row = await self._db.fetch_one(f"SELECT * FROM {table} WHERE id = ?", [project_id])
            if row and tenant_id:
                row_tenant = row.get("tenant_id")
                if row_tenant is None or str(row_tenant) == str(tenant_id):
                    return self._row_to_project(row)
                return None
            return self._row_to_project(row) if row else None

        row = await self._db.fetch_one(f"SELECT * FROM {table} WHERE id = ?", [project_id])
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

        # Add tenant filtering if tenant context is available (include legacy: tenant_id NULL)
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND (tenant_id = ? OR tenant_id IS NULL)"
            params.append(str(tenant_id))

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
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

    async def delete_project(self, project_id: str, delete_collections: bool = True) -> bool:
        """
        Delete a project and all associated data (documents, vectors, analyses, etc.).

        Calls delete_data_for_project on other shards, then deletes vector collections,
        project activity, documents, members, and the project record.

        Args:
            project_id: Project ID to delete
            delete_collections: Whether to delete vector collections (default: True)

        Returns:
            True if successful
        """
        if not self._db:
            return False

        # Ask other shards to delete their project-scoped data first
        shards = getattr(self.frame, "shards", None) or {}
        for name, shard in shards.items():
            if name == self.name:
                continue
            if hasattr(shard, "delete_data_for_project"):
                try:
                    await shard.delete_data_for_project(project_id)
                    logger.info(f"Shard '{name}' deleted data for project {project_id}")
                except Exception as e:
                    logger.warning("Shard '%s' failed to delete data for project %s: %s", name, project_id, e)

        # Delete vector collections
        if delete_collections and self._vectors:
            collection_results = await self.delete_project_collections(project_id)
            logger.info(f"Deleted collections for project {project_id}: {collection_results}")

        # Delete project-scoped tables (activity, project_documents, members, project)
        await self._db.execute("DELETE FROM arkham_project_activity WHERE project_id = ?", [project_id])
        await self._db.execute("DELETE FROM arkham_project_documents WHERE project_id = ?", [project_id])
        await self._db.execute("DELETE FROM arkham_project_members WHERE project_id = ?", [project_id])
        await self._db.execute("DELETE FROM arkham_projects WHERE id = ?", [project_id])

        # Emit event
        if self._events:
            await self._events.emit(
                "projects.project.deleted",
                {"project_id": project_id, "collections_deleted": delete_collections},
                source=self.name,
            )

        return True

    async def add_document(
        self,
        project_id: str,
        document_id: str,
        added_by: str = "system",
    ) -> ProjectDocument:
        """Add a document to a project. Raises ValueError if the project does not exist."""
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

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
        """Remove a member from a project. Fails if it would leave the project with zero members."""
        if not self._db:
            return False

        members = await self.list_members(project_id)
        if len(members) <= 1:
            return False  # Cannot remove last member

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

    async def list_documents(self, project_id: str) -> List[ProjectDocument]:
        """List documents associated with a project."""
        if not self._db:
            return []
        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_project_documents WHERE project_id = ? ORDER BY added_at DESC",
            [project_id],
        )
        return [self._row_to_project_document(row) for row in rows]

    async def list_members(self, project_id: str) -> List[ProjectMember]:
        """List members of a project."""
        if not self._db:
            return []
        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_project_members WHERE project_id = ? ORDER BY added_at ASC",
            [project_id],
        )
        return [self._row_to_project_member(row) for row in rows]

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

        # Build query with tenant filtering (include legacy: tenant_id NULL)
        query = "SELECT COUNT(*) as count FROM arkham_projects WHERE 1=1"
        params = []

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND (tenant_id = ? OR tenant_id IS NULL)"
            params.append(str(tenant_id))

        if status:
            query += " AND status = ?"
            params.append(status)

        result = await self._db.fetch_one(query, params)
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
            project.tenant_id,
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
                    name=?, description=?, status=?, tenant_id=?,
                    created_at=?, updated_at=?, settings=?, metadata=?,
                    member_count=?, document_count=?
                WHERE id=?
            """, data[1:] + (project.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_projects (
                    id, name, description, status, tenant_id,
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
            tenant_id=str(row["tenant_id"]) if row.get("tenant_id") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            settings=json.loads(row["settings"] or "{}"),
            metadata=json.loads(row["metadata"] or "{}"),
            member_count=row.get("member_count", 0),
            document_count=row.get("document_count", 0),
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

    def _row_to_project_document(self, row: Dict[str, Any]) -> ProjectDocument:
        """Convert database row to ProjectDocument object."""
        return ProjectDocument(
            id=row["id"],
            project_id=row["project_id"],
            document_id=row["document_id"],
            added_at=datetime.fromisoformat(row["added_at"]) if row["added_at"] else datetime.utcnow(),
            added_by=row["added_by"] or "system",
        )

    def _row_to_project_member(self, row: Dict[str, Any]) -> ProjectMember:
        """Convert database row to ProjectMember object."""
        return ProjectMember(
            id=row["id"],
            project_id=row["project_id"],
            user_id=row["user_id"],
            role=ProjectRole(row["role"]) if row["role"] else ProjectRole.VIEWER,
            added_at=datetime.fromisoformat(row["added_at"]) if row["added_at"] else datetime.utcnow(),
            added_by=row["added_by"] or "system",
        )
