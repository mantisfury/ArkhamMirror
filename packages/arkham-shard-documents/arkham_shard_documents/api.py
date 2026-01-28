"""Documents Shard API endpoints."""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import DocumentsShard

try:
    from arkham_frame.auth import (
        current_active_user,
        current_optional_user,
        require_project_member,
    )
except ImportError:
    async def current_active_user():
        return None
    async def current_optional_user():
        return None
    async def require_project_member():
        return None

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
    user = Depends(current_active_user),
):
    """
    List documents with pagination and filtering.

    Supports filtering by status, file type, and project.
    Authentication required for data access.
    """
    logger.debug(f"list_documents called by user {user.id if user else 'None'}")
    
    try:
        shard = get_shard(request)
        
        # Use active project if no project_id specified
        if not project_id and shard.frame:
            project_id = await shard.frame.get_active_project_id(str(user.id))
        
        if not project_id:
            raise HTTPException(
                status_code=400,
                detail="No active project selected. Please select a project to view documents."
            )
        
        # Verify user is a member of the project
        await require_project_member(project_id, user, request)

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
async def get_document(
    document_id: str,
    request: Request,
    user = Depends(current_active_user),
):
    """
    Get a single document by ID.

    Returns full document metadata including counts.
    Authentication required for data access.
    """
    
    shard = get_shard(request)
    document = await shard.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    # Verify user is a member of the document's project
    if document.project_id:
        await require_project_member(document.project_id, user, request)

    return document_to_response(document)


@router.patch("/items/{document_id}", response_model=DocumentMetadata)
async def update_document_metadata(
    document_id: str,
    body: UpdateMetadataRequest,
    request: Request,
    user = Depends(current_active_user),
):
    """
    Update document metadata.
    Authentication required for data modification.

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
async def delete_document(
    document_id: str,
    request: Request,
    user = Depends(current_active_user),
):
    """
    Delete a document.

    Removes document and all associated data.
    Authentication required for deletion.
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
    user = Depends(current_active_user),
):
    """
    Get document content.

    For multi-page documents, specify page number.
    Publishes documents.view.opened event.
    Authentication required for content access.
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
    user = Depends(current_active_user),
):
    """
    Get total document count (for badge).

    Optionally filter by status.
    Authentication required for data access.
    """
    
    shard = get_shard(request)
    count = await shard.get_document_count(status=status)
    return {"count": count}


@router.get("/stats", response_model=DocumentStats)
async def get_document_stats(
    request: Request,
    user = Depends(current_active_user),
):
    """
    Get document statistics.

    Returns counts, totals, and aggregate data.
    Authentication required for data access.
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


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""

    target_id: str
    context: Dict[str, Any] = {}
    depth: str = "quick"
    session_id: Optional[str] = None
    message: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for document analysis.

    Provides streaming AI analysis of document content and metadata.
    """
    shard = get_shard(request)
    frame = shard._frame
    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(status_code=503, detail="AI Analyst service not available")

    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Map depth string to enum
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.DETAILED,
        "detailed": AnalysisDepth.DETAILED,
        "deep": AnalysisDepth.DETAILED,
    }
    depth = depth_map.get(body.depth, AnalysisDepth.QUICK)

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=m["role"], content=m["content"])
            for m in body.conversation_history
        ]

    # Create analysis request
    analysis_request = AnalysisRequest(
        shard="documents",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Return streaming response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Deduplication Endpoints ---


class DuplicateMatchResponse(BaseModel):
    """A potential duplicate match."""
    document_id: str
    title: str
    similarity_score: float
    hamming_distance: int
    match_type: str


class DuplicateGroupResponse(BaseModel):
    """A group of duplicate documents."""
    group_id: str
    primary_document_id: str
    duplicate_ids: List[str]
    similarity_threshold: float
    detection_method: str


class MergeRequest(BaseModel):
    """Request to merge duplicate documents."""
    primary_id: str
    duplicate_ids: List[str]
    strategy: str = "keep_primary"
    preserve_references: bool = True
    cleanup_action: str = "soft_delete"


class MergeResponse(BaseModel):
    """Response from merge operation."""
    primary_id: str
    merged_count: int
    references_updated: int
    documents_cleaned: int
    cleanup_action: str


class DeduplicationStats(BaseModel):
    """Deduplication statistics."""
    total_documents: int
    documents_with_hash: int
    unique_content_hashes: int
    potential_duplicates: int


@router.post("/{document_id}/compute-hash")
async def compute_document_hash(document_id: str, request: Request):
    """
    Compute and store content hashes for a document.

    Computes MD5, SHA256, and SimHash for deduplication.
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    # Get document content
    content = await shard.get_document_content(document_id)
    if not content:
        raise HTTPException(status_code=404, detail=f"Document content not found: {document_id}")

    # Compute hashes
    result = await shard.deduplication.compute_hash(
        document_id=document_id,
        text=content["content"],
        store=True,
    )

    return {
        "document_id": document_id,
        "content_md5": result["content_md5"],
        "content_sha256": result["content_sha256"],
        "simhash": result["simhash"],
        "text_length": result["text_length"],
    }


