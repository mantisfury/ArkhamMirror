"""
DocumentService - Full document management service.

Provides CRUD operations, content access, search, and batch operations for documents.
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    """Document not found."""
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        super().__init__(f"Document not found: {doc_id}")


class DocumentError(Exception):
    """General document operation error."""
    pass


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    UPLOADED = "uploaded"  # Initial upload state
    PROCESSING = "processing"
    PROCESSED = "processed"  # Ingest complete
    PARSED = "parsed"
    EMBEDDED = "embedded"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    MERGED = "merged"  # Document merged into another


@dataclass
class Document:
    """Document data model."""
    id: str
    filename: str
    storage_id: str
    project_id: Optional[str]
    status: DocumentStatus
    mime_type: Optional[str]
    file_size: int
    page_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class Chunk:
    """Text chunk from a document."""
    id: str
    document_id: str
    page_number: Optional[int]
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    token_count: int
    vector_id: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Page:
    """Page from a document."""
    id: str
    document_id: str
    page_number: int
    text: str
    image_path: Optional[str]
    width: Optional[int]
    height: Optional[int]
    word_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result with relevance score."""
    document: Document
    chunk: Optional[Chunk]
    score: float
    highlights: List[str] = field(default_factory=list)


@dataclass
class BatchResult:
    """Result of a batch operation."""
    total: int
    successful: int
    failed: int
    errors: Dict[str, str] = field(default_factory=dict)


class DocumentService:
    """
    Full document management service.

    Provides:
    - CRUD operations for documents
    - Content access (text, chunks, pages)
    - Search (via VectorService)
    - Batch operations
    """

    # Frame schema for core tables
    SCHEMA = "arkham_frame"

    def __init__(self, db=None, vectors=None, storage=None, config=None):
        """
        Initialize DocumentService.

        Args:
            db: DatabaseService instance
            vectors: VectorService instance
            storage: StorageService instance
            config: ConfigService instance
        """
        self.db = db
        self.vectors = vectors
        self.storage = storage
        self.config = config
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize document service and create tables."""
        logger.info("Initializing DocumentService...")

        if self.db and await self.db.is_connected():
            await self._ensure_tables()
            self._initialized = True
            logger.info("DocumentService initialized")
        else:
            logger.warning("DocumentService: Database not available")

    async def _ensure_tables(self) -> None:
        """Ensure document tables exist."""
        if not self.db or not self.db._engine:
            return

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                # Create schema if not exists
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.SCHEMA}"))

                # Documents table
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.SCHEMA}.documents (
                        id VARCHAR(36) PRIMARY KEY,
                        filename VARCHAR(500) NOT NULL,
                        storage_id VARCHAR(100),
                        project_id VARCHAR(36),
                        status VARCHAR(20) DEFAULT 'pending',
                        mime_type VARCHAR(100),
                        file_size BIGINT DEFAULT 0,
                        page_count INTEGER DEFAULT 0,
                        chunk_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP,
                        metadata JSONB DEFAULT '{{}}',
                        error TEXT
                    )
                """))

                # Add chunk_count if missing (migration for existing tables)
                conn.execute(text(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = '{self.SCHEMA}'
                            AND table_name = 'documents'
                            AND column_name = 'chunk_count'
                        ) THEN
                            ALTER TABLE {self.SCHEMA}.documents ADD COLUMN chunk_count INTEGER DEFAULT 0;
                        END IF;
                    END
                    $$;
                """))

                # Chunks table
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.SCHEMA}.chunks (
                        id VARCHAR(36) PRIMARY KEY,
                        document_id VARCHAR(36) REFERENCES {self.SCHEMA}.documents(id) ON DELETE CASCADE,
                        page_number INTEGER,
                        chunk_index INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        start_char INTEGER,
                        end_char INTEGER,
                        token_count INTEGER DEFAULT 0,
                        vector_id VARCHAR(36),
                        metadata JSONB DEFAULT '{{}}'
                    )
                """))

                # Pages table
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {self.SCHEMA}.pages (
                        id VARCHAR(36) PRIMARY KEY,
                        document_id VARCHAR(36) REFERENCES {self.SCHEMA}.documents(id) ON DELETE CASCADE,
                        page_number INTEGER NOT NULL,
                        text TEXT,
                        image_path VARCHAR(500),
                        width INTEGER,
                        height INTEGER,
                        word_count INTEGER DEFAULT 0,
                        metadata JSONB DEFAULT '{{}}'
                    )
                """))

                # Indexes
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_documents_project ON {self.SCHEMA}.documents(project_id)
                """))
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_documents_status ON {self.SCHEMA}.documents(status)
                """))
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_chunks_document ON {self.SCHEMA}.chunks(document_id)
                """))
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS idx_pages_document ON {self.SCHEMA}.pages(document_id)
                """))

                conn.commit()
                logger.debug("Document tables created/verified")

        except Exception as e:
            logger.error(f"Failed to create document tables: {e}")
            raise DocumentError(f"Table creation failed: {e}")

    # =========================================================================
    # Document CRUD
    # =========================================================================

    async def create_document(
        self,
        filename: str,
        content: bytes,
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Create a new document.

        Args:
            filename: Original filename
            content: File content as bytes
            project_id: Optional project to associate with
            metadata: Optional metadata

        Returns:
            Created Document
        """
        if not self.db or not self.db._engine:
            raise DocumentError("Database not available")

        doc_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Store file if storage service available
        storage_id = None
        if self.storage:
            storage_path = f"{now.year}/{now.month:02d}/{doc_id}/{filename}"
            storage_id = await self.storage.store(
                storage_path, content, metadata={"document_id": doc_id}
            )

        # Detect mime type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)

        from sqlalchemy import text
        import json
        from psycopg2.extras import Json

        try:
            with self.db._engine.connect() as conn:
                conn.execute(
                    text(f"""
                        INSERT INTO {self.SCHEMA}.documents
                        (id, filename, storage_id, project_id, status, mime_type, file_size,
                         page_count, created_at, updated_at, metadata)
                        VALUES (:id, :filename, :storage_id, :project_id, :status, :mime_type,
                                :file_size, :page_count, :created_at, :updated_at, :metadata)
                    """),
                    {
                        "id": doc_id,
                        "filename": filename,
                        "storage_id": storage_id,
                        "project_id": project_id,
                        "status": DocumentStatus.PENDING.value,
                        "mime_type": mime_type,
                        "file_size": len(content),
                        "page_count": 0,
                        "created_at": now,
                        "updated_at": now,
                        "metadata": Json(metadata or {}),  # Wrap dict for JSONB
                    },
                )
                conn.commit()

            return Document(
                id=doc_id,
                filename=filename,
                storage_id=storage_id,
                project_id=project_id,
                status=DocumentStatus.PENDING,
                mime_type=mime_type,
                file_size=len(content),
                page_count=0,
                created_at=now,
                updated_at=now,
                processed_at=None,
                metadata=metadata or {},
            )

        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise DocumentError(f"Document creation failed: {e}")

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT * FROM {self.SCHEMA}.documents WHERE id = :id"),
                    {"id": doc_id},
                )
                row = result.fetchone()

                if row:
                    return self._row_to_document(row._mapping)
                return None

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def list_documents(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
        sort: str = "created_at",
        order: str = "desc",
    ) -> Tuple[List[Document], int]:
        """
        List documents with pagination.

        Args:
            project_id: Filter by project
            status: Filter by status
            offset: Number of records to skip
            limit: Maximum records to return
            sort: Column to sort by
            order: Sort order (asc/desc)

        Returns:
            Tuple of (documents list, total count)
        """
        if not self.db or not self.db._engine:
            return [], 0

        from sqlalchemy import text

        # Build where clause
        conditions = []
        params = {"offset": offset, "limit": limit}

        if project_id:
            conditions.append("project_id = :project_id")
            params["project_id"] = project_id

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Validate sort column
        allowed_sorts = ["created_at", "updated_at", "filename", "file_size", "status"]
        if sort not in allowed_sorts:
            sort = "created_at"

        order = "DESC" if order.lower() == "desc" else "ASC"

        try:
            with self.db._engine.connect() as conn:
                # Get total count
                count_result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {self.SCHEMA}.documents {where}"),
                    params,
                )
                total = count_result.scalar()

                # Get documents
                result = conn.execute(
                    text(f"""
                        SELECT * FROM {self.SCHEMA}.documents
                        {where}
                        ORDER BY {sort} {order}
                        OFFSET :offset LIMIT :limit
                    """),
                    params,
                )

                documents = [
                    self._row_to_document(row._mapping) for row in result.fetchall()
                ]

                return documents, total

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return [], 0

    async def update_document(
        self,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Update a document.

        Args:
            doc_id: Document ID
            metadata: New metadata (merged with existing)
            status: New status

        Returns:
            Updated Document or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        updates = []
        params = {"id": doc_id, "updated_at": datetime.utcnow()}

        if status:
            updates.append("status = :status")
            params["status"] = status
            if status == DocumentStatus.COMPLETED.value:
                updates.append("processed_at = :processed_at")
                params["processed_at"] = datetime.utcnow()

        if metadata:
            updates.append("metadata = metadata || :metadata")
            params["metadata"] = metadata

        if not updates:
            return await self.get_document(doc_id)

        updates.append("updated_at = :updated_at")

        try:
            with self.db._engine.connect() as conn:
                conn.execute(
                    text(f"""
                        UPDATE {self.SCHEMA}.documents
                        SET {", ".join(updates)}
                        WHERE id = :id
                    """),
                    params,
                )
                conn.commit()

            return await self.get_document(doc_id)

        except Exception as e:
            logger.error(f"Failed to update document {doc_id}: {e}")
            return None

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        if not self.db or not self.db._engine:
            return False

        # Get document first for cleanup
        doc = await self.get_document(doc_id)
        if not doc:
            return False

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                # Delete from DB (cascades to chunks and pages)
                result = conn.execute(
                    text(f"DELETE FROM {self.SCHEMA}.documents WHERE id = :id"),
                    {"id": doc_id},
                )
                conn.commit()

                if result.rowcount == 0:
                    return False

            # Clean up storage
            if self.storage and doc.storage_id:
                await self.storage.delete(doc.storage_id)

            # Clean up vectors
            if self.vectors:
                await self.vectors.delete_by_document(doc_id)

            logger.debug(f"Deleted document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    # =========================================================================
    # Content Access
    # =========================================================================

    async def get_document_text(self, doc_id: str) -> Optional[str]:
        """
        Get the full text of a document.

        Args:
            doc_id: Document ID

        Returns:
            Full document text or None if not found
        """
        if not self.db or not self.db._engine:
            return None

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT text FROM {self.SCHEMA}.pages
                        WHERE document_id = :doc_id
                        ORDER BY page_number
                    """),
                    {"doc_id": doc_id},
                )

                texts = [row[0] for row in result.fetchall() if row[0]]
                return "\n\n".join(texts) if texts else None

        except Exception as e:
            logger.error(f"Failed to get document text {doc_id}: {e}")
            return None

    async def get_document_chunks(self, doc_id: str) -> List[Chunk]:
        """
        Get all chunks for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of Chunk objects
        """
        if not self.db or not self.db._engine:
            return []

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT * FROM {self.SCHEMA}.chunks
                        WHERE document_id = :doc_id
                        ORDER BY chunk_index
                    """),
                    {"doc_id": doc_id},
                )

                return [self._row_to_chunk(row._mapping) for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get chunks for {doc_id}: {e}")
            return []

    async def get_document_pages(self, doc_id: str) -> List[Page]:
        """
        Get all pages for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of Page objects
        """
        if not self.db or not self.db._engine:
            return []

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"""
                        SELECT * FROM {self.SCHEMA}.pages
                        WHERE document_id = :doc_id
                        ORDER BY page_number
                    """),
                    {"doc_id": doc_id},
                )

                return [self._row_to_page(row._mapping) for row in result.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get pages for {doc_id}: {e}")
            return []

    async def add_page(
        self,
        doc_id: str,
        page_number: int,
        text: str,
        image_path: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Page:
        """
        Add a page to a document.

        Args:
            doc_id: Document ID
            page_number: Page number (1-indexed)
            text: Page text content
            image_path: Optional path to page image
            width: Optional image width
            height: Optional image height
            metadata: Optional metadata

        Returns:
            Created Page
        """
        if not self.db or not self.db._engine:
            raise DocumentError("Database not available")

        page_id = str(uuid.uuid4())
        word_count = len(text.split()) if text else 0

        from sqlalchemy import text as sql_text
        from psycopg2.extras import Json

        try:
            with self.db._engine.connect() as conn:
                conn.execute(
                    sql_text(f"""
                        INSERT INTO {self.SCHEMA}.pages
                        (id, document_id, page_number, text, image_path, width, height, word_count, metadata)
                        VALUES (:id, :document_id, :page_number, :text, :image_path, :width, :height, :word_count, :metadata)
                    """),
                    {
                        "id": page_id,
                        "document_id": doc_id,
                        "page_number": page_number,
                        "text": text,
                        "image_path": image_path,
                        "width": width,
                        "height": height,
                        "word_count": word_count,
                        "metadata": Json(metadata or {}),  # Wrap dict for JSONB
                    },
                )

                # Update document page count
                conn.execute(
                    sql_text(f"""
                        UPDATE {self.SCHEMA}.documents
                        SET page_count = (
                            SELECT COUNT(*) FROM {self.SCHEMA}.pages WHERE document_id = :doc_id
                        )
                        WHERE id = :doc_id
                    """),
                    {"doc_id": doc_id},
                )

                conn.commit()

            return Page(
                id=page_id,
                document_id=doc_id,
                page_number=page_number,
                text=text,
                image_path=image_path,
                width=width,
                height=height,
                word_count=word_count,
                metadata=metadata or {},
            )

        except Exception as e:
            logger.error(f"Failed to add page to document {doc_id}: {e}")
            raise DocumentError(f"Page creation failed: {e}")

    async def add_chunk(
        self,
        doc_id: str,
        chunk_index: int,
        text: str,
        start_char: int,
        end_char: int,
        page_number: Optional[int] = None,
        token_count: int = 0,
        vector_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Chunk:
        """
        Add a chunk to a document.

        Args:
            doc_id: Document ID
            chunk_index: Chunk index (0-indexed)
            text: Chunk text content
            start_char: Start character position
            end_char: End character position
            page_number: Optional page number
            token_count: Token count
            vector_id: Optional vector ID if embedded
            metadata: Optional metadata

        Returns:
            Created Chunk
        """
        if not self.db or not self.db._engine:
            raise DocumentError("Database not available")

        chunk_id = str(uuid.uuid4())

        from sqlalchemy import text as sql_text
        from psycopg2.extras import Json

        try:
            with self.db._engine.connect() as conn:
                conn.execute(
                    sql_text(f"""
                        INSERT INTO {self.SCHEMA}.chunks
                        (id, document_id, page_number, chunk_index, text, start_char, end_char,
                         token_count, vector_id, metadata)
                        VALUES (:id, :document_id, :page_number, :chunk_index, :text, :start_char,
                                :end_char, :token_count, :vector_id, :metadata)
                    """),
                    {
                        "id": chunk_id,
                        "document_id": doc_id,
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                        "text": text,
                        "start_char": start_char,
                        "end_char": end_char,
                        "token_count": token_count,
                        "vector_id": vector_id,
                        "metadata": Json(metadata or {}),  # Wrap dict for JSONB
                    },
                )
                conn.commit()


            return Chunk(
                id=chunk_id,
                document_id=doc_id,
                page_number=page_number,
                chunk_index=chunk_index,
                text=text,
                start_char=start_char,
                end_char=end_char,
                token_count=token_count,
                vector_id=vector_id,
                metadata=metadata or {},
            )

        except Exception as e:
            logger.error(f"Failed to add chunk to document {doc_id}: {e}")
            raise DocumentError(f"Chunk creation failed: {e}")

    async def update_chunk_count(self, doc_id: str) -> int:
        """
        Update document's chunk_count based on actual chunks in database.

        Args:
            doc_id: Document ID

        Returns:
            Updated chunk count
        """
        if not self.db or not self.db._engine:
            return 0

        from sqlalchemy import text as sql_text

        try:
            with self.db._engine.connect() as conn:
                # Get actual count
                result = conn.execute(
                    sql_text(f"""
                        SELECT COUNT(*) FROM {self.SCHEMA}.chunks
                        WHERE document_id = :doc_id
                    """),
                    {"doc_id": doc_id},
                )
                count = result.scalar() or 0

                # Update document
                conn.execute(
                    sql_text(f"""
                        UPDATE {self.SCHEMA}.documents
                        SET chunk_count = :count, updated_at = CURRENT_TIMESTAMP
                        WHERE id = :doc_id
                    """),
                    {"doc_id": doc_id, "count": count},
                )
                conn.commit()

                logger.debug(f"Updated chunk_count to {count} for document {doc_id}")
                return count

        except Exception as e:
            logger.error(f"Failed to update chunk count for {doc_id}: {e}")
            return 0

    # =========================================================================
    # Search
    # =========================================================================

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search documents using vector similarity.

        Args:
            query: Search query text
            project_id: Optional project filter
            limit: Maximum results to return
            filters: Optional additional filters

        Returns:
            List of SearchResult objects
        """
        if not self.vectors:
            logger.warning("Search unavailable: VectorService not initialized")
            return []

        try:
            # Build filter for vector search
            vector_filter = {}
            if project_id:
                vector_filter["project_id"] = project_id
            if filters:
                vector_filter.update(filters)

            # Perform vector search using text query
            # search_text handles embedding internally
            results = await self.vectors.search_text(
                collection="arkham_documents",  # Use correct collection name
                text=query,
                limit=limit,
                filter=vector_filter if vector_filter else None,
            )

            search_results = []
            for result in results:
                # SearchResult is a dataclass with .payload attribute
                payload = result.payload if hasattr(result, 'payload') else result
                doc_id = payload.get("document_id") if isinstance(payload, dict) else None
                if doc_id:
                    doc = await self.get_document(doc_id)
                    if doc:
                        # Extract score from SearchResult dataclass
                        score = result.score if hasattr(result, 'score') else (payload.get("score", 0.0) if isinstance(payload, dict) else 0.0)
                        highlights = payload.get("highlights", []) if isinstance(payload, dict) else []
                        search_results.append(
                            SearchResult(
                                document=doc,
                                chunk=None,  # Could load chunk if needed
                                score=score,
                                highlights=highlights,
                            )
                        )

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def batch_delete(self, doc_ids: List[str]) -> BatchResult:
        """
        Delete multiple documents.

        Args:
            doc_ids: List of document IDs to delete

        Returns:
            BatchResult with success/failure counts
        """
        result = BatchResult(total=len(doc_ids), successful=0, failed=0)

        for doc_id in doc_ids:
            try:
                if await self.delete_document(doc_id):
                    result.successful += 1
                else:
                    result.failed += 1
                    result.errors[doc_id] = "Not found"
            except Exception as e:
                result.failed += 1
                result.errors[doc_id] = str(e)

        return result

    async def batch_update_status(
        self, doc_ids: List[str], status: str
    ) -> BatchResult:
        """
        Update status for multiple documents.

        Args:
            doc_ids: List of document IDs
            status: New status to set

        Returns:
            BatchResult with success/failure counts
        """
        if not self.db or not self.db._engine:
            return BatchResult(
                total=len(doc_ids),
                successful=0,
                failed=len(doc_ids),
                errors={doc_id: "Database unavailable" for doc_id in doc_ids},
            )

        from sqlalchemy import text

        try:
            with self.db._engine.connect() as conn:
                params = {
                    "status": status,
                    "updated_at": datetime.utcnow(),
                    "ids": tuple(doc_ids),
                }

                if status == DocumentStatus.COMPLETED.value:
                    conn.execute(
                        text(f"""
                            UPDATE {self.SCHEMA}.documents
                            SET status = :status, updated_at = :updated_at, processed_at = :updated_at
                            WHERE id IN :ids
                        """),
                        params,
                    )
                else:
                    conn.execute(
                        text(f"""
                            UPDATE {self.SCHEMA}.documents
                            SET status = :status, updated_at = :updated_at
                            WHERE id IN :ids
                        """),
                        params,
                    )

                conn.commit()

            return BatchResult(total=len(doc_ids), successful=len(doc_ids), failed=0)

        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            return BatchResult(
                total=len(doc_ids),
                successful=0,
                failed=len(doc_ids),
                errors={doc_id: str(e) for doc_id in doc_ids},
            )

    async def get_document_count(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """
        Get count of documents matching filters.

        Args:
            project_id: Optional project filter
            status: Optional status filter

        Returns:
            Document count
        """
        if not self.db or not self.db._engine:
            return 0

        from sqlalchemy import text

        conditions = []
        params = {}

        if project_id:
            conditions.append("project_id = :project_id")
            params["project_id"] = project_id

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        try:
            with self.db._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {self.SCHEMA}.documents {where}"),
                    params,
                )
                return result.scalar() or 0

        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            return 0

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_document(self, row: Dict) -> Document:
        """Convert database row to Document object."""
        return Document(
            id=row["id"],
            filename=row["filename"],
            storage_id=row.get("storage_id"),
            project_id=row.get("project_id"),
            status=DocumentStatus(row.get("status", "pending")),
            mime_type=row.get("mime_type"),
            file_size=row.get("file_size", 0),
            page_count=row.get("page_count", 0),
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
            processed_at=row.get("processed_at"),
            metadata=row.get("metadata", {}),
            error=row.get("error"),
        )

    def _row_to_chunk(self, row: Dict) -> Chunk:
        """Convert database row to Chunk object."""
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            page_number=row.get("page_number"),
            chunk_index=row.get("chunk_index", 0),
            text=row.get("text", ""),
            start_char=row.get("start_char", 0),
            end_char=row.get("end_char", 0),
            token_count=row.get("token_count", 0),
            vector_id=row.get("vector_id"),
            metadata=row.get("metadata", {}),
        )

    def _row_to_page(self, row: Dict) -> Page:
        """Convert database row to Page object."""
        return Page(
            id=row["id"],
            document_id=row["document_id"],
            page_number=row.get("page_number", 0),
            text=row.get("text", ""),
            image_path=row.get("image_path"),
            width=row.get("width"),
            height=row.get("height"),
            word_count=row.get("word_count", 0),
            metadata=row.get("metadata", {}),
        )
