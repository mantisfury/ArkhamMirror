"""
Parse stage - Entity extraction and NER dispatcher.

This stage dispatches NER jobs to the cpu-ner worker pool.
Workers are registered by the arkham-shard-parse package.
"""

from typing import Dict, Any
from datetime import datetime
import logging
import uuid

from .base import PipelineStage, StageResult, StageStatus

logger = logging.getLogger(__name__)


class ParseStage(PipelineStage):
    """
    Dispatches parsing/NER jobs to worker pools.

    Routes to:
        - cpu-ner: Named entity recognition (spaCy)
    """

    def __init__(self, frame=None):
        super().__init__("parse", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have text to parse."""
        return "document_id" in context or "text" in context

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Dispatch parsing to worker pool.

        Expected context:
            - document_id: Document to process
            - text: Text to parse (if not fetching from DB)
            - total_text: Text from OCR stage (alternative)
        """
        started_at = datetime.utcnow()

        try:
            document_id = context.get("document_id")
            text = context.get("text") or context.get("total_text", "")

            logger.info(f"Dispatching parse for document {document_id}")

            # Get worker service
            workers = self.frame.get_service("workers") if self.frame else None
            if not workers:
                logger.warning("Worker service not available, skipping parse dispatch")
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.SKIPPED,
                    output={"reason": "Worker service not available"},
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Check if NER pool has registered workers
            pool = "cpu-ner"
            if not workers.get_worker_class(pool):
                logger.warning(f"No workers registered for pool {pool}")
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.SKIPPED,
                    output={"reason": f"No workers for pool {pool}"},
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Dispatch NER job
            payload = {
                "document_id": document_id,
                "text": text,
                "job_type": "extract_entities",
            }

            try:
                result = await workers.enqueue_and_wait(
                    pool=pool,
                    payload=payload,
                    timeout=60.0,  # 1 minute for NER
                )

                output = {
                    "document_id": document_id,
                    "entities_found": result.get("entity_count", 0),
                    "entities": result.get("entities", []),
                    "status": "parsed",
                }

            except Exception as e:
                logger.error(f"NER dispatch failed: {e}")
                output = {
                    "document_id": document_id,
                    "entities_found": 0,
                    "error": str(e),
                    "status": "parse_failed",
                }

            # Emit event
            events = self.frame.get_service("events") if self.frame else None
            if events:
                await events.publish(
                    "parse.document.completed",
                    {
                        "document_id": document_id,
                        "entities_found": output.get("entities_found", 0),
                    },
                    source="pipeline-parse",
                )

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Parse dispatch failed: {e}")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
