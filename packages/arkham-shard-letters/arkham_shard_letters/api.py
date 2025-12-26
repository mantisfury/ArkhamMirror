"""
Letters Shard - FastAPI Routes

REST API endpoints for letter generation and management.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .models import (
    ExportFormat,
    LetterStatus,
    LetterType,
)

router = APIRouter(prefix="/api/letters", tags=["letters"])

# === Pydantic Request/Response Models ===


class LetterCreate(BaseModel):
    """Request model for creating a letter."""
    title: str = Field(..., description="Letter title")
    letter_type: LetterType = Field(..., description="Type of letter")
    content: str = Field(default="", description="Letter content")
    template_id: Optional[str] = Field(default=None, description="Template to use")
    recipient_name: Optional[str] = Field(default=None)
    recipient_address: Optional[str] = Field(default=None)
    subject: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class LetterUpdate(BaseModel):
    """Request model for updating a letter."""
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[LetterStatus] = None
    recipient_name: Optional[str] = None
    recipient_address: Optional[str] = None
    subject: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LetterResponse(BaseModel):
    """Response model for a letter."""
    id: str
    title: str
    letter_type: str
    status: str
    content: str
    template_id: Optional[str]
    recipient_name: Optional[str]
    recipient_address: Optional[str]
    recipient_email: Optional[str]
    sender_name: Optional[str]
    sender_address: Optional[str]
    sender_email: Optional[str]
    subject: Optional[str]
    reference_number: Optional[str]
    re_line: Optional[str]
    created_at: str
    updated_at: str
    finalized_at: Optional[str]
    sent_at: Optional[str]
    last_export_format: Optional[str]
    last_export_path: Optional[str]
    last_exported_at: Optional[str]
    metadata: Dict[str, Any]


class LetterListResponse(BaseModel):
    """Response model for listing letters."""
    letters: List[LetterResponse]
    total: int
    limit: int
    offset: int


class TemplateCreate(BaseModel):
    """Request model for creating a template."""
    name: str = Field(..., description="Template name")
    letter_type: LetterType
    description: str = Field(..., description="Template description")
    content_template: str = Field(..., description="Template content with {{placeholders}}")
    subject_template: Optional[str] = Field(default=None)
    default_sender_name: Optional[str] = None
    default_sender_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TemplateUpdate(BaseModel):
    """Request model for updating a template."""
    name: Optional[str] = None
    description: Optional[str] = None
    content_template: Optional[str] = None
    subject_template: Optional[str] = None


class TemplateResponse(BaseModel):
    """Response model for a template."""
    id: str
    name: str
    letter_type: str
    description: str
    content_template: str
    subject_template: Optional[str]
    placeholders: List[str]
    required_placeholders: List[str]
    default_sender_name: Optional[str]
    default_sender_address: Optional[str]
    default_sender_email: Optional[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


class PlaceholderValueModel(BaseModel):
    """Placeholder value for template rendering."""
    key: str
    value: str
    required: bool = False


class ApplyTemplateRequest(BaseModel):
    """Request model for applying a template."""
    template_id: str = Field(..., description="Template to apply")
    title: str = Field(..., description="Letter title")
    placeholder_values: List[PlaceholderValueModel] = Field(default_factory=list)
    recipient_name: Optional[str] = None
    recipient_address: Optional[str] = None


class ExportRequest(BaseModel):
    """Request model for exporting a letter."""
    export_format: ExportFormat = Field(..., description="Export format")


class ExportResponse(BaseModel):
    """Response model for letter export."""
    letter_id: str
    success: bool
    export_format: str
    file_path: Optional[str]
    file_size: Optional[int]
    processing_time_ms: float
    errors: List[str]
    warnings: List[str]


class StatisticsResponse(BaseModel):
    """Response model for statistics."""
    total_letters: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    total_templates: int
    by_template_type: Dict[str, int]
    letters_last_24h: int
    letters_last_7d: int
    letters_last_30d: int
    total_exports: int
    by_export_format: Dict[str, int]


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    services: Dict[str, bool]


# === Helper Functions ===


def _get_shard():
    """Get the letters shard instance from the frame."""
    from arkham_frame import get_frame
    frame = get_frame()
    shard = frame.get_shard("letters")
    if not shard:
        raise HTTPException(status_code=503, detail="Letters shard not available")
    return shard


def _letter_to_response(letter) -> LetterResponse:
    """Convert Letter object to response model."""
    return LetterResponse(
        id=letter.id,
        title=letter.title,
        letter_type=letter.letter_type.value,
        status=letter.status.value,
        content=letter.content,
        template_id=letter.template_id,
        recipient_name=letter.recipient_name,
        recipient_address=letter.recipient_address,
        recipient_email=letter.recipient_email,
        sender_name=letter.sender_name,
        sender_address=letter.sender_address,
        sender_email=letter.sender_email,
        subject=letter.subject,
        reference_number=letter.reference_number,
        re_line=letter.re_line,
        created_at=letter.created_at.isoformat(),
        updated_at=letter.updated_at.isoformat(),
        finalized_at=letter.finalized_at.isoformat() if letter.finalized_at else None,
        sent_at=letter.sent_at.isoformat() if letter.sent_at else None,
        last_export_format=letter.last_export_format.value if letter.last_export_format else None,
        last_export_path=letter.last_export_path,
        last_exported_at=letter.last_exported_at.isoformat() if letter.last_exported_at else None,
        metadata=letter.metadata,
    )


def _template_to_response(template) -> TemplateResponse:
    """Convert LetterTemplate object to response model."""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        letter_type=template.letter_type.value,
        description=template.description,
        content_template=template.content_template,
        subject_template=template.subject_template,
        placeholders=template.placeholders,
        required_placeholders=template.required_placeholders,
        default_sender_name=template.default_sender_name,
        default_sender_address=template.default_sender_address,
        default_sender_email=template.default_sender_email,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
        metadata=template.metadata,
    )


# === Endpoints ===


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    shard = _get_shard()
    return HealthResponse(
        status="healthy",
        version=shard.version,
        services={
            "database": shard._db is not None,
            "events": shard._events is not None,
            "llm": shard._llm is not None,
            "storage": shard._storage is not None,
        },
    )


@router.get("/count", response_model=CountResponse)
async def get_letters_count(
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of letters (used for badge)."""
    shard = _get_shard()
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


