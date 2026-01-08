"""
Templates Shard - Main Implementation

Provides template management, versioning, and rendering capabilities.
Uses PostgreSQL for persistence following the ACH shard pattern.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from jinja2 import Environment, TemplateSyntaxError, meta
from arkham_frame import ArkhamShard

from .models import (
    OutputFormat,
    PlaceholderWarning,
    PlaceholderDataType,
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


def _parse_json_field(value: Any, default: Any = None) -> Any:
    """Parse a JSON field that may already be parsed by the database driver."""
    if value is None:
        return default if default is not None else []
    if isinstance(value, (list, dict)):
        return value  # Already parsed by PostgreSQL JSONB
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []
    return default if default is not None else []


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

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.templates_shard = self

        logger.info("Templates shard initialized")

    async def shutdown(self) -> None:
        """Clean up resources."""
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

        now = datetime.utcnow()

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
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

        # Save to database
        await self._save_template(template)

        # Create initial version
        await self._create_version_record(
            template,
            created_by=created_by,
            changes="Initial version"
        )

        # Publish event
        if self._event_bus:
            await self._event_bus.emit("templates.template.created", {
                "template_id": template.id,
                "name": template.name,
                "template_type": template.template_type.value,
                "created_by": created_by,
            }, source="templates-shard")

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

        return await self._load_template(template_id)

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

        # Build WHERE clause and parameters
        where_clauses = []
        params: Dict[str, Any] = {}

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            where_clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        if filters:
            if filters.template_type:
                where_clauses.append("template_type = :template_type")
                params["template_type"] = filters.template_type.value
            if filters.is_active is not None:
                where_clauses.append("is_active = :is_active")
                params["is_active"] = filters.is_active
            if filters.name_contains:
                where_clauses.append("LOWER(name) LIKE :name_contains")
                params["name_contains"] = f"%{filters.name_contains.lower()}%"
            if filters.created_after:
                where_clauses.append("created_at >= :created_after")
                params["created_after"] = filters.created_after
            if filters.created_before:
                where_clauses.append("created_at <= :created_before")
                params["created_before"] = filters.created_before

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM arkham_templates WHERE {where_sql}"
        count_row = await self._db.fetch_one(count_query, params)
        total = count_row["count"] if count_row else 0

        # Validate sort field to prevent SQL injection
        valid_sort_fields = {"created_at", "updated_at", "name", "template_type", "version"}
        if sort not in valid_sort_fields:
            sort = "created_at"

        # Validate order
        order_sql = "DESC" if order.lower() == "desc" else "ASC"

        # Paginate
        offset = (page - 1) * page_size
        params["limit"] = page_size
        params["offset"] = offset

        # Get templates
        query = f"""
            SELECT * FROM arkham_templates
            WHERE {where_sql}
            ORDER BY {sort} {order_sql}
            LIMIT :limit OFFSET :offset
        """

        rows = await self._db.fetch_all(query, params)
        templates = [self._row_to_template(row) for row in rows]

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

        template = await self._load_template(template_id)
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

        # Save to database
        await self._save_template(template)

        # Publish event
        if self._event_bus:
            await self._event_bus.emit("templates.template.updated", {
                "template_id": template.id,
                "name": template.name,
                "version": template.version,
                "updated_by": updated_by,
            }, source="templates-shard")

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

        template = await self._load_template(template_id)
        if not template:
            return False

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            # Delete from database (CASCADE will handle versions)
            await self._db.execute(
                "DELETE FROM arkham_templates WHERE id = :id AND tenant_id = :tenant_id",
                {"id": template_id, "tenant_id": str(tenant_id)}
            )
        else:
            # Delete from database (CASCADE will handle versions)
            await self._db.execute(
                "DELETE FROM arkham_templates WHERE id = :id",
                {"id": template_id}
            )

        # Publish event
        if self._event_bus:
            await self._event_bus.emit("templates.template.deleted", {
                "template_id": template_id,
                "name": template.name,
                "deleted_by": deleted_by,
            }, source="templates-shard")

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
        if not template:
            return None

        template.is_active = True
        template.updated_at = datetime.utcnow()
        template.updated_by = activated_by

        await self._save_template(template)

        if self._event_bus:
            await self._event_bus.emit("templates.template.activated", {
                "template_id": template_id,
                "name": template.name,
                "activated_by": activated_by,
            }, source="templates-shard")

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
        if not template:
            return None

        template.is_active = False
        template.updated_at = datetime.utcnow()
        template.updated_by = deactivated_by

        await self._save_template(template)

        if self._event_bus:
            await self._event_bus.emit("templates.template.deactivated", {
                "template_id": template_id,
                "name": template.name,
                "deactivated_by": deactivated_by,
            }, source="templates-shard")

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
        if not template:
            return None

        template.version += 1
        await self._save_template(template)

        version = await self._create_version_record(
            template,
            created_by=created_by,
            changes=version_data.changes
        )

        if self._event_bus:
            await self._event_bus.emit("templates.version.created", {
                "template_id": template_id,
                "version_id": version.id,
                "version_number": version.version_number,
                "created_by": created_by,
            }, source="templates-shard")

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

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_template_versions
                WHERE template_id = :template_id AND tenant_id = :tenant_id
                ORDER BY version_number DESC
                """,
                {"template_id": template_id, "tenant_id": str(tenant_id)}
            )
        else:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_template_versions
                WHERE template_id = :template_id
                ORDER BY version_number DESC
                """,
                {"template_id": template_id}
            )

        return [self._row_to_version(row) for row in rows]

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT * FROM arkham_template_versions
                WHERE id = :id AND template_id = :template_id AND tenant_id = :tenant_id
                """,
                {"id": version_id, "template_id": template_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                """
                SELECT * FROM arkham_template_versions
                WHERE id = :id AND template_id = :template_id
                """,
                {"id": version_id, "template_id": template_id}
            )

        if not row:
            return None

        return self._row_to_version(row)

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
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

        # Save updated template
        await self._save_template(template)

        # Create new version record
        await self._create_version_record(
            template,
            created_by=restored_by,
            changes=f"Restored from version {version.version_number}"
        )

        if self._event_bus:
            await self._event_bus.emit("templates.version.restored", {
                "template_id": template_id,
                "version_id": version_id,
                "new_version": template.version,
                "restored_by": restored_by,
            }, source="templates-shard")

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
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
            await self._event_bus.emit("templates.rendered", {
                "template_id": template_id,
                "template_name": template.name,
                "output_format": render_request.output_format.value,
            }, source="templates-shard")

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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        template = await self._load_template(template_id)
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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        tenant_filter_and = " AND tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        # Count total and active/inactive
        total_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_templates{tenant_filter}",
            params
        )
        total_templates = total_row["count"] if total_row else 0

        active_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_templates WHERE is_active = TRUE{tenant_filter_and}",
            params
        )
        active_templates = active_row["count"] if active_row else 0
        inactive_templates = total_templates - active_templates

        # Count by type
        type_rows = await self._db.fetch_all(
            f"""
            SELECT template_type, COUNT(*) as count
            FROM arkham_templates{tenant_filter}
            GROUP BY template_type
            """,
            params
        )
        by_type = {row["template_type"]: row["count"] for row in type_rows}

        # Recent templates (last 5)
        recent_rows = await self._db.fetch_all(
            f"""
            SELECT * FROM arkham_templates{tenant_filter}
            ORDER BY created_at DESC
            LIMIT 5
            """,
            params
        )
        recent = [self._row_to_template(row) for row in recent_rows]

        # Total versions
        versions_row = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_template_versions{tenant_filter}",
            params
        )
        total_versions = versions_row["count"] if versions_row else 0

        return TemplateStatistics(
            total_templates=total_templates,
            active_templates=active_templates,
            inactive_templates=inactive_templates,
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
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()

        if active_only:
            if tenant_id:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_templates WHERE is_active = TRUE AND tenant_id = :tenant_id",
                    {"tenant_id": str(tenant_id)}
                )
            else:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_templates WHERE is_active = TRUE",
                    {}
                )
        else:
            if tenant_id:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_templates WHERE tenant_id = :tenant_id",
                    {"tenant_id": str(tenant_id)}
                )
            else:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_templates",
                    {}
                )

        return row["count"] if row else 0

    async def get_template_types(self) -> List[TemplateTypeInfo]:
        """
        Get information about template types.

        Returns:
            List of template type info
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        # Get counts by type
        type_rows = await self._db.fetch_all(
            f"""
            SELECT template_type, COUNT(*) as count
            FROM arkham_templates{tenant_filter}
            GROUP BY template_type
            """,
            params
        )
        type_counts = {row["template_type"]: row["count"] for row in type_rows}

        type_info = []
        for template_type in TemplateType:
            count = type_counts.get(template_type.value, 0)
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
        # Create templates table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                content TEXT NOT NULL,
                placeholders JSONB DEFAULT '[]',
                version INTEGER DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Create template versions table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_template_versions (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                placeholders JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                changes TEXT DEFAULT '',
                FOREIGN KEY (template_id) REFERENCES arkham_templates(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_templates_type
            ON arkham_templates(template_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_templates_active
            ON arkham_templates(is_active)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_template_versions_template_id
            ON arkham_template_versions(template_id)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_templates', 'arkham_template_versions'];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_templates_tenant
            ON arkham_templates(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_template_versions_tenant
            ON arkham_template_versions(tenant_id)
        """)

        logger.info("Templates database schema created")

    async def _save_template(self, template: Template) -> None:
        """Save template to database."""
        if not self._db:
            raise RuntimeError("Database not available")

        # Serialize placeholders to JSON
        placeholders_json = json.dumps([
            {
                "name": p.name,
                "description": p.description,
                "data_type": p.data_type.value if hasattr(p.data_type, 'value') else p.data_type,
                "default_value": p.default_value,
                "required": p.required,
                "example": p.example,
            }
            for p in template.placeholders
        ])

        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()

        # Check if template exists
        existing = await self._db.fetch_one(
            "SELECT id FROM arkham_templates WHERE id = :id",
            {"id": template.id}
        )

        if existing:
            # Update with tenant_id filter
            if tenant_id:
                await self._db.execute(
                    """
                    UPDATE arkham_templates SET
                        name = :name,
                        template_type = :template_type,
                        description = :description,
                        content = :content,
                        placeholders = :placeholders,
                        version = :version,
                        is_active = :is_active,
                        metadata = :metadata,
                        updated_at = :updated_at,
                        updated_by = :updated_by,
                        tenant_id = :tenant_id
                    WHERE id = :id AND tenant_id = :tenant_id
                    """,
                    {
                        "id": template.id,
                        "name": template.name,
                        "template_type": template.template_type.value,
                        "description": template.description,
                        "content": template.content,
                        "placeholders": placeholders_json,
                        "version": template.version,
                        "is_active": template.is_active,
                        "metadata": json.dumps(template.metadata),
                        "updated_at": template.updated_at,
                        "updated_by": template.updated_by,
                        "tenant_id": str(tenant_id),
                    }
                )
            else:
                await self._db.execute(
                    """
                    UPDATE arkham_templates SET
                        name = :name,
                        template_type = :template_type,
                        description = :description,
                        content = :content,
                        placeholders = :placeholders,
                        version = :version,
                        is_active = :is_active,
                        metadata = :metadata,
                        updated_at = :updated_at,
                        updated_by = :updated_by
                    WHERE id = :id
                    """,
                    {
                        "id": template.id,
                        "name": template.name,
                        "template_type": template.template_type.value,
                        "description": template.description,
                        "content": template.content,
                        "placeholders": placeholders_json,
                        "version": template.version,
                        "is_active": template.is_active,
                        "metadata": json.dumps(template.metadata),
                        "updated_at": template.updated_at,
                        "updated_by": template.updated_by,
                    }
                )
        else:
            # Insert with tenant_id
            await self._db.execute(
                """
                INSERT INTO arkham_templates (
                    id, name, template_type, description, content,
                    placeholders, version, is_active, metadata,
                    created_at, updated_at, created_by, updated_by, tenant_id
                ) VALUES (
                    :id, :name, :template_type, :description, :content,
                    :placeholders, :version, :is_active, :metadata,
                    :created_at, :updated_at, :created_by, :updated_by, :tenant_id
                )
                """,
                {
                    "id": template.id,
                    "name": template.name,
                    "template_type": template.template_type.value,
                    "description": template.description,
                    "content": template.content,
                    "placeholders": placeholders_json,
                    "version": template.version,
                    "is_active": template.is_active,
                    "metadata": json.dumps(template.metadata),
                    "created_at": template.created_at,
                    "updated_at": template.updated_at,
                    "created_by": template.created_by,
                    "updated_by": template.updated_by,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                }
            )

    async def _load_template(self, template_id: str) -> Optional[Template]:
        """Load template from database."""
        if not self._db:
            return None

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_templates WHERE id = :id AND tenant_id = :tenant_id",
                {"id": template_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_templates WHERE id = :id",
                {"id": template_id}
            )

        if not row:
            return None

        return self._row_to_template(row)

    def _row_to_template(self, row: Dict[str, Any]) -> Template:
        """Convert database row to Template model."""
        # Parse placeholders
        placeholders_data = _parse_json_field(row.get("placeholders"), [])
        placeholders = [
            TemplatePlaceholder(
                name=p.get("name", ""),
                description=p.get("description", ""),
                data_type=PlaceholderDataType(p.get("data_type", "string")),
                default_value=p.get("default_value"),
                required=p.get("required", False),
                example=p.get("example"),
            )
            for p in placeholders_data
        ]

        # Parse metadata
        metadata = _parse_json_field(row.get("metadata"), {})

        # Parse timestamps
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return Template(
            id=row["id"],
            name=row["name"],
            template_type=TemplateType(row["template_type"]),
            description=row.get("description", ""),
            content=row["content"],
            placeholders=placeholders,
            version=row.get("version", 1),
            is_active=row.get("is_active", True),
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            created_by=row.get("created_by"),
            updated_by=row.get("updated_by"),
        )

    def _row_to_version(self, row: Dict[str, Any]) -> TemplateVersion:
        """Convert database row to TemplateVersion model."""
        # Parse placeholders
        placeholders_data = _parse_json_field(row.get("placeholders"), [])
        placeholders = [
            TemplatePlaceholder(
                name=p.get("name", ""),
                description=p.get("description", ""),
                data_type=PlaceholderDataType(p.get("data_type", "string")),
                default_value=p.get("default_value"),
                required=p.get("required", False),
                example=p.get("example"),
            )
            for p in placeholders_data
        ]

        # Parse timestamp
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif created_at is None:
            created_at = datetime.utcnow()

        return TemplateVersion(
            id=row["id"],
            template_id=row["template_id"],
            version_number=row.get("version_number", 1),
            content=row["content"],
            placeholders=placeholders,
            created_at=created_at,
            created_by=row.get("created_by"),
            changes=row.get("changes", ""),
        )

    async def _save_version(self, version: TemplateVersion) -> None:
        """Save template version to database."""
        if not self._db:
            raise RuntimeError("Database not available")

        # Serialize placeholders to JSON
        placeholders_json = json.dumps([
            {
                "name": p.name,
                "description": p.description,
                "data_type": p.data_type.value if hasattr(p.data_type, 'value') else p.data_type,
                "default_value": p.default_value,
                "required": p.required,
                "example": p.example,
            }
            for p in version.placeholders
        ])

        # Include tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        await self._db.execute(
            """
            INSERT INTO arkham_template_versions (
                id, template_id, version_number, content,
                placeholders, created_at, created_by, changes, tenant_id
            ) VALUES (
                :id, :template_id, :version_number, :content,
                :placeholders, :created_at, :created_by, :changes, :tenant_id
            )
            """,
            {
                "id": version.id,
                "template_id": version.template_id,
                "version_number": version.version_number,
                "content": version.content,
                "placeholders": placeholders_json,
                "created_at": version.created_at,
                "created_by": version.created_by,
                "changes": version.changes,
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

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

        # Save to database
        await self._save_version(version)

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
