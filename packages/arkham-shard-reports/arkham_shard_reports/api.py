"""
Reports Shard - FastAPI Routes

REST API endpoints for report generation and management.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .shard import ReportsShard

from .models import (
    ReportFormat,
    ReportStatus,
    ReportType,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# === Pydantic Request/Response Models ===


class ReportCreate(BaseModel):
    """Request model for creating a report."""
    report_type: ReportType = Field(..., description="Type of report")
    title: str = Field(..., description="Report title")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Generation parameters")
    output_format: ReportFormat = Field(default=ReportFormat.HTML)


class ReportResponse(BaseModel):
    """Response model for a report."""
    id: str
    report_type: str
    title: str
    status: str
    created_at: str
    completed_at: Optional[str]
    parameters: Dict[str, Any]
    output_format: str
    file_path: Optional[str]
    file_size: Optional[int]
    error: Optional[str]
    metadata: Dict[str, Any]


class ReportListResponse(BaseModel):
    """Response model for listing reports."""
    reports: List[ReportResponse]
    total: int
    limit: int
    offset: int


class TemplateCreate(BaseModel):
    """Request model for creating a template."""
    name: str = Field(..., description="Template name")
    report_type: ReportType
    description: str = Field(..., description="Template description")
    parameters_schema: Optional[Dict[str, Any]] = Field(default=None)
    default_format: ReportFormat = Field(default=ReportFormat.HTML)
    template_content: str = Field(default="")


class TemplateResponse(BaseModel):
    """Response model for a template."""
    id: str
    name: str
    report_type: str
    description: str
    parameters_schema: Dict[str, Any]
    default_format: str
    template_content: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


class ScheduleCreate(BaseModel):
    """Request model for creating a schedule."""
    template_id: str = Field(..., description="Template to use")
    cron_expression: str = Field(..., description="Cron schedule")
    parameters: Optional[Dict[str, Any]] = Field(default=None)
    output_format: ReportFormat = Field(default=ReportFormat.HTML)
    retention_days: int = Field(default=30, ge=1, le=365)


class ScheduleResponse(BaseModel):
    """Response model for a schedule."""
    id: str
    template_id: str
    cron_expression: str
    enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]
    parameters: Dict[str, Any]
    output_format: str
    retention_days: int
    email_recipients: List[str]
    metadata: Dict[str, Any]


class PreviewRequest(BaseModel):
    """Request model for report preview."""
    report_type: ReportType
    title: str
    parameters: Optional[Dict[str, Any]] = None
    output_format: ReportFormat = ReportFormat.HTML


class PreviewResponse(BaseModel):
    """Response model for report preview."""
    preview_content: str
    estimated_size: int
    warnings: List[str]


class StatisticsResponse(BaseModel):
    """Response model for report statistics."""
    total_reports: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_format: Dict[str, int]
    total_templates: int
    total_schedules: int
    active_schedules: int
    total_file_size_bytes: int
    avg_generation_time_ms: float
    reports_last_24h: int
    reports_last_7d: int
    reports_last_30d: int


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    services: Dict[str, bool]


# === Helper Functions ===


def get_shard(request: Request) -> "ReportsShard":
    """Get the reports shard instance from app state."""
    shard = getattr(request.app.state, "reports_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Reports shard not available")
    return shard


def _report_to_response(report) -> ReportResponse:
    """Convert Report object to response model."""
    return ReportResponse(
        id=report.id,
        report_type=report.report_type.value,
        title=report.title,
        status=report.status.value,
        created_at=report.created_at.isoformat(),
        completed_at=report.completed_at.isoformat() if report.completed_at else None,
        parameters=report.parameters,
        output_format=report.output_format.value,
        file_path=report.file_path,
        file_size=report.file_size,
        error=report.error,
        metadata=report.metadata,
    )


def _template_to_response(template) -> TemplateResponse:
    """Convert ReportTemplate object to response model."""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        report_type=template.report_type.value,
        description=template.description,
        parameters_schema=template.parameters_schema,
        default_format=template.default_format.value,
        template_content=template.template_content,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
        metadata=template.metadata,
    )


def _schedule_to_response(schedule) -> ScheduleResponse:
    """Convert ReportSchedule object to response model."""
    return ScheduleResponse(
        id=schedule.id,
        template_id=schedule.template_id,
        cron_expression=schedule.cron_expression,
        enabled=schedule.enabled,
        last_run=schedule.last_run.isoformat() if schedule.last_run else None,
        next_run=schedule.next_run.isoformat() if schedule.next_run else None,
        parameters=schedule.parameters,
        output_format=schedule.output_format.value,
        retention_days=schedule.retention_days,
        email_recipients=schedule.email_recipients,
        metadata=schedule.metadata,
    )


# === Endpoints ===


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)
    return HealthResponse(
        status="healthy",
        version=shard.version,
        services={
            "database": shard._db is not None,
            "events": shard._events is not None,
            "llm": shard._llm is not None,
            "storage": shard._storage is not None,
            "workers": shard._workers is not None,
        },
    )


@router.get("/count", response_model=CountResponse)
async def get_reports_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of reports (used for badge)."""
    shard = get_shard(request)
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


@router.get("/pending/count", response_model=CountResponse)
async def get_pending_count(request: Request):
    """Get count of pending reports (badge endpoint)."""
    shard = get_shard(request)
    count = await shard.get_count(status="pending")
    return CountResponse(count=count)


