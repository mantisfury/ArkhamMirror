"""
Export API endpoints.

Provides REST API for document and data export.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

router = APIRouter()


class ExportRequest(BaseModel):
    """Request body for export operation."""
    data: Any = Field(..., description="Data to export")
    format: str = Field("json", description="Export format: json, csv, markdown, html, text")
    title: Optional[str] = Field(None, description="Export title")
    author: Optional[str] = Field(None, description="Export author")
    include_metadata: bool = Field(True, description="Include export metadata")
    pretty_print: bool = Field(True, description="Pretty print output (JSON)")


class ExportResponse(BaseModel):
    """Response for export operation."""
    filename: str
    content_type: str
    size_bytes: int
    exported_at: str
    content: Optional[str] = None  # Included if not binary


class BatchExportRequest(BaseModel):
    """Request body for batch export."""
    data: Any = Field(..., description="Data to export")
    formats: List[str] = Field(..., description="List of formats to export to")
    title: Optional[str] = None
    author: Optional[str] = None


@router.get("/formats")
async def list_formats() -> Dict[str, Any]:
    """List supported export formats."""
    from ..main import get_frame

    frame = get_frame()
    export_service = frame.get_service("export")

    if not export_service:
        return {
            "formats": ["json", "csv", "markdown", "html", "text"],
            "note": "Export service not initialized",
        }

    return {
        "formats": [f.value for f in export_service.supported_formats],
    }


@router.post("/{format}")
async def export_data(
    format: str,
    request: ExportRequest,
) -> Response:
    """
    Export data to the specified format.

    Returns the exported content with appropriate content-type header.
    """
    from ..main import get_frame
    from ..services.export import ExportFormat, ExportOptions, ExportError

    frame = get_frame()
    export_service = frame.get_service("export")

    if not export_service:
        raise HTTPException(status_code=503, detail="Export service not available")

    try:
        options = ExportOptions(
            format=ExportFormat(format.lower()),
            title=request.title,
            author=request.author,
            include_metadata=request.include_metadata,
            pretty_print=request.pretty_print,
        )

        result = export_service.export(request.data, format=format, options=options)

        # Return appropriate response based on content type
        return Response(
            content=result.content if isinstance(result.content, bytes)
                    else result.content.encode('utf-8'),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
                "X-Export-Size": str(result.size_bytes),
                "X-Export-Format": result.format.value,
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}")
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_export(
    request: BatchExportRequest,
) -> Dict[str, Any]:
    """
    Export data to multiple formats at once.

    Returns metadata about each export (content not included in response).
    """
    from ..main import get_frame
    from ..services.export import ExportOptions, ExportError

    frame = get_frame()
    export_service = frame.get_service("export")

    if not export_service:
        raise HTTPException(status_code=503, detail="Export service not available")

    try:
        options = ExportOptions(
            title=request.title,
            author=request.author,
        )

        results = export_service.batch_export(
            request.data,
            formats=request.formats,
            options=options,
        )

        return {
            "exports": [
                {
                    "format": r.format.value,
                    "filename": r.filename,
                    "content_type": r.content_type,
                    "size_bytes": r.size_bytes,
                    "exported_at": r.exported_at.isoformat(),
                }
                for r in results.values()
            ],
            "count": len(results),
        }

    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_export_history(
    limit: int = Query(100, le=1000),
) -> Dict[str, Any]:
    """Get export history."""
    from ..main import get_frame

    frame = get_frame()
    export_service = frame.get_service("export")

    if not export_service:
        raise HTTPException(status_code=503, detail="Export service not available")

    history = export_service.get_history(limit=limit)

    return {
        "history": history,
        "count": len(history),
    }
