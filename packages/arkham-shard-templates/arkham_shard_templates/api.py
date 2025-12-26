"""
Templates Shard - FastAPI Routes

API endpoints for template management, versioning, and rendering.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .models import (
    BulkActionRequest,
    BulkActionResponse,
    OutputFormat,
    Template,
    TemplateCreate,
    TemplateFilter,
    TemplateListResponse,
    TemplateRenderRequest,
    TemplateRenderResult,
    TemplateStatistics,
    TemplateType,
    TemplateTypeInfo,
    TemplateUpdate,
    TemplateVersion,
    TemplateVersionCreate,
    PlaceholderWarning,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])

# Shard instance will be injected by the Frame
_shard = None


def get_shard():
    """Get the shard instance."""
    if _shard is None:
        raise RuntimeError("Templates shard not initialized")
    return _shard


def set_shard(shard):
    """Set the shard instance (called by Frame)."""
    global _shard
    _shard = shard


# === Health & Status ===

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "shard": "templates",
        "version": "0.1.0"
    }


@router.get("/count")
async def get_count(active_only: bool = Query(False, description="Count only active templates")):
    """
    Get total template count (for navigation badge).

    Args:
        active_only: Count only active templates

    Returns:
        Count response
    """
    shard = get_shard()
    count = await shard.get_count(active_only=active_only)
    return {"count": count}


@router.get("/stats", response_model=TemplateStatistics)
async def get_statistics():
    """
    Get template statistics.

    Returns:
        Template statistics including counts by type, versions, and recent templates
    """
    shard = get_shard()
    return await shard.get_statistics()


# === Template CRUD ===

@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    template_type: Optional[TemplateType] = Query(None, description="Filter by template type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    name_contains: Optional[str] = Query(None, description="Search by name"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
):
    """
    List templates with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        template_type: Filter by template type
        is_active: Filter by active status
        name_contains: Search templates by name
        sort: Field to sort by
        order: Sort order (asc or desc)

    Returns:
        Paginated list of templates
    """
    shard = get_shard()

    # Build filters
    filters = TemplateFilter(
        template_type=template_type,
        is_active=is_active,
        name_contains=name_contains,
    )

    # Get templates
    templates, total = await shard.list_templates(
        page=page,
        page_size=page_size,
        filters=filters,
        sort=sort,
        order=order,
    )

    return TemplateListResponse(
        items=templates,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=Template, status_code=201)
async def create_template(template_data: TemplateCreate):
    """
    Create a new template.

    Args:
        template_data: Template creation data

    Returns:
        Created template

    Raises:
        HTTPException: If template creation fails
    """
    shard = get_shard()

    try:
        template = await shard.create_template(template_data)
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {e}")


@router.get("/{template_id}", response_model=Template)
async def get_template(template_id: str):
    """
    Get a template by ID.

    Args:
        template_id: Template ID

    Returns:
        Template details

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    template = await shard.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.put("/{template_id}", response_model=Template)
async def update_template(
    template_id: str,
    update_data: TemplateUpdate,
    create_version: bool = Query(True, description="Create new version on content change")
):
    """
    Update an existing template.

    Args:
        template_id: Template ID
        update_data: Update data
        create_version: Whether to create new version on content change

    Returns:
        Updated template

    Raises:
        HTTPException: If template not found or update fails
    """
    shard = get_shard()

    try:
        template = await shard.update_template(
            template_id,
            update_data,
            create_version=create_version
        )

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update template: {e}")


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """
    Delete a template.

    Args:
        template_id: Template ID

    Returns:
        Success response

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    success = await shard.delete_template(template_id)

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"deleted": True, "template_id": template_id}


@router.post("/{template_id}/activate", response_model=Template)
async def activate_template(template_id: str):
    """
    Activate a template.

    Args:
        template_id: Template ID

    Returns:
        Updated template

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    template = await shard.activate_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.post("/{template_id}/deactivate", response_model=Template)
async def deactivate_template(template_id: str):
    """
    Deactivate a template.

    Args:
        template_id: Template ID

    Returns:
        Updated template

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    template = await shard.deactivate_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


# === Versioning ===

@router.get("/{template_id}/versions", response_model=list[TemplateVersion])
async def get_template_versions(template_id: str):
    """
    Get all versions of a template.

    Args:
        template_id: Template ID

    Returns:
        List of template versions (newest first)

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()

    # Check template exists
    template = await shard.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    versions = await shard.get_versions(template_id)
    return versions


