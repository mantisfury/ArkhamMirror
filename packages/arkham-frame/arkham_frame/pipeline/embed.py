"""
Embed stage - Generate embeddings dispatcher.

This stage dispatches embedding jobs to the gpu-embed worker pool.
Workers are registered by the arkham-shard-embed package.
"""

from typing import Dict, Any, List
from datetime import datetime
import logging
import uuid

from .base import PipelineStage, StageResult, StageStatus

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

        try:
            document_id = context.get("document_id")
            embedding_model = context.get("embedding_model", "bge-m3")

            # Get text to embed
            chunks = context.get("chunks", [])
            if not chunks:
                text = context.get("text") or context.get("total_text", "")
                if text:
                    # Create simple chunks if none provided
                    chunks = self._simple_chunk(text)

            logger.info(f"Dispatching embed for document {document_id} ({len(chunks)} chunks)")

            # Get worker service
            workers = self.frame.get_service("workers") if self.frame else None
            if not workers:
                logger.warning("Worker service not available, skipping embed dispatch")
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

            try:
                result = await workers.enqueue_and_wait(
                    pool=pool,
                    payload=payload,
                    timeout=300.0,  # 5 minutes for large batches
                )

                output = {
                    "document_id": document_id,
                    "embedding_model": embedding_model,
                    "pool_used": pool,
                    "chunks_embedded": result.get("embedded_count", len(chunks)),
                    "dimensions": result.get("dimensions", 0),
                    "status": "embedded",
                }

            except Exception as e:
                logger.error(f"Embed dispatch failed: {e}")
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
