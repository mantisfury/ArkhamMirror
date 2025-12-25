"""
Template API endpoints.

Provides REST API for template management and rendering.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter()


class TemplateCreateRequest(BaseModel):
    """Request body for creating a template."""
    name: str = Field(..., description="Template name (unique identifier)")
    content: str = Field(..., description="Template content (Jinja2 syntax)")
    description: str = Field("", description="Template description")
    category: str = Field("general", description="Template category")
    variables: Optional[List[str]] = Field(None, description="Expected variables")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TemplateUpdateRequest(BaseModel):
    """Request body for updating a template."""
    content: Optional[str] = Field(None, description="New template content")
    description: Optional[str] = Field(None, description="New description")
    category: Optional[str] = Field(None, description="New category")


class RenderRequest(BaseModel):
    """Request body for rendering a template."""
    variables: Dict[str, Any] = Field(default_factory=dict, description="Template variables")


class RenderStringRequest(BaseModel):
    """Request body for rendering a template string."""
    content: str = Field(..., description="Template content")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Template variables")


class ValidateRequest(BaseModel):
    """Request body for validating a template."""
    content: str = Field(..., description="Template content to validate")


@router.get("/")
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
) -> Dict[str, Any]:
    """List all templates."""
    from ..main import get_frame

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    templates = template_service.list(category=category)

    return {
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "variables": t.variables,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in templates
        ],
        "count": len(templates),
    }


@router.get("/categories")
async def get_categories() -> Dict[str, Any]:
    """Get list of template categories."""
    from ..main import get_frame

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    categories = template_service.get_categories()

    return {
        "categories": categories,
        "count": len(categories),
    }


@router.post("/")
async def create_template(request: TemplateCreateRequest) -> Dict[str, Any]:
    """Create a new template."""
    from ..main import get_frame
    from ..services.templates import TemplateError

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    # Check if template already exists
    existing = template_service.get(request.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Template '{request.name}' already exists")

    try:
        template = template_service.register(
            name=request.name,
            content=request.content,
            description=request.description,
            category=request.category,
            variables=request.variables,
            metadata=request.metadata,
        )

        return {
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "variables": template.variables,
            "created_at": template.created_at.isoformat(),
        }

    except TemplateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}")
async def get_template(name: str) -> Dict[str, Any]:
    """Get a template by name."""
    from ..main import get_frame

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    template = template_service.get(name)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")

    return {
        "name": template.name,
        "content": template.content,
        "description": template.description,
        "category": template.category,
        "variables": template.variables,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
        "metadata": template.metadata,
    }


@router.delete("/{name}")
async def delete_template(name: str) -> Dict[str, Any]:
    """Delete a template."""
    from ..main import get_frame

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    if not template_service.delete(name):
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")

    return {"deleted": name}


@router.post("/{name}/render")
async def render_template(name: str, request: RenderRequest) -> Dict[str, Any]:
    """Render a template with variables."""
    from ..main import get_frame
    from ..services.templates import TemplateNotFoundError, TemplateRenderError

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    try:
        result = template_service.render(name, variables=request.variables)

        return {
            "content": result.content,
            "template_name": result.template_name,
            "rendered_at": result.rendered_at.isoformat(),
            "variables_used": list(result.variables_used.keys()),
        }

    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    except TemplateRenderError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/render")
async def render_string(request: RenderStringRequest) -> Dict[str, Any]:
    """Render a template string directly."""
    from ..main import get_frame
    from ..services.templates import TemplateRenderError

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    try:
        content = template_service.render_string(
            request.content,
            variables=request.variables,
        )

        return {
            "content": content,
        }

    except TemplateRenderError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate")
async def validate_template(request: ValidateRequest) -> Dict[str, Any]:
    """Validate template syntax."""
    from ..main import get_frame

    frame = get_frame()
    template_service = frame.get_service("templates")

    if not template_service:
        raise HTTPException(status_code=503, detail="Template service not available")

    errors = template_service.validate(request.content)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }
