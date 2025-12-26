"""
Templates Shard - Main Implementation

Provides template management, versioning, and rendering capabilities.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from jinja2 import Environment, Template as Jinja2Template, TemplateSyntaxError, meta
from arkham_frame import ArkhamShard

from .models import (
    OutputFormat,
    PlaceholderWarning,
    Template,
    TemplateCreate,
    TemplateFilter,
    TemplatePlaceholder,
    TemplateRenderRequest,
    TemplateRenderResult,
    TemplateStatistics,
    TemplateType,
    TemplateTypeInfo,
    TemplateUpdate,
    TemplateVersion,
    TemplateVersionCreate,
)

logger = logging.getLogger(__name__)


class TemplatesShard(ArkhamShard):
    """
    Template management and rendering shard.

    Provides comprehensive template management with versioning,
    placeholder validation, and Jinja2-based rendering.

    Events Published:
        - templates.template.created
        - templates.template.updated
        - templates.template.deleted
        - templates.template.activated
        - templates.template.deactivated
        - templates.version.created
        - templates.version.restored
        - templates.rendered

    Events Subscribed:
        - (none)
    """

    name = "templates"
    version = "0.1.0"
    description = "Template management shard - create, edit, version, and render templates for reports, letters, and exports"

    def __init__(self):
        super().__init__()
        self._frame = None
        self._db = None
        self._event_bus = None
        self._storage = None
        self._jinja_env = None

        # In-memory caches (production would use database)
        self._templates: Dict[str, Template] = {}
        self._versions: Dict[str, List[TemplateVersion]] = {}
        self._render_count = 0

    async def initialize(self, frame) -> None:
        """Initialize the shard with Frame services."""
        self._frame = frame

        # Get required services
        self._db = frame.get_service("database")
        if not self._db:
            raise RuntimeError("Database service required for Templates shard")

        self._event_bus = frame.get_service("events")
        if not self._event_bus:
            raise RuntimeError("Events service required for Templates shard")

        # Get optional services
        self._storage = frame.get_service("storage")
        if not self._storage:
            logger.info("Storage service not available - export features limited")

        # Initialize Jinja2 environment
        self._jinja_env = Environment(
            autoescape=True,  # Security: auto-escape by default
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Initialize database schema
        await self._create_schema()

        logger.info("Templates shard initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
        # Clear caches
        self._templates.clear()
        self._versions.clear()

        self._db = None
        self._event_bus = None
        self._storage = None
        self._jinja_env = None
        self._frame = None

        logger.info("Templates shard shut down")

    def get_routes(self):
        """Return the API router."""
        from .api import router
        return router

    # === Template CRUD ===

    async def create_template(
        self,
        template_data: TemplateCreate,
        created_by: Optional[str] = None
    ) -> Template:
        """
        Create a new template.

        Args:
            template_data: Template creation data
            created_by: User creating the template

        Returns:
            Created template
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Validate template syntax
        try:
            self._jinja_env.from_string(template_data.content)
        except TemplateSyntaxError as e:
            raise ValueError(f"Invalid template syntax: {e}")

        # Auto-detect placeholders if not provided
        if not template_data.placeholders:
            detected = self._detect_placeholders(template_data.content)
            template_data.placeholders = detected

        # Create template
        template = Template(
            id=f"tpl_{uuid4().hex[:12]}",
            name=template_data.name,
            template_type=template_data.template_type,
            description=template_data.description,
            content=template_data.content,
            placeholders=template_data.placeholders,
            version=1,
            is_active=template_data.is_active,
            metadata=template_data.metadata,
            created_by=created_by,
            updated_by=created_by,
        )

        # Store in cache (production: database)
        self._templates[template.id] = template

        # Create initial version
        await self._create_version_record(
            template,
            created_by=created_by,
            changes="Initial version"
        )

        # Publish event
        if self._event_bus:
            await self._event_bus.publish("templates.template.created", {
                "template_id": template.id,
                "name": template.name,
                "template_type": template.template_type.value,
                "created_by": created_by,
            })

        logger.info(f"Created template: {template.name} ({template.id})")
        return template

    async def get_template(self, template_id: str) -> Optional[Template]:
        """
        Get a template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Get from cache (production: database query)
        return self._templates.get(template_id)

    async def list_templates(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[TemplateFilter] = None,
        sort: str = "created_at",
        order: str = "desc"
    ) -> tuple[List[Template], int]:
        """
        List templates with pagination and filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            filters: Filter criteria
            sort: Sort field
            order: Sort order (asc/desc)

        Returns:
            Tuple of (templates, total_count)
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Get all templates (production: database query)
        templates = list(self._templates.values())

        # Apply filters
        if filters:
            if filters.template_type:
                templates = [t for t in templates if t.template_type == filters.template_type]
            if filters.is_active is not None:
                templates = [t for t in templates if t.is_active == filters.is_active]
            if filters.name_contains:
                search = filters.name_contains.lower()
                templates = [t for t in templates if search in t.name.lower()]
            if filters.created_after:
                templates = [t for t in templates if t.created_at >= filters.created_after]
            if filters.created_before:
                templates = [t for t in templates if t.created_at <= filters.created_before]

        total = len(templates)

        # Sort
        reverse = (order == "desc")
        templates.sort(key=lambda t: getattr(t, sort, t.created_at), reverse=reverse)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        templates = templates[start:end]

        return templates, total

    async def update_template(
        self,
        template_id: str,
        update_data: TemplateUpdate,
        updated_by: Optional[str] = None,
        create_version: bool = True
    ) -> Optional[Template]:
        """
        Update an existing template.

        Args:
            template_id: Template ID
            update_data: Update data
            updated_by: User updating the template
            create_version: Whether to create a new version

        Returns:
            Updated template or None if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = self._templates.get(template_id)
        if not template:
            return None

        # Store old version if content changed
        content_changed = False

        # Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if key == "content" and value != template.content:
                content_changed = True
            setattr(template, key, value)

        template.updated_at = datetime.utcnow()
        template.updated_by = updated_by

        # Validate new content if changed
        if "content" in update_dict:
            try:
                self._jinja_env.from_string(template.content)
            except TemplateSyntaxError as e:
                raise ValueError(f"Invalid template syntax: {e}")

        # Create new version if content changed
        if content_changed and create_version:
            template.version += 1
            await self._create_version_record(
                template,
                created_by=updated_by,
                changes="Template updated"
            )

        # Publish event
        if self._event_bus:
            await self._event_bus.publish("templates.template.updated", {
                "template_id": template.id,
                "name": template.name,
                "version": template.version,
                "updated_by": updated_by,
            })

        logger.info(f"Updated template: {template.name} ({template.id})")
        return template

    async def delete_template(
        self,
        template_id: str,
        deleted_by: Optional[str] = None
    ) -> bool:
        """
        Delete a template.

        Args:
            template_id: Template ID
            deleted_by: User deleting the template

        Returns:
            True if deleted, False if not found
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        if template_id not in self._templates:
            return False

        template = self._templates[template_id]

        # Remove from storage
        del self._templates[template_id]
        if template_id in self._versions:
            del self._versions[template_id]

        # Publish event
        if self._event_bus:
            await self._event_bus.publish("templates.template.deleted", {
                "template_id": template_id,
                "name": template.name,
                "deleted_by": deleted_by,
            })

        logger.info(f"Deleted template: {template.name} ({template_id})")
        return True

    async def activate_template(
        self,
        template_id: str,
        activated_by: Optional[str] = None
    ) -> Optional[Template]:
        """
        Activate a template.

        Args:
            template_id: Template ID
            activated_by: User activating the template

        Returns:
            Updated template or None if not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        template.is_active = True
        template.updated_at = datetime.utcnow()
        template.updated_by = activated_by

        if self._event_bus:
            await self._event_bus.publish("templates.template.activated", {
                "template_id": template_id,
                "name": template.name,
                "activated_by": activated_by,
            })

        logger.info(f"Activated template: {template.name} ({template_id})")
        return template

    async def deactivate_template(
        self,
        template_id: str,
        deactivated_by: Optional[str] = None
    ) -> Optional[Template]:
        """
        Deactivate a template.

        Args:
            template_id: Template ID
            deactivated_by: User deactivating the template

        Returns:
            Updated template or None if not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        template.is_active = False
        template.updated_at = datetime.utcnow()
        template.updated_by = deactivated_by

        if self._event_bus:
            await self._event_bus.publish("templates.template.deactivated", {
                "template_id": template_id,
                "name": template.name,
                "deactivated_by": deactivated_by,
            })

        logger.info(f"Deactivated template: {template.name} ({template_id})")
        return template

    # === Versioning ===

    async def create_version(
        self,
        template_id: str,
        version_data: TemplateVersionCreate,
        created_by: Optional[str] = None
    ) -> Optional[TemplateVersion]:
        """
        Create a new version of a template.

        Args:
            template_id: Template ID
            version_data: Version creation data
            created_by: User creating the version

        Returns:
            Created version or None if template not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        template.version += 1
        version = await self._create_version_record(
            template,
            created_by=created_by,
            changes=version_data.changes
        )

        if self._event_bus:
            await self._event_bus.publish("templates.version.created", {
                "template_id": template_id,
                "version_id": version.id,
                "version_number": version.version_number,
                "created_by": created_by,
            })

        return version

    async def get_versions(self, template_id: str) -> List[TemplateVersion]:
        """
        Get all versions of a template.

        Args:
            template_id: Template ID

        Returns:
            List of versions, newest first
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        versions = self._versions.get(template_id, [])
        return sorted(versions, key=lambda v: v.version_number, reverse=True)

    async def get_version(
        self,
        template_id: str,
        version_id: str
    ) -> Optional[TemplateVersion]:
        """
        Get a specific version.

        Args:
            template_id: Template ID
            version_id: Version ID

        Returns:
            Version or None if not found
        """
        versions = self._versions.get(template_id, [])
        for version in versions:
            if version.id == version_id:
                return version
        return None

    async def restore_version(
        self,
        template_id: str,
        version_id: str,
        restored_by: Optional[str] = None
    ) -> Optional[Template]:
        """
        Restore a template to a previous version.

        Args:
            template_id: Template ID
            version_id: Version ID to restore
            restored_by: User restoring the version

        Returns:
            Updated template or None if not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        version = await self.get_version(template_id, version_id)
        if not version:
            return None

        # Restore content and placeholders
        template.content = version.content
        template.placeholders = version.placeholders
        template.version += 1
        template.updated_at = datetime.utcnow()
        template.updated_by = restored_by

        # Create new version record
        await self._create_version_record(
            template,
            created_by=restored_by,
            changes=f"Restored from version {version.version_number}"
        )

        if self._event_bus:
            await self._event_bus.publish("templates.version.restored", {
                "template_id": template_id,
                "version_id": version_id,
                "new_version": template.version,
                "restored_by": restored_by,
            })

        logger.info(f"Restored template {template_id} to version {version.version_number}")
        return template

    # === Rendering ===

    async def render_template(
        self,
        template_id: str,
        render_request: TemplateRenderRequest
    ) -> Optional[TemplateRenderResult]:
        """
        Render a template with data.

        Args:
            template_id: Template ID
            render_request: Render request with data

        Returns:
            Render result or None if template not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        # Validate placeholders
        warnings = self._validate_placeholders(
            template,
            render_request.data,
            strict=render_request.strict
        )

        # Apply defaults for missing optional placeholders
        data = self._apply_defaults(template, render_request.data)

        # Render with Jinja2
        try:
            jinja_template = self._jinja_env.from_string(template.content)
            rendered = jinja_template.render(**data)
        except Exception as e:
            logger.error(f"Template render error: {e}")
            raise ValueError(f"Template rendering failed: {e}")

        # Track what was used
        placeholders_used = [k for k in data.keys() if k in template.content]

        # Increment render count
        self._render_count += 1

        result = TemplateRenderResult(
            rendered_content=rendered,
            placeholders_used=placeholders_used,
            warnings=warnings,
            output_format=render_request.output_format,
        )

        if self._event_bus:
            await self._event_bus.publish("templates.rendered", {
                "template_id": template_id,
                "template_name": template.name,
                "output_format": render_request.output_format.value,
            })

        return result

    async def preview_template(
        self,
        template_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[TemplateRenderResult]:
        """
        Preview a template with sample data.

        Args:
            template_id: Template ID
            data: Optional preview data (uses placeholder examples if not provided)

        Returns:
            Render result or None if template not found
        """
        template = self._templates.get(template_id)
        if not template:
            return None

        # Use provided data or generate from examples
        preview_data = data or self._generate_preview_data(template)

        request = TemplateRenderRequest(
            data=preview_data,
            output_format=OutputFormat.TEXT,
            strict=False  # Don't error on missing in preview
        )

        return await self.render_template(template_id, request)

    async def validate_placeholders(
        self,
        template_id: str,
        data: Dict[str, Any]
    ) -> List[PlaceholderWarning]:
        """
        Validate placeholder data without rendering.

        Args:
            template_id: Template ID
            data: Data to validate

        Returns:
            List of validation warnings
        """
        template = self._templates.get(template_id)
        if not template:
            return [PlaceholderWarning(
                placeholder="template",
                message="Template not found",
                severity="error"
            )]

        return self._validate_placeholders(template, data, strict=False)

    # === Statistics ===

    async def get_statistics(self) -> TemplateStatistics:
        """
        Get template statistics.

        Returns:
            Template statistics
        """
        templates = list(self._templates.values())

        # Count by type
        by_type = {}
        for template_type in TemplateType:
            count = len([t for t in templates if t.template_type == template_type])
            if count > 0:
                by_type[template_type.value] = count

        # Recent templates (last 5)
        recent = sorted(templates, key=lambda t: t.created_at, reverse=True)[:5]

        # Total versions
        total_versions = sum(len(versions) for versions in self._versions.values())

        return TemplateStatistics(
            total_templates=len(templates),
            active_templates=len([t for t in templates if t.is_active]),
            inactive_templates=len([t for t in templates if not t.is_active]),
            by_type=by_type,
            total_versions=total_versions,
            total_renders=self._render_count,
            recent_templates=recent,
        )

    async def get_count(self, active_only: bool = False) -> int:
        """
        Get template count.

        Args:
            active_only: Count only active templates

        Returns:
            Template count
        """
        templates = list(self._templates.values())
        if active_only:
            templates = [t for t in templates if t.is_active]
        return len(templates)

    async def get_template_types(self) -> List[TemplateTypeInfo]:
        """
        Get information about template types.

        Returns:
            List of template type info
        """
        templates = list(self._templates.values())

        type_info = []
        for template_type in TemplateType:
            count = len([t for t in templates if t.template_type == template_type])
            type_info.append(TemplateTypeInfo(
                type=template_type,
                name=template_type.value.title(),
                description=self._get_type_description(template_type),
                count=count,
            ))

        return type_info

    # === Private Methods ===

    async def _create_schema(self) -> None:
        """Create database schema for templates."""
        # Production implementation would create:
        # - arkham_templates.templates table
        # - arkham_templates.template_versions table
        # - arkham_templates.template_renders table (optional)
        # - Indexes on frequently queried fields
        pass

    async def _create_version_record(
        self,
        template: Template,
        created_by: Optional[str] = None,
        changes: str = ""
    ) -> TemplateVersion:
        """Create a version record for a template."""
        version = TemplateVersion(
            id=f"ver_{uuid4().hex[:12]}",
            template_id=template.id,
            version_number=template.version,
            content=template.content,
            placeholders=template.placeholders.copy(),
            created_by=created_by,
            changes=changes,
        )

        # Store in cache
        if template.id not in self._versions:
            self._versions[template.id] = []
        self._versions[template.id].append(version)

        return version

    def _detect_placeholders(self, content: str) -> List[TemplatePlaceholder]:
        """Auto-detect placeholders from template content."""
        try:
            ast = self._jinja_env.parse(content)
            placeholders_names = meta.find_undeclared_variables(ast)

            return [
                TemplatePlaceholder(
                    name=name,
                    description=f"Auto-detected placeholder: {name}",
                    data_type="string",
                    required=False,
                )
                for name in sorted(placeholders_names)
            ]
        except Exception as e:
            logger.warning(f"Failed to auto-detect placeholders: {e}")
            return []

    def _validate_placeholders(
        self,
        template: Template,
        data: Dict[str, Any],
        strict: bool = True
    ) -> List[PlaceholderWarning]:
        """Validate placeholder data against template requirements."""
        warnings = []

        # Check required placeholders
        for placeholder in template.placeholders:
            if placeholder.required and placeholder.name not in data:
                message = f"Required placeholder '{placeholder.name}' is missing"
                warnings.append(PlaceholderWarning(
                    placeholder=placeholder.name,
                    message=message,
                    severity="error" if strict else "warning",
                ))

        # Check for unused provided data
        placeholder_names = {p.name for p in template.placeholders}
        for key in data.keys():
            if key not in placeholder_names:
                warnings.append(PlaceholderWarning(
                    placeholder=key,
                    message=f"Provided data '{key}' is not a defined placeholder",
                    severity="info",
                ))

        return warnings

    def _apply_defaults(
        self,
        template: Template,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply default values for missing placeholders."""
        result = data.copy()

        for placeholder in template.placeholders:
            if placeholder.name not in result and placeholder.default_value is not None:
                result[placeholder.name] = placeholder.default_value

        return result

    def _generate_preview_data(self, template: Template) -> Dict[str, Any]:
        """Generate preview data from placeholder definitions."""
        data = {}

        for placeholder in template.placeholders:
            if placeholder.example:
                data[placeholder.name] = placeholder.example
            elif placeholder.default_value is not None:
                data[placeholder.name] = placeholder.default_value
            else:
                # Generate sample data based on type
                data[placeholder.name] = self._generate_sample_value(placeholder)

        return data

    def _generate_sample_value(self, placeholder: TemplatePlaceholder) -> Any:
        """Generate a sample value for a placeholder."""
        samples = {
            "string": f"[{placeholder.name}]",
            "number": "123",
            "boolean": "true",
            "date": "2024-01-01",
            "email": "example@example.com",
            "url": "https://example.com",
            "text": f"Sample text for {placeholder.name}",
            "json": "{}",
            "list": "[]",
        }
        return samples.get(placeholder.data_type.value, f"[{placeholder.name}]")

    def _get_type_description(self, template_type: TemplateType) -> str:
        """Get description for a template type."""
        descriptions = {
            TemplateType.REPORT: "Analysis reports and findings",
            TemplateType.LETTER: "Formal letters and correspondence",
            TemplateType.EXPORT: "Data export templates",
            TemplateType.EMAIL: "Email templates",
            TemplateType.CUSTOM: "Custom user-defined templates",
        }
        return descriptions.get(template_type, "")
