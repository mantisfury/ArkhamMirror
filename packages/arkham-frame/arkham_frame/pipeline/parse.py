"""
Parse stage - Entity extraction and NER.
"""

from typing import Dict, Any
from datetime import datetime
import logging

from .base import PipelineStage, StageResult, StageStatus

logger = logging.getLogger(__name__)


class ParseStage(PipelineStage):
    """
    Parses document text to extract entities and structure.
    """

    def __init__(self, frame=None):
        super().__init__("parse", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have text to parse."""
        return "document_id" in context or "text" in context

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Parse document text for entities.

        Expected context:
            - document_id: Document to process
            - text: Text to parse (if not fetching from DB)
        """
        started_at = datetime.utcnow()

        try:
            document_id = context.get("document_id")

            logger.info(f"Parsing document {document_id}")

            # In a real implementation, this would:
            # 1. Load document text
            # 2. Run spaCy NER
            # 3. Extract entities (PERSON, ORG, GPE, DATE, MONEY)
            # 4. Store entity mentions
            # 5. Link to canonical entities

            output = {
                "document_id": document_id,
                "entities_found": 0,
                "entity_types": {},
                "status": "parsed",
            }

            return StageResult(
                stage_name=self.name,
                status=StageStatus.COMPLETED,
                output=output,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Parse failed: {e}")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
