"""
ArkhamFrame - The core orchestrator.

Initializes and manages all Frame services.
"""

from typing import Optional, Dict, Any
import logging

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
        - vectors: Vector store (Qdrant)
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
        self.events = None
        self.workers = None

        # Loaded shards
        self.shards: Dict[str, Any] = {}

        # Active project for routing operations to project-scoped collections
        self._active_project_id: Optional[str] = None

        _frame_instance = self

    @property
    def database(self):
        """Alias for db (for backwards compatibility with shards)."""
        return self.db

    async def initialize(self) -> None:
        """Initialize all Frame services."""
        logger.info("Initializing ArkhamFrame...")

        # Initialize config first
        from arkham_frame.services.config import ConfigService
        self.config = ConfigService()
        logger.info("ConfigService initialized")

        # Initialize resources (hardware detection) - early because workers depend on it
        try:
            from arkham_frame.services.resources import ResourceService
            self.resources = ResourceService(config=self.config)
            await self.resources.initialize()
            logger.info(f"ResourceService initialized (tier: {self.resources.get_tier_name()})")
        except Exception as e:
            logger.warning(f"ResourceService failed to initialize: {e}")

        # Initialize storage
        try:
            from arkham_frame.services.storage import StorageService
            self.storage = StorageService(config=self.config)
            await self.storage.initialize()
            logger.info("StorageService initialized")
        except Exception as e:
            logger.warning(f"StorageService failed to initialize: {e}")

        # Initialize database
        try:
            from arkham_frame.services.database import DatabaseService
            self.db = DatabaseService(config=self.config)
            await self.db.initialize()
            logger.info("DatabaseService initialized")
        except Exception as e:
            logger.warning(f"DatabaseService failed to initialize: {e}")

        # Initialize vectors
        try:
            from arkham_frame.services.vectors import VectorService
            self.vectors = VectorService(config=self.config)
            await self.vectors.initialize()
            logger.info("VectorService initialized")
        except Exception as e:
            logger.warning(f"VectorService failed to initialize: {e}")

        # Initialize LLM
        try:
            from arkham_frame.services.llm import LLMService
            self.llm = LLMService(config=self.config)
            await self.llm.initialize()
            logger.info("LLMService initialized")
        except Exception as e:
            logger.warning(f"LLMService failed to initialize: {e}")

        # Initialize chunks (text chunking and tokenization)
        try:
            from arkham_frame.services.chunks import ChunkService
            self.chunks = ChunkService(config=self.config)
            await self.chunks.initialize()
            logger.info("ChunkService initialized")
        except Exception as e:
            logger.warning(f"ChunkService failed to initialize: {e}")

        # Initialize events
        try:
            from arkham_frame.services.events import EventBus
            self.events = EventBus(config=self.config)
            await self.events.initialize()
            logger.info("EventBus initialized")
        except Exception as e:
            logger.warning(f"EventBus failed to initialize: {e}")

        # Initialize workers
        try:
            from arkham_frame.services.workers import WorkerService
            self.workers = WorkerService(config=self.config)
            self.workers.set_event_bus(self.events)  # Connect EventBus for job notifications
            await self.workers.initialize()
            logger.info("WorkerService initialized")
        except Exception as e:
            import traceback
            logger.warning(f"WorkerService failed to initialize: {e}")
            logger.warning(f"Traceback: {traceback.format_exc()}")

        # Initialize document/entity/project services
        try:
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

            logger.info("Document/Entity/Project services initialized")
        except Exception as e:
            logger.warning(f"Data services failed to initialize: {e}")

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
            "events": self.events,
            "workers": self.workers,
            "documents": self.documents,
            "entities": self.entities,
            "projects": self.projects,
        }
        return service_map.get(name)

    # ---- Active Project Management ----

    @property
    def active_project_id(self) -> Optional[str]:
        """Get the currently active project ID."""
        return self._active_project_id

    async def set_active_project(self, project_id: Optional[str]) -> bool:
        """
        Set the active project for routing operations.

        Args:
            project_id: Project ID to set as active, or None to clear.

        Returns:
            True if set successfully, False if project doesn't exist.
        """
        if project_id is None:
            self._active_project_id = None
            logger.info("Active project cleared")
            return True

        # Verify project exists
        if self.projects:
            try:
                await self.projects.get_project(project_id)
                self._active_project_id = project_id
                logger.info(f"Active project set to: {project_id}")
                return True
            except Exception as e:
                logger.warning(f"Failed to set active project: {e}")
                return False
        else:
            # No project service, just set it
            self._active_project_id = project_id
            return True

    async def get_active_project(self) -> Optional[Dict[str, Any]]:
        """
        Get the full active project details.

        Returns:
            Project dict or None if no active project.
        """
        if not self._active_project_id:
            return None

        if self.projects:
            try:
                project = await self.projects.get_project(self._active_project_id)
                return project
            except Exception:
                return None
        return None

    def get_collection_name(self, base_name: str) -> str:
        """
        Get the collection name for the active project context.

        If an active project is set, returns project-scoped collection name.
        Otherwise, returns the global collection name.

        Args:
            base_name: Base collection name (e.g., "documents", "chunks", "entities")

        Returns:
            Collection name (e.g., "project_abc123_documents" or "arkham_documents")
        """
        if self._active_project_id:
            return f"project_{self._active_project_id}_{base_name}"
        # Fall back to global collections
        return f"arkham_{base_name}"

    def get_project_collections(self, project_id: Optional[str] = None) -> Dict[str, str]:
        """
        Get all collection names for a project.

        Args:
            project_id: Project ID, or None to use active project.

        Returns:
            Dict mapping base name to full collection name.
        """
        pid = project_id or self._active_project_id
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
                "events": self.events is not None,
                "workers": self.workers is not None,
            },
            "shards": list(self.shards.keys()),
        }

        # Add resource tier if available
        if self.resources:
            state["resource_tier"] = self.resources.get_tier_name()

        return state
