"""
OCR stage - Optical character recognition dispatcher.

This stage dispatches OCR jobs to the appropriate worker pool.
Workers are registered by the arkham-shard-ocr package.
"""

from typing import Dict, Any
from datetime import datetime
import logging
import uuid

from .base import PipelineStage, StageResult, StageStatus

logger = logging.getLogger(__name__)


class OCRStage(PipelineStage):
    """
    Dispatches OCR jobs to worker pools.

    Routes to:
        - gpu-paddle: PaddleOCR for standard document OCR
        - gpu-qwen: Qwen-VL for complex/handwritten OCR
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
        Dispatch OCR to worker pool.

        Expected context:
            - document_id: Document to process
            - page_paths: List of page image paths
            - ocr_engine: Which OCR engine to use (paddle/qwen)
        """
        started_at = datetime.utcnow()

        try:
            document_id = context.get("document_id")
            page_paths = context.get("page_paths", [])
            ocr_engine = context.get("ocr_engine", "paddle")

            logger.info(f"Dispatching OCR for document {document_id} with {ocr_engine}")

            # Get worker service
            workers = self.frame.get_service("workers") if self.frame else None
            if not workers:
                logger.warning("Worker service not available, skipping OCR dispatch")
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.SKIPPED,
                    output={"reason": "Worker service not available"},
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Determine worker pool based on engine
            pool = "gpu-qwen" if ocr_engine == "qwen" else "gpu-paddle"

            # Check if pool has registered workers
            if not workers.get_worker_class(pool):
                # Fallback to cpu-ocr if GPU pool not available
                if workers.get_worker_class("cpu-ocr"):
                    pool = "cpu-ocr"
                else:
                    logger.warning(f"No workers registered for pool {pool}")
                    return StageResult(
                        stage_name=self.name,
                        status=StageStatus.SKIPPED,
                        output={"reason": f"No workers for pool {pool}"},
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )

            # Process each page
            results = []
            total_text = ""

            for i, page_path in enumerate(page_paths):
                job_id = str(uuid.uuid4())
                payload = {
                    "document_id": document_id,
                    "page_number": i + 1,
                    "image_path": page_path,
                    "language": context.get("language", "en"),
                    "job_type": "ocr_page",
                }

                try:
                    # Enqueue and wait for result
                    result = await workers.enqueue_and_wait(
                        pool=pool,
                        payload=payload,
                        timeout=120.0,  # 2 minutes per page
                    )
                    results.append(result)
                    total_text += result.get("text", "") + "\n"
                except Exception as e:
                    logger.error(f"OCR failed for page {i + 1}: {e}")
                    results.append({"page": i + 1, "error": str(e)})

            output = {
                "document_id": document_id,
                "ocr_engine": ocr_engine,
                "pool_used": pool,
                "pages_processed": len([r for r in results if "error" not in r]),
                "pages_failed": len([r for r in results if "error" in r]),
                "total_text": total_text.strip(),
                "status": "ocr_complete",
            }

            # Emit event
            events = self.frame.get_service("events") if self.frame else None
            if events:
                await events.publish(
                    "ocr.document.completed",
                    {"document_id": document_id, "pages": len(page_paths)},
                    source="pipeline-ocr",
                )

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"OCR dispatch failed: {e}")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
