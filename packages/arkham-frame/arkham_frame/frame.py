"""
ArkhamFrame - The core orchestrator.

Initializes and manages all Frame services.
"""

from typing import Optional, Dict, Any
import os
import logging
from time import perf_counter

logger = logging.getLogger(__name__)

# Global frame instance
_frame_instance: Optional["ArkhamFrame"] = None


def get_frame() -> "ArkhamFrame":
    """Get the global Frame instance."""
    if _frame_instance is None:
        raise RuntimeError("Frame not initialized. Call ArkhamFrame() first.")
    return _frame_instance


class ArkhamFrame:
    """
    The ArkhamFrame orchestrates all core services.

    Services:
        - config: Configuration management
        - resources: System resource detection and management
        - storage: File and blob storage
        - db: Database access (PostgreSQL)
        - documents: Document service
        - entities: Entity service
        - projects: Project management
        - chunks: Text chunking and tokenization
        - vectors: Vector store (pgvector)
        - llm: LLM service
        - events: Event bus
        - workers: Worker management
    """

    def __init__(self):
        global _frame_instance

        self.config = None
        self.resources = None
        self.storage = None
        self.db = None
        self.documents = None
        self.entities = None
        self.projects = None
        self.chunks = None
        self.vectors = None
        self.llm = None
        self.ai_analyst = None
        self.events = None
        self.workers = None
        self.models = None  # ML model management (for air-gap deployments)

        # Backwards-compatible "active project" (legacy global context).
        # The new model is per-user active project via SessionService, but some
        # shards/services still read `frame.active_project_id`.
        self._active_project_id: Optional[str] = None

        # Loaded shards
        self.shards: Dict[str, Any] = {}

        # Session service for per-user active project storage
        self.session = None

        _frame_instance = self

    @property
    def database(self):
        """Alias for db (for backwards compatibility with shards)."""
        return self.db

    @property
    def active_project_id(self) -> Optional[str]:
        """
        Backwards-compatible active project id.

        Note: Preferred API is `await get_active_project_id(user_id)` which is
        per-user. This property is a legacy global context used by older shards.
        """
        return self._active_project_id

    async def initialize(self) -> None:
        """Initialize all Frame services."""
        logger.info("Initializing ArkhamFrame...")

        # Dev-focused knobs to speed up startup when you don't need everything.
        # (All default to false, so production behavior is unchanged.)
        disable_models = os.environ.get("ARKHAM_DISABLE_MODELS", "false").lower() == "true"
        disable_resources = os.environ.get("ARKHAM_DISABLE_RESOURCES", "false").lower() == "true"
        disable_storage = os.environ.get("ARKHAM_DISABLE_STORAGE", "false").lower() == "true"
        disable_db = os.environ.get("ARKHAM_DISABLE_DB", "false").lower() == "true"
        disable_vectors = os.environ.get("ARKHAM_DISABLE_VECTORS", "false").lower() == "true"
        disable_llm = os.environ.get("ARKHAM_DISABLE_LLM", "false").lower() == "true"
        disable_chunks = os.environ.get("ARKHAM_DISABLE_CHUNKS", "false").lower() == "true"
        disable_events = os.environ.get("ARKHAM_DISABLE_EVENTS", "false").lower() == "true"
        disable_workers = os.environ.get("ARKHAM_DISABLE_WORKERS", "false").lower() == "true"

        # Initialize config first
        t0 = perf_counter()
        from arkham_frame.services.config import ConfigService
        self.config = ConfigService()
        logger.info(f"ConfigService initialized in {(perf_counter() - t0):.2f}s")

        # Initialize model service (for ML model management in air-gap deployments)
        if disable_models:
            logger.info("ModelService disabled via ARKHAM_DISABLE_MODELS=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.models import ModelService
                self.models = ModelService(
                    offline_mode=self.config.offline_mode,
                    cache_path=self.config.model_cache_path or None,
                )
                if self.config.offline_mode:
                    logger.info(
                        f"ModelService initialized (OFFLINE MODE - no auto-downloads) in {(perf_counter() - t0):.2f}s"
                    )
                else:
                    logger.info(f"ModelService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"ModelService failed to initialize: {e}")

        # Initialize resources (hardware detection) - early because workers depend on it
        if disable_resources:
            logger.info("ResourceService disabled via ARKHAM_DISABLE_RESOURCES=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.resources import ResourceService
                self.resources = ResourceService(config=self.config)
                await self.resources.initialize()
                logger.info(
                    f"ResourceService initialized (tier: {self.resources.get_tier_name()}) in {(perf_counter() - t0):.2f}s"
                )
            except Exception as e:
                logger.warning(f"ResourceService failed to initialize: {e}")

        # Initialize storage
        if disable_storage:
            logger.info("StorageService disabled via ARKHAM_DISABLE_STORAGE=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.storage import StorageService
                self.storage = StorageService(config=self.config)
                await self.storage.initialize()
                logger.info(f"StorageService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"StorageService failed to initialize: {e}")

        # Initialize database
        if disable_db:
            logger.info("DatabaseService disabled via ARKHAM_DISABLE_DB=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.database import DatabaseService
                self.db = DatabaseService(config=self.config)
                await self.db.initialize()
                logger.info(f"DatabaseService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"DatabaseService failed to initialize: {e}")

        # Initialize vectors
        if disable_vectors:
            logger.info("VectorService disabled via ARKHAM_DISABLE_VECTORS=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.vectors import VectorService
                self.vectors = VectorService(config=self.config)
                await self.vectors.initialize()
                logger.info(f"VectorService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"VectorService failed to initialize: {e}")

        # Initialize LLM (pass db for loading persisted settings)
        if disable_llm:
            logger.info("LLMService disabled via ARKHAM_DISABLE_LLM=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.llm import LLMService
                self.llm = LLMService(config=self.config, db=self.db)
                await self.llm.initialize()
                logger.info(f"LLMService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"LLMService failed to initialize: {e}")

        # Initialize AI Junior Analyst (depends on LLM)
        try:
            t0 = perf_counter()
            from arkham_frame.services.ai_analyst import AIJuniorAnalystService
            self.ai_analyst = AIJuniorAnalystService(llm_service=self.llm)
            logger.info(f"AIJuniorAnalystService initialized in {(perf_counter() - t0):.2f}s")
        except Exception as e:
            logger.warning(f"AIJuniorAnalystService failed to initialize: {e}")

        # Initialize chunks (text chunking and tokenization)
        if disable_chunks:
            logger.info("ChunkService disabled via ARKHAM_DISABLE_CHUNKS=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.chunks import ChunkService
                self.chunks = ChunkService(config=self.config)
                await self.chunks.initialize()
                logger.info(f"ChunkService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                logger.warning(f"ChunkService failed to initialize: {e}")

        # Initialize events
        if disable_events:
            logger.info("EventBus disabled via ARKHAM_DISABLE_EVENTS=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.events import EventBus
                self.events = EventBus(config=self.config)
                await self.events.initialize()
                logger.info(f"EventBus initialized in {(perf_counter() - t0):.2f}s")

                # Connect event bus to AI Analyst for audit trail
                if self.ai_analyst:
                    self.ai_analyst.set_event_bus(self.events)
                    logger.debug("EventBus connected to AIJuniorAnalystService")
            except Exception as e:
                logger.warning(f"EventBus failed to initialize: {e}")

        # Initialize workers
        if disable_workers:
            logger.info("WorkerService disabled via ARKHAM_DISABLE_WORKERS=true")
        else:
            try:
                t0 = perf_counter()
                from arkham_frame.services.workers import WorkerService
                self.workers = WorkerService(config=self.config)
                self.workers.set_event_bus(self.events)  # Connect EventBus for job notifications
                await self.workers.initialize()
                logger.info(f"WorkerService initialized in {(perf_counter() - t0):.2f}s")
            except Exception as e:
                import traceback
                logger.warning(f"WorkerService failed to initialize: {e}")
                logger.warning(f"Traceback: {traceback.format_exc()}")

        # Initialize document/entity/project services
        try:
            t0 = perf_counter()
            from arkham_frame.services.documents import DocumentService
            from arkham_frame.services.entities import EntityService
            from arkham_frame.services.projects import ProjectService

            self.documents = DocumentService(
                db=self.db, vectors=self.vectors, storage=self.storage, config=self.config
            )
            await self.documents.initialize()

            self.entities = EntityService(db=self.db, config=self.config)
            await self.entities.initialize()

            self.projects = ProjectService(db=self.db, storage=self.storage, config=self.config)
            await self.projects.initialize()

            logger.info(f"Document/Entity/Project services initialized in {(perf_counter() - t0):.2f}s")
        except Exception as e:
            logger.warning(f"Data services failed to initialize: {e}")

        # Initialize session service (for per-user active project storage)
        try:
            t0 = perf_counter()
            from arkham_frame.services.session import SessionService
            self.session = SessionService(db=self.db)
            await self.session.initialize()
            logger.info(f"SessionService initialized in {(perf_counter() - t0):.2f}s")
        except Exception as e:
            logger.warning(f"SessionService failed to initialize: {e}")

        logger.info("ArkhamFrame initialization complete")

    async def shutdown(self) -> None:
        """Shutdown all Frame services."""
        logger.info("Shutting down ArkhamFrame...")

        # Shutdown in reverse order
        if self.workers:
            await self.workers.shutdown()

        if self.events:
            await self.events.shutdown()

        if self.llm:
            await self.llm.shutdown()

        if self.vectors:
            await self.vectors.shutdown()

        if self.db:
            await self.db.shutdown()

        if self.storage:
            await self.storage.shutdown()

        if self.resources:
            await self.resources.shutdown()

        logger.info("ArkhamFrame shutdown complete")

    def get_service(self, name: str) -> Optional[Any]:
        """
        Get a service by name.

        Args:
            name: Service name (config, resources, storage, database, vectors, llm, events, workers, etc.)

        Returns:
            The service instance or None if not available.
        """
        service_map = {
            "config": self.config,
            "resources": self.resources,
            "storage": self.storage,
            "database": self.db,
            "db": self.db,
            "chunks": self.chunks,
            "vectors": self.vectors,
            "embeddings": self.vectors,  # Alias for vectors (provides embedding methods)
            "llm": self.llm,
            "ai_analyst": self.ai_analyst,
            "events": self.events,
            "workers": self.workers,
            "documents": self.documents,
            "entities": self.entities,
            "projects": self.projects,
            "models": self.models,  # ML model management
        }
        return service_map.get(name)

    # ---- Active Project Management ----

    async def get_active_project_id(self, user_id: Optional[str] = None) -> Optional[str]:
        """
        Get the active project ID for a user.
        
        Args:
            user_id: User ID. If None, returns None (per-user sessions required).
            
        Returns:
            Active project ID or None if not set.
        """
        if not user_id:
            return None
        
        if self.session:
            return await self.session.get_active_project(str(user_id))
        return None

    async def set_active_project(self, user_id: str, project_id: Optional[str]) -> bool:
        """
        Set the active project for a user.

        Args:
            user_id: User ID (required for per-user sessions)
            project_id: Project ID to set as active, or None to clear.

        Returns:
            True if set successfully, False if project doesn't exist.
        """
        if project_id is None:
            if self.session:
                await self.session.set_active_project(str(user_id), None)
            # Keep legacy global context in sync for older code paths.
            self._active_project_id = None
            logger.info(f"Active project cleared for user {user_id}")
            return True

        # Verify project exists - try projects shard first, then fall back to ProjectService
        projects_shard = self.shards.get("projects")
        
        if projects_shard:
            try:
                proj = await projects_shard.get_project(project_id)
                if proj:
                    if self.session:
                        await self.session.set_active_project(str(user_id), project_id)
                    # Keep legacy global context in sync for older code paths.
                    self._active_project_id = project_id
                    logger.info(f"Active project set to {project_id} for user {user_id}")
                    return True
            except Exception as e:
                logger.debug(f"Projects shard couldn't find project {project_id}: {e}")
        
        # Fall back to ProjectService if shard doesn't exist or project not found
        if self.projects:
            try:
                await self.projects.get_project(project_id)
                if self.session:
                    await self.session.set_active_project(str(user_id), project_id)
                # Keep legacy global context in sync for older code paths.
                self._active_project_id = project_id
                logger.info(f"Active project set to {project_id} for user {user_id}")
                return True
            except Exception as e:
                logger.warning(f"Failed to set active project: {e}")
                return False
        else:
            # No project service, just set it (for backward compatibility)
            if self.session:
                await self.session.set_active_project(str(user_id), project_id)
            # Keep legacy global context in sync for older code paths.
            self._active_project_id = project_id
            return True

    async def get_active_project(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the full active project details for a user.

        Args:
            user_id: User ID. If None, returns None (per-user sessions required).

        Returns:
            Project dict or None if no active project.
        """
        if not user_id:
            return None
        
        active_project_id = await self.get_active_project_id(user_id)
        if not active_project_id:
            return None

        # Try projects shard first, then fall back to ProjectService
        projects_shard = self.shards.get("projects")
        
        if projects_shard:
            try:
                proj = await projects_shard.get_project(active_project_id)
                if proj:
                    # Convert Project dataclass to dict
                    return {
                        "id": proj.id,
                        "name": proj.name,
                        "description": proj.description,
                        "status": proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
                        "created_at": proj.created_at.isoformat() if hasattr(proj.created_at, 'isoformat') else str(proj.created_at),
                        "updated_at": proj.updated_at.isoformat() if hasattr(proj.updated_at, 'isoformat') else str(proj.updated_at),
                        "settings": proj.settings,
                        "metadata": proj.metadata,
                        "member_count": proj.member_count,
                        "document_count": proj.document_count,
                    }
            except Exception:
                pass
        
        # Fall back to ProjectService
        if self.projects:
            try:
                project = await self.projects.get_project(active_project_id)
                return project
            except Exception:
                return None
        return None

    async def get_collection_name(self, base_name: str, user_id: Optional[str] = None) -> str:
        """
        Get the collection name for the active project context.

        If an active project is set for the user, returns project-scoped collection name.
        Otherwise, returns the global collection name.

        Args:
            base_name: Base collection name (e.g., "documents", "chunks", "entities")
            user_id: User ID to get active project for

        Returns:
            Collection name (e.g., "project_abc123_documents" or "arkham_documents")
        """
        active_project_id = await self.get_active_project_id(user_id) if user_id else None
        if active_project_id:
            return f"project_{active_project_id}_{base_name}"
        # Fall back to global collections
        return f"arkham_{base_name}"

    async def get_project_collections(self, project_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, str]:
        """
        Get all collection names for a project.

        Args:
            project_id: Project ID, or None to use active project for user.
            user_id: User ID to get active project for if project_id is None.

        Returns:
            Dict mapping base name to full collection name.
        """
        pid = project_id
        if not pid and user_id:
            pid = await self.get_active_project_id(user_id)
        if pid:
            prefix = f"project_{pid}_"
        else:
            prefix = "arkham_"

        return {
            "documents": f"{prefix}documents",
            "chunks": f"{prefix}chunks",
            "entities": f"{prefix}entities",
        }

    def get_state(self) -> Dict[str, Any]:
        """Get current Frame state for API."""
        state = {
            "version": "0.1.0",
            "active_project_id": self._active_project_id,
            "services": {
                "config": self.config is not None,
                "resources": self.resources is not None,
                "storage": self.storage is not None,
                "database": self.db is not None,
                "chunks": self.chunks is not None,
                "vectors": self.vectors is not None,
                "llm": self.llm is not None and self.llm.is_available() if self.llm else False,
                "ai_analyst": self.ai_analyst is not None and self.ai_analyst.is_available() if self.ai_analyst else False,
                "events": self.events is not None,
                "workers": self.workers is not None,
                "models": self.models is not None,
            },
            "shards": list(self.shards.keys()),
        }

        # Add resource tier if available
        if self.resources:
            state["resource_tier"] = self.resources.get_tier_name()

        # Add offline mode status
        if self.config:
            state["offline_mode"] = self.config.offline_mode

        return state
