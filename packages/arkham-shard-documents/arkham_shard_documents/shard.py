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
            await self._events.subscribe("document.processed", self._on_document_processed)
            await self._events.subscribe("document.deleted", self._on_document_deleted)
            logger.info("Subscribed to document events")

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.documents_shard = self

        logger.info("Documents Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Documents Shard...")

        # Unsubscribe from events
        if self._events:
            await self._events.unsubscribe("document.processed", self._on_document_processed)
            await self._events.unsubscribe("document.deleted", self._on_document_deleted)

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
        - arkham_frame.documents table (canonical document registry from Frame)
        - viewing_history table
        - custom_metadata table
        - user_preferences table
        """
        if not self._db:
            return

        # Ensure arkham_frame schema exists
        await self._db.execute("CREATE SCHEMA IF NOT EXISTS arkham_frame")

        # Create Frame's documents table if it doesn't exist
        # This ensures the table exists even if DocumentService didn't initialize
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_frame.documents (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR(500) NOT NULL,
                storage_id VARCHAR(100),
                project_id VARCHAR(36),
                status VARCHAR(20) DEFAULT 'pending',
                mime_type VARCHAR(100),
                file_size BIGINT DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                metadata JSONB DEFAULT '{}',
                error TEXT
            )
        """)

        # Create indexes for Frame's documents table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_frame_documents_project
            ON arkham_frame.documents(project_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_frame_documents_status
            ON arkham_frame.documents(status)
        """)

        # Create viewing history table
        # Note: No FK constraint on document_id since documents are in arkham_frame.documents
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_document_views (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                user_id TEXT,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                view_mode TEXT DEFAULT 'content',
                page_number INTEGER,
                duration_seconds INTEGER
            )
        """)

        # Drop any existing FK constraint that may have been added incorrectly
        try:
            await self._db.execute("""
                ALTER TABLE arkham_document_views
                DROP CONSTRAINT IF EXISTS arkham_document_views_document_id_fkey
            """)
        except Exception:
            pass  # Ignore if constraint doesn't exist or can't be dropped

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

        # Create indexes for shard-specific tables
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

    def _frame_row_to_document(self, row: Dict[str, Any]) -> DocumentRecord:
        """Convert arkham_frame.documents row to DocumentRecord object."""
        # Map Frame schema to DocumentRecord (Frame uses different column names)
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return DocumentRecord(
            id=row["id"],
            title=row.get("filename", ""),  # Frame uses filename, no separate title
            filename=row.get("filename", ""),
            file_type=row.get("mime_type", ""),
            file_size=row.get("file_size", 0),
            status=DocumentStatus(row.get("status", "pending")),
            page_count=row.get("page_count", 0),
            chunk_count=row.get("chunk_count", 0),
            entity_count=0,  # Not stored in Frame's table
            word_count=0,  # Not stored in Frame's table
            project_id=row.get("project_id"),
            tags=[],  # Not stored in Frame's table
            custom_metadata=metadata,
            processing_error=row.get("error"),
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

        # Query Frame's arkham_frame.documents table (canonical document registry)
        query = "SELECT * FROM arkham_frame.documents WHERE 1=1"
        params: Dict[str, Any] = {}

        if search:
            query += " AND (filename ILIKE :search)"
            params["search"] = f"%{search}%"

        if status:
            query += " AND status = :status"
            params["status"] = status

        if file_type:
            query += " AND mime_type ILIKE :file_type"
            params["file_type"] = f"%{file_type}%"

        if project_id:
            query += " AND project_id = :project_id"
            params["project_id"] = project_id

        # Add sorting
        valid_sort_fields = ["created_at", "updated_at", "filename", "file_size", "status"]
        if sort not in valid_sort_fields:
            sort = "created_at"

        order_clause = "DESC" if order.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort} {order_clause}"

        # Add pagination
        query += " LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        try:
            rows = await self._db.fetch_all(query, params)
            return [self._frame_row_to_document(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            # Return empty list on error instead of crashing
            return []

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

        # Query Frame's arkham_frame.documents table
        row = await self._db.fetch_one(
            "SELECT * FROM arkham_frame.documents WHERE id = :id",
            {"id": document_id}
        )

        if row:
            return self._frame_row_to_document(row)

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

        # Build update query for Frame's arkham_frame.documents table
        # Note: Frame table uses 'metadata' JSONB column, not separate title/tags columns
        updates = []
        params: Dict[str, Any] = {"id": document_id, "updated_at": datetime.utcnow()}

        # Frame uses filename as title, and metadata JSONB for custom data
        if title is not None:
            updates.append("filename = :filename")
            params["filename"] = title

        # Tags and custom_metadata go into the metadata JSONB column
        if tags is not None or custom_metadata is not None:
            # Merge into metadata - we need to fetch current metadata first
            current_metadata = existing.custom_metadata or {}
            if tags is not None:
                current_metadata["tags"] = tags
            if custom_metadata is not None:
                current_metadata.update(custom_metadata)
            updates.append("metadata = :metadata")
            params["metadata"] = json.dumps(current_metadata)

        if not updates:
            return existing

        updates.append("updated_at = :updated_at")
        query = f"UPDATE arkham_frame.documents SET {', '.join(updates)} WHERE id = :id"

        await self._db.execute(query, params)

        # Emit event
        if self._events:
            await self._events.emit("documents.metadata.updated", {
                "document_id": document_id,
                "title": title,
                "tags": tags,
            }, source="documents-shard")

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

        # Delete from Frame's arkham_frame.documents table (cascade will handle chunks/pages)
        await self._db.execute(
            "DELETE FROM arkham_frame.documents WHERE id = :id",
            {"id": document_id}
        )

        # Emit event
        if self._events:
            await self._events.emit("documents.selection.changed", {
                "document_id": None,
                "action": "deleted",
            }, source="documents-shard")

        return True

    async def get_document_stats(self) -> Dict[str, Any]:
        """
        Get document statistics.

        Returns:
            Dictionary with aggregate statistics
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Count by status from Frame's arkham_frame.documents table
        # Note: Frame's table uses 'pending'/'processing'/'completed'/'failed' statuses
        counts_query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status IN ('processed', 'completed', 'parsed', 'embedded') THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COALESCE(SUM(file_size), 0) as total_size,
                COALESCE(SUM(page_count), 0) as total_pages
            FROM arkham_frame.documents
        """

        try:
            row = await self._db.fetch_one(counts_query)

            if row:
                return {
                    "total_documents": row["total"] or 0,
                    "processed_documents": row["processed"] or 0,
                    "processing_documents": row["processing"] or 0,
                    "failed_documents": row["failed"] or 0,
                    "uploaded_documents": row["pending"] or 0,
                    "total_size_bytes": row["total_size"] or 0,
                    "total_pages": row["total_pages"] or 0,
                    "total_chunks": 0,  # Would need separate query to chunks table
                }
        except Exception as e:
            logger.error(f"Failed to get document stats: {e}")

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

        try:
            if status:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_frame.documents WHERE status = :status",
                    {"status": status}
                )
            else:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_frame.documents"
                )

            return row["count"] if row else 0
        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0

    # --- Event Handlers ---

    async def _on_document_processed(self, event: dict):
        """
        Handle document.processed event from Frame.

        Updates UI state when a document finishes processing.

        Args:
            event: Event payload containing document_id and status
        """
        document_id = event.get("document_id")
        status = event.get("status")
        error = event.get("error")

        if not document_id:
            return

        logger.info(f"Document processed event: {document_id} -> {status}")

        # Update document status in our table
        if self._db:
            try:
                await self._db.execute(
                    """
                    UPDATE arkham_documents
                    SET status = :status, processing_error = :error, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """,
                    {"id": document_id, "status": status or "processed", "error": error}
                )
            except Exception as e:
                logger.warning(f"Could not update document status: {e}")

        # Publish status changed event for UI
        if self._events:
            await self._events.emit("documents.status.changed", {
                "document_id": document_id,
                "status": status,
                "error": error,
            }, source="documents-shard")

    async def _on_document_deleted(self, event: dict):
        """
        Handle document.deleted event from Frame.

        Cleans up shard-specific data when a document is deleted.

        Args:
            event: Event payload containing document_id
        """
        document_id = event.get("document_id")

        if not document_id:
            return

        logger.info(f"Document deleted event: {document_id}")

        # Clean up viewing history (should cascade, but be explicit)
        if self._db:
            try:
                await self._db.execute(
                    "DELETE FROM arkham_document_views WHERE document_id = :document_id",
                    {"document_id": document_id}
                )
            except Exception as e:
                logger.warning(f"Could not clean up document views: {e}")

        # Publish selection changed event
        if self._events:
            await self._events.emit("documents.selection.changed", {
                "document_id": None,
                "action": "deleted",
                "deleted_id": document_id,
            }, source="documents-shard")

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
        if not self._db:
            return 0

        row = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_document_views WHERE document_id = :document_id",
            {"document_id": document_id}
        )

        return row["count"] if row else 0

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
        if not self._db:
            return []

        if user_id:
            query = """
                SELECT DISTINCT ON (document_id) document_id, viewed_at
                FROM arkham_document_views
                WHERE user_id = :user_id
                ORDER BY document_id, viewed_at DESC
            """
            # PostgreSQL version; for SQLite compatibility, use subquery
            query = """
                SELECT document_id, MAX(viewed_at) as last_viewed
                FROM arkham_document_views
                WHERE user_id = :user_id
                GROUP BY document_id
                ORDER BY last_viewed DESC
                LIMIT :limit
            """
            rows = await self._db.fetch_all(query, {"user_id": user_id, "limit": limit})
        else:
            query = """
                SELECT document_id, MAX(viewed_at) as last_viewed
                FROM arkham_document_views
                GROUP BY document_id
                ORDER BY last_viewed DESC
                LIMIT :limit
            """
            rows = await self._db.fetch_all(query, {"limit": limit})

        return [row["document_id"] for row in rows]

    async def mark_document_viewed(
        self,
        document_id: str,
        user_id: str = None,
        view_mode: str = "content",
        page_number: int = None,
    ):
        """
        Record that a document was viewed.

        Public method for other shards to track document views.

        Args:
            document_id: Document ID
            user_id: Optional user ID
            view_mode: View mode (content, chunks, entities)
            page_number: Optional page number being viewed
        """
        if not self._db:
            return

        import uuid

        view_id = str(uuid.uuid4())

        try:
            await self._db.execute(
                """
                INSERT INTO arkham_document_views (id, document_id, user_id, view_mode, page_number)
                VALUES (:id, :document_id, :user_id, :view_mode, :page_number)
                """,
                {
                    "id": view_id,
                    "document_id": document_id,
                    "user_id": user_id,
                    "view_mode": view_mode,
                    "page_number": page_number,
                }
            )
        except Exception as e:
            # Don't crash if view tracking fails (e.g., FK constraint issues)
            logger.warning(f"Could not record document view for {document_id}: {e}")
            return

        # Emit event
        if self._events:
            await self._events.emit("documents.view.opened", {
                "document_id": document_id,
                "user_id": user_id,
                "view_mode": view_mode,
                "page_number": page_number,
            }, source="documents-shard")

    async def get_document_content(
        self,
        document_id: str,
        page_number: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get document text content.

        Retrieves text from Frame's document service (arkham_frame.pages table).

        Args:
            document_id: Document ID
            page_number: Optional specific page (1-indexed)

        Returns:
            Dict with content, page_number, and total_pages
        """
        if not self._document_service:
            # Fall back to direct database query if Frame service unavailable
            if not self._db:
                return None

            # Query the Frame's pages table directly
            if page_number:
                row = await self._db.fetch_one(
                    """
                    SELECT text, page_number FROM arkham_frame.pages
                    WHERE document_id = :document_id AND page_number = :page_number
                    """,
                    {"document_id": document_id, "page_number": page_number}
                )

                if not row:
                    return None

                # Get total pages
                total_row = await self._db.fetch_one(
                    "SELECT COUNT(*) as total FROM arkham_frame.pages WHERE document_id = :document_id",
                    {"document_id": document_id}
                )

                return {
                    "document_id": document_id,
                    "content": row["text"] or "",
                    "page_number": row["page_number"],
                    "total_pages": total_row["total"] if total_row else 1,
                }
            else:
                # Get all pages concatenated
                rows = await self._db.fetch_all(
                    """
                    SELECT text, page_number FROM arkham_frame.pages
                    WHERE document_id = :document_id
                    ORDER BY page_number
                    """,
                    {"document_id": document_id}
                )

                if not rows:
                    return None

                content = "\n\n".join(row["text"] or "" for row in rows)
                return {
                    "document_id": document_id,
                    "content": content,
                    "page_number": None,
                    "total_pages": len(rows),
                }

        # Use Frame's document service
        if page_number:
            pages = await self._document_service.get_document_pages(document_id)
            if not pages:
                return None

            page = next((p for p in pages if p.page_number == page_number), None)
            if not page:
                return None

            return {
                "document_id": document_id,
                "content": page.text or "",
                "page_number": page.page_number,
                "total_pages": len(pages),
            }
        else:
            content = await self._document_service.get_document_text(document_id)
            if content is None:
                return None

            pages = await self._document_service.get_document_pages(document_id)
            return {
                "document_id": document_id,
                "content": content,
                "page_number": None,
                "total_pages": len(pages) if pages else 1,
            }

    async def get_document_chunks(
        self,
        document_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get document chunks with pagination.

        Retrieves chunks from Frame's document service (arkham_frame.chunks table).

        Args:
            document_id: Document ID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with items, total, page, page_size
        """
        offset = (page - 1) * page_size

        if not self._document_service:
            # Fall back to direct database query
            if not self._db:
                return {"items": [], "total": 0, "page": page, "page_size": page_size}

            # Get total count
            count_row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_frame.chunks WHERE document_id = :document_id",
                {"document_id": document_id}
            )
            total = count_row["count"] if count_row else 0

            # Get paginated chunks
            rows = await self._db.fetch_all(
                """
                SELECT id, document_id, chunk_index, text, page_number, token_count, vector_id
                FROM arkham_frame.chunks
                WHERE document_id = :document_id
                ORDER BY chunk_index
                LIMIT :limit OFFSET :offset
                """,
                {"document_id": document_id, "limit": page_size, "offset": offset}
            )

            chunks = [
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "content": row["text"] or "",
                    "page_number": row["page_number"],
                    "token_count": row["token_count"] or 0,
                    "embedding_id": row["vector_id"],
                }
                for row in rows
            ]

            return {"items": chunks, "total": total, "page": page, "page_size": page_size}

        # Use Frame's document service
        all_chunks = await self._document_service.get_document_chunks(document_id)
        total = len(all_chunks)

        # Apply pagination
        paginated = all_chunks[offset : offset + page_size]

        chunks = [
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.text or "",
                "page_number": chunk.page_number,
                "token_count": chunk.token_count or 0,
                "embedding_id": chunk.vector_id,
            }
            for chunk in paginated
        ]

        return {"items": chunks, "total": total, "page": page, "page_size": page_size}

    async def get_document_entities(
        self,
        document_id: str,
        entity_type: str = None,
    ) -> Dict[str, Any]:
        """
        Get entities extracted from a document.

        Queries the entities shard's tables or Frame's entity service.

        Args:
            document_id: Document ID
            entity_type: Optional filter by entity type

        Returns:
            Dict with items and total
        """
        if not self._db:
            return {"items": [], "total": 0}

        # Query Frame's entities table directly - this is where Parse shard saves entities
        query = """
            SELECT text, entity_type, canonical_id, confidence, metadata,
                   COUNT(*) as occurrence_count
            FROM arkham_frame.entities
            WHERE document_id = :document_id
        """
        params: Dict[str, Any] = {"document_id": document_id}

        if entity_type:
            query += " AND entity_type = :entity_type"
            params["entity_type"] = entity_type

        query += " GROUP BY text, entity_type, canonical_id, confidence, metadata"
        query += " ORDER BY occurrence_count DESC"

        try:
            rows = await self._db.fetch_all(query, params)

            entities = []
            for row in rows:
                # Get context snippets from metadata if available
                metadata = row["metadata"] or {}
                context = []
                if metadata.get("sentence"):
                    context.append(metadata["sentence"])

                entities.append({
                    "id": f"{document_id}:{row['text']}",  # Composite ID for UI
                    "document_id": document_id,
                    "entity_type": row["entity_type"],
                    "text": row["text"],
                    "confidence": row["confidence"] or 0.0,
                    "occurrences": row["occurrence_count"] or 1,
                    "context": context,
                    "canonical_id": row["canonical_id"],
                })

            return {"items": entities, "total": len(entities)}

        except Exception as e:
            logger.warning(f"Could not fetch entities for document {document_id}: {e}")
            # Tables may not exist yet
            return {"items": [], "total": 0}

    async def batch_update_tags(
        self,
        document_ids: List[str],
        add_tags: List[str] = None,
        remove_tags: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Update tags for multiple documents.

        Args:
            document_ids: List of document IDs
            add_tags: Tags to add
            remove_tags: Tags to remove

        Returns:
            Dict with processed, failed, and details
        """
        if not self._db:
            return {"processed": 0, "failed": len(document_ids), "details": []}

        processed = 0
        failed = 0
        details = []

        for doc_id in document_ids:
            try:
                # Get current document
                doc = await self.get_document(doc_id)
                if not doc:
                    failed += 1
                    details.append({"id": doc_id, "error": "Not found"})
                    continue

                # Calculate new tags
                current_tags = set(doc.tags or [])

                if add_tags:
                    current_tags.update(add_tags)

                if remove_tags:
                    current_tags -= set(remove_tags)

                new_tags = list(current_tags)

                # Update document
                await self.update_document(doc_id, tags=new_tags)
                processed += 1
                details.append({"id": doc_id, "success": True, "tags": new_tags})

            except Exception as e:
                failed += 1
                details.append({"id": doc_id, "error": str(e)})

        return {"processed": processed, "failed": failed, "details": details}

    async def batch_delete_documents(self, document_ids: List[str]) -> Dict[str, Any]:
        """
        Delete multiple documents.

        Args:
            document_ids: List of document IDs

        Returns:
            Dict with processed, failed, and details
        """
        if not self._db:
            return {"processed": 0, "failed": len(document_ids), "details": []}

        processed = 0
        failed = 0
        details = []

        for doc_id in document_ids:
            try:
                success = await self.delete_document(doc_id)
                if success:
                    processed += 1
                    details.append({"id": doc_id, "success": True})
                else:
                    failed += 1
                    details.append({"id": doc_id, "error": "Not found"})
            except Exception as e:
                failed += 1
                details.append({"id": doc_id, "error": str(e)})

        return {"processed": processed, "failed": failed, "details": details}
