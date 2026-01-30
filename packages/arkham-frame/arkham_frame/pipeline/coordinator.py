"""
Pipeline Coordinator - Orchestrates pipeline execution.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import time

from .base import PipelineStage, StageResult, StageStatus, PipelineError

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

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
        document_id = context.get("document_id") or context.get("doc_id")
        
        with log_operation("pipeline.process", document_id=document_id) as event:
            if event:
                event.context("component", "pipeline_coordinator")
                event.context("operation", "process")
                event.input(
                    document_id=document_id,
                    start_stage=start_stage,
                    end_stage=end_stage,
                    has_file_path="file_path" in context,
                    has_file_bytes="file_bytes" in context,
                    project_id=context.get("project_id"),
                )
                if context.get("project_id"):
                    event.context("project_id", context.get("project_id"))
            
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
                    if event:
                        event.error("UnknownStage", f"Unknown stage: {start_stage}")
                    raise PipelineError(f"Unknown stage: {start_stage}")

            if end_stage:
                try:
                    end_idx = stage_names.index(end_stage) + 1
                except ValueError:
                    if event:
                        event.error("UnknownStage", f"Unknown stage: {end_stage}")
                    raise PipelineError(f"Unknown stage: {end_stage}")

            pipeline_start = time.time()
            stages_completed = []
            stages_failed = []

            # Run stages
            for stage in self.stages[start_idx:end_idx]:
                logger.info(f"Running stage: {stage.name}")

                stage_start = time.time()

                # Check skip condition
                if stage.should_skip(current_context):
                    results[stage.name] = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                    if event:
                        event.dependency(f"stage_{stage.name}", duration_ms=0, status="skipped")
                    continue

                # Validate
                if not await stage.validate(current_context):
                    results[stage.name] = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error="Validation failed",
                    )
                    stages_failed.append(stage.name)
                    if event:
                        event.dependency(f"stage_{stage.name}", duration_ms=int((time.time() - stage_start) * 1000), error="Validation failed")
                    break

                # Process
                try:
                    result = await stage.process(current_context)
                    results[stage.name] = result
                    stage_duration_ms = int((time.time() - stage_start) * 1000)

                    # Track stage dependency
                    if event:
                        event.dependency(
                            f"stage_{stage.name}",
                            duration_ms=stage_duration_ms,
                            status=result.status.value if hasattr(result.status, 'value') else str(result.status),
                            success=result.success,
                        )

                    # Merge output into context for next stage
                    if result.success and result.output:
                        current_context.update(result.output)
                        stages_completed.append(stage.name)

                    # Stop on failure
                    if not result.success:
                        logger.error(f"Stage {stage.name} failed: {result.error}")
                        stages_failed.append(stage.name)
                        await stage.on_error(Exception(result.error), current_context)
                        if event:
                            event.error("StageFailed", f"Stage {stage.name} failed: {result.error}")
                        break

                except Exception as e:
                    stage_duration_ms = int((time.time() - stage_start) * 1000)
                    logger.error(f"Stage {stage.name} exception: {e}")
                    await stage.on_error(e, current_context)
                    results[stage.name] = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error=str(e),
                    )
                    stages_failed.append(stage.name)
                    if event:
                        event.dependency(f"stage_{stage.name}", duration_ms=stage_duration_ms, error=str(e))
                        emit_wide_error(event, "StageException", f"Stage {stage.name} exception: {e}", exc=e)
                    break

            pipeline_duration_ms = int((time.time() - pipeline_start) * 1000)
            
            if event:
                event.output(
                    stages_completed=len(stages_completed),
                    stages_failed=len(stages_failed),
                    total_stages=len(results),
                    pipeline_duration_ms=pipeline_duration_ms,
                )

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
