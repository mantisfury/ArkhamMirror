"""
Reports Shard - Main Shard Implementation

Analytical report generation for ArkhamFrame - creates summary reports,
entity profiles, timeline reports, and custom analytical outputs.
"""

import io
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from arkham_frame import ArkhamShard

# Base URL for internal API calls
INTERNAL_API_BASE = "http://127.0.0.1:8100"

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
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._llm = None
        self._storage = None
        self._workers = None
        self._initialized = False
        self._reports_dir = None

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._llm = getattr(frame, "llm", None)
        self._storage = getattr(frame, "storage", None)
        self._workers = getattr(frame, "workers", None)

        # Setup reports output directory
        self._reports_dir = os.path.join(tempfile.gettempdir(), "arkham_reports")
        os.makedirs(self._reports_dir, exist_ok=True)

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

        # Queue generation if workers available, otherwise generate inline
        try:
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
                await self._generate_report_inline(report)
        except Exception as e:
            # Worker pool not available, generate inline
            logger.info(f"Workers not available, generating inline: {e}")
            await self._generate_report_inline(report)

        return report

    async def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_reports WHERE id = :report_id",
            {"report_id": report_id},
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
        params: Dict[str, Any] = {}

        if filter:
            if filter.status:
                query += " AND status = :status"
                params["status"] = filter.status.value
            if filter.report_type:
                query += " AND report_type = :report_type"
                params["report_type"] = filter.report_type.value
            if filter.output_format:
                query += " AND output_format = :output_format"
                params["output_format"] = filter.output_format.value
            if filter.search_text:
                query += " AND title LIKE :search_text"
                params["search_text"] = f"%{filter.search_text}%"

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

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
            "DELETE FROM arkham_reports WHERE id = :id",
            {"id": report_id},
        )

        return True

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of reports, optionally filtered by status."""
        if not self._db:
            return 0

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_reports WHERE status = :status",
                {"status": status},
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
            "SELECT * FROM arkham_report_templates WHERE id = :template_id",
            {"template_id": template_id},
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
        params: Dict[str, Any] = {}

        if report_type:
            query += " AND report_type = :report_type"
            params["report_type"] = report_type.value

        query += " ORDER BY name LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

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
            "DELETE FROM arkham_report_schedules WHERE id = :id",
            {"id": schedule_id},
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

            # Generate content by fetching real data
            await self._generate_content(report)

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

    async def _generate_content(self, report: Report) -> None:
        """Generate report content by fetching real data from other shards."""
        # Fetch data based on report type
        data = await self._fetch_report_data(report)

        # Generate output based on format
        file_ext = report.output_format.value
        filename = f"report_{report.id}.{file_ext}"
        file_path = os.path.join(self._reports_dir, filename)

        if report.output_format == ReportFormat.PDF:
            await self._generate_pdf(file_path, report, data)
        elif report.output_format == ReportFormat.HTML:
            await self._generate_html(file_path, report, data)
        elif report.output_format == ReportFormat.MARKDOWN:
            await self._generate_markdown(file_path, report, data)
        elif report.output_format == ReportFormat.JSON:
            await self._generate_json(file_path, report, data)
        else:
            # Fallback to markdown
            await self._generate_markdown(file_path, report, data)

        report.file_path = file_path
        report.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    async def _fetch_report_data(self, report: Report) -> Dict[str, Any]:
        """Fetch data from shards based on report type."""
        data: Dict[str, Any] = {
            "title": report.title,
            "report_type": report.report_type.value,
            "generated_at": datetime.utcnow().isoformat(),
            "parameters": report.parameters,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if report.report_type == ReportType.SUMMARY:
                    data["content"] = await self._fetch_summary_data(client, report.parameters)
                elif report.report_type == ReportType.ENTITY_PROFILE:
                    data["content"] = await self._fetch_entity_profile_data(client, report.parameters)
                elif report.report_type == ReportType.TIMELINE:
                    data["content"] = await self._fetch_timeline_data(client, report.parameters)
                elif report.report_type == ReportType.CONTRADICTION:
                    data["content"] = await self._fetch_contradiction_data(client, report.parameters)
                elif report.report_type == ReportType.ACH_ANALYSIS:
                    data["content"] = await self._fetch_ach_data(client, report.parameters)
                elif report.report_type == ReportType.CUSTOM:
                    data["content"] = await self._fetch_custom_data(client, report.parameters)
                else:
                    data["content"] = {"message": "Unknown report type"}
        except Exception as e:
            logger.error(f"Failed to fetch report data: {e}")
            data["content"] = {"error": str(e)}

        return data

    async def _fetch_summary_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch system summary data from multiple shards."""
        summary = {
            "documents": {"total": 0, "by_status": {}},
            "entities": {"total": 0, "by_type": {}},
            "claims": {"total": 0, "verified": 0, "unverified": 0},
            "contradictions": {"total": 0, "confirmed": 0},
            "anomalies": {"total": 0, "by_severity": {}},
            "timeline_events": {"total": 0},
        }

        # Documents
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/documents/count")
            if resp.status_code == 200:
                summary["documents"]["total"] = resp.json().get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch documents count: {e}")

        # Entities
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/entities/count")
            if resp.status_code == 200:
                summary["entities"]["total"] = resp.json().get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch entities count: {e}")

        # Claims
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/claims/count")
            if resp.status_code == 200:
                summary["claims"]["total"] = resp.json().get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch claims count: {e}")

        # Contradictions
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/contradictions/count")
            if resp.status_code == 200:
                summary["contradictions"]["total"] = resp.json().get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch contradictions count: {e}")

        # Anomalies
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/anomalies/count")
            if resp.status_code == 200:
                summary["anomalies"]["total"] = resp.json().get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch anomalies count: {e}")

        # Timeline
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/timeline/stats")
            if resp.status_code == 200:
                stats = resp.json()
                summary["timeline_events"]["total"] = stats.get("total_events", 0)
        except Exception as e:
            logger.warning(f"Failed to fetch timeline stats: {e}")

        return summary

    async def _fetch_entity_profile_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch entity profile data."""
        entity_id = params.get("entity_id")
        if not entity_id:
            return {"error": "entity_id parameter required"}

        profile = {"entity": None, "relationships": [], "mentions": [], "claims": []}

        # Get entity details
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/entities/{entity_id}")
            if resp.status_code == 200:
                profile["entity"] = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch entity: {e}")
            return {"error": str(e)}

        # Get relationships
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/entities/{entity_id}/relationships")
            if resp.status_code == 200:
                profile["relationships"] = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch relationships: {e}")

        # Get claims mentioning entity
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/claims/", params={"entity_id": entity_id, "limit": 20})
            if resp.status_code == 200:
                profile["claims"] = resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"Failed to fetch claims: {e}")

        return profile

    async def _fetch_timeline_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch timeline report data."""
        timeline = {"events": [], "conflicts": [], "stats": {}}

        fetch_params = {"limit": params.get("limit", 100), "offset": 0}
        if params.get("start_date"):
            fetch_params["start_date"] = params["start_date"]
        if params.get("end_date"):
            fetch_params["end_date"] = params["end_date"]

        # Get events
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/timeline/events", params=fetch_params)
            if resp.status_code == 200:
                data = resp.json()
                timeline["events"] = data.get("events", [])
        except Exception as e:
            logger.warning(f"Failed to fetch timeline events: {e}")

        # Get conflicts
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/timeline/conflicts")
            if resp.status_code == 200:
                timeline["conflicts"] = resp.json().get("conflicts", [])
        except Exception as e:
            logger.warning(f"Failed to fetch timeline conflicts: {e}")

        # Get stats
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/timeline/stats")
            if resp.status_code == 200:
                timeline["stats"] = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch timeline stats: {e}")

        return timeline

    async def _fetch_contradiction_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch contradiction analysis data."""
        contradictions_data = {"contradictions": [], "stats": {}, "chains": []}

        # Get stats
        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/contradictions/stats")
            if resp.status_code == 200:
                contradictions_data["stats"] = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch contradiction stats: {e}")

        # Get contradictions
        try:
            limit = params.get("limit", 50)
            status = params.get("status")
            req_params = {"limit": limit}
            if status:
                req_params["status"] = status

            resp = await client.get(f"{INTERNAL_API_BASE}/api/contradictions/", params=req_params)
            if resp.status_code == 200:
                contradictions_data["contradictions"] = resp.json().get("items", [])
        except Exception as e:
            logger.warning(f"Failed to fetch contradictions: {e}")

        return contradictions_data

    async def _fetch_ach_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch ACH matrix data."""
        matrix_id = params.get("matrix_id")
        if not matrix_id:
            # Get all matrices
            try:
                resp = await client.get(f"{INTERNAL_API_BASE}/api/ach/matrices")
                if resp.status_code == 200:
                    return {"matrices": resp.json().get("matrices", [])}
            except Exception as e:
                logger.warning(f"Failed to fetch ACH matrices: {e}")
                return {"error": str(e)}
            return {"matrices": []}

        # Get specific matrix with full details
        ach_data = {"matrix": None, "hypotheses": [], "evidence": [], "ratings": []}

        try:
            resp = await client.get(f"{INTERNAL_API_BASE}/api/ach/matrix/{matrix_id}")
            if resp.status_code == 200:
                ach_data["matrix"] = resp.json()

            # Get hypotheses
            resp = await client.get(f"{INTERNAL_API_BASE}/api/ach/matrix/{matrix_id}/hypotheses")
            if resp.status_code == 200:
                ach_data["hypotheses"] = resp.json().get("hypotheses", [])

            # Get evidence
            resp = await client.get(f"{INTERNAL_API_BASE}/api/ach/matrix/{matrix_id}/evidence")
            if resp.status_code == 200:
                ach_data["evidence"] = resp.json().get("evidence", [])

            # Get ratings
            resp = await client.get(f"{INTERNAL_API_BASE}/api/ach/matrix/{matrix_id}/ratings")
            if resp.status_code == 200:
                ach_data["ratings"] = resp.json().get("ratings", [])

        except Exception as e:
            logger.warning(f"Failed to fetch ACH matrix {matrix_id}: {e}")
            ach_data["error"] = str(e)

        return ach_data

    async def _fetch_custom_data(self, client: httpx.AsyncClient, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch custom data based on parameters."""
        custom_data = {}

        # Check if this is from a shared template with rendered content
        if params.get("from_shared_template") and params.get("rendered_content"):
            custom_data["rendered_content"] = params["rendered_content"]
            custom_data["template_name"] = params.get("shared_template_name", "")
            # Also fetch summary data for context
            summary = await self._fetch_summary_data(client, params)
            custom_data["system_summary"] = summary
            return custom_data

        # Allow custom endpoints to be specified
        endpoints = params.get("endpoints", [])
        if endpoints:
            for endpoint_config in endpoints:
                endpoint = endpoint_config.get("url", "")
                key = endpoint_config.get("key", endpoint)
                try:
                    resp = await client.get(f"{INTERNAL_API_BASE}{endpoint}")
                    if resp.status_code == 200:
                        custom_data[key] = resp.json()
                except Exception as e:
                    logger.warning(f"Failed to fetch custom endpoint {endpoint}: {e}")
                    custom_data[key] = {"error": str(e)}
        else:
            # Default: fetch summary data if no endpoints specified
            custom_data = await self._fetch_summary_data(client, params)

        return custom_data

    # === Format Generators ===

    async def _generate_pdf(self, file_path: str, report: Report, data: Dict[str, Any]) -> None:
        """Generate PDF report using reportlab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                PageBreak,
            )
        except ImportError:
            logger.error("reportlab not installed - falling back to text")
            await self._generate_markdown(file_path.replace(".pdf", ".md"), report, data)
            return

        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=20,
            spaceAfter=20,
            textColor=colors.darkblue,
        )
        story.append(Paragraph(report.title, title_style))
        story.append(Spacer(1, 12))

        # Report metadata
        info_style = styles["Normal"]
        story.append(Paragraph(f"<b>Report Type:</b> {report.report_type.value.replace('_', ' ').title()}", info_style))
        story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", info_style))
        story.append(Paragraph(f"<b>Report ID:</b> {report.id[:8]}...", info_style))
        story.append(Spacer(1, 20))

        # Content based on report type
        content = data.get("content", {})

        if report.report_type == ReportType.SUMMARY:
            self._add_summary_to_pdf(story, content, styles)
        elif report.report_type == ReportType.ENTITY_PROFILE:
            self._add_entity_profile_to_pdf(story, content, styles)
        elif report.report_type == ReportType.TIMELINE:
            self._add_timeline_to_pdf(story, content, styles)
        elif report.report_type == ReportType.CONTRADICTION:
            self._add_contradictions_to_pdf(story, content, styles)
        elif report.report_type == ReportType.ACH_ANALYSIS:
            self._add_ach_to_pdf(story, content, styles)
        else:
            self._add_generic_to_pdf(story, content, styles)

        doc.build(story)

    def _add_summary_to_pdf(self, story, content, styles):
        """Add summary content to PDF."""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        story.append(Paragraph("System Summary", heading_style))
        story.append(Spacer(1, 10))

        # Documents
        docs = content.get("documents", {})
        story.append(Paragraph(f"<b>Documents:</b> {docs.get('total', 0)} total", normal_style))

        # Entities
        entities = content.get("entities", {})
        story.append(Paragraph(f"<b>Entities:</b> {entities.get('total', 0)} total", normal_style))
        by_type = entities.get("by_type", {})
        if by_type:
            for etype, count in list(by_type.items())[:5]:
                story.append(Paragraph(f"  - {etype}: {count}", normal_style))

        # Claims
        claims = content.get("claims", {})
        story.append(Paragraph(
            f"<b>Claims:</b> {claims.get('total', 0)} total "
            f"({claims.get('verified', 0)} verified)",
            normal_style
        ))

        # Contradictions
        contradictions = content.get("contradictions", {})
        story.append(Paragraph(
            f"<b>Contradictions:</b> {contradictions.get('total', 0)} total "
            f"({contradictions.get('confirmed', 0)} confirmed)",
            normal_style
        ))

        # Anomalies
        anomalies = content.get("anomalies", {})
        story.append(Paragraph(f"<b>Anomalies:</b> {anomalies.get('total', 0)} total", normal_style))

        # Timeline
        timeline = content.get("timeline_events", {})
        story.append(Paragraph(f"<b>Timeline Events:</b> {timeline.get('total', 0)}", normal_style))

        story.append(Spacer(1, 20))

    def _add_entity_profile_to_pdf(self, story, content, styles):
        """Add entity profile to PDF."""
        from reportlab.platypus import Paragraph, Spacer

        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        entity = content.get("entity", {})
        if not entity:
            story.append(Paragraph("Entity not found", normal_style))
            return

        story.append(Paragraph(f"Entity Profile: {entity.get('name', 'Unknown')}", heading_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph(f"<b>Type:</b> {entity.get('entity_type', 'N/A')}", normal_style))
        story.append(Paragraph(f"<b>ID:</b> {entity.get('id', 'N/A')}", normal_style))

        # Relationships
        relationships = content.get("relationships", [])
        if relationships:
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>Relationships ({len(relationships)}):</b>", normal_style))
            for rel in relationships[:10]:
                story.append(Paragraph(
                    f"  - {rel.get('relationship_type', 'related to')} {rel.get('target_name', 'Unknown')}",
                    normal_style
                ))

        # Claims
        claims = content.get("claims", [])
        if claims:
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>Related Claims ({len(claims)}):</b>", normal_style))
            for claim in claims[:5]:
                text = claim.get("text", "")[:100]
                story.append(Paragraph(f"  - {text}...", normal_style))

        story.append(Spacer(1, 20))

    def _add_timeline_to_pdf(self, story, content, styles):
        """Add timeline content to PDF."""
        from reportlab.platypus import Paragraph, Spacer

        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        story.append(Paragraph("Timeline Report", heading_style))
        story.append(Spacer(1, 10))

        stats = content.get("stats", {})
        story.append(Paragraph(f"<b>Total Events:</b> {stats.get('total_events', 0)}", normal_style))
        story.append(Spacer(1, 10))

        events = content.get("events", [])
        if events:
            story.append(Paragraph("<b>Events:</b>", normal_style))
            for event in events[:50]:
                date = event.get("date_start", "Unknown date")
                text = event.get("text", "")[:150]
                story.append(Paragraph(f"<b>{date}:</b> {text}", normal_style))
                story.append(Spacer(1, 4))

        conflicts = content.get("conflicts", [])
        if conflicts:
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>Temporal Conflicts ({len(conflicts)}):</b>", normal_style))
            for conflict in conflicts[:10]:
                story.append(Paragraph(f"  - {conflict.get('description', 'Conflict')}", normal_style))

        story.append(Spacer(1, 20))

    def _add_contradictions_to_pdf(self, story, content, styles):
        """Add contradictions to PDF."""
        from reportlab.platypus import Paragraph, Spacer

        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        story.append(Paragraph("Contradiction Analysis", heading_style))
        story.append(Spacer(1, 10))

        stats = content.get("stats", {})
        story.append(Paragraph(f"<b>Total Contradictions:</b> {stats.get('total', 0)}", normal_style))

        contradictions = content.get("contradictions", [])
        if contradictions:
            story.append(Spacer(1, 10))
            for i, c in enumerate(contradictions[:20]):
                story.append(Paragraph(f"<b>Contradiction {i+1}:</b>", normal_style))
                story.append(Paragraph(f"  Status: {c.get('status', 'N/A')}", normal_style))
                story.append(Paragraph(f"  Severity: {c.get('severity', 'N/A')}", normal_style))
                story.append(Paragraph(f"  Type: {c.get('contradiction_type', 'N/A')}", normal_style))
                story.append(Spacer(1, 6))

        story.append(Spacer(1, 20))

    def _add_ach_to_pdf(self, story, content, styles):
        """Add ACH matrix content to PDF."""
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        # Check if single matrix or list
        if "matrix" in content:
            matrix = content.get("matrix", {})
            story.append(Paragraph(f"ACH Matrix: {matrix.get('title', 'Untitled')}", heading_style))
            story.append(Spacer(1, 10))

            story.append(Paragraph(f"<b>Description:</b> {matrix.get('description', 'N/A')}", normal_style))
            story.append(Paragraph(f"<b>Status:</b> {matrix.get('status', 'N/A')}", normal_style))

            hypotheses = content.get("hypotheses", [])
            if hypotheses:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<b>Hypotheses ({len(hypotheses)}):</b>", normal_style))
                for h in hypotheses:
                    story.append(Paragraph(f"  - {h.get('title', 'Untitled')}", normal_style))

            evidence = content.get("evidence", [])
            if evidence:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<b>Evidence Items ({len(evidence)}):</b>", normal_style))
                for e in evidence[:10]:
                    story.append(Paragraph(f"  - {e.get('description', 'No description')[:100]}", normal_style))

        else:
            matrices = content.get("matrices", [])
            story.append(Paragraph(f"ACH Matrices ({len(matrices)})", heading_style))
            story.append(Spacer(1, 10))

            for m in matrices:
                story.append(Paragraph(f"<b>{m.get('title', 'Untitled')}</b>", normal_style))
                story.append(Paragraph(f"  Status: {m.get('status', 'N/A')}", normal_style))
                story.append(Spacer(1, 6))

        story.append(Spacer(1, 20))

    def _add_generic_to_pdf(self, story, content, styles):
        """Add generic content to PDF."""
        from reportlab.platypus import Paragraph, Spacer

        normal_style = styles["Normal"]

        story.append(Paragraph("<b>Report Content:</b>", normal_style))
        story.append(Spacer(1, 10))

        # Render content as key-value pairs
        def render_dict(d, indent=0):
            for key, value in d.items():
                prefix = "&nbsp;" * (indent * 4)
                if isinstance(value, dict):
                    story.append(Paragraph(f"{prefix}<b>{key}:</b>", normal_style))
                    render_dict(value, indent + 1)
                elif isinstance(value, list):
                    story.append(Paragraph(f"{prefix}<b>{key}:</b> [{len(value)} items]", normal_style))
                else:
                    story.append(Paragraph(f"{prefix}<b>{key}:</b> {value}", normal_style))

        if isinstance(content, dict):
            render_dict(content)
        else:
            story.append(Paragraph(str(content), normal_style))

        story.append(Spacer(1, 20))

    async def _generate_html(self, file_path: str, report: Report, data: Dict[str, Any]) -> None:
        """Generate HTML report."""
        content = data.get("content", {})

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{report.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
        .stat {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
        .stat-label {{ font-size: 12px; color: #7f8c8d; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <div class="meta">
        <p><strong>Report Type:</strong> {report.report_type.value.replace('_', ' ').title()}</p>
        <p><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Report ID:</strong> {report.id}</p>
    </div>
"""

        # Add content based on report type
        if report.report_type == ReportType.SUMMARY:
            html += self._generate_summary_html(content)
        elif report.report_type == ReportType.ENTITY_PROFILE:
            html += self._generate_entity_profile_html(content)
        elif report.report_type == ReportType.TIMELINE:
            html += self._generate_timeline_html(content)
        elif report.report_type == ReportType.CUSTOM:
            html += self._generate_custom_html(content)
        else:
            html += f"<div class='section'><pre>{json.dumps(content, indent=2, default=str)}</pre></div>"

        html += """
</body>
</html>"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _generate_summary_html(self, content: Dict[str, Any]) -> str:
        """Generate summary HTML content."""
        docs = content.get("documents", {})
        entities = content.get("entities", {})
        claims = content.get("claims", {})
        contradictions = content.get("contradictions", {})
        anomalies = content.get("anomalies", {})
        timeline = content.get("timeline_events", {})

        return f"""
    <h2>System Overview</h2>
    <div class="section">
        <div class="stat"><div class="stat-value">{docs.get('total', 0)}</div><div class="stat-label">Documents</div></div>
        <div class="stat"><div class="stat-value">{entities.get('total', 0)}</div><div class="stat-label">Entities</div></div>
        <div class="stat"><div class="stat-value">{claims.get('total', 0)}</div><div class="stat-label">Claims</div></div>
        <div class="stat"><div class="stat-value">{contradictions.get('total', 0)}</div><div class="stat-label">Contradictions</div></div>
        <div class="stat"><div class="stat-value">{anomalies.get('total', 0)}</div><div class="stat-label">Anomalies</div></div>
        <div class="stat"><div class="stat-value">{timeline.get('total', 0)}</div><div class="stat-label">Timeline Events</div></div>
    </div>
"""

    def _generate_entity_profile_html(self, content: Dict[str, Any]) -> str:
        """Generate entity profile HTML content."""
        entity = content.get("entity", {})
        relationships = content.get("relationships", [])
        claims = content.get("claims", [])

        html = f"""
    <h2>Entity: {entity.get('name', 'Unknown')}</h2>
    <div class="section">
        <p><strong>Type:</strong> {entity.get('entity_type', 'N/A')}</p>
        <p><strong>ID:</strong> {entity.get('id', 'N/A')}</p>
    </div>
"""

        if relationships:
            html += "<h2>Relationships</h2><div class='section'><ul>"
            for rel in relationships[:20]:
                html += f"<li>{rel.get('relationship_type', 'related to')} {rel.get('target_name', 'Unknown')}</li>"
            html += "</ul></div>"

        if claims:
            html += "<h2>Related Claims</h2><div class='section'><ul>"
            for claim in claims[:10]:
                html += f"<li>{claim.get('text', '')[:150]}...</li>"
            html += "</ul></div>"

        return html

    def _generate_timeline_html(self, content: Dict[str, Any]) -> str:
        """Generate timeline HTML content."""
        events = content.get("events", [])
        stats = content.get("stats", {})

        html = f"""
    <h2>Timeline Summary</h2>
    <div class="section">
        <p><strong>Total Events:</strong> {stats.get('total_events', 0)}</p>
    </div>
    <h2>Events</h2>
    <table>
        <tr><th>Date</th><th>Event</th><th>Type</th></tr>
"""
        for event in events[:100]:
            html += f"<tr><td>{event.get('date_start', 'N/A')}</td><td>{event.get('text', '')[:200]}</td><td>{event.get('event_type', 'N/A')}</td></tr>"

        html += "</table>"
        return html

    def _generate_custom_html(self, content: Dict[str, Any]) -> str:
        """Generate custom report HTML content."""
        html = ""
        
        # Check if this is from a shared template
        if content.get("rendered_content"):
            template_name = content.get("template_name", "Custom Template")
            rendered = content["rendered_content"]
            
            html += f"""
    <h2>Report Content</h2>
    <div class="section">
        <p><em>Generated from template: {template_name}</em></p>
    </div>
    <div class="section">
        {rendered}
    </div>
"""
            
            # Add system summary if available
            if content.get("system_summary"):
                html += "<h2>System Context</h2>"
                html += self._generate_summary_html(content["system_summary"])
        else:
            # Fallback to summary-style output
            html += self._generate_summary_html(content)
        
        return html

    async def _generate_markdown(self, file_path: str, report: Report, data: Dict[str, Any]) -> None:
        """Generate Markdown report."""
        content = data.get("content", {})

        md = f"""# {report.title}

**Report Type:** {report.report_type.value.replace('_', ' ').title()}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Report ID:** {report.id}

---

"""

        # Add content based on report type
        if report.report_type == ReportType.SUMMARY:
            docs = content.get("documents", {})
            entities = content.get("entities", {})
            claims = content.get("claims", {})
            md += f"""## System Summary

| Metric | Count |
|--------|-------|
| Documents | {docs.get('total', 0)} |
| Entities | {entities.get('total', 0)} |
| Claims | {claims.get('total', 0)} |
| Contradictions | {content.get('contradictions', {}).get('total', 0)} |
| Anomalies | {content.get('anomalies', {}).get('total', 0)} |
| Timeline Events | {content.get('timeline_events', {}).get('total', 0)} |

"""
        else:
            md += f"## Content\n\n```json\n{json.dumps(content, indent=2, default=str)}\n```\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md)

    async def _generate_json(self, file_path: str, report: Report, data: Dict[str, Any]) -> None:
        """Generate JSON report."""
        output = {
            "report_info": {
                "id": report.id,
                "title": report.title,
                "report_type": report.report_type.value,
                "generated_at": datetime.utcnow().isoformat(),
                "parameters": report.parameters,
            },
            "content": data.get("content", {}),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

    async def _save_report(self, report: Report, update: bool = False) -> None:
        """Save a report to the database."""
        if not self._db:
            return

        import json
        params = {
            "id": report.id,
            "report_type": report.report_type.value,
            "title": report.title,
            "status": report.status.value,
            "created_at": report.created_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "parameters": json.dumps(report.parameters),
            "output_format": report.output_format.value,
            "file_path": report.file_path,
            "file_size": report.file_size,
            "error": report.error,
            "metadata": json.dumps(report.metadata),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_reports SET
                    report_type=:report_type, title=:title, status=:status, created_at=:created_at,
                    completed_at=:completed_at, parameters=:parameters, output_format=:output_format,
                    file_path=:file_path, file_size=:file_size, error=:error, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_reports (
                    id, report_type, title, status, created_at,
                    completed_at, parameters, output_format,
                    file_path, file_size, error, metadata
                ) VALUES (:id, :report_type, :title, :status, :created_at,
                    :completed_at, :parameters, :output_format,
                    :file_path, :file_size, :error, :metadata)
            """, params)

    async def _save_template(self, template: ReportTemplate, update: bool = False) -> None:
        """Save a template to the database."""
        if not self._db:
            return

        import json
        params = {
            "id": template.id,
            "name": template.name,
            "report_type": template.report_type.value,
            "description": template.description,
            "parameters_schema": json.dumps(template.parameters_schema),
            "default_format": template.default_format.value,
            "template_content": template.template_content,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat(),
            "metadata": json.dumps(template.metadata),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_report_templates SET
                    name=:name, report_type=:report_type, description=:description,
                    parameters_schema=:parameters_schema, default_format=:default_format, template_content=:template_content,
                    created_at=:created_at, updated_at=:updated_at, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_report_templates (
                    id, name, report_type, description,
                    parameters_schema, default_format, template_content,
                    created_at, updated_at, metadata
                ) VALUES (:id, :name, :report_type, :description,
                    :parameters_schema, :default_format, :template_content,
                    :created_at, :updated_at, :metadata)
            """, params)

    async def _save_schedule(self, schedule: ReportSchedule, update: bool = False) -> None:
        """Save a schedule to the database."""
        if not self._db:
            return

        import json
        params = {
            "id": schedule.id,
            "template_id": schedule.template_id,
            "cron_expression": schedule.cron_expression,
            "enabled": 1 if schedule.enabled else 0,
            "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
            "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
            "parameters": json.dumps(schedule.parameters),
            "output_format": schedule.output_format.value,
            "retention_days": schedule.retention_days,
            "email_recipients": json.dumps(schedule.email_recipients),
            "metadata": json.dumps(schedule.metadata),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_report_schedules SET
                    template_id=:template_id, cron_expression=:cron_expression, enabled=:enabled,
                    last_run=:last_run, next_run=:next_run, parameters=:parameters,
                    output_format=:output_format, retention_days=:retention_days, email_recipients=:email_recipients, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_report_schedules (
                    id, template_id, cron_expression, enabled,
                    last_run, next_run, parameters,
                    output_format, retention_days, email_recipients, metadata
                ) VALUES (:id, :template_id, :cron_expression, :enabled,
                    :last_run, :next_run, :parameters,
                    :output_format, :retention_days, :email_recipients, :metadata)
            """, params)

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
