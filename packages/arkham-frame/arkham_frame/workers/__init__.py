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

# Production workers
from .extract_worker import ExtractWorker
from .ner_worker import NERWorker
from .embed_worker import EmbedWorker
from .light_worker import LightWorker
from .paddle_worker import PaddleWorker
from .qwen_worker import QwenWorker
from .file_worker import FileWorker
from .image_worker import ImageWorker
from .enrich_worker import EnrichWorker
from .db_worker import DBWorker
from .archive_worker import ArchiveWorker
from .whisper_worker import WhisperWorker
from .analysis_worker import AnalysisWorker

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
    # Production workers
    "ExtractWorker",
    "NERWorker",
    "EmbedWorker",
    "LightWorker",
    "PaddleWorker",
    "QwenWorker",
    "FileWorker",
    "ImageWorker",
    "EnrichWorker",
    "DBWorker",
    "ArchiveWorker",
    "WhisperWorker",
    "AnalysisWorker",
    # Example workers (for testing)
    "EchoWorker",
    "FailWorker",
    "SlowWorker",
    "EXAMPLE_WORKERS",
]
