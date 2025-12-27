"""
Reports Shard - Main Shard Implementation

Analytical report generation for ArkhamFrame - creates summary reports,
entity profiles, timeline reports, and custom analytical outputs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    GeneratedSection,
    Report,
    ReportFilter,
    ReportFormat,
    ReportGenerationResult,
    ReportSchedule,
    ReportStatistics,
    ReportStatus,
    ReportTemplate,
    ReportType,
)

logger = logging.getLogger(__name__)


class ReportsShard(ArkhamShard):
    """
    Reports Shard - Generates analytical reports from investigation data.

    This shard provides:
    - Report generation in multiple formats (HTML, PDF, Markdown, JSON)
    - Reusable report templates
    - Scheduled report generation
    - Summary, entity, timeline, and custom reports
    - Report statistics and management
    """

    name = "reports"
    version = "0.1.0"
    description = "Analytical report generation - summary reports, entity profiles, timeline reports"

    def __init__(self):
        self.frame = None
        self._db = None
        self._events = None
        self._llm = None
        self._storage = None
        self._workers = None
        self._initialized = False

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._llm = getattr(frame, "llm", None)
        self._storage = getattr(frame, "storage", None)
        self._workers = getattr(frame, "workers", None)

        # Create database schema
        await self._create_schema()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.reports_shard = self

        self._initialized = True
        logger.info(f"ReportsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        self._initialized = False
        logger.info("ReportsShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for reports shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        # Reports table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_reports (
                id TEXT PRIMARY KEY,
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',

                created_at TEXT,
                completed_at TEXT,

                parameters TEXT DEFAULT '{}',
                output_format TEXT,
                file_path TEXT,
                file_size INTEGER,

                error TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Templates table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_report_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                description TEXT,

                parameters_schema TEXT DEFAULT '{}',
                default_format TEXT,
                template_content TEXT,

                created_at TEXT,
                updated_at TEXT,
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Schedules table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_report_schedules (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,

                last_run TEXT,
                next_run TEXT,

                parameters TEXT DEFAULT '{}',
                output_format TEXT,
                retention_days INTEGER DEFAULT 30,
                email_recipients TEXT DEFAULT '[]',

                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (template_id) REFERENCES arkham_report_templates(id)
            )
        """)

        # Create indexes for common queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_status ON arkham_reports(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_type ON arkham_reports(report_type)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_created ON arkham_reports(created_at)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_template ON arkham_report_schedules(template_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON arkham_report_schedules(enabled)
        """)

        logger.debug("Reports schema created/verified")

    # === Public API Methods - Reports ===

    async def generate_report(
        self,
        report_type: ReportType,
        title: str,
        parameters: Optional[Dict[str, Any]] = None,
        output_format: ReportFormat = ReportFormat.HTML,
        template_id: Optional[str] = None,
    ) -> Report:
        """Generate a new report."""
        report_id = str(uuid4())
        now = datetime.utcnow()

        report = Report(
            id=report_id,
            report_type=report_type,
            title=title,
            status=ReportStatus.PENDING,
            created_at=now,
            parameters=parameters or {},
            output_format=output_format,
        )

        await self._save_report(report)

        # Emit event
        if self._events:
            await self._events.emit(
                "reports.report.scheduled",
                {
                    "report_id": report_id,
                    "report_type": report_type.value,
                    "title": title,
                    "output_format": output_format.value,
                },
                source=self.name,
            )

        # Queue generation if workers available
        if self._workers:
            await self._workers.enqueue(
                pool="reports",
                job_id=f"report-gen-{report_id}",
                payload={
                    "report_id": report_id,
                    "action": "generate_report",
                },
            )
        else:
            # Generate inline (stub implementation)
            await self._generate_report_inline(report)

        return report

    async def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_reports WHERE id = ?",
            [report_id],
        )
        return self._row_to_report(row) if row else None

    async def list_reports(
        self,
        filter: Optional[ReportFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Report]:
        """List reports with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_reports WHERE 1=1"
        params = []

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.report_type:
                query += " AND report_type = ?"
                params.append(filter.report_type.value)
            if filter.output_format:
                query += " AND output_format = ?"
                params.append(filter.output_format.value)
            if filter.search_text:
                query += " AND title LIKE ?"
                params.append(f"%{filter.search_text}%")

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_report(row) for row in rows]

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        if not self._db:
            return False

        # Get report to delete file
        report = await self.get_report(report_id)
        if not report:
            return False

        # Delete file if exists
        if report.file_path and self._storage:
            try:
                await self._storage.delete(report.file_path)
            except Exception as e:
                logger.warning(f"Failed to delete report file: {e}")

        # Delete from database
        await self._db.execute(
            "DELETE FROM arkham_reports WHERE id = ?",
            [report_id],
        )

        return True

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of reports, optionally filtered by status."""
        if not self._db:
            return 0

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_reports WHERE status = ?",
                [status],
            )
        else:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_reports"
            )

        return result["count"] if result else 0

    # === Public API Methods - Templates ===

    async def create_template(
        self,
        name: str,
        report_type: ReportType,
        description: str,
        parameters_schema: Optional[Dict[str, Any]] = None,
        default_format: ReportFormat = ReportFormat.HTML,
        template_content: str = "",
    ) -> ReportTemplate:
        """Create a new report template."""
        template_id = str(uuid4())
        now = datetime.utcnow()

        template = ReportTemplate(
            id=template_id,
            name=name,
            report_type=report_type,
            description=description,
            parameters_schema=parameters_schema or {},
            default_format=default_format,
            template_content=template_content,
            created_at=now,
            updated_at=now,
        )

        await self._save_template(template)

        # Emit event
        if self._events:
            await self._events.emit(
                "reports.template.created",
                {
                    "template_id": template_id,
                    "name": name,
                    "report_type": report_type.value,
                },
                source=self.name,
            )

        return template

    async def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """Get a template by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_report_templates WHERE id = ?",
            [template_id],
        )
        return self._row_to_template(row) if row else None

    async def list_templates(
        self,
        report_type: Optional[ReportType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReportTemplate]:
        """List report templates."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_report_templates WHERE 1=1"
        params = []

        if report_type:
            query += " AND report_type = ?"
            params.append(report_type.value)

        query += " ORDER BY name LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_template(row) for row in rows]

    # === Public API Methods - Schedules ===

    async def create_schedule(
        self,
        template_id: str,
        cron_expression: str,
        parameters: Optional[Dict[str, Any]] = None,
        output_format: ReportFormat = ReportFormat.HTML,
        retention_days: int = 30,
    ) -> ReportSchedule:
        """Create a new report schedule."""
        schedule_id = str(uuid4())

        schedule = ReportSchedule(
            id=schedule_id,
            template_id=template_id,
            cron_expression=cron_expression,
            enabled=True,
            parameters=parameters or {},
            output_format=output_format,
            retention_days=retention_days,
        )

        await self._save_schedule(schedule)

        # Emit event
        if self._events:
            await self._events.emit(
                "reports.schedule.created",
                {
                    "schedule_id": schedule_id,
                    "template_id": template_id,
                    "cron_expression": cron_expression,
                },
                source=self.name,
            )

        return schedule

    async def list_schedules(
        self,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReportSchedule]:
        """List report schedules."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_report_schedules WHERE 1=1"
        params = []

        if enabled_only:
            query += " AND enabled = 1"

        query += " ORDER BY next_run LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_schedule(row) for row in rows]

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a report schedule."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_report_schedules WHERE id = ?",
            [schedule_id],
        )
        return True

    # === Statistics ===

    async def get_statistics(self) -> ReportStatistics:
        """Get statistics about reports in the system."""
        if not self._db:
            return ReportStatistics()

        # Total reports
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_reports"
        )
        total_reports = total["count"] if total else 0

        # By status
        status_rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) as count FROM arkham_reports GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By type
        type_rows = await self._db.fetch_all(
            "SELECT report_type, COUNT(*) as count FROM arkham_reports GROUP BY report_type"
        )
        by_type = {row["report_type"]: row["count"] for row in type_rows}

        # By format
        format_rows = await self._db.fetch_all(
            "SELECT output_format, COUNT(*) as count FROM arkham_reports GROUP BY output_format"
        )
        by_format = {row["output_format"]: row["count"] for row in format_rows}

        # Templates and schedules
        templates = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_report_templates"
        )
        schedules = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_report_schedules"
        )
        active_schedules = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_report_schedules WHERE enabled = 1"
        )

        # File sizes
        file_size = await self._db.fetch_one(
            "SELECT SUM(file_size) as total FROM arkham_reports WHERE file_size IS NOT NULL"
        )

        return ReportStatistics(
            total_reports=total_reports,
            by_status=by_status,
            by_type=by_type,
            by_format=by_format,
            total_templates=templates["count"] if templates else 0,
            total_schedules=schedules["count"] if schedules else 0,
            active_schedules=active_schedules["count"] if active_schedules else 0,
            total_file_size_bytes=file_size["total"] if file_size and file_size["total"] else 0,
        )

    # === Private Helper Methods ===

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored, e.g., "SHATTERED")
        - String that needs parsing (raw JSON, e.g., '{"key": "value"}')
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                import json
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                # (e.g., JSONB stored "SHATTERED" comes back as 'SHATTERED')
                return value
        return default

    async def _generate_report_inline(self, report: Report) -> ReportGenerationResult:
        """Generate report inline (stub implementation)."""
        import time
        start_time = time.time()

        try:
            # Update status to generating
            report.status = ReportStatus.GENERATING
            await self._save_report(report, update=True)

            # Stub: simulate generation
            await self._stub_generate_content(report)

            # Update status to completed
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.utcnow()
            await self._save_report(report, update=True)

            processing_time = (time.time() - start_time) * 1000

            # Emit success event
            if self._events:
                await self._events.emit(
                    "reports.report.generated",
                    {
                        "report_id": report.id,
                        "report_type": report.report_type.value,
                        "processing_time_ms": processing_time,
                    },
                    source=self.name,
                )

            return ReportGenerationResult(
                report_id=report.id,
                success=True,
                file_path=report.file_path,
                file_size=report.file_size,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            await self._save_report(report, update=True)

            # Emit failure event
            if self._events:
                await self._events.emit(
                    "reports.report.failed",
                    {
                        "report_id": report.id,
                        "error": str(e),
                    },
                    source=self.name,
                )

            return ReportGenerationResult(
                report_id=report.id,
                success=False,
                errors=[str(e)],
            )

    async def _stub_generate_content(self, report: Report) -> None:
        """Stub implementation of report content generation."""
        # Stub: create placeholder content
        content = f"# {report.title}\n\nGenerated: {datetime.utcnow().isoformat()}\n\nReport type: {report.report_type.value}\n\n(Report content would be generated here based on parameters)"

        # Stub: save to storage if available
        if self._storage:
            file_name = f"report_{report.id}.{report.output_format.value}"
            file_path = await self._storage.save(file_name, content.encode('utf-8'))
            report.file_path = file_path
            report.file_size = len(content.encode('utf-8'))
        else:
            # No storage, just set stub path
            report.file_path = f"/tmp/report_{report.id}.{report.output_format.value}"
            report.file_size = len(content.encode('utf-8'))

    async def _save_report(self, report: Report, update: bool = False) -> None:
        """Save a report to the database."""
        if not self._db:
            return

        import json
        data = (
            report.id,
            report.report_type.value,
            report.title,
            report.status.value,
            report.created_at.isoformat(),
            report.completed_at.isoformat() if report.completed_at else None,
            json.dumps(report.parameters),
            report.output_format.value,
            report.file_path,
            report.file_size,
            report.error,
            json.dumps(report.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_reports SET
                    report_type=?, title=?, status=?, created_at=?,
                    completed_at=?, parameters=?, output_format=?,
                    file_path=?, file_size=?, error=?, metadata=?
                WHERE id=?
            """, data[1:] + (report.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_reports (
                    id, report_type, title, status, created_at,
                    completed_at, parameters, output_format,
                    file_path, file_size, error, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_template(self, template: ReportTemplate, update: bool = False) -> None:
        """Save a template to the database."""
        if not self._db:
            return

        import json
        data = (
            template.id,
            template.name,
            template.report_type.value,
            template.description,
            json.dumps(template.parameters_schema),
            template.default_format.value,
            template.template_content,
            template.created_at.isoformat(),
            template.updated_at.isoformat(),
            json.dumps(template.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_report_templates SET
                    name=?, report_type=?, description=?,
                    parameters_schema=?, default_format=?, template_content=?,
                    created_at=?, updated_at=?, metadata=?
                WHERE id=?
            """, data[1:] + (template.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_report_templates (
                    id, name, report_type, description,
                    parameters_schema, default_format, template_content,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_schedule(self, schedule: ReportSchedule, update: bool = False) -> None:
        """Save a schedule to the database."""
        if not self._db:
            return

        import json
        data = (
            schedule.id,
            schedule.template_id,
            schedule.cron_expression,
            1 if schedule.enabled else 0,
            schedule.last_run.isoformat() if schedule.last_run else None,
            schedule.next_run.isoformat() if schedule.next_run else None,
            json.dumps(schedule.parameters),
            schedule.output_format.value,
            schedule.retention_days,
            json.dumps(schedule.email_recipients),
            json.dumps(schedule.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_report_schedules SET
                    template_id=?, cron_expression=?, enabled=?,
                    last_run=?, next_run=?, parameters=?,
                    output_format=?, retention_days=?, email_recipients=?, metadata=?
                WHERE id=?
            """, data[1:] + (schedule.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_report_schedules (
                    id, template_id, cron_expression, enabled,
                    last_run, next_run, parameters,
                    output_format, retention_days, email_recipients, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    def _row_to_report(self, row: Dict[str, Any]) -> Report:
        """Convert database row to Report object."""
        return Report(
            id=row["id"],
            report_type=ReportType(row["report_type"]),
            title=row["title"],
            status=ReportStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            parameters=self._parse_jsonb(row.get("parameters"), {}),
            output_format=ReportFormat(row["output_format"]) if row["output_format"] else ReportFormat.HTML,
            file_path=row["file_path"],
            file_size=row["file_size"],
            error=row["error"],
            metadata=self._parse_jsonb(row.get("metadata"), {}),
        )

    def _row_to_template(self, row: Dict[str, Any]) -> ReportTemplate:
        """Convert database row to ReportTemplate object."""
        return ReportTemplate(
            id=row["id"],
            name=row["name"],
            report_type=ReportType(row["report_type"]),
            description=row["description"] or "",
            parameters_schema=self._parse_jsonb(row.get("parameters_schema"), {}),
            default_format=ReportFormat(row["default_format"]) if row["default_format"] else ReportFormat.HTML,
            template_content=row["template_content"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            metadata=self._parse_jsonb(row.get("metadata"), {}),
        )

    def _row_to_schedule(self, row: Dict[str, Any]) -> ReportSchedule:
        """Convert database row to ReportSchedule object."""
        return ReportSchedule(
            id=row["id"],
            template_id=row["template_id"],
            cron_expression=row["cron_expression"],
            enabled=bool(row["enabled"]),
            last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
            next_run=datetime.fromisoformat(row["next_run"]) if row["next_run"] else None,
            parameters=self._parse_jsonb(row.get("parameters"), {}),
            output_format=ReportFormat(row["output_format"]) if row["output_format"] else ReportFormat.HTML,
            retention_days=row["retention_days"] or 30,
            email_recipients=self._parse_jsonb(row.get("email_recipients"), []),
            metadata=self._parse_jsonb(row.get("metadata"), {}),
        )
