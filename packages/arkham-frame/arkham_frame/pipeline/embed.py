"""
Embed stage - Generate embeddings dispatcher.

This stage dispatches embedding jobs to the gpu-embed worker pool.
Workers are registered by the arkham-shard-embed package.
"""

from typing import Dict, Any, List
from datetime import datetime
import logging
import uuid
import time

from .base import PipelineStage, StageResult, StageStatus

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


class EmbedStage(PipelineStage):
    """
    Dispatches embedding jobs to worker pools.

    Routes to:
        - gpu-embed: Text embedding with sentence-transformers
    """

    def __init__(self, frame=None):
        super().__init__("embed", frame)

    async def validate(self, context: Dict[str, Any]) -> bool:
        """Check if we have content to embed."""
        return "document_id" in context or "chunks" in context or "text" in context

    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Dispatch embedding to worker pool.

        Expected context:
            - document_id: Document to process
            - chunks: List of text chunks (if not fetching from DB)
            - text: Single text to embed (alternative to chunks)
            - total_text: Text from OCR stage (will be chunked)
            - embedding_model: Model to use (default: bge-m3)
        """
        started_at = datetime.utcnow()
        document_id = context.get("document_id")
        
        with log_operation("pipeline.stage.embed", document_id=document_id) as event:
            if event:
                event.context("component", "pipeline_stage")
                event.context("stage", "embed")
                event.input(
                    document_id=document_id,
                    embedding_model=context.get("embedding_model", "bge-m3"),
                    has_chunks="chunks" in context,
                )

            try:
                embedding_model = context.get("embedding_model", "bge-m3")

                # Get text to embed
                chunks = context.get("chunks", [])
                if not chunks:
                    text = context.get("text") or context.get("total_text", "")
                    if text:
                        # Create simple chunks if none provided
                        chunks = self._simple_chunk(text)

                logger.info(f"Dispatching embed for document {document_id} ({len(chunks)} chunks)")

                if event:
                    event.input(chunk_count=len(chunks))

                # Get worker service
                workers = self.frame.get_service("workers") if self.frame else None
                if not workers:
                    logger.warning("Worker service not available, skipping embed dispatch")
                    if event:
                        event.error("WorkerServiceUnavailable", "Worker service not available")
                    return StageResult(
                        stage_name=self.name,
                        status=StageStatus.SKIPPED,
                        output={"reason": "Worker service not available"},
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )

                # Check if embed pool has registered workers
                pool = "gpu-embed"
                if not workers.get_worker_class(pool):
                    # Fallback to cpu pool
                    if workers.get_worker_class("cpu-embed"):
                        pool = "cpu-embed"
                    else:
                        logger.warning(f"No workers registered for pool {pool}")
                        if event:
                            event.error("NoWorkersAvailable", f"No workers for pool {pool}")
                        return StageResult(
                            stage_name=self.name,
                            status=StageStatus.SKIPPED,
                            output={"reason": f"No workers for pool {pool}"},
                            started_at=started_at,
                            completed_at=datetime.utcnow(),
                        )

                # Dispatch batch embedding job
                payload = {
                    "document_id": document_id,
                    "chunks": chunks,
                    "model": embedding_model,
                    "job_type": "embed_batch",
                }

                start_time = time.time()
                try:
                    result = await workers.enqueue_and_wait(
                        pool=pool,
                        payload=payload,
                        timeout=300.0,  # 5 minutes for large batches
                    )
                    duration_ms = int((time.time() - start_time) * 1000)

                    output = {
                        "document_id": document_id,
                        "embedding_model": embedding_model,
                        "pool_used": pool,
                        "chunks_embedded": result.get("embedded_count", len(chunks)),
                        "dimensions": result.get("dimensions", 0),
                        "status": "embedded",
                    }

                    if event:
                        event.dependency(f"worker_pool_{pool}", duration_ms=duration_ms)
                        event.output(
                            chunks_embedded=output.get("chunks_embedded", 0),
                            dimensions=output.get("dimensions", 0),
                            pool_used=pool,
                        )

                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"Embed dispatch failed: {e}")
                    if event:
                        event.dependency(f"worker_pool_{pool}", duration_ms=duration_ms, error=str(e))
                        emit_wide_error(event, "EmbedDispatchFailed", str(e), exc=e)
                    output = {
                        "document_id": document_id,
                        "chunks_embedded": 0,
                        "error": str(e),
                        "status": "embed_failed",
                    }

                # Emit event
                events = self.frame.get_service("events") if self.frame else None
                if events:
                    await events.publish(
                        "embed.document.completed",
                        {
                            "document_id": document_id,
                            "chunks_embedded": output.get("chunks_embedded", 0),
                        },
                        source="pipeline-embed",
                    )

                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.COMPLETED,
                    output=output,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            except Exception as e:
                logger.error(f"Embed dispatch failed: {e}")
                if event:
                    emit_wide_error(event, "EmbedStageFailed", str(e), exc=e)
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

    def _simple_chunk(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Simple text chunking fallback.

        The ChunkService in Frame provides more sophisticated chunking.
        This is a fallback for when chunks aren't pre-provided.
        """
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap

        return chunks