# === Reports CRUD ===


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    request: Request,
    status: Optional[ReportStatus] = Query(None),
    report_type: Optional[ReportType] = Query(None),
    output_format: Optional[ReportFormat] = Query(None),
    search: Optional[str] = Query(None, description="Search in report title"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List reports with optional filtering."""
    from .models import ReportFilter

    shard = get_shard(request)

    filter = ReportFilter(
        status=status,
        report_type=report_type,
        output_format=output_format,
        search_text=search,
    )

    reports = await shard.list_reports(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status=status.value if status else None)

    return ReportListResponse(
        reports=[_report_to_response(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=ReportResponse, status_code=201)
async def create_report(request: Request, body: ReportCreate):
    """Generate a new report."""
    shard = get_shard(request)

    report = await shard.generate_report(
        report_type=body.report_type,
        title=body.title,
        parameters=body.parameters,
        output_format=body.output_format,
    )

    return _report_to_response(report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(request: Request, report_id: str):
    """Get a specific report by ID."""
    shard = get_shard(request)
    report = await shard.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    return _report_to_response(report)


@router.delete("/{report_id}", status_code=204)
async def delete_report(request: Request, report_id: str):
    """Delete a report."""
    shard = get_shard(request)

    success = await shard.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")


@router.get("/{report_id}/download")
async def download_report(request: Request, report_id: str):
    """Download a report file."""
    shard = get_shard(request)
    report = await shard.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    if not report.file_path:
        raise HTTPException(status_code=404, detail=f"Report file not found")

    # Stub: would return file response here
    return {
        "message": "Download endpoint (stub)",
        "file_path": report.file_path,
        "file_size": report.file_size,
    }


# === Templates ===


@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    request: Request,
    report_type: Optional[ReportType] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List report templates."""
    shard = get_shard(request)
    templates = await shard.list_templates(
        report_type=report_type,
        limit=limit,
        offset=offset,
    )
    return [_template_to_response(t) for t in templates]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(request: Request, template_id: str):
    """Get a specific template by ID."""
    shard = get_shard(request)
    template = await shard.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    return _template_to_response(template)


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(request: Request, body: TemplateCreate):
    """Create a new report template."""
    shard = get_shard(request)

    template = await shard.create_template(
        name=body.name,
        report_type=body.report_type,
        description=body.description,
        parameters_schema=body.parameters_schema,
        default_format=body.default_format,
        template_content=body.template_content,
    )

    return _template_to_response(template)


# === Schedules ===


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    request: Request,
    enabled_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List report schedules."""
    shard = get_shard(request)
    schedules = await shard.list_schedules(
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )
    return [_schedule_to_response(s) for s in schedules]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(request: Request, body: ScheduleCreate):
    """Create a new report schedule."""
    shard = get_shard(request)

    # Verify template exists
    template = await shard.get_template(body.template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {body.template_id} not found")

    schedule = await shard.create_schedule(
        template_id=body.template_id,
        cron_expression=body.cron_expression,
        parameters=body.parameters,
        output_format=body.output_format,
        retention_days=body.retention_days,
    )

    return _schedule_to_response(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(request: Request, schedule_id: str):
    """Delete a report schedule."""
    shard = get_shard(request)

    success = await shard.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")


# === Preview ===


@router.post("/preview", response_model=PreviewResponse)
async def preview_report(body: PreviewRequest):
    """Preview a report without saving it."""
    # Stub implementation
    preview_content = f"# {body.title}\n\nReport Type: {body.report_type.value}\nFormat: {body.output_format.value}\n\n(Preview content would be generated here)"

    return PreviewResponse(
        preview_content=preview_content,
        estimated_size=len(preview_content),
        warnings=[],
    )


# === Statistics ===


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics(request: Request):
    """Get statistics about reports in the system."""
    shard = get_shard(request)
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_reports=stats.total_reports,
        by_status=stats.by_status,
        by_type=stats.by_type,
        by_format=stats.by_format,
        total_templates=stats.total_templates,
        total_schedules=stats.total_schedules,
        active_schedules=stats.active_schedules,
        total_file_size_bytes=stats.total_file_size_bytes,
        avg_generation_time_ms=stats.avg_generation_time_ms,
        reports_last_24h=stats.reports_last_24h,
        reports_last_7d=stats.reports_last_7d,
        reports_last_30d=stats.reports_last_30d,
    )


# === Filtered List Endpoints (for sub-routes) ===


@router.get("/pending", response_model=ReportListResponse)
async def list_pending_reports(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List pending reports."""
    from .models import ReportFilter

    shard = get_shard(request)
    filter = ReportFilter(status=ReportStatus.PENDING)
    reports = await shard.list_reports(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="pending")

    return ReportListResponse(
        reports=[_report_to_response(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/completed", response_model=ReportListResponse)
async def list_completed_reports(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List completed reports."""
    from .models import ReportFilter

    shard = get_shard(request)
    filter = ReportFilter(status=ReportStatus.COMPLETED)
    reports = await shard.list_reports(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="completed")

    return ReportListResponse(
        reports=[_report_to_response(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/failed", response_model=ReportListResponse)
async def list_failed_reports(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List failed reports."""
    from .models import ReportFilter

    shard = get_shard(request)
    filter = ReportFilter(status=ReportStatus.FAILED)
    reports = await shard.list_reports(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="failed")

    return ReportListResponse(
        reports=[_report_to_response(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )
