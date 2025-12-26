"""Documents Shard - Document browser and viewer."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import router

logger = logging.getLogger(__name__)


class DocumentsShard(ArkhamShard):
    """
    Document browser with viewer and metadata editor.

    Provides the primary interface for document interaction in the ArkhamFrame system.

    Features:
    - Document browsing with filtering and search
    - Document viewer with page navigation
    - Metadata editing
    - Chunk browsing
    - Entity viewing
    - Processing status tracking

    Events Published:
        - documents.view.opened
        - documents.metadata.updated
        - documents.status.changed
        - documents.selection.changed

    Events Subscribed:
        - document.processed (Frame event)
        - document.deleted (Frame event)
    """

    name = "documents"
    version = "0.1.0"
    description = "Document browser with viewer and metadata editor - primary interface for document interaction"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self._frame = None
        self._db = None
        self._events = None
        self._storage = None
        self._document_service = None

    async def initialize(self, frame) -> None:
        """
        Initialize the Documents shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Documents Shard...")

        # Get required services
        self._db = frame.get_service("database")
        self._events = frame.get_service("events")

        if not self._db:
            raise RuntimeError(f"{self.name}: Database service required")

        # Get optional services
        self._storage = frame.get_service("storage")
        self._document_service = frame.get_service("documents")

        if not self._storage:
            logger.warning("Storage service not available - file access limited")

        if not self._document_service:
            logger.warning("Document service not available - using database directly")

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        if self._events:
            # Subscribe to Frame document events
            # self._events.subscribe("document.processed", self._on_document_processed)
            # self._events.subscribe("document.deleted", self._on_document_deleted)
            pass

        logger.info("Documents Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Documents Shard...")

        # Unsubscribe from events
        if self._events:
            # self._events.unsubscribe("document.processed", self._on_document_processed)
            # self._events.unsubscribe("document.deleted", self._on_document_deleted)
            pass

        # Clear references
        self._db = None
        self._events = None
        self._storage = None
        self._document_service = None

        logger.info("Documents Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _create_schema(self) -> None:
        """
        Create database schema for documents shard.

        Creates:
        - arkham_documents schema
        - viewing_history table
        - custom_metadata table
        - user_preferences table
        """
        if not self._db:
            return

        # TODO: Implement schema creation
        # Schema should include:
        # - viewing_history: track when users view documents
        # - custom_metadata: user-defined metadata fields
        # - user_preferences: per-user document viewing preferences
        logger.info("Schema creation not yet implemented")
        pass

    # --- Event Handlers (stubs) ---

    async def _on_document_processed(self, event: dict):
        """
        Handle document.processed event from Frame.

        Updates UI state when a document finishes processing.

        Args:
            event: Event payload containing document_id and status
        """
        # TODO: Implement event handler
        # - Update document status in cache
        # - Publish documents.status.changed event
        # - Trigger any UI notifications
        pass

    async def _on_document_deleted(self, event: dict):
        """
        Handle document.deleted event from Frame.

        Cleans up shard-specific data when a document is deleted.

        Args:
            event: Event payload containing document_id
        """
        # TODO: Implement event handler
        # - Remove viewing history for deleted document
        # - Remove custom metadata
        # - Publish documents.selection.changed if deleted doc was active
        pass

    # --- Public API for other shards (via Frame) ---

    async def get_document_view_count(self, document_id: str) -> int:
        """
        Get the number of times a document has been viewed.

        Public method for other shards to query view statistics.

        Args:
            document_id: Document ID

        Returns:
            View count
        """
        # TODO: Implement
        # Query viewing_history table for document_id count
        return 0

    async def get_recently_viewed(self, user_id: str = None, limit: int = 10) -> list:
        """
        Get recently viewed documents.

        Public method for other shards to get user's document history.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of documents to return

        Returns:
            List of document IDs in recently viewed order
        """
        # TODO: Implement
        # Query viewing_history ordered by timestamp DESC
        return []

    async def mark_document_viewed(self, document_id: str, user_id: str = None):
        """
        Record that a document was viewed.

        Public method for other shards to track document views.

        Args:
            document_id: Document ID
            user_id: Optional user ID
        """
        # TODO: Implement
        # Insert into viewing_history
        # Publish documents.view.opened event
        pass
