"""
Document API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional

router = APIRouter()


@router.get("/")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """List documents with optional filtering."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.documents:
        raise HTTPException(status_code=503, detail="Document service unavailable")

    docs = await frame.documents.list_documents(
        project_id=project_id,
        limit=limit,
        offset=offset,
    )

    return {
        "documents": docs,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{document_id}")
async def get_document(document_id: str) -> Dict[str, Any]:
    """Get a document by ID."""
    from ..main import get_frame
    from ..services import DocumentNotFoundError

    frame = get_frame()

    if not frame.documents:
        raise HTTPException(status_code=503, detail="Document service unavailable")

    try:
        doc = await frame.documents.get_document(document_id)
        return doc
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    limit: int = Query(default=100, le=1000),
) -> Dict[str, Any]:
    """Get chunks for a document."""
    from ..main import get_frame
    from ..services import DocumentNotFoundError

    frame = get_frame()

    if not frame.documents:
        raise HTTPException(status_code=503, detail="Document service unavailable")

    try:
        chunks = await frame.documents.get_chunks(document_id, limit=limit)
        return {
            "document_id": document_id,
            "chunks": chunks,
        }
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")


@router.post("/{document_id}/search")
async def search_in_document(
    document_id: str,
    query: str,
    limit: int = Query(default=10, le=100),
) -> Dict[str, Any]:
    """Search within a specific document."""
    from ..main import get_frame
    from ..services import DocumentNotFoundError

    frame = get_frame()

    if not frame.documents:
        raise HTTPException(status_code=503, detail="Document service unavailable")

    try:
        results = await frame.documents.search_in_document(
            document_id=document_id,
            query=query,
            limit=limit,
        )
        return {
            "document_id": document_id,
            "query": query,
            "results": results,
        }
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
