"""
Pipeline Coordinator - Orchestrates pipeline execution.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .base import PipelineStage, StageResult, StageStatus, PipelineError

logger = logging.getLogger(__name__)


class PipelineCoordinator:
    """
    Coordinates document processing pipeline execution.

    Manages the flow: Ingest -> OCR -> Parse -> Embed
    """

    def __init__(self, frame=None):
        self.frame = frame
        self.stages: List[PipelineStage] = []
        self._initialized = False

    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages.append(stage)

    def get_stages(self) -> List[str]:
        """Get list of stage names."""
        return [s.name for s in self.stages]

    async def initialize(self) -> None:
        """Initialize the coordinator with default stages."""
        from .ingest import IngestStage
        from .ocr import OCRStage
        from .parse import ParseStage
        from .embed import EmbedStage

        self.stages = [
            IngestStage(frame=self.frame),
            OCRStage(frame=self.frame),
            ParseStage(frame=self.frame),
            EmbedStage(frame=self.frame),
        ]
        self._initialized = True
        logger.info(f"Pipeline initialized with stages: {self.get_stages()}")

    async def process(
        self,
        context: Dict[str, Any],
        start_stage: Optional[str] = None,
        end_stage: Optional[str] = None,
    ) -> Dict[str, StageResult]:
        """
        Run the pipeline on a document.

        Args:
            context: Initial pipeline context
            start_stage: Start from this stage (optional)
            end_stage: Stop after this stage (optional)

        Returns:
            Dict mapping stage names to results
        """
        if not self._initialized:
            await self.initialize()

        results: Dict[str, StageResult] = {}
        current_context = context.copy()

        # Find start/end indices
        stage_names = self.get_stages()
        start_idx = 0
        end_idx = len(self.stages)

        if start_stage:
            try:
                start_idx = stage_names.index(start_stage)
            except ValueError:
                raise PipelineError(f"Unknown stage: {start_stage}")

        if end_stage:
            try:
                end_idx = stage_names.index(end_stage) + 1
            except ValueError:
                raise PipelineError(f"Unknown stage: {end_stage}")

        # Run stages
        for stage in self.stages[start_idx:end_idx]:
            logger.info(f"Running stage: {stage.name}")

            # Check skip condition
            if stage.should_skip(current_context):
                results[stage.name] = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                )
                continue

            # Validate
            if not await stage.validate(current_context):
                results[stage.name] = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    error="Validation failed",
                )
                break

            # Process
            try:
                result = await stage.process(current_context)
                results[stage.name] = result

                # Merge output into context for next stage
                if result.success and result.output:
                    current_context.update(result.output)

                # Stop on failure
                if not result.success:
                    logger.error(f"Stage {stage.name} failed: {result.error}")
                    await stage.on_error(Exception(result.error), current_context)
                    break

            except Exception as e:
                logger.error(f"Stage {stage.name} exception: {e}")
                await stage.on_error(e, current_context)
                results[stage.name] = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    error=str(e),
                )
                break

        return results

    async def get_status(self, document_id: str) -> Dict[str, Any]:
        """Get processing status for a document."""
        # In a real implementation, this would query the database
        return {
            "document_id": document_id,
            "stages": {name: "unknown" for name in self.get_stages()},
            "current_stage": None,
            "completed": False,
        }