@router.get("/{document_id}/duplicates/exact", response_model=List[DuplicateMatchResponse])
async def find_exact_duplicates(
    document_id: str,
    request: Request,
    project_id: Optional[str] = Query(None, description="Limit to project"),
):
    """
    Find exact duplicates of a document.

    Uses content SHA256 hash for exact matching.
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    matches = await shard.deduplication.find_exact_duplicates(
        document_id=document_id,
        project_id=project_id,
    )

    return [
        DuplicateMatchResponse(
            document_id=m.document_id,
            title=m.title,
            similarity_score=m.similarity_score,
            hamming_distance=m.hamming_distance,
            match_type=m.match_type,
        )
        for m in matches
    ]


@router.get("/{document_id}/duplicates/similar", response_model=List[DuplicateMatchResponse])
async def find_similar_documents(
    document_id: str,
    request: Request,
    threshold: float = Query(0.85, ge=0.0, le=1.0, description="Similarity threshold"),
    project_id: Optional[str] = Query(None, description="Limit to project"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Find similar documents using SimHash.

    Returns documents with similarity above threshold.
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    matches = await shard.deduplication.find_similar_documents(
        document_id=document_id,
        threshold=threshold,
        project_id=project_id,
        limit=limit,
    )

    return [
        DuplicateMatchResponse(
            document_id=m.document_id,
            title=m.title,
            similarity_score=m.similarity_score,
            hamming_distance=m.hamming_distance,
            match_type=m.match_type,
        )
        for m in matches
    ]


@router.post("/deduplication/scan", response_model=List[DuplicateGroupResponse])
async def scan_project_duplicates(
    request: Request,
    project_id: str = Query(..., description="Project to scan"),
    threshold: float = Query(0.85, ge=0.0, le=1.0, description="Similarity threshold"),
):
    """
    Scan entire project for duplicate groups.

    Returns groups of documents that appear to be duplicates.
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    groups = await shard.deduplication.scan_project_duplicates(
        project_id=project_id,
        threshold=threshold,
    )

    return [
        DuplicateGroupResponse(
            group_id=g.group_id,
            primary_document_id=g.primary_document_id,
            duplicate_ids=g.duplicate_ids,
            similarity_threshold=g.similarity_threshold,
            detection_method=g.detection_method,
        )
        for g in groups
    ]


@router.post("/deduplication/merge", response_model=MergeResponse)
async def merge_duplicates(body: MergeRequest, request: Request):
    """
    Merge duplicate documents into a primary document.

    Cleanup actions:
    - soft_delete: Mark duplicates as merged (recommended)
    - archive: Move to archive status
    - hard_delete: Permanently delete (irreversible)
    - keep: Only update references, keep duplicates
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    # Validate primary document exists
    primary_doc = await shard.get_document(body.primary_id)
    if not primary_doc:
        raise HTTPException(status_code=404, detail=f"Primary document not found: {body.primary_id}")

    result = await shard.deduplication.merge_documents(
        primary_id=body.primary_id,
        duplicate_ids=body.duplicate_ids,
        strategy=body.strategy,
        preserve_references=body.preserve_references,
        cleanup_action=body.cleanup_action,
    )

    # Emit event
    if shard._events:
        await shard._events.emit(
            "documents.duplicates.merged",
            {
                "primary_id": result.primary_id,
                "merged_count": result.merged_count,
                "cleanup_action": result.cleanup_action,
            },
            source="documents-shard",
        )

    return MergeResponse(
        primary_id=result.primary_id,
        merged_count=result.merged_count,
        references_updated=result.references_updated,
        documents_cleaned=result.documents_cleaned,
        cleanup_action=result.cleanup_action,
    )


@router.get("/deduplication/stats", response_model=DeduplicationStats)
async def get_deduplication_stats(
    request: Request,
    project_id: Optional[str] = Query(None, description="Filter by project"),
):
    """
    Get deduplication statistics.

    Returns counts of documents, unique hashes, and potential duplicates.
    """
    shard = get_shard(request)

    if not shard.deduplication:
        raise HTTPException(status_code=503, detail="Deduplication service not available")

    stats = await shard.deduplication.get_deduplication_stats(project_id=project_id)

    return DeduplicationStats(
        total_documents=stats.get("total_documents", 0),
        documents_with_hash=stats.get("documents_with_hash", 0),
        unique_content_hashes=stats.get("unique_content_hashes", 0),
        potential_duplicates=stats.get("potential_duplicates", 0),
    )
