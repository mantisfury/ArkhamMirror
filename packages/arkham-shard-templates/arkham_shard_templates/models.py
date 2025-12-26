"""
Templates Shard - Pydantic Models

Data models for template management, versioning, and rendering.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TemplateType(str, Enum):
    """Template type enumeration."""
    REPORT = "REPORT"
    LETTER = "LETTER"
    EXPORT = "EXPORT"
    EMAIL = "EMAIL"
    CUSTOM = "CUSTOM"


class PlaceholderDataType(str, Enum):
    """Placeholder data type enumeration."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    EMAIL = "email"
    URL = "url"
    TEXT = "text"  # Multi-line text
    JSON = "json"
    LIST = "list"


class TemplatePlaceholder(BaseModel):
    """Template placeholder definition."""
    name: str = Field(..., description="Placeholder name (alphanumeric + underscore)")
    description: str = Field(default="", description="Human-readable description")
    data_type: PlaceholderDataType = Field(
        default=PlaceholderDataType.STRING,
        description="Expected data type"
    )
    default_value: Optional[Any] = Field(
        default=None,
        description="Default value if not provided"
    )
    required: bool = Field(default=False, description="Whether placeholder is required")
    example: Optional[str] = Field(default=None, description="Example value")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate placeholder name is alphanumeric + underscore."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Placeholder name must be alphanumeric with underscores")
        return v


class Template(BaseModel):
    """Template model."""
    id: str = Field(..., description="Unique template ID")
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    template_type: TemplateType = Field(..., description="Template type")
    description: str = Field(default="", max_length=1000, description="Template description")
    content: str = Field(..., min_length=1, description="Template content (Jinja2)")
    placeholders: List[TemplatePlaceholder] = Field(
        default_factory=list,
        description="Placeholder definitions"
    )
    version: int = Field(default=1, ge=1, description="Current version number")
    is_active: bool = Field(default=True, description="Whether template is active")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, description="User who created template")
    updated_by: Optional[str] = Field(default=None, description="User who last updated template")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "tpl_abc123",
                "name": "FOIA Request Letter",
                "template_type": "LETTER",
                "description": "Template for Freedom of Information Act requests",
                "content": "Dear {{ agency_name }},\n\nI request access to {{ records }}.",
                "placeholders": [
                    {
                        "name": "agency_name",
                        "description": "Agency name",
                        "data_type": "string",
                        "required": True
                    }
                ],
                "version": 1,
                "is_active": True
            }
        }


class TemplateCreate(BaseModel):
    """Model for creating a new template."""
    name: str = Field(..., min_length=1, max_length=255)
    template_type: TemplateType
    description: str = Field(default="", max_length=1000)
    content: str = Field(..., min_length=1)
    placeholders: List[TemplatePlaceholder] = Field(default_factory=list)
    is_active: bool = Field(default=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TemplateUpdate(BaseModel):
    """Model for updating an existing template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    template_type: Optional[TemplateType] = None
    description: Optional[str] = Field(None, max_length=1000)
    content: Optional[str] = Field(None, min_length=1)
    placeholders: Optional[List[TemplatePlaceholder]] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class TemplateVersion(BaseModel):
    """Template version history entry."""
    id: str = Field(..., description="Version ID")
    template_id: str = Field(..., description="Parent template ID")
    version_number: int = Field(..., ge=1, description="Version number")
    content: str = Field(..., description="Template content at this version")
    placeholders: List[TemplatePlaceholder] = Field(
        default_factory=list,
        description="Placeholders at this version"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, description="User who created this version")
    changes: str = Field(default="", description="Description of changes in this version")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "ver_xyz789",
                "template_id": "tpl_abc123",
                "version_number": 2,
                "content": "Updated content...",
                "changes": "Added new placeholder for contact information"
            }
        }


class TemplateVersionCreate(BaseModel):
    """Model for creating a new template version."""
    changes: str = Field(default="", max_length=500, description="Description of changes")


class OutputFormat(str, Enum):
    """Output format for rendered templates."""
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class TemplateRenderRequest(BaseModel):
    """Request to render a template."""
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data to populate placeholders"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Desired output format"
    )
    strict: bool = Field(
        default=True,
        description="Raise error on missing required placeholders"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "agency_name": "U.S. Department of Justice",
                    "records": "All records related to case #2024-001"
                },
                "output_format": "text",
                "strict": True
            }
        }


class PlaceholderWarning(BaseModel):
    """Warning about placeholder usage."""
    placeholder: str
    message: str
    severity: str = Field(default="warning")  # warning, error, info


class TemplateRenderResult(BaseModel):
    """Result of template rendering."""
    rendered_content: str = Field(..., description="Rendered template output")
    placeholders_used: List[str] = Field(
        default_factory=list,
        description="Placeholders that were populated"
    )
    warnings: List[PlaceholderWarning] = Field(
        default_factory=list,
        description="Warnings about placeholders"
    )
    output_format: OutputFormat
    rendered_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "rendered_content": "Dear U.S. Department of Justice,\n\nI request access to...",
                "placeholders_used": ["agency_name", "records"],
                "warnings": [],
                "output_format": "text"
            }
        }


class TemplateFilter(BaseModel):
    """Filter criteria for listing templates."""
    template_type: Optional[TemplateType] = None
    is_active: Optional[bool] = None
    name_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None


class TemplateListResponse(BaseModel):
    """Response for list templates endpoint."""
    items: List[Template]
    total: int
    page: int
    page_size: int


class TemplateStatistics(BaseModel):
    """Template statistics."""
    total_templates: int = 0
    active_templates: int = 0
    inactive_templates: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    total_versions: int = 0
    total_renders: int = 0
    recent_templates: List[Template] = Field(default_factory=list, max_length=5)

    class Config:
        json_schema_extra = {
            "example": {
                "total_templates": 25,
                "active_templates": 20,
                "inactive_templates": 5,
                "by_type": {
                    "REPORT": 10,
                    "LETTER": 8,
                    "EXPORT": 5,
                    "EMAIL": 2
                },
                "total_versions": 47,
                "total_renders": 156
            }
        }


class TemplateTypeInfo(BaseModel):
    """Information about a template type."""
    type: TemplateType
    name: str
    description: str
    count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "type": "LETTER",
                "name": "Letter",
                "description": "Formal letters and correspondence",
                "count": 8
            }
        }


class BulkActionRequest(BaseModel):
    """Request for bulk actions on templates."""
    template_ids: List[str] = Field(..., min_length=1, description="Template IDs to act on")


class BulkActionResponse(BaseModel):
    """Response for bulk actions."""
    success: bool
    processed: int
    failed: int
    errors: List[str] = Field(default_factory=list)
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "processed": 5,
                "failed": 0,
                "errors": [],
                "message": "5 templates processed successfully"
            }
        }
