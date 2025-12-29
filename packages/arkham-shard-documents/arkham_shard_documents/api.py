"""Documents Shard API endpoints."""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import DocumentsShard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# === Helper to get shard instance ===

def get_shard(request: Request) -> "DocumentsShard":
    """Get the documents shard instance from app state."""
    shard = getattr(request.app.state, "documents_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Documents shard not available")
    return shard


# --- Request/Response Models ---


class DocumentMetadata(BaseModel):
    """Document metadata model."""
    id: str
    title: str
    filename: str
    file_type: str
    file_size: int
    status: str  # uploaded, processing, processed, failed
    page_count: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    created_at: str
    updated_at: str
    project_id: Optional[str] = None
    tags: List[str] = []
    custom_metadata: dict = {}


class DocumentContent(BaseModel):
    """Document content model."""
    document_id: str
    content: str
    page_number: Optional[int] = None
    total_pages: int = 1


class DocumentChunk(BaseModel):
    """Document chunk model."""
    id: str
    document_id: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    token_count: int
    embedding_id: Optional[str] = None


class DocumentEntity(BaseModel):
    """Extracted entity model."""
    id: str
    document_id: str
    entity_type: str  # PERSON, ORG, GPE, DATE, etc.
    text: str
    confidence: float
    occurrences: int
    context: List[str] = []


class DocumentListResponse(BaseModel):
    """Paginated document list response."""
    items: List[DocumentMetadata]
    total: int
    page: int
    page_size: int


class UpdateMetadataRequest(BaseModel):
    """Request to update document metadata."""
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_metadata: Optional[dict] = None


class DocumentStats(BaseModel):
    """Document statistics."""
    total_documents: int
    processed_documents: int
    processing_documents: int
    failed_documents: int
    total_size_bytes: int
    total_pages: int
    total_chunks: int


class ChunkListResponse(BaseModel):
    """Paginated chunk list response."""
    items: List[DocumentChunk]
    total: int
    page: int
    page_size: int


class EntityListResponse(BaseModel):
    """Entity list response."""
    items: List[DocumentEntity]
    total: int


# --- Helper Functions ---


def document_to_response(doc) -> DocumentMetadata:
    """Convert DocumentRecord to API response."""
    return DocumentMetadata(
        id=doc.id,
        title=doc.title,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        entity_count=doc.entity_count,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        project_id=doc.project_id,
        tags=doc.tags,
        custom_metadata=doc.custom_metadata,
    )


# --- Health Check ---


@router.get("/health")
async def health(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)
    count = await shard.get_document_count()
    return {"status": "healthy", "shard": "documents", "document_count": count}


# --- Document Management Endpoints ---


@router.get("/items", response_model=DocumentListResponse)
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    q: Optional[str] = Query(None, description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
):
    """
    List documents with pagination and filtering.

    Supports filtering by status, file type, and project.
    """
    try:
        shard = get_shard(request)

        offset = (page - 1) * page_size

        documents = await shard.list_documents(
            search=q,
            status=status,
            file_type=file_type,
            project_id=project_id,
            limit=page_size,
            offset=offset,
            sort=sort,
            order=order,
        )

        # Get total count for pagination
        total = await shard.get_document_count(status=status)

        response = DocumentListResponse(
            items=[document_to_response(doc) for doc in documents],
            total=total,
            page=page,
            page_size=page_size,
        )
        logger.info(f"list_documents returning {len(documents)} documents, total={total}")
        return response
    except Exception as e:
        logger.error(f"list_documents failed: {e}", exc_info=True)
        # Return empty response on error instead of crashing
        return DocumentListResponse(items=[], total=0, page=page, page_size=page_size)


