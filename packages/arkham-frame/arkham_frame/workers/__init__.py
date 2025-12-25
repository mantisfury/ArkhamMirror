"""
Worker infrastructure for ArkhamFrame.

Provides base classes and process management for distributed workers.

Usage:
    # Run workers via CLI
    python -m arkham_frame.workers --pool cpu-light --count 2

    # Create a custom worker
    from arkham_frame.workers import BaseWorker

    class MyWorker(BaseWorker):
        pool = "cpu-light"
        name = "MyWorker"

        async def process_job(self, job_id, payload):
            # Do work
            return {"result": "done"}
"""

from .base import BaseWorker, WorkerState, WorkerMetrics, run_worker
from .runner import WorkerRunner, run_single_worker
from .registry import WorkerRegistry, WorkerInfo
from .examples import EchoWorker, FailWorker, SlowWorker, EXAMPLE_WORKERS

# Frame workers (infrastructure workers that stay in Frame)
from .light_worker import LightWorker
from .db_worker import DBWorker

# Future shard workers (will be moved when shards are created)
from .enrich_worker import EnrichWorker
from .whisper_worker import WhisperWorker
from .analysis_worker import AnalysisWorker

# Note: The following workers have been moved to their respective shards:
# - ExtractWorker, FileWorker, ArchiveWorker, ImageWorker -> arkham-shard-ingest
# - NERWorker -> arkham-shard-parse
# - EmbedWorker -> arkham-shard-embed
# - PaddleWorker, QwenWorker -> arkham-shard-ocr

__all__ = [
    # Base classes
    "BaseWorker",
    "WorkerState",
    "WorkerMetrics",
    "run_worker",
    # Runner
    "WorkerRunner",
    "run_single_worker",
    # Registry
    "WorkerRegistry",
    "WorkerInfo",
    # Frame workers (infrastructure)
    "LightWorker",
    "DBWorker",
    # Future shard workers
    "EnrichWorker",
    "WhisperWorker",
    "AnalysisWorker",
    # Example workers (for testing)
    "EchoWorker",
    "FailWorker",
    "SlowWorker",
    "EXAMPLE_WORKERS",
]
