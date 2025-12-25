"""
OCR stage - Optical character recognition.
"""

from typing import Dict, Any
from datetime import datetime
import logging

from .base import PipelineStage, StageResult, StageStatus

logger = logging.getLogger(__name__)


class OCRStage(PipelineStage):
    """
    Performs OCR on document pages.
    """

    def __init__(self, frame=None):
        super().__init__("ocr", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have pages to OCR."""
        return "document_id" in context or "page_paths" in context

    def should_skip(self, context: Dict[str, Any]) -> bool:
        """Skip if document already has text."""
        return context.get("has_text", False)

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Perform OCR on document pages.

        Expected context:
            - document_id: Document to process
            - page_paths: List of page image paths
            - ocr_engine: Which OCR engine to use (paddle/qwen)
        """
        started_at = datetime.utcnow()

        try:
            document_id = context.get("document_id")
            ocr_engine = context.get("ocr_engine", "paddle")

            logger.info(f"Running OCR on document {document_id} with {ocr_engine}")

            # In a real implementation, this would:
            # 1. Load page images
            # 2. Run OCR (PaddleOCR or Qwen-VL)
            # 3. Extract text and bounding boxes
            # 4. Store results

            output = {
                "document_id": document_id,
                "ocr_engine": ocr_engine,
                "pages_processed": 0,
                "status": "ocr_complete",
            }

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