# === Letters CRUD ===


@router.get("/", response_model=LetterListResponse)
async def list_letters(
    status: Optional[LetterStatus] = Query(None),
    letter_type: Optional[LetterType] = Query(None),
    template_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in title, content, recipient"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List letters with optional filtering."""
    from .models import LetterFilter

    shard = _get_shard()

    filter = LetterFilter(
        status=status,
        letter_type=letter_type,
        template_id=template_id,
        search_text=search,
    )

    letters = await shard.list_letters(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status=status.value if status else None)

    return LetterListResponse(
        letters=[_letter_to_response(l) for l in letters],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=LetterResponse, status_code=201)
async def create_letter(request: LetterCreate):
    """Create a new letter."""
    shard = _get_shard()

    letter = await shard.create_letter(
        title=request.title,
        letter_type=request.letter_type,
        content=request.content,
        template_id=request.template_id,
        recipient_name=request.recipient_name,
        recipient_address=request.recipient_address,
        subject=request.subject,
        metadata=request.metadata,
    )

    return _letter_to_response(letter)


@router.get("/{letter_id}", response_model=LetterResponse)
async def get_letter(letter_id: str):
    """Get a specific letter by ID."""
    shard = _get_shard()
    letter = await shard.get_letter(letter_id)

    if not letter:
        raise HTTPException(status_code=404, detail=f"Letter {letter_id} not found")

    return _letter_to_response(letter)


@router.put("/{letter_id}", response_model=LetterResponse)
async def update_letter(letter_id: str, request: LetterUpdate):
    """Update a letter."""
    shard = _get_shard()

    letter = await shard.update_letter(
        letter_id=letter_id,
        title=request.title,
        content=request.content,
        status=request.status,
        recipient_name=request.recipient_name,
        recipient_address=request.recipient_address,
        subject=request.subject,
        metadata=request.metadata,
    )

    if not letter:
        raise HTTPException(status_code=404, detail=f"Letter {letter_id} not found")

    return _letter_to_response(letter)


@router.delete("/{letter_id}", status_code=204)
async def delete_letter(letter_id: str):
    """Delete a letter."""
    shard = _get_shard()

    success = await shard.delete_letter(letter_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Letter {letter_id} not found")


# === Letter Export ===


@router.post("/{letter_id}/export", response_model=ExportResponse)
async def export_letter(letter_id: str, request: ExportRequest):
    """Export a letter to a file format."""
    shard = _get_shard()

    result = await shard.export_letter(
        letter_id=letter_id,
        export_format=request.export_format,
    )

    return ExportResponse(
        letter_id=result.letter_id,
        success=result.success,
        export_format=result.export_format.value,
        file_path=result.file_path,
        file_size=result.file_size,
        processing_time_ms=result.processing_time_ms,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.get("/{letter_id}/download")
async def download_letter(letter_id: str):
    """Download the last exported letter file."""
    shard = _get_shard()
    letter = await shard.get_letter(letter_id)

    if not letter:
        raise HTTPException(status_code=404, detail=f"Letter {letter_id} not found")

    if not letter.last_export_path:
        raise HTTPException(status_code=404, detail="No exported file found for this letter")

    # Stub: would return file response here
    return {
        "message": "Download endpoint (stub)",
        "file_path": letter.last_export_path,
        "export_format": letter.last_export_format.value if letter.last_export_format else None,
    }


# === Templates ===


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    letter_type: Optional[LetterType] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List letter templates."""
    shard = _get_shard()
    templates = await shard.list_templates(
        letter_type=letter_type,
        limit=limit,
        offset=offset,
    )
    return [_template_to_response(t) for t in templates]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get a specific template by ID."""
    shard = _get_shard()
    template = await shard.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    return _template_to_response(template)


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(request: TemplateCreate):
    """Create a new letter template."""
    shard = _get_shard()

    template = await shard.create_template(
        name=request.name,
        letter_type=request.letter_type,
        description=request.description,
        content_template=request.content_template,
        subject_template=request.subject_template,
        default_sender_name=request.default_sender_name,
        default_sender_address=request.default_sender_address,
        metadata=request.metadata,
    )

    return _template_to_response(template)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: str, request: TemplateUpdate):
    """Update a template."""
    shard = _get_shard()

    template = await shard.update_template(
        template_id=template_id,
        name=request.name,
        description=request.description,
        content_template=request.content_template,
        subject_template=request.subject_template,
    )

    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    return _template_to_response(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(template_id: str):
    """Delete a template."""
    shard = _get_shard()

    success = await shard.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")


# === Template Application ===


@router.post("/apply-template", response_model=LetterResponse, status_code=201)
async def apply_template(request: ApplyTemplateRequest):
    """Create a new letter from a template."""
    from .models import PlaceholderValue

    shard = _get_shard()

    # Convert request placeholders to domain models
    placeholders = [
        PlaceholderValue(key=pv.key, value=pv.value, required=pv.required)
        for pv in request.placeholder_values
    ]

    try:
        letter = await shard.apply_template(
            template_id=request.template_id,
            title=request.title,
            placeholder_values=placeholders,
            recipient_name=request.recipient_name,
            recipient_address=request.recipient_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _letter_to_response(letter)


# === Statistics ===


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics():
    """Get statistics about letters in the system."""
    shard = _get_shard()
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_letters=stats.total_letters,
        by_status=stats.by_status,
        by_type=stats.by_type,
        total_templates=stats.total_templates,
        by_template_type=stats.by_template_type,
        letters_last_24h=stats.letters_last_24h,
        letters_last_7d=stats.letters_last_7d,
        letters_last_30d=stats.letters_last_30d,
        total_exports=stats.total_exports,
        by_export_format=stats.by_export_format,
    )


# === Filtered List Endpoints (for sub-routes) ===


@router.get("/drafts", response_model=LetterListResponse)
async def list_draft_letters(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List draft letters."""
    from .models import LetterFilter

    shard = _get_shard()
    filter = LetterFilter(status=LetterStatus.DRAFT)
    letters = await shard.list_letters(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="draft")

    return LetterListResponse(
        letters=[_letter_to_response(l) for l in letters],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/finalized", response_model=LetterListResponse)
async def list_finalized_letters(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List finalized letters."""
    from .models import LetterFilter

    shard = _get_shard()
    filter = LetterFilter(status=LetterStatus.FINALIZED)
    letters = await shard.list_letters(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="finalized")

    return LetterListResponse(
        letters=[_letter_to_response(l) for l in letters],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sent", response_model=LetterListResponse)
async def list_sent_letters(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List sent letters."""
    from .models import LetterFilter

    shard = _get_shard()
    filter = LetterFilter(status=LetterStatus.SENT)
    letters = await shard.list_letters(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="sent")

    return LetterListResponse(
        letters=[_letter_to_response(l) for l in letters],
        total=total,
        limit=limit,
        offset=offset,
    )