@router.get("/items/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str, request: Request):
    """
    Get a single document by ID.

    Returns full document metadata including counts.
    """
    shard = get_shard(request)
    document = await shard.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return document_to_response(document)


@router.patch("/items/{document_id}", response_model=DocumentMetadata)
async def update_document_metadata(
    document_id: str,
    body: UpdateMetadataRequest,
    request: Request,
):
    """
    Update document metadata.

    Allows updating title, tags, and custom metadata fields.
    Publishes documents.metadata.updated event.
    """
    shard = get_shard(request)

    try:
        document = await shard.update_document(
            document_id,
            title=body.title,
            tags=body.tags,
            custom_metadata=body.custom_metadata,
        )

        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

        return document_to_response(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{document_id}")
async def delete_document(document_id: str, request: Request):
    """
    Delete a document.

    Removes document and all associated data.
    """
    shard = get_shard(request)

    success = await shard.delete_document(document_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return {"deleted": True, "document_id": document_id}


# --- Document Content Endpoints ---


@router.get("/{document_id}/content", response_model=DocumentContent)
async def get_document_content(
    document_id: str,
    request: Request,
    page: Optional[int] = Query(None, description="Page number for multi-page docs"),
):
    """
    Get document content.

    For multi-page documents, specify page number.
    Publishes documents.view.opened event.
    """
    shard = get_shard(request)

    # Check document exists
    document = await shard.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    # Get content
    content_data = await shard.get_document_content(document_id, page_number=page)
    if not content_data:
        raise HTTPException(status_code=404, detail="Document content not available")

    # Record view
    await shard.mark_document_viewed(document_id, view_mode="content", page_number=page)

    return DocumentContent(
        document_id=document_id,
        content=content_data["content"],
        page_number=content_data.get("page_number"),
        total_pages=content_data.get("total_pages", 1),
    )


@router.get("/{document_id}/pages/{page_number}", response_model=DocumentContent)
async def get_document_page(document_id: str, page_number: int, request: Request):
    """
    Get specific page of a multi-page document.
    """
    shard = get_shard(request)

    # Check document exists
    document = await shard.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    # Get page content
    content_data = await shard.get_document_content(document_id, page_number=page_number)
    if not content_data:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found")

    # Record view
    await shard.mark_document_viewed(document_id, view_mode="content", page_number=page_number)

    return DocumentContent(
        document_id=document_id,
        content=content_data["content"],
        page_number=content_data.get("page_number"),
        total_pages=content_data.get("total_pages", 1),
    )


# --- Related Data Endpoints ---


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Get document chunks with pagination.

    Returns chunks generated during document processing.
    """
    shard = get_shard(request)

    # Check document exists
    document = await shard.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    # Get chunks
    chunks_data = await shard.get_document_chunks(document_id, page=page, page_size=page_size)

    # Record view
    await shard.mark_document_viewed(document_id, view_mode="chunks")

    # Convert to response models
    items = [
        DocumentChunk(
            id=chunk["id"],
            document_id=chunk["document_id"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            page_number=chunk.get("page_number"),
            token_count=chunk.get("token_count", 0),
            embedding_id=chunk.get("embedding_id"),
        )
        for chunk in chunks_data["items"]
    ]

    return ChunkListResponse(
        items=items,
        total=chunks_data["total"],
        page=chunks_data["page"],
        page_size=chunks_data["page_size"],
    )


@router.get("/{document_id}/entities", response_model=EntityListResponse)
async def get_document_entities(
    document_id: str,
    request: Request,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
):
    """
    Get entities extracted from document.

    Optionally filter by entity type (PERSON, ORG, GPE, etc.).
    """
    shard = get_shard(request)

    # Check document exists
    document = await shard.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    # Get entities
    entities_data = await shard.get_document_entities(document_id, entity_type=entity_type)

    # Record view
    await shard.mark_document_viewed(document_id, view_mode="entities")

    # Convert to response models
    items = [
        DocumentEntity(
            id=entity["id"],
            document_id=entity["document_id"],
            entity_type=entity["entity_type"],
            text=entity["text"],
            confidence=entity.get("confidence", 0.0),
            occurrences=entity.get("occurrences", 1),
            context=entity.get("context", []),
        )
        for entity in entities_data["items"]
    ]

    return EntityListResponse(
        items=items,
        total=entities_data["total"],
    )


@router.get("/{document_id}/metadata", response_model=DocumentMetadata)
async def get_full_metadata(document_id: str, request: Request):
    """
    Get full document metadata including all custom fields.
    """
    shard = get_shard(request)

    document = await shard.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    return document_to_response(document)


# --- Statistics Endpoints ---


@router.get("/count")
async def get_document_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Get total document count (for badge).

    Optionally filter by status.
    """
    shard = get_shard(request)
    count = await shard.get_document_count(status=status)
    return {"count": count}


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(request: Request):
    """
    Get document statistics.

    Returns counts, totals, and aggregate data.
    """
    try:
        shard = get_shard(request)
        stats = await shard.get_document_stats()

        response = DocumentStats(
            total_documents=stats["total_documents"],
            processed_documents=stats["processed_documents"],
            processing_documents=stats["processing_documents"],
            failed_documents=stats["failed_documents"],
            total_size_bytes=stats["total_size_bytes"],
            total_pages=stats["total_pages"],
            total_chunks=stats["total_chunks"],
        )
        logger.info(f"get_document_stats returning {stats}")
        return response
    except Exception as e:
        logger.error(f"get_document_stats failed: {e}", exc_info=True)
        # Return zero stats on error
        return DocumentStats(
            total_documents=0,
            processed_documents=0,
            processing_documents=0,
            failed_documents=0,
            total_size_bytes=0,
            total_pages=0,
            total_chunks=0,
        )


@router.get("/recently-viewed")
async def get_recently_viewed(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    Get recently viewed documents.

    Returns document IDs in order of most recent view.
    """
    shard = get_shard(request)

    document_ids = await shard.get_recently_viewed(user_id=user_id, limit=limit)

    # Fetch full document details for each
    documents = []
    for doc_id in document_ids:
        doc = await shard.get_document(doc_id)
        if doc:
            documents.append(document_to_response(doc))

    return {
        "items": documents,
        "total": len(documents),
    }


# --- Batch Operations ---


class BatchTagUpdateRequest(BaseModel):
    """Request for batch tag update."""
    document_ids: List[str]
    add_tags: Optional[List[str]] = None
    remove_tags: Optional[List[str]] = None


@router.post("/batch/update-tags")
async def batch_update_tags(
    body: BatchTagUpdateRequest,
    request: Request,
):
    """
    Update tags for multiple documents.

    Can add and/or remove tags in bulk.
    """
    shard = get_shard(request)

    if not body.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    if not body.add_tags and not body.remove_tags:
        raise HTTPException(status_code=400, detail="No tags to add or remove")

    result = await shard.batch_update_tags(
        document_ids=body.document_ids,
        add_tags=body.add_tags,
        remove_tags=body.remove_tags,
    )

    return {
        "success": result["failed"] == 0,
        "processed": result["processed"],
        "failed": result["failed"],
        "message": f"Tags updated for {result['processed']} documents, {result['failed']} failed",
        "details": result.get("details", []),
    }


class BatchDeleteRequest(BaseModel):
    """Request for batch delete."""
    document_ids: List[str]


@router.post("/batch/delete")
async def batch_delete_documents(
    body: BatchDeleteRequest,
    request: Request,
):
    """
    Delete multiple documents.

    Removes documents and all associated data.
    """
    shard = get_shard(request)

    if not body.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    result = await shard.batch_delete_documents(body.document_ids)

    return {
        "success": result["failed"] == 0,
        "processed": result["processed"],
        "failed": result["failed"],
        "message": f"{result['processed']} documents deleted, {result['failed']} failed",
        "details": result.get("details", []),
    }
