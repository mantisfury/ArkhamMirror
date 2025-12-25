"""
Ingest stage - Document ingestion and splitting.
"""

from typing import Dict, Any
from datetime import datetime
import logging

from .base import PipelineStage, StageResult, StageStatus

logger = logging.getLogger(__name__)


class IngestStage(PipelineStage):
    """
    Ingests documents and splits them into pages.
    """

    def __init__(self, frame=None):
        super().__init__("ingest", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have a file to ingest."""
        return "file_path" in context or "file_bytes" in context

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Ingest a document.

        Expected context:
            - file_path: Path to the file
            - file_bytes: Raw file bytes (alternative to file_path)
            - filename: Original filename
            - project_id: Optional project ID
        """
        started_at = datetime.utcnow()

        try:
            file_path = context.get("file_path")
            filename = context.get("filename", "unknown")

            logger.info(f"Ingesting document: {filename}")

            # In a real implementation, this would:
            # 1. Validate file type
            # 2. Extract pages (PDF, images, etc.)
            # 3. Store document metadata
            # 4. Queue pages for OCR

            # Placeholder implementation
            output = {
                "document_id": context.get("document_id", "doc-placeholder"),
                "filename": filename,
                "page_count": 0,
                "status": "ingested",
            }

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Ingest failed: {e}")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
