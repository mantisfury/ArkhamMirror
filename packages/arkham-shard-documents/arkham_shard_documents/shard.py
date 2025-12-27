"""Documents Shard - Document browser and viewer."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from arkham_frame.shard_interface import ArkhamShard

from .api import router
from .models import DocumentRecord, DocumentStatus

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

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.documents_shard = self

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
        - arkham_documents table (main documents table)
        - viewing_history table
        - custom_metadata table
        - user_preferences table
        """
        if not self._db:
            return

        # Create main documents table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER DEFAULT 0,
                status TEXT DEFAULT 'uploaded',
                page_count INTEGER DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                entity_count INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                project_id TEXT,
                tags JSONB DEFAULT '[]',
                custom_metadata JSONB DEFAULT '{}',
                processing_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)

        # Create viewing history table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_document_views (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                user_id TEXT,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                view_mode TEXT DEFAULT 'content',
                page_number INTEGER,
                duration_seconds INTEGER,
                FOREIGN KEY (document_id) REFERENCES arkham_documents(id) ON DELETE CASCADE
            )
        """)

        # Create custom metadata fields table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_document_metadata_fields (
                id TEXT PRIMARY KEY,
                field_name TEXT NOT NULL UNIQUE,
                field_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                required BOOLEAN DEFAULT FALSE,
                default_value JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create user preferences table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_document_user_prefs (
                user_id TEXT PRIMARY KEY,
                viewer_zoom FLOAT DEFAULT 1.0,
                show_metadata BOOLEAN DEFAULT TRUE,
                chunk_display_mode TEXT DEFAULT 'detailed',
                items_per_page INTEGER DEFAULT 20,
                default_sort TEXT DEFAULT 'created_at',
                default_sort_order TEXT DEFAULT 'desc',
                default_filter TEXT,
                saved_filters JSONB DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_documents_status
            ON arkham_documents(status)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_documents_file_type
            ON arkham_documents(file_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_documents_project_id
            ON arkham_documents(project_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_documents_created_at
            ON arkham_documents(created_at DESC)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_document_views_document_id
            ON arkham_document_views(document_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_document_views_user_id
            ON arkham_document_views(user_id)
        """)

        logger.info("Documents shard database schema created")

    # --- Helper Methods ---

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default

    def _row_to_document(self, row: Dict[str, Any]) -> DocumentRecord:
        """Convert database row to DocumentRecord object."""
        # Parse JSONB fields
        tags = self._parse_jsonb(row.get("tags"), [])
        custom_metadata = self._parse_jsonb(row.get("custom_metadata"), {})

        return DocumentRecord(
            id=row["id"],
            title=row["title"],
            filename=row["filename"],
            file_type=row.get("file_type", ""),
            file_size=row.get("file_size", 0),
            status=DocumentStatus(row.get("status", "uploaded")),
            page_count=row.get("page_count", 0),
            chunk_count=row.get("chunk_count", 0),
            entity_count=row.get("entity_count", 0),
            word_count=row.get("word_count", 0),
            project_id=row.get("project_id"),
            tags=tags,
            custom_metadata=custom_metadata,
            processing_error=row.get("processing_error"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            processed_at=row.get("processed_at"),
        )

    # --- Public Service Methods ---

    async def list_documents(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        file_type: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_at",
        order: str = "desc",
    ) -> List[DocumentRecord]:
        """
        List documents with optional filtering.

        Args:
            search: Search query for title/filename
            status: Filter by status
            file_type: Filter by file type
            project_id: Filter by project
            limit: Maximum results
            offset: Result offset for pagination
            sort: Sort field
            order: Sort order (asc/desc)

        Returns:
            List of DocumentRecord objects
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Build query with filters
        query = "SELECT * FROM arkham_documents WHERE 1=1"
        params: Dict[str, Any] = {}

        if search:
            query += " AND (title ILIKE :search OR filename ILIKE :search)"
            params["search"] = f"%{search}%"

        if status:
            query += " AND status = :status"
            params["status"] = status

        if file_type:
            query += " AND file_type = :file_type"
            params["file_type"] = file_type

        if project_id:
            query += " AND project_id = :project_id"
            params["project_id"] = project_id

        # Add sorting
        valid_sort_fields = ["created_at", "updated_at", "title", "filename", "file_size", "status"]
        if sort not in valid_sort_fields:
            sort = "created_at"

        order_clause = "DESC" if order.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort} {order_clause}"

        # Add pagination
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_document(row) for row in rows]

    async def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        """
        Get a document by ID.

        Args:
            document_id: Document ID

        Returns:
            DocumentRecord or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_documents WHERE id = :id",
            {"id": document_id}
        )

        if row:
            return self._row_to_document(row)

        return None

    async def update_document(
        self,
        document_id: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[DocumentRecord]:
        """
        Update document metadata.

        Args:
            document_id: Document ID
            title: New title
            tags: New tags list
            custom_metadata: New custom metadata

        Returns:
            Updated DocumentRecord or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Check if document exists
        existing = await self.get_document(document_id)
        if not existing:
            return None

        # Build update query
        updates = []
        params: Dict[str, Any] = {"id": document_id, "updated_at": datetime.utcnow()}

        if title is not None:
            updates.append("title = :title")
            params["title"] = title

        if tags is not None:
            updates.append("tags = :tags")
            params["tags"] = json.dumps(tags)

        if custom_metadata is not None:
            updates.append("custom_metadata = :custom_metadata")
            params["custom_metadata"] = json.dumps(custom_metadata)

        if not updates:
            return existing

        updates.append("updated_at = :updated_at")
        query = f"UPDATE arkham_documents SET {', '.join(updates)} WHERE id = :id"

        await self._db.execute(query, params)

        # Emit event
        if self._events:
            await self._events.publish("documents.metadata.updated", {
                "document_id": document_id,
                "title": title,
                "tags": tags,
            })

        # Return updated document
        return await self.get_document(document_id)

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Check if exists
        existing = await self.get_document(document_id)
        if not existing:
            return False

        # Delete from database (cascade will handle views)
        await self._db.execute(
            "DELETE FROM arkham_documents WHERE id = :id",
            {"id": document_id}
        )

        # Emit event
        if self._events:
            await self._events.publish("documents.selection.changed", {
                "document_id": None,
                "action": "deleted",
            })

        return True

    async def get_document_stats(self) -> Dict[str, Any]:
        """
        Get document statistics.

        Returns:
            Dictionary with aggregate statistics
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Count by status
        counts_query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'uploaded' THEN 1 ELSE 0 END) as uploaded,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(file_size) as total_size,
                SUM(page_count) as total_pages,
                SUM(chunk_count) as total_chunks
            FROM arkham_documents
        """

        row = await self._db.fetch_one(counts_query)

        if row:
            return {
                "total_documents": row["total"] or 0,
                "processed_documents": row["processed"] or 0,
                "processing_documents": row["processing"] or 0,
                "failed_documents": row["failed"] or 0,
                "uploaded_documents": row["uploaded"] or 0,
                "total_size_bytes": row["total_size"] or 0,
                "total_pages": row["total_pages"] or 0,
                "total_chunks": row["total_chunks"] or 0,
            }

        return {
            "total_documents": 0,
            "processed_documents": 0,
            "processing_documents": 0,
            "failed_documents": 0,
            "uploaded_documents": 0,
            "total_size_bytes": 0,
            "total_pages": 0,
            "total_chunks": 0,
        }

    async def get_document_count(self, status: Optional[str] = None) -> int:
        """
        Get total document count, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            Document count
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        if status:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_documents WHERE status = :status",
                {"status": status}
            )
        else:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_documents"
            )

        return row["count"] if row else 0

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