@router.post("/{template_id}/versions", response_model=TemplateVersion, status_code=201)
async def create_template_version(
    template_id: str,
    version_data: TemplateVersionCreate
):
    """
    Create a new version of a template.

    Args:
        template_id: Template ID
        version_data: Version creation data

    Returns:
        Created version

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    version = await shard.create_version(template_id, version_data)

    if not version:
        raise HTTPException(status_code=404, detail="Template not found")

    return version


@router.get("/{template_id}/versions/{version_id}", response_model=TemplateVersion)
async def get_template_version(template_id: str, version_id: str):
    """
    Get a specific template version.

    Args:
        template_id: Template ID
        version_id: Version ID

    Returns:
        Template version

    Raises:
        HTTPException: If template or version not found
    """
    shard = get_shard()
    version = await shard.get_version(template_id, version_id)

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return version


@router.post("/{template_id}/restore/{version_id}", response_model=Template)
async def restore_template_version(template_id: str, version_id: str):
    """
    Restore a template to a previous version.

    This creates a new version with the content from the specified version.

    Args:
        template_id: Template ID
        version_id: Version ID to restore

    Returns:
        Updated template

    Raises:
        HTTPException: If template or version not found
    """
    shard = get_shard()
    template = await shard.restore_version(template_id, version_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template or version not found")

    return template


# === Rendering ===

@router.post("/{template_id}/render", response_model=TemplateRenderResult)
async def render_template(template_id: str, render_request: TemplateRenderRequest):
    """
    Render a template with provided data.

    Args:
        template_id: Template ID
        render_request: Render request with data and options

    Returns:
        Rendered template result

    Raises:
        HTTPException: If template not found or rendering fails
    """
    shard = get_shard()

    try:
        result = await shard.render_template(template_id, render_request)

        if not result:
            raise HTTPException(status_code=404, detail="Template not found")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render template: {e}")


@router.post("/{template_id}/preview", response_model=TemplateRenderResult)
async def preview_template(
    template_id: str,
    data: Optional[dict] = None
):
    """
    Preview a template with sample or provided data.

    If no data is provided, uses placeholder examples or defaults.

    Args:
        template_id: Template ID
        data: Optional preview data

    Returns:
        Rendered preview result

    Raises:
        HTTPException: If template not found or preview fails
    """
    shard = get_shard()

    try:
        result = await shard.preview_template(template_id, data)

        if not result:
            raise HTTPException(status_code=404, detail="Template not found")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview template: {e}")


@router.post("/{template_id}/validate", response_model=list[PlaceholderWarning])
async def validate_template_data(template_id: str, data: dict):
    """
    Validate placeholder data without rendering.

    Args:
        template_id: Template ID
        data: Data to validate against placeholders

    Returns:
        List of validation warnings and errors

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()

    try:
        warnings = await shard.validate_placeholders(template_id, data)
        return warnings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate data: {e}")


# === Metadata ===

@router.get("/types", response_model=list[TemplateTypeInfo])
async def get_template_types():
    """
    Get available template types with counts.

    Returns:
        List of template type information
    """
    shard = get_shard()
    return await shard.get_template_types()


@router.get("/{template_id}/placeholders", response_model=list)
async def get_template_placeholders(template_id: str):
    """
    Get placeholder definitions for a template.

    Args:
        template_id: Template ID

    Returns:
        List of placeholder definitions

    Raises:
        HTTPException: If template not found
    """
    shard = get_shard()
    template = await shard.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template.placeholders


# === Bulk Actions ===

@router.post("/batch/activate", response_model=BulkActionResponse)
async def bulk_activate(request: BulkActionRequest):
    """
    Activate multiple templates.

    Args:
        request: Bulk action request with template IDs

    Returns:
        Bulk action result
    """
    shard = get_shard()

    processed = 0
    failed = 0
    errors = []

    for template_id in request.template_ids:
        try:
            result = await shard.activate_template(template_id)
            if result:
                processed += 1
            else:
                failed += 1
                errors.append(f"Template {template_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Template {template_id}: {str(e)}")

    return BulkActionResponse(
        success=(failed == 0),
        processed=processed,
        failed=failed,
        errors=errors,
        message=f"Activated {processed} templates, {failed} failed"
    )


@router.post("/batch/deactivate", response_model=BulkActionResponse)
async def bulk_deactivate(request: BulkActionRequest):
    """
    Deactivate multiple templates.

    Args:
        request: Bulk action request with template IDs

    Returns:
        Bulk action result
    """
    shard = get_shard()

    processed = 0
    failed = 0
    errors = []

    for template_id in request.template_ids:
        try:
            result = await shard.deactivate_template(template_id)
            if result:
                processed += 1
            else:
                failed += 1
                errors.append(f"Template {template_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Template {template_id}: {str(e)}")

    return BulkActionResponse(
        success=(failed == 0),
        processed=processed,
        failed=failed,
        errors=errors,
        message=f"Deactivated {processed} templates, {failed} failed"
    )


@router.post("/batch/delete", response_model=BulkActionResponse)
async def bulk_delete(request: BulkActionRequest):
    """
    Delete multiple templates.

    Args:
        request: Bulk action request with template IDs

    Returns:
        Bulk action result
    """
    shard = get_shard()

    processed = 0
    failed = 0
    errors = []

    for template_id in request.template_ids:
        try:
            result = await shard.delete_template(template_id)
            if result:
                processed += 1
            else:
                failed += 1
                errors.append(f"Template {template_id} not found")
        except Exception as e:
            failed += 1
            errors.append(f"Template {template_id}: {str(e)}")

    return BulkActionResponse(
        success=(failed == 0),
        processed=processed,
        failed=failed,
        errors=errors,
        message=f"Deleted {processed} templates, {failed} failed"
    )
