"""
Export Shard - Main Shard Implementation

Data export for ArkhamFrame - export documents, entities, claims, and
analysis results in various formats.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    ExportFilter,
    ExportFormat,
    ExportJob,
    ExportOptions,
    ExportResult,
    ExportStatistics,
    ExportStatus,
    ExportTarget,
    FormatInfo,
    TargetInfo,
)

logger = logging.getLogger(__name__)


class ExportShard(ArkhamShard):
    """
    Export Shard - Export data in various formats.

    This shard provides:
    - Multi-format export (JSON, CSV, PDF, DOCX)
    - Export job management with status tracking
    - Multiple export targets (documents, entities, claims, etc.)
    - File management with expiration
    - Export history and statistics
    """

    name = "export"
    version = "0.1.0"
    description = "Data export in multiple formats (JSON, CSV, PDF, DOCX)"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._storage = None
        self._initialized = False
        self._export_dir = None

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._storage = getattr(frame, "storage", None)

        # Setup export directory
        self._export_dir = os.path.join(tempfile.gettempdir(), "arkham_exports")
        os.makedirs(self._export_dir, exist_ok=True)

        # Create database schema
        await self._create_schema()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.export_shard = self

        self._initialized = True
        logger.info(f"ExportShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        self._initialized = False
        logger.info("ExportShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for export shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_export_jobs (
                id TEXT PRIMARY KEY,
                format TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT DEFAULT 'pending',

                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,

                file_path TEXT,
                file_size INTEGER,
                download_url TEXT,
                expires_at TEXT,

                error TEXT,
                filters TEXT DEFAULT '{}',
                options TEXT DEFAULT '{}',

                record_count INTEGER DEFAULT 0,
                processing_time_ms REAL DEFAULT 0,
                created_by TEXT DEFAULT 'system',
                metadata TEXT DEFAULT '{}'
            )
        """)

        # Create indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON arkham_export_jobs(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_jobs_created ON arkham_export_jobs(created_at)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_jobs_format ON arkham_export_jobs(format)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_export_jobs_target ON arkham_export_jobs(target)
        """)

        logger.debug("Export schema created/verified")

    # === Public API Methods ===

    async def create_export_job(
        self,
        format: ExportFormat,
        target: ExportTarget,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[ExportOptions] = None,
        created_by: str = "system",
    ) -> ExportJob:
        """Create a new export job."""
        job_id = str(uuid4())
        now = datetime.utcnow()

        # Default options
        if options is None:
            options = ExportOptions()

        # Calculate expiration (24 hours from creation)
        expires_at = now + timedelta(hours=24)

        job = ExportJob(
            id=job_id,
            format=format,
            target=target,
            status=ExportStatus.PENDING,
            created_at=now,
            filters=filters or {},
            options=options,
            created_by=created_by,
            expires_at=expires_at,
        )

        await self._save_job(job)

        # Emit event
        if self._events:
            await self._events.emit(
                "export.job.created",
                {
                    "job_id": job_id,
                    "format": format.value,
                    "target": target.value,
                    "created_by": created_by,
                },
                source=self.name,
            )

        # Start processing asynchronously (in real implementation)
        # For now, we'll process immediately
        await self._process_job(job)

        return job

    async def get_job_status(self, job_id: str) -> Optional[ExportJob]:
        """Get the status of an export job."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_export_jobs WHERE id = ?",
            [job_id],
        )
        return self._row_to_job(row) if row else None

    async def list_jobs(
        self,
        filter: Optional[ExportFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExportJob]:
        """List export jobs with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_export_jobs WHERE 1=1"
        params = []

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.format:
                query += " AND format = ?"
                params.append(filter.format.value)
            if filter.target:
                query += " AND target = ?"
                params.append(filter.target.value)
            if filter.created_by:
                query += " AND created_by = ?"
                params.append(filter.created_by)
            if filter.created_after:
                query += " AND created_at >= ?"
                params.append(filter.created_after.isoformat())
            if filter.created_before:
                query += " AND created_at <= ?"
                params.append(filter.created_before.isoformat())

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_job(row) for row in rows]

    async def cancel_job(self, job_id: str) -> Optional[ExportJob]:
        """Cancel a pending export job."""
        job = await self.get_job_status(job_id)
        if not job:
            return None

        if job.status in [ExportStatus.PENDING, ExportStatus.PROCESSING]:
            job.status = ExportStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            await self._save_job(job, update=True)

            # Emit event
            if self._events:
                await self._events.emit(
                    "export.job.cancelled",
                    {"job_id": job_id},
                    source=self.name,
                )

        return job

    async def get_download_url(self, job_id: str) -> Optional[str]:
        """Get download URL for a completed export job."""
        job = await self.get_job_status(job_id)
        if not job or job.status != ExportStatus.COMPLETED:
            return None

        # Check if file expired
        if job.expires_at and datetime.utcnow() > job.expires_at:
            return None

        return job.download_url

    async def get_statistics(self) -> ExportStatistics:
        """Get statistics about export jobs."""
        if not self._db:
            return ExportStatistics()

        # Total jobs
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_export_jobs"
        )
        total_jobs = total["count"] if total else 0

        # By status
        status_rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) as count FROM arkham_export_jobs GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By format
        format_rows = await self._db.fetch_all(
            "SELECT format, COUNT(*) as count FROM arkham_export_jobs GROUP BY format"
        )
        by_format = {row["format"]: row["count"] for row in format_rows}

        # By target
        target_rows = await self._db.fetch_all(
            "SELECT target, COUNT(*) as count FROM arkham_export_jobs GROUP BY target"
        )
        by_target = {row["target"]: row["count"] for row in target_rows}

        # Aggregates
        totals = await self._db.fetch_one("""
            SELECT
                SUM(record_count) as total_records,
                SUM(file_size) as total_size,
                AVG(processing_time_ms) as avg_time
            FROM arkham_export_jobs
            WHERE status = 'completed'
        """)

        # Oldest pending
        oldest = await self._db.fetch_one("""
            SELECT MIN(created_at) as oldest
            FROM arkham_export_jobs
            WHERE status = 'pending'
        """)

        return ExportStatistics(
            total_jobs=total_jobs,
            by_status=by_status,
            by_format=by_format,
            by_target=by_target,
            jobs_pending=by_status.get("pending", 0),
            jobs_processing=by_status.get("processing", 0),
            jobs_completed=by_status.get("completed", 0),
            jobs_failed=by_status.get("failed", 0),
            total_records_exported=totals["total_records"] if totals and totals["total_records"] else 0,
            total_file_size_bytes=totals["total_size"] if totals and totals["total_size"] else 0,
            avg_processing_time_ms=totals["avg_time"] if totals and totals["avg_time"] else 0.0,
            oldest_pending_job=datetime.fromisoformat(oldest["oldest"]) if oldest and oldest["oldest"] else None,
        )

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of export jobs, optionally filtered by status."""
        if not self._db:
            return 0

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_export_jobs WHERE status = ?",
                [status],
            )
        else:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_export_jobs WHERE status = 'pending'"
            )

        return result["count"] if result else 0

    def get_supported_formats(self) -> List[FormatInfo]:
        """Get list of supported export formats."""
        return [
            FormatInfo(
                format=ExportFormat.JSON,
                name="JSON",
                description="JavaScript Object Notation - structured data",
                file_extension=".json",
                mime_type="application/json",
                supports_metadata=True,
            ),
            FormatInfo(
                format=ExportFormat.CSV,
                name="CSV",
                description="Comma-Separated Values - tabular data",
                file_extension=".csv",
                mime_type="text/csv",
                supports_flatten=True,
            ),
            FormatInfo(
                format=ExportFormat.PDF,
                name="PDF",
                description="Portable Document Format - formatted documents",
                file_extension=".pdf",
                mime_type="application/pdf",
                placeholder=True,
            ),
            FormatInfo(
                format=ExportFormat.DOCX,
                name="DOCX",
                description="Microsoft Word Document",
                file_extension=".docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                placeholder=True,
            ),
            FormatInfo(
                format=ExportFormat.XLSX,
                name="XLSX",
                description="Microsoft Excel Spreadsheet",
                file_extension=".xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                placeholder=True,
            ),
        ]

    def get_export_targets(self) -> List[TargetInfo]:
        """Get list of available export targets."""
        return [
            TargetInfo(
                target=ExportTarget.DOCUMENTS,
                name="Documents",
                description="Export document records with text and metadata",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV],
            ),
            TargetInfo(
                target=ExportTarget.ENTITIES,
                name="Entities",
                description="Export extracted entities with relationships",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV],
            ),
            TargetInfo(
                target=ExportTarget.CLAIMS,
                name="Claims",
                description="Export claims with evidence and verification status",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV, ExportFormat.PDF],
            ),
            TargetInfo(
                target=ExportTarget.TIMELINE,
                name="Timeline",
                description="Export timeline events in chronological order",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV],
            ),
            TargetInfo(
                target=ExportTarget.GRAPH,
                name="Graph",
                description="Export graph nodes and edges",
                available_formats=[ExportFormat.JSON],
            ),
            TargetInfo(
                target=ExportTarget.MATRIX,
                name="ACH Matrix",
                description="Export ACH matrix with hypotheses and evidence",
                available_formats=[ExportFormat.JSON, ExportFormat.CSV, ExportFormat.PDF],
            ),
        ]

    # === Private Helper Methods ===

    async def _process_job(self, job: ExportJob) -> ExportResult:
        """Process an export job (stub implementation)."""
        import time
        start_time = time.time()

        try:
            job.status = ExportStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await self._save_job(job, update=True)

            # Emit started event
            if self._events:
                await self._events.emit(
                    "export.job.started",
                    {"job_id": job.id, "format": job.format.value, "target": job.target.value},
                    source=self.name,
                )

            # Generate stub export file
            file_path, record_count = await self._generate_export_file(job)

            # Update job
            job.status = ExportStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.file_path = file_path
            job.file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
            job.download_url = f"/api/export/jobs/{job.id}/download"
            job.record_count = record_count
            job.processing_time_ms = (time.time() - start_time) * 1000

            await self._save_job(job, update=True)

            # Emit completed event
            if self._events:
                await self._events.emit(
                    "export.job.completed",
                    {
                        "job_id": job.id,
                        "record_count": record_count,
                        "file_size": job.file_size,
                        "processing_time_ms": job.processing_time_ms,
                    },
                    source=self.name,
                )
                await self._events.emit(
                    "export.file.created",
                    {
                        "job_id": job.id,
                        "file_path": file_path,
                        "file_size": job.file_size,
                    },
                    source=self.name,
                )

            return ExportResult(
                job_id=job.id,
                success=True,
                file_path=file_path,
                file_size=job.file_size,
                download_url=job.download_url,
                expires_at=job.expires_at,
                record_count=record_count,
                processing_time_ms=job.processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Export job {job.id} failed: {e}")
            job.status = ExportStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            await self._save_job(job, update=True)

            # Emit failed event
            if self._events:
                await self._events.emit(
                    "export.job.failed",
                    {"job_id": job.id, "error": str(e)},
                    source=self.name,
                )

            return ExportResult(
                job_id=job.id,
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    async def _generate_export_file(self, job: ExportJob) -> tuple[Optional[str], int]:
        """Generate export file (stub implementation)."""
        # Stub: Create empty/placeholder files
        filename = f"{job.id}_{job.target.value}.{self._get_file_extension(job.format)}"
        file_path = os.path.join(self._export_dir, filename)

        if job.format == ExportFormat.JSON:
            data = {"target": job.target.value, "records": [], "metadata": {"job_id": job.id}}
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return file_path, 0

        elif job.format == ExportFormat.CSV:
            with open(file_path, "w") as f:
                f.write("id,name,type,created_at\n")
                f.write("# No data - placeholder export\n")
            return file_path, 0

        elif job.format in [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.XLSX]:
            # Placeholder for PDF/DOCX/XLSX
            with open(file_path, "wb") as f:
                f.write(b"Placeholder export file - not yet implemented")
            return file_path, 0

        return None, 0

    def _get_file_extension(self, format: ExportFormat) -> str:
        """Get file extension for format."""
        extensions = {
            ExportFormat.JSON: "json",
            ExportFormat.CSV: "csv",
            ExportFormat.PDF: "pdf",
            ExportFormat.DOCX: "docx",
            ExportFormat.XLSX: "xlsx",
        }
        return extensions.get(format, "bin")

    async def _save_job(self, job: ExportJob, update: bool = False) -> None:
        """Save export job to database."""
        if not self._db:
            return

        # Serialize options
        options_json = "{}"
        if job.options:
            options_json = json.dumps({
                "include_metadata": job.options.include_metadata,
                "include_relationships": job.options.include_relationships,
                "date_range_start": job.options.date_range_start.isoformat() if job.options.date_range_start else None,
                "date_range_end": job.options.date_range_end.isoformat() if job.options.date_range_end else None,
                "entity_types": job.options.entity_types,
                "flatten": job.options.flatten,
                "max_records": job.options.max_records,
                "sort_by": job.options.sort_by,
                "sort_order": job.options.sort_order,
            })

        data = (
            job.id,
            job.format.value,
            job.target.value,
            job.status.value,
            job.created_at.isoformat(),
            job.started_at.isoformat() if job.started_at else None,
            job.completed_at.isoformat() if job.completed_at else None,
            job.file_path,
            job.file_size,
            job.download_url,
            job.expires_at.isoformat() if job.expires_at else None,
            job.error,
            json.dumps(job.filters),
            options_json,
            job.record_count,
            job.processing_time_ms,
            job.created_by,
            json.dumps(job.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_export_jobs SET
                    format=?, target=?, status=?, created_at=?, started_at=?,
                    completed_at=?, file_path=?, file_size=?, download_url=?,
                    expires_at=?, error=?, filters=?, options=?,
                    record_count=?, processing_time_ms=?, created_by=?, metadata=?
                WHERE id=?
            """, data[1:] + (job.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_export_jobs (
                    id, format, target, status, created_at, started_at,
                    completed_at, file_path, file_size, download_url,
                    expires_at, error, filters, options,
                    record_count, processing_time_ms, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    def _row_to_job(self, row: Dict[str, Any]) -> ExportJob:
        """Convert database row to ExportJob object."""
        # Parse options
        options = None
        if row.get("options"):
            options_data = json.loads(row["options"])
            options = ExportOptions(
                include_metadata=options_data.get("include_metadata", True),
                include_relationships=options_data.get("include_relationships", True),
                date_range_start=datetime.fromisoformat(options_data["date_range_start"]) if options_data.get("date_range_start") else None,
                date_range_end=datetime.fromisoformat(options_data["date_range_end"]) if options_data.get("date_range_end") else None,
                entity_types=options_data.get("entity_types"),
                flatten=options_data.get("flatten", False),
                max_records=options_data.get("max_records"),
                sort_by=options_data.get("sort_by"),
                sort_order=options_data.get("sort_order", "asc"),
            )

        return ExportJob(
            id=row["id"],
            format=ExportFormat(row["format"]),
            target=ExportTarget(row["target"]),
            status=ExportStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            file_path=row["file_path"],
            file_size=row["file_size"],
            download_url=row["download_url"],
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            error=row["error"],
            filters=json.loads(row["filters"] or "{}"),
            options=options,
            record_count=row["record_count"],
            processing_time_ms=row["processing_time_ms"],
            created_by=row["created_by"],
            metadata=json.loads(row["metadata"] or "{}"),
        )
